from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.base import AuditLog, ComfyJob, GpuResourceLease, QueueStatus
from backend.app.schemas.voice import GpuLeaseAcquireRequest
from backend.app.services.comfy.client import WorkerRuntimeControlPermit, _issue_runtime_control_permit
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.comfy.submission import (
    ControlledComfySubmissionService,
    ControlledSubmissionResult,
    WorkerSubmissionContext,
)
from backend.app.services.queue.service import QueueService, SubmissionReadinessResult
from backend.app.services.runtime.gpu_leases import DEFAULT_EXCLUSIVE_GROUP, DEFAULT_RESOURCE_KEY, acquire_lease, heartbeat_lease


QueueJobHandler = Callable[[ComfyJob], None]


@dataclass(frozen=True)
class QueueWorkerResult:
    worker_id: str
    claimed_job_id: UUID | None
    claimed: bool
    handler_called: bool
    handler_succeeded: bool | None
    error: str | None = None

    @classmethod
    def no_job(cls, worker_id: str) -> "QueueWorkerResult":
        return cls(
            worker_id=worker_id,
            claimed_job_id=None,
            claimed=False,
            handler_called=False,
            handler_succeeded=None,
        )


class QueueWorker:
    def __init__(
        self,
        worker_id: str,
        queue_service: QueueService | None = None,
        handler: QueueJobHandler | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.queue_service = queue_service or QueueService()
        self.handler = handler

    def run_once(self, db: Session) -> QueueWorkerResult:
        job = self.queue_service.claim_next_pending_job(db, self.worker_id, "worker run once")
        if job is None:
            return QueueWorkerResult.no_job(self.worker_id)

        if self.handler is None:
            return QueueWorkerResult(
                worker_id=self.worker_id,
                claimed_job_id=job.id,
                claimed=True,
                handler_called=False,
                handler_succeeded=None,
            )

        try:
            self.handler(job)
        except Exception as exc:
            return QueueWorkerResult(
                worker_id=self.worker_id,
                claimed_job_id=job.id,
                claimed=True,
                handler_called=True,
                handler_succeeded=False,
                error=str(exc),
            )

        return QueueWorkerResult(
            worker_id=self.worker_id,
            claimed_job_id=job.id,
            claimed=True,
            handler_called=True,
            handler_succeeded=True,
        )

    def run_batch(self, db: Session, max_jobs: int) -> list[QueueWorkerResult]:
        if max_jobs < 1:
            return []

        results: list[QueueWorkerResult] = []
        for _ in range(max_jobs):
            result = self.run_once(db)
            if not result.claimed:
                break
            results.append(result)
        return results

    def heartbeat_once(self, db: Session, job_id: UUID) -> bool:
        return self.queue_service.heartbeat_job(db, job_id, self.worker_id) is not None

    def preflight_submission_once(
        self,
        db: Session,
        job_id: UUID,
        object_info_cache: ObjectInfoCacheService,
    ) -> SubmissionReadinessResult:
        return self.queue_service.evaluate_submission_readiness(
            db,
            job_id,
            self.worker_id,
            object_info_cache,
        )

    async def controlled_submission_once(
        self,
        db: Session,
        job_id: UUID,
        client_id: str,
        object_info_cache: ObjectInfoCacheService,
        submission_service: ControlledComfySubmissionService,
        gpu_lease_id: UUID | None = None,
    ) -> ControlledSubmissionResult:
        lease_id = gpu_lease_id
        if lease_id is None:
            lease = self.acquire_gpu_lease_once(db, job_id)
            if lease is None:
                return ControlledSubmissionResult(
                    submitted=False,
                    job_id=job_id,
                    worker_id=self.worker_id,
                    status=QueueStatus.validation_failed.value,
                    code="gpu_lease_acquisition_failed",
                    errors=["Worker does not own an active reserved job for GPU lease acquisition"],
                )
            lease_id = lease.id
        else:
            self.heartbeat_gpu_lease_once(db, job_id, lease_id=lease_id)
        context = WorkerSubmissionContext(
            job_id=job_id,
            worker_id=self.worker_id,
            client_id=client_id,
            object_info_cache=object_info_cache,
            gpu_lease_id=lease_id,
        )
        return await submission_service.submit_reserved_job(db, context)

    def acquire_gpu_lease_once(self, db: Session, job_id: UUID, ttl_seconds: int = 300) -> GpuResourceLease | None:
        if not self._owns_job(db, job_id):
            return None
        lease = acquire_lease(
            db,
            GpuLeaseAcquireRequest(
                resource_key=DEFAULT_RESOURCE_KEY,
                exclusive_group=DEFAULT_EXCLUSIVE_GROUP,
                workload_type="comfy_job",
                workload_id=str(job_id),
                owner=f"queue-worker:{self.worker_id}",
                worker_id=self.worker_id,
                ttl_seconds=ttl_seconds,
                metadata={"job_id": str(job_id), "acquired_by": "queue_worker"},
            ),
        )
        self.queue_service.bind_gpu_lease(
            db,
            job_id,
            lease.id,
            "queue worker acquired GPU lease",
            actor="worker",
            worker_id=self.worker_id,
        )
        return lease

    def heartbeat_gpu_lease_once(
        self,
        db: Session,
        job_id: UUID,
        *,
        lease_id: UUID | None = None,
        extend_seconds: int = 300,
    ) -> GpuResourceLease | None:
        if not self._owns_job(db, job_id):
            return None
        job = db.get(ComfyJob, job_id)
        if job is None:
            return None
        if lease_id is None:
            lease_id_raw = (job.recovery_metadata or {}).get("gpu_lease_id")
            if not lease_id_raw:
                return None
            lease_id = UUID(str(lease_id_raw))
        lease = heartbeat_lease(db, lease_id, extend_seconds=extend_seconds)
        db.add(
            AuditLog(
                entity_type="comfy_job",
                entity_id=job_id,
                action="gpu_lease_heartbeat",
                details={
                    "worker_id": self.worker_id,
                    "gpu_lease_id": str(lease.id),
                    "expires_at": lease.expires_at.isoformat() if lease.expires_at else None,
                },
            )
        )
        db.commit()
        db.refresh(lease)
        return lease

    def timeout_job_once(self, db: Session, job_id: UUID, reason: str = "worker timeout") -> ComfyJob | None:
        if not self._owns_job(db, job_id):
            return None
        return self.queue_service.mark_terminal_job(
            db,
            job_id,
            QueueStatus.timeout,
            reason,
            actor="worker",
            worker_id=self.worker_id,
            error_message=reason,
        )

    def interrupt_job_once(self, db: Session, job_id: UUID, reason: str = "worker interruption") -> ComfyJob | None:
        if not self._owns_job(db, job_id):
            return None
        return self.queue_service.mark_terminal_job(
            db,
            job_id,
            QueueStatus.interrupted,
            reason,
            actor="worker",
            worker_id=self.worker_id,
            error_message=reason,
        )

    async def interrupt_runtime_once(
        self,
        db: Session,
        job_id: UUID,
        runtime_client,
        reason: str = "worker runtime interruption",
    ) -> dict | None:
        permit = self._runtime_control_permit(db, job_id)
        if permit is None:
            return None
        result = await runtime_client.interrupt(permit=permit)
        self.interrupt_job_once(db, job_id, reason)
        return result

    async def cleanup_runtime_queue_once(self, db: Session, job_id: UUID, runtime_client) -> dict | None:
        permit = self._runtime_control_permit(db, job_id)
        job = db.get(ComfyJob, job_id)
        if permit is None or job is None or not job.prompt_id:
            return None
        return await runtime_client.delete_queue_items([job.prompt_id], permit=permit)

    async def free_runtime_memory_once(self, db: Session, job_id: UUID, runtime_client) -> dict | None:
        permit = self._runtime_control_permit(db, job_id)
        if permit is None:
            return None
        return await runtime_client.free_memory(permit=permit)

    async def connect_progress_once(self, db: Session, job_id: UUID, runtime_client) -> object | None:
        permit = self._runtime_control_permit(db, job_id)
        job = db.get(ComfyJob, job_id)
        if permit is None or job is None or not job.client_id:
            return None
        return await runtime_client.connect_progress_websocket(job.client_id, permit=permit)

    def cancel_job_once(self, db: Session, job_id: UUID, reason: str = "worker cancellation") -> ComfyJob | None:
        if not self._owns_job(db, job_id):
            return None
        return self.queue_service.mark_terminal_job(
            db,
            job_id,
            QueueStatus.canceled,
            reason,
            actor="worker",
            worker_id=self.worker_id,
            error_message=reason,
        )

    def _owns_job(self, db: Session, job_id: UUID) -> bool:
        job = db.get(ComfyJob, job_id)
        return job is not None and job.worker_id == self.worker_id

    def _runtime_control_permit(self, db: Session, job_id: UUID) -> WorkerRuntimeControlPermit | None:
        job = db.get(ComfyJob, job_id)
        if job is None or job.worker_id != self.worker_id:
            return None
        if job.status not in {QueueStatus.submitted, QueueStatus.running, QueueStatus.collecting_outputs, QueueStatus.timeout}:
            return None
        return _issue_runtime_control_permit(
            worker_id=self.worker_id,
            job_id=str(job.id),
            prompt_id=job.prompt_id,
        )

    def recover_stale_once(
        self,
        db: Session,
        stale_before: datetime,
        max_attempts: int,
        limit: int = 100,
    ) -> list[UUID]:
        recovered_jobs = self.queue_service.recover_stale_reserved_jobs(
            db,
            stale_before=stale_before,
            max_attempts=max_attempts,
            limit=limit,
            reason="worker stale reservation recovery",
        )
        return [job.id for job in recovered_jobs]
