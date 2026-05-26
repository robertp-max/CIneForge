from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.errors import CineForgeError
from backend.app.db.base import AuditLog, ComfyJob, QueueStatus
from backend.app.queue.state_machine import InvalidTransition, JobState, transition


class QueueJobNotFound(CineForgeError):
    pass


class QueueService:
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

        job.status = QueueStatus(result.current.value)
        audit_details = {
            "previous_state": result.previous.value,
            "new_state": result.current.value,
            "reason": reason,
            "actor": actor,
        }
        if worker_id is not None:
            audit_details["worker_id"] = worker_id

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
