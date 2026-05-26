from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import CineForgeError
from backend.app.db.base import AuditLog, ComfyJob, QueueStatus
from backend.app.queue.state_machine import InvalidTransition, JobState, transition


class QueueJobNotFound(CineForgeError):
    pass


class QueueService:
    def claim_next_pending_job(
        self,
        db: Session,
        worker_id: str,
        reason: str = "worker claim",
    ) -> ComfyJob | None:
        claim_query = (
            select(ComfyJob)
            .where(ComfyJob.status == QueueStatus.pending)
            .order_by(ComfyJob.id)
            .limit(1)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            claim_query = claim_query.with_for_update(skip_locked=True)

        job = db.scalars(claim_query).first()
        if job is None:
            db.commit()
            return None

        now = datetime.now(UTC)
        previous_state = self._status_value(job.status)
        try:
            result = transition(previous_state, JobState.reserved.value, reason)
        except (InvalidTransition, ValueError):
            db.rollback()
            raise

        job.status = QueueStatus(result.current.value)
        job.worker_id = worker_id
        job.reserved_at = now
        job.heartbeat_at = now
        job.attempt_count = (job.attempt_count or 0) + 1
        job.last_state_change_at = now
        job.recovery_metadata = job.recovery_metadata or {}

        audit_details = {
            "previous_state": result.previous.value,
            "new_state": result.current.value,
            "reason": reason,
            "actor": "system",
            "worker_id": worker_id,
            "attempt_count": job.attempt_count,
        }
        db.add(
            AuditLog(
                entity_type="comfy_job",
                entity_id=job.id,
                action="worker_claim",
                details=audit_details,
            )
        )
        db.commit()
        db.refresh(job)
        return job

    def transition_job(
        self,
        db: Session,
        job_id: UUID,
        target_state: JobState | QueueStatus | str,
        reason: str,
        actor: str = "system",
        worker_id: str | None = None,
    ) -> ComfyJob:
        job = db.get(ComfyJob, job_id)
        if job is None:
            raise QueueJobNotFound(f"ComfyJob not found: {job_id}")

        previous_state = self._status_value(job.status)
        try:
            result = transition(previous_state, self._status_value(target_state), reason)
        except (InvalidTransition, ValueError):
            db.rollback()
            raise

        now = datetime.now(UTC)
        job.status = QueueStatus(result.current.value)
        job.last_state_change_at = now
        if result.current == JobState.reserved and worker_id is not None:
            job.worker_id = worker_id
            job.reserved_at = now
            job.heartbeat_at = now
            job.attempt_count = (job.attempt_count or 0) + 1

        audit_details = {
            "previous_state": result.previous.value,
            "new_state": result.current.value,
            "reason": reason,
            "actor": actor,
        }
        audit_worker_id = worker_id or job.worker_id
        if audit_worker_id is not None:
            audit_details["worker_id"] = audit_worker_id

        db.add(
            AuditLog(
                entity_type="comfy_job",
                entity_id=job.id,
                action="queue_transition",
                details=audit_details,
            )
        )
        db.commit()
        db.refresh(job)
        return job

    def reserve_job(
        self,
        db: Session,
        job_id: UUID,
        worker_id: str,
        reason: str,
    ) -> ComfyJob:
        return self.transition_job(
            db,
            job_id,
            JobState.reserved,
            reason,
            actor="system",
            worker_id=worker_id,
        )

    @staticmethod
    def _status_value(status: JobState | QueueStatus | str) -> str:
        if isinstance(status, JobState | QueueStatus):
            return status.value
        return str(status)
