from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import CineForgeError
from backend.app.db.base import AuditLog, ComfyJob, GpuResourceLease, QueueStatus, WorkflowRun
from backend.app.queue.state_machine import JobState
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.queue.service import QueueService, SubmissionReadinessResult
from backend.app.services.runtime.gpu_leases import VIDEO_GPU_WORKLOADS
from backend.app.services.workflows.template_service import sha256_json


class ControlledSubmissionError(CineForgeError):
    pass


_PROMPT_SUBMISSION_PERMIT_TOKEN = object()


class WorkerPromptSubmissionPermit:
    """Ephemeral capability proving the controlled service passed all prompt gates."""

    def __init__(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        gpu_lease_id: UUID,
        submission_mode: Literal["queue_worker", "hardware_operator"],
        client_id: str,
        workflow_sha256: str,
        issued_at: datetime,
        _token: object,
    ) -> None:
        self.job_id = job_id
        self.worker_id = worker_id
        self.gpu_lease_id = gpu_lease_id
        self.submission_mode = submission_mode
        self.client_id = client_id
        self.workflow_sha256 = workflow_sha256
        self.issued_at = issued_at
        self._token = _token

    def require_valid(self, *, prompt: dict[str, Any], client_id: str) -> None:
        if self._token is not _PROMPT_SUBMISSION_PERMIT_TOKEN:
            raise ControlledSubmissionError(
                "CONTROLLED_SUBMISSION_PERMIT_REQUIRED: Comfy /prompt calls require a permit issued by the controlled submission service"
            )
        if client_id != self.client_id:
            raise ControlledSubmissionError("CONTROLLED_SUBMISSION_PERMIT_MISMATCH: client_id differs from the permitted submission")
        if sha256_json(prompt) != self.workflow_sha256:
            raise ControlledSubmissionError("CONTROLLED_SUBMISSION_PERMIT_MISMATCH: workflow hash differs from the permitted submission")


def _issue_prompt_submission_permit(
    *,
    job_id: UUID,
    worker_id: str,
    gpu_lease_id: UUID,
    submission_mode: Literal["queue_worker", "hardware_operator"],
    client_id: str,
    workflow: dict[str, Any],
) -> WorkerPromptSubmissionPermit:
    return WorkerPromptSubmissionPermit(
        job_id=job_id,
        worker_id=worker_id,
        gpu_lease_id=gpu_lease_id,
        submission_mode=submission_mode,
        client_id=client_id,
        workflow_sha256=sha256_json(workflow),
        issued_at=datetime.now(UTC),
        _token=_PROMPT_SUBMISSION_PERMIT_TOKEN,
    )


class PromptSubmissionAdapter(Protocol):
    async def submit_prompt(
        self,
        prompt: dict[str, Any],
        client_id: str,
        *,
        permit: WorkerPromptSubmissionPermit | None = None,
    ) -> dict[str, Any]:
        """Submit a prompt from the approved worker/runtime path only."""


class ComfyWorkerPromptSubmissionAdapter:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        tracked_worker_submission: bool = False,
    ) -> None:
        if not tracked_worker_submission:
            raise ControlledSubmissionError(
                "UNTRACKED_DIRECT_COMFY_SUBMISSION: Comfy /prompt adapter may only be constructed by the tracked backend worker"
            )
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)

    async def __aenter__(self) -> "ComfyWorkerPromptSubmissionAdapter":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def submit_prompt(
        self,
        prompt: dict[str, Any],
        client_id: str,
        *,
        permit: WorkerPromptSubmissionPermit | None = None,
    ) -> dict[str, Any]:
        if permit is None or not isinstance(permit, WorkerPromptSubmissionPermit):
            raise ControlledSubmissionError(
                "CONTROLLED_SUBMISSION_PERMIT_REQUIRED: Comfy /prompt calls require a permit issued by the controlled submission service"
            )
        permit.require_valid(prompt=prompt, client_id=client_id)
        response = await self._client.post("/prompt", json={"prompt": prompt, "client_id": client_id})
        response.raise_for_status()
        return response.json()


