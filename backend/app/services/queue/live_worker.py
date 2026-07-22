"""Gated durable ComfyUI worker orchestration.

This module is the one general-worker execution path.  It composes the
existing reservation, admission, controlled-submission, GPU-lease, progress,
history-fallback, output-provenance, and terminal-state services.  It is inert
unless ``CINEFORGE_QUEUE_WORKER_ENABLED=true`` and it never starts or mutates a
ComfyUI process by itself.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.db.base import ComfyJob, QueueStatus, WorkflowRun
from backend.app.queue.state_machine import JobState
from backend.app.services.comfy.client import ComfyUIClient, ComfyWorkerRuntimeClient
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.comfy.progress_monitor import ComfyJobProgressRecorder
from backend.app.services.comfy.submission import (
    ComfyWorkerPromptSubmissionAdapter,
    ControlledComfySubmissionService,
)
from backend.app.services.local_generation import SemanticGenerationRequestManifestStore
from backend.app.services.output_collector import OutputCollector
from backend.app.services.queue.service import QueueService
from backend.app.services.queue.worker import QueueWorker
from backend.app.utils.path_safety import sanitize_comfy_output_prefix


@dataclass(frozen=True)
class LiveWorkerResult:
    worker_id: str
    job_id: UUID | None
    state: str
    prompt_id: str | None = None
    detail: str | None = None


class LiveComfyQueueWorker:
    """Run at most one claimed job through the tracked local ComfyUI path."""

    def __init__(
        self,
        *,
        worker_id: str,
        settings: Settings | None = None,
        queue_service: QueueService | None = None,
        output_collector: OutputCollector | None = None,
        manifest_store: SemanticGenerationRequestManifestStore | None = None,
        public_client_factory: Callable[[], Any] | None = None,
        runtime_client_factory: Callable[[], Any] | None = None,
        submission_adapter_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.settings = settings or get_settings()
        self.queue_service = queue_service or QueueService()
        self.worker = QueueWorker(worker_id, queue_service=self.queue_service)
        self.recorder = ComfyJobProgressRecorder(queue_service=self.queue_service)
        self.output_collector = output_collector or OutputCollector(
            settings=self.settings,
            queue_service=self.queue_service,
        )
        self.manifest_store = manifest_store or SemanticGenerationRequestManifestStore(self.settings)
        base_url = str(self.settings.comfyui_base_url).rstrip("/")
        timeout = self.settings.comfyui_request_timeout_sec
        self.public_client_factory = public_client_factory or (
            lambda: ComfyUIClient(base_url, timeout=timeout)
        )
        self.runtime_client_factory = runtime_client_factory or (
            lambda: ComfyWorkerRuntimeClient(
                base_url,
                timeout=timeout,
                tracked_worker_runtime=True,
            )
        )
        self.submission_adapter_factory = submission_adapter_factory or (
            lambda: ComfyWorkerPromptSubmissionAdapter(
                base_url,
                timeout=timeout,
                tracked_worker_submission=True,
            )
        )

    async def run_once(self, db: Session) -> LiveWorkerResult:
        if not self.settings.queue_worker_enabled:
            return LiveWorkerResult(self.worker_id, None, "disabled", detail="Queue worker gate is disabled")

        self._recover_stale_jobs(db)

        job = self.queue_service.claim_next_pending_job(db, self.worker_id, "live worker claim")
        if job is None:
            return LiveWorkerResult(self.worker_id, None, "idle")
        self._sync_manifest(db, job, detail="Durable job claimed")

        try:
            object_info = await self._load_object_info()
        except Exception as exc:
            failed = self._fail_reserved_validation(db, job.id, f"ComfyUI object_info unavailable: {exc}")
            self._sync_manifest(db, failed, detail=failed.error_message)
            retry = self._schedule_retry(
                db,
                failed,
                reason=failed.error_message or "ComfyUI object_info unavailable",
                allow_validation_failure=True,
            )
            return self._result_with_retry(failed, retry)

        lease = self.worker.acquire_gpu_lease_once(db, job.id)
        if lease is None:
            failed = self._fail_reserved_validation(db, job.id, "Exclusive GPU lease acquisition failed")
            self._sync_manifest(db, failed, detail=failed.error_message)
            retry = self._schedule_retry(
                db,
                failed,
                reason=failed.error_message or "Exclusive GPU lease acquisition failed",
                allow_validation_failure=True,
            )
            return self._result_with_retry(failed, retry)

        client_id = f"cineforge-{job.id}-{uuid4().hex[:8]}"
        try:
            async with self.submission_adapter_factory() as adapter:
                submission = ControlledComfySubmissionService(
                    queue_service=self.queue_service,
                    submission_adapter=adapter,
                    settings=self.settings,
                )
                result = await self.worker.controlled_submission_once(
                    db,
                    job.id,
                    client_id,
                    ObjectInfoCacheService(object_info),
                    submission,
                    gpu_lease_id=lease.id,
                )
            submitted_job = self._require_job(db, job.id)
            self._sync_manifest(db, submitted_job, detail=result.code)
            if not result.submitted:
                return self._result(submitted_job, detail="; ".join(result.errors or [result.code]))

            async with self.runtime_client_factory() as runtime_client:
                try:
                    completed = await self._monitor_submitted_job(db, submitted_job.id, runtime_client)
                except asyncio.CancelledError:
                    await self._best_effort_runtime_cleanup(db, submitted_job.id, runtime_client)
                    self.worker.interrupt_job_once(
                        db,
                        submitted_job.id,
                        "Worker task canceled during active ComfyUI execution",
                    )
                    raise
            self._sync_manifest(db, completed, detail=completed.error_message)
            retry = self._schedule_retry(
                db,
                completed,
                reason=completed.error_message or f"Transient terminal state: {completed.status.value}",
            )
            return self._result_with_retry(completed, retry)
        except asyncio.CancelledError:
            await self._best_effort_interrupt(db, job.id)
            raise
        except Exception as exc:
            terminal = self._mark_unexpected_failure(db, job.id, str(exc))
            self._sync_manifest(db, terminal, detail=str(exc))
            retry = self._schedule_retry(
                db,
                terminal,
                reason=str(exc),
                allow_validation_failure=True,
            )
            return self._result_with_retry(terminal, retry, detail=str(exc))

    async def _load_object_info(self) -> dict[str, Any]:
        async with self.public_client_factory() as client:
            object_info = await client.get_object_info()
        if not isinstance(object_info, dict) or not object_info:
            raise ValidationError("ComfyUI returned empty object_info")
        return object_info

    async def _monitor_submitted_job(self, db: Session, job_id: UUID, runtime_client: Any) -> ComfyJob:
        deadline = time.monotonic() + self.settings.comfyui_job_timeout_sec
        websocket = None
        try:
            websocket = await self.worker.connect_progress_once(db, job_id, runtime_client)
        except Exception:
            websocket = None

        try:
            while time.monotonic() < deadline:
                self.queue_service.heartbeat_active_job(db, job_id, self.worker_id)
                self.worker.heartbeat_gpu_lease_once(db, job_id)
                payload = await self._next_websocket_payload(websocket)
                if payload is not None:
                    event = self.recorder.record_event(db, job_id, self.worker_id, payload)
                    current = self._require_job(db, job_id)
                    self._sync_manifest(db, current, detail=event.kind.value)
                    if current.status in self._terminal_states():
                        return current
                    if current.status == QueueStatus.collecting_outputs:
                        return self._collect_outputs(db, current)

                current = await self._history_fallback(db, job_id, runtime_client)
                if current.status in self._terminal_states():
                    return current
                if current.status == QueueStatus.collecting_outputs:
                    return self._collect_outputs(db, current)
                await asyncio.sleep(self.settings.comfyui_progress_poll_interval_sec)
        finally:
            if websocket is not None:
                close = getattr(websocket, "close", None)
                if close is not None:
                    result = close()
                    if hasattr(result, "__await__"):
                        await result

        await self._best_effort_runtime_cleanup(db, job_id, runtime_client)
        current = self._require_job(db, job_id)
        if current.status == QueueStatus.submitted:
            self.queue_service.transition_job(
                db,
                job_id,
                JobState.running,
                "ComfyUI job timeout after submission",
                actor="worker",
                worker_id=self.worker_id,
            )
        return self.queue_service.mark_terminal_job(
            db,
            job_id,
            JobState.timeout,
            "ComfyUI job exceeded configured deadline",
            actor="worker",
            worker_id=self.worker_id,
            error_message="ComfyUI job exceeded configured deadline",
        )

    async def _next_websocket_payload(self, websocket: Any) -> dict[str, Any] | None:
        if websocket is None:
            return None
        recv = getattr(websocket, "recv", None)
        if recv is None:
            return None
        try:
            raw = await asyncio.wait_for(
                recv(),
                timeout=self.settings.comfyui_progress_poll_interval_sec,
            )
        except (TimeoutError, asyncio.TimeoutError):
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        return raw if isinstance(raw, dict) else None

    async def _history_fallback(self, db: Session, job_id: UUID, runtime_client: Any) -> ComfyJob:
        job = self._require_job(db, job_id)
        if not job.prompt_id:
            return job
        try:
            history = await runtime_client.get_history(job.prompt_id)
        except Exception:
            return self._require_job(db, job_id)
        entry = history.get(job.prompt_id) if isinstance(history, dict) else None
        if not isinstance(entry, dict):
            return self._require_job(db, job_id)

        error = self._history_error(entry)
        if error:
            self.recorder.record_event(
                db,
                job_id,
                self.worker_id,
                {"type": "execution_error", "data": {"prompt_id": job.prompt_id, "exception_message": error}},
            )
            return self._require_job(db, job_id)
        if self._history_complete(entry):
            if job.status == QueueStatus.submitted:
                self.recorder.record_event(
                    db,
                    job_id,
                    self.worker_id,
                    {"type": "execution_start", "data": {"prompt_id": job.prompt_id}},
                )
            current = self._require_job(db, job_id)
            if current.status == QueueStatus.running:
                self.recorder.record_event(
                    db,
                    job_id,
                    self.worker_id,
                    {"type": "executing", "data": {"prompt_id": job.prompt_id, "node": None}},
                )
        return self._require_job(db, job_id)

    def _collect_outputs(self, db: Session, job: ComfyJob) -> ComfyJob:
        run = db.get(WorkflowRun, job.workflow_run_id)
        if run is None:
            return self.queue_service.mark_terminal_job(
                db,
                job.id,
                JobState.postprocess_failed,
                "Workflow run missing during output collection",
                actor="worker",
                worker_id=self.worker_id,
                error_message="Workflow run missing during output collection",
            )
        prefix = sanitize_comfy_output_prefix(str((run.patch_payload_json or {}).get("output_prefix") or ""))
        parts = PurePosixPath(prefix).parts
        if len(parts) != 2:
            return self.queue_service.mark_terminal_job(
                db,
                job.id,
                JobState.postprocess_failed,
                "Managed output prefix must contain project folder and run stem",
                actor="worker",
                worker_id=self.worker_id,
                error_message="Managed output prefix must contain project folder and run stem",
            )
        self.output_collector.collect_for_job(
            db,
            job.id,
            parts[0],
            parts[1],
            worker_id=self.worker_id,
            probe=True,
        )
        return self._require_job(db, job.id)

    def _fail_reserved_validation(self, db: Session, job_id: UUID, message: str) -> ComfyJob:
        job = self._require_job(db, job_id)
        if job.status == QueueStatus.reserved:
            self.queue_service.transition_job(
                db,
                job_id,
                JobState.validating,
                message,
                actor="worker",
                worker_id=self.worker_id,
            )
        return self.queue_service.mark_terminal_job(
            db,
            job_id,
            JobState.validation_failed,
            message,
            actor="worker",
            worker_id=self.worker_id,
            error_message=message,
        )

    def _mark_unexpected_failure(self, db: Session, job_id: UUID, message: str) -> ComfyJob:
        job = self._require_job(db, job_id)
        if job.status in self._terminal_states():
            return job
        if job.status == QueueStatus.reserved:
            return self._fail_reserved_validation(db, job_id, message)
        if job.status == QueueStatus.validating:
            return self.queue_service.mark_terminal_job(
                db,
                job_id,
                JobState.validation_failed,
                message,
                actor="worker",
                worker_id=self.worker_id,
                error_message=message,
            )
        if job.status == QueueStatus.submitted:
            self.queue_service.transition_job(
                db,
                job_id,
                JobState.running,
                "Unexpected worker failure after submission",
                actor="worker",
                worker_id=self.worker_id,
            )
        return self.queue_service.mark_terminal_job(
            db,
            job_id,
            JobState.runtime_failed,
            message,
            actor="worker",
            worker_id=self.worker_id,
            error_message=message,
        )

    async def _best_effort_runtime_cleanup(self, db: Session, job_id: UUID, runtime_client: Any) -> None:
        try:
            await self.worker.cleanup_runtime_queue_once(db, job_id, runtime_client)
        except Exception:
            pass
        try:
            permit = self.worker._runtime_control_permit(db, job_id)
            if permit is not None:
                await runtime_client.interrupt(permit=permit)
        except Exception:
            pass
        try:
            await self.worker.free_runtime_memory_once(db, job_id, runtime_client)
        except Exception:
            pass

    async def _best_effort_interrupt(self, db: Session, job_id: UUID) -> None:
        job = db.get(ComfyJob, job_id)
        if job is None or job.status in self._terminal_states():
            return
        try:
            self._mark_unexpected_failure(db, job_id, "Worker task canceled")
        except Exception:
            self.queue_service.release_bound_gpu_lease(
                db,
                job_id,
                "Worker task canceled",
                actor="worker",
                worker_id=self.worker_id,
            )

    def _sync_manifest(self, db: Session, job: ComfyJob, *, detail: str | None) -> None:
        run = db.get(WorkflowRun, job.workflow_run_id)
        request_id = (run.patch_payload_json or {}).get("semantic_request_id") if run is not None else None
        if not request_id:
            return
        try:
            self.manifest_store.update_execution_state(
                UUID(str(request_id)),
                state=job.status.value,
                queue_job_id=job.id,
                prompt_id=job.prompt_id,
                detail=detail,
            )
        except Exception:
            # DB queue state is authoritative once promoted; a damaged/missing
            # file mirror must never hide or roll back the durable job state.
            return

    def _schedule_retry(
        self,
        db: Session,
        terminal_job: ComfyJob,
        *,
        reason: str,
        allow_validation_failure: bool = False,
    ) -> ComfyJob | None:
        retry = self.queue_service.schedule_bounded_retry(
            db,
            terminal_job.id,
            max_attempts=self.settings.comfyui_max_job_attempts,
            reason=reason,
            allow_validation_failure=allow_validation_failure,
        )
        if retry is None:
            return None
        previous_run = db.get(WorkflowRun, terminal_job.workflow_run_id)
        request_id = (
            (previous_run.patch_payload_json or {}).get("semantic_request_id")
            if previous_run is not None
            else None
        )
        if request_id:
            try:
                self.manifest_store.bind_retry(
                    UUID(str(request_id)),
                    previous_job_id=terminal_job.id,
                    retry_job_id=retry.id,
                    detail=reason,
                )
            except Exception:
                # The DB retry remains authoritative. A damaged file-backed
                # mirror must not delete or invalidate the durable retry.
                pass
        return retry

    def _recover_stale_jobs(self, db: Session) -> None:
        stale_before = datetime.now(UTC) - timedelta(seconds=self.settings.comfyui_active_stale_after_sec)
        reserved = self.queue_service.recover_stale_reserved_jobs(
            db,
            stale_before,
            max_attempts=self.settings.comfyui_max_job_attempts,
            reason="Live worker recovered a stale reservation",
        )
        for recovered in reserved:
            self._sync_manifest(db, recovered, detail="Stale reservation recovered")

        active = self.queue_service.recover_stale_active_jobs(
            db,
            stale_before,
            reason="Live worker recovered an orphaned active execution",
        )
        for terminal in active:
            self._sync_manifest(db, terminal, detail=terminal.error_message)
            self._schedule_retry(
                db,
                terminal,
                reason=terminal.error_message or "Orphaned active execution",
            )

    @staticmethod
    def _history_complete(entry: dict[str, Any]) -> bool:
        status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
        return bool(status.get("completed")) or str(status.get("status_str") or "").lower() == "success"

    @staticmethod
    def _history_error(entry: dict[str, Any]) -> str | None:
        status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
        if str(status.get("status_str") or "").lower() in {"error", "failed"}:
            return str(status.get("error") or "ComfyUI history reported failure")
        messages = status.get("messages") if isinstance(status.get("messages"), list) else []
        for message in messages:
            if isinstance(message, list) and len(message) >= 2 and message[0] == "execution_error":
                detail = message[1] if isinstance(message[1], dict) else {}
                return str(detail.get("exception_message") or detail.get("exception_type") or "ComfyUI execution error")
        return None

    @staticmethod
    def _terminal_states() -> set[QueueStatus]:
        return {
            QueueStatus.complete,
            QueueStatus.validation_failed,
            QueueStatus.comfy_rejected,
            QueueStatus.runtime_failed,
            QueueStatus.timeout,
            QueueStatus.interrupted,
            QueueStatus.oom,
            QueueStatus.postprocess_failed,
            QueueStatus.canceled,
        }

    @staticmethod
    def _require_job(db: Session, job_id: UUID) -> ComfyJob:
        job = db.get(ComfyJob, job_id)
        if job is None:
            raise ValidationError(f"ComfyJob not found: {job_id}")
        return job

    def _result(self, job: ComfyJob, *, detail: str | None = None) -> LiveWorkerResult:
        return LiveWorkerResult(
            self.worker_id,
            job.id,
            job.status.value,
            prompt_id=job.prompt_id,
            detail=detail or job.error_message,
        )

    def _result_with_retry(
        self,
        job: ComfyJob,
        retry: ComfyJob | None,
        *,
        detail: str | None = None,
    ) -> LiveWorkerResult:
        message = detail or job.error_message
        if retry is not None:
            retry_detail = f"retry queued as {retry.id}"
            message = f"{message}; {retry_detail}" if message else retry_detail
        return self._result(job, detail=message)