@dataclass(frozen=True)
class WorkerSubmissionContext:
    job_id: UUID
    worker_id: str
    client_id: str
    object_info_cache: ObjectInfoCacheService
    gpu_lease_id: UUID | None = None
    submission_mode: Literal["queue_worker", "hardware_operator"] = "queue_worker"


@dataclass(frozen=True)
class ControlledSubmissionResult:
    submitted: bool
    job_id: UUID
    worker_id: str
    status: str
    code: str
    prompt_id: str | None = None
    queue_number: int | None = None
    errors: list[str] | None = None


class ControlledComfySubmissionService:
    def __init__(
        self,
        queue_service: QueueService | None = None,
        submission_adapter: PromptSubmissionAdapter | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.queue_service = queue_service or QueueService()
        self.submission_adapter = submission_adapter
        self.settings = settings or get_settings()

    async def submit_reserved_job(
        self,
        db: Session,
        context: WorkerSubmissionContext,
    ) -> ControlledSubmissionResult:
        if self.submission_adapter is None:
            raise ControlledSubmissionError("Controlled submission adapter is not configured")

        gate_failure = self._submission_gate_failure(context)
        if gate_failure is not None:
            gate_code, gate_error = gate_failure
            if context.gpu_lease_id is not None and self._gpu_lease_error(db, context) is None:
                self._release_context_gpu_lease(db, context, "controlled submission gate disabled")
            return self._mark_preflight_blocked(db, context, gate_code, gate_error)

        lease_error = self._gpu_lease_error(db, context)
        if lease_error is not None:
            return self._mark_preflight_blocked(db, context, "gpu_lease_required", lease_error)

        assert context.gpu_lease_id is not None
        self.queue_service.bind_gpu_lease(
            db,
            context.job_id,
            context.gpu_lease_id,
            "controlled submission lease validated",
            actor="worker",
            worker_id=context.worker_id,
        )

        readiness = self.queue_service.evaluate_submission_readiness(
            db,
            context.job_id,
            context.worker_id,
            context.object_info_cache,
        )
        if not readiness.ready:
            self._mark_validation_failed_if_worker_owned_reserved(db, readiness)
            self.queue_service.release_bound_gpu_lease(
                db,
                context.job_id,
                "controlled submission readiness failed",
                actor="worker",
                worker_id=context.worker_id,
            )
            return ControlledSubmissionResult(
                submitted=False,
                job_id=context.job_id,
                worker_id=context.worker_id,
                status="validation_failed",
                code=readiness.code,
                errors=readiness.errors,
            )

        self.queue_service.transition_job(
            db,
            context.job_id,
            JobState.validating,
            "controlled submission readiness passed",
            actor="worker",
            worker_id=context.worker_id,
        )

        job = self._require_job(db, context.job_id)
        workflow_run = self._require_workflow_run(db, job.workflow_run_id)
        permit = _issue_prompt_submission_permit(
            job_id=context.job_id,
            worker_id=context.worker_id,
            gpu_lease_id=context.gpu_lease_id,
            submission_mode=context.submission_mode,
            client_id=context.client_id,
            workflow=workflow_run.patched_workflow_json,
        )
        try:
            response = await self.submission_adapter.submit_prompt(
                workflow_run.patched_workflow_json,
                context.client_id,
                permit=permit,
            )
        except Exception as exc:
            self._mark_submission_failure(
                db,
                job,
                QueueStatus.comfy_rejected,
                "worker_prompt_rejected",
                "controlled submission adapter rejected prompt",
                str(exc),
                context.worker_id,
                release_gpu_lease=True,
            )
            return ControlledSubmissionResult(
                submitted=False,
                job_id=context.job_id,
                worker_id=context.worker_id,
                status=QueueStatus.comfy_rejected.value,
                code="comfy_rejected",
                errors=[str(exc)],
            )

        node_errors = response.get("node_errors")
        if node_errors:
            error_message = f"ComfyUI node_errors: {node_errors}"
            self._mark_submission_failure(
                db,
                job,
                QueueStatus.validation_failed,
                "worker_prompt_node_errors",
                "controlled submission returned node_errors",
                error_message,
                context.worker_id,
                release_gpu_lease=True,
            )
            return ControlledSubmissionResult(
                submitted=False,
                job_id=context.job_id,
                worker_id=context.worker_id,
                status=QueueStatus.validation_failed.value,
                code="node_errors",
                errors=[error_message],
            )

        prompt_id = response.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            error_message = "Controlled submission response missing prompt_id"
            self._mark_submission_failure(
                db,
                job,
                QueueStatus.comfy_rejected,
                "worker_prompt_rejected",
                "controlled submission response missing prompt_id",
                error_message,
                context.worker_id,
                release_gpu_lease=True,
            )
            return ControlledSubmissionResult(
                submitted=False,
                job_id=context.job_id,
                worker_id=context.worker_id,
                status=QueueStatus.comfy_rejected.value,
                code="missing_prompt_id",
                errors=[error_message],
            )

        queue_number = response.get("number")
        submitted_job = self._mark_submitted(
            db,
            job,
            prompt_id,
            queue_number if isinstance(queue_number, int) else None,
            context.client_id,
            context.worker_id,
        )
        return ControlledSubmissionResult(
            submitted=True,
            job_id=context.job_id,
            worker_id=context.worker_id,
            status=submitted_job.status.value,
            code="submitted",
            prompt_id=prompt_id,
            queue_number=submitted_job.queue_number,
            errors=[],
        )

    def _submission_gate_failure(self, context: WorkerSubmissionContext) -> tuple[str, str] | None:
        if context.submission_mode == "hardware_operator":
            if self.settings.hardware_operator_enabled:
                return None
            return (
                "hardware_operator_gate_disabled",
                "Hardware-operator ComfyUI submission requires CINEFORGE_HARDWARE_OPERATOR_ENABLED=true; public submission remains disabled.",
            )
        if context.submission_mode == "queue_worker":
            if self.settings.queue_worker_enabled:
                return None
            return (
                "queue_worker_gate_disabled",
                "Queue-worker ComfyUI submission requires CINEFORGE_QUEUE_WORKER_ENABLED=true; public submission remains disabled.",
            )
        return ("submission_mode_invalid", f"Unsupported submission mode: {context.submission_mode}")

    def _gpu_lease_error(self, db: Session, context: WorkerSubmissionContext) -> str | None:
        if context.gpu_lease_id is None:
            return "Controlled ComfyUI submission requires an active GPU lease id."
        lease = db.get(GpuResourceLease, context.gpu_lease_id)
        if lease is None:
            return f"GPU lease not found: {context.gpu_lease_id}"
        if lease.status != "active":
            return f"GPU lease {context.gpu_lease_id} is not active (status={lease.status})."
        if lease.worker_id != context.worker_id:
            return f"GPU lease {context.gpu_lease_id} is not owned by worker {context.worker_id}."
        if lease.workload_type not in VIDEO_GPU_WORKLOADS:
            return f"GPU lease {context.gpu_lease_id} is for unsupported workload type {lease.workload_type}."
        job = db.get(ComfyJob, context.job_id)
        allowed_workload_ids = {str(context.job_id)}
        if job is not None:
            allowed_workload_ids.add(str(job.workflow_run_id))
        if lease.workload_id not in allowed_workload_ids:
            return f"GPU lease {context.gpu_lease_id} is not bound to job {context.job_id}."
        return None

    def _release_context_gpu_lease(self, db: Session, context: WorkerSubmissionContext, reason: str) -> None:
        if context.gpu_lease_id is None:
            return
        lease = db.get(GpuResourceLease, context.gpu_lease_id)
        if lease is None or lease.status != "active":
            return
        now = datetime.now(UTC)
        lease.status = "released"
        lease.released_at = now
        db.add(
            AuditLog(
                entity_type="comfy_job",
                entity_id=context.job_id,
                action="gpu_lease_released",
                details={
                    "reason": reason,
                    "actor": "worker",
                    "worker_id": context.worker_id,
                    "gpu_lease_id": str(context.gpu_lease_id),
                    "status": "preflight_blocked",
                },
            )
        )
        db.commit()

    def _mark_preflight_blocked(
        self,
        db: Session,
        context: WorkerSubmissionContext,
        code: str,
        message: str,
    ) -> ControlledSubmissionResult:
        readiness = SubmissionReadinessResult(
            ready=False,
            job_id=context.job_id,
            worker_id=context.worker_id,
            code=code,
            errors=[message],
            checked_at=datetime.now(UTC),
        )
        self._mark_validation_failed_if_worker_owned_reserved(db, readiness)
        return ControlledSubmissionResult(
            submitted=False,
            job_id=context.job_id,
            worker_id=context.worker_id,
            status=QueueStatus.validation_failed.value,
            code=code,
            errors=[message],
        )

    def _mark_validation_failed_if_worker_owned_reserved(
        self,
        db: Session,
        readiness: SubmissionReadinessResult,
    ) -> None:
        job = db.get(ComfyJob, readiness.job_id)
        if job is None or job.status != QueueStatus.reserved or job.worker_id != readiness.worker_id:
            return

        self.queue_service.transition_job(
            db,
            readiness.job_id,
            JobState.validating,
            "controlled submission readiness failed",
            actor="worker",
            worker_id=readiness.worker_id,
        )
        job = self._require_job(db, readiness.job_id)
        self._mark_submission_failure(
            db,
            job,
            QueueStatus.validation_failed,
            "worker_submission_readiness_failed",
            "controlled submission readiness failed",
            "; ".join(readiness.errors),
            readiness.worker_id,
        )

    def _mark_submitted(
        self,
        db: Session,
        job: ComfyJob,
        prompt_id: str,
        queue_number: int | None,
        client_id: str,
        worker_id: str,
    ) -> ComfyJob:
        now = datetime.now(UTC)
        previous_state = job.status.value
        job.status = QueueStatus.submitted
        job.prompt_id = prompt_id
        job.queue_number = queue_number
        job.client_id = client_id
        job.submitted_at = now
        job.last_state_change_at = now
        workflow_run = self._require_workflow_run(db, job.workflow_run_id)
        workflow_run.status = QueueStatus.submitted.value
        db.add(
            AuditLog(
                entity_type="comfy_job",
                entity_id=job.id,
                action="worker_prompt_submission",
                details={
                    "previous_state": previous_state,
                    "new_state": QueueStatus.submitted.value,
                    "reason": "controlled worker prompt submission",
                    "actor": "worker",
                    "worker_id": worker_id,
                    "prompt_id": prompt_id,
                    "queue_number": queue_number,
                },
            )
        )
        db.commit()
        db.refresh(job)
        return job

    def _mark_submission_failure(
        self,
        db: Session,
        job: ComfyJob,
        target_status: QueueStatus,
        action: str,
        reason: str,
        error_message: str,
        worker_id: str,
        *,
        release_gpu_lease: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        previous_state = job.status.value
        job.status = target_status
        job.error_message = error_message
        job.last_state_change_at = now
        workflow_run = self._require_workflow_run(db, job.workflow_run_id)
        workflow_run.status = target_status.value
        db.add(
            AuditLog(
                entity_type="comfy_job",
                entity_id=job.id,
                action=action,
                details={
                    "previous_state": previous_state,
                    "new_state": target_status.value,
                    "reason": reason,
                    "actor": "worker",
                    "worker_id": worker_id,
                    "error_message": error_message,
                },
            )
        )
        db.commit()
        if release_gpu_lease:
            self.queue_service.release_bound_gpu_lease(
                db,
                job.id,
                reason,
                actor="worker",
                worker_id=worker_id,
            )

    @staticmethod
    def _require_job(db: Session, job_id: UUID) -> ComfyJob:
        job = db.get(ComfyJob, job_id)
        if job is None:
            raise ControlledSubmissionError(f"ComfyJob not found: {job_id}")
        return job

    @staticmethod
    def _require_workflow_run(db: Session, workflow_run_id: UUID) -> WorkflowRun:
        workflow_run = db.get(WorkflowRun, workflow_run_id)
        if workflow_run is None:
            raise ControlledSubmissionError(f"WorkflowRun not found: {workflow_run_id}")
        return workflow_run
