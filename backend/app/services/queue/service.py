from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import CineForgeError
from backend.app.db.base import AuditLog, ComfyJob, QueueStatus
from backend.app.queue.state_machine import InvalidTransition, JobState, transition


class QueueJobNotFound(CineForgeError):
    pass


DEFAULT_RECOVERY_LIMIT = 100


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

    def heartbeat_job(
        self,
        db: Session,
        job_id: UUID,
        worker_id: str,
        reason: str = "worker heartbeat",
    ) -> ComfyJob | None:
        job = db.get(ComfyJob, job_id)
        if job is None:
            raise QueueJobNotFound(f"ComfyJob not found: {job_id}")

        if job.status != QueueStatus.reserved or job.worker_id != worker_id:
            db.commit()
            return None

        now = datetime.now(UTC)
        previous_heartbeat_at = job.heartbeat_at
        job.heartbeat_at = now
        db.add(
            AuditLog(
                entity_type="comfy_job",
                entity_id=job.id,
                action="worker_heartbeat",
                details={
                    "status": self._status_value(job.status),
                    "reason": reason,
                    "actor": "worker",
                    "worker_id": worker_id,
                    "previous_heartbeat_at": self._datetime_value(previous_heartbeat_at),
                    "heartbeat_at": self._datetime_value(now),
                },
            )
        )
        db.commit()
        db.refresh(job)
        return job

    def recover_stale_reserved_jobs(
        self,
        db: Session,
        stale_before: datetime,
        max_attempts: int,
        limit: int = DEFAULT_RECOVERY_LIMIT,
        reason: str = "stale reservation recovery",
    ) -> list[ComfyJob]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if limit < 1:
            return []

        candidates = list(
            db.scalars(
                select(ComfyJob)
                .where(ComfyJob.status == QueueStatus.reserved)
                .order_by(ComfyJob.id)
                .limit(limit)
            ).all()
        )
        recovered_jobs: list[ComfyJob] = []
        now = datetime.now(UTC)
        for job in candidates:
            stale_at = job.heartbeat_at or job.reserved_at
            if stale_at is not None and self._as_utc(stale_at) >= self._as_utc(stale_before):
                continue

            previous_worker_id = job.worker_id
            previous_state = self._status_value(job.status)
            attempt_count = job.attempt_count or 0
            target_state = QueueStatus.pending if attempt_count < max_attempts else QueueStatus.timeout
            action = "worker_recovery" if target_state == QueueStatus.pending else "worker_timeout"
            result = transition(previous_state, target_state.value, reason)

            metadata = dict(job.recovery_metadata or {})
            recovery_count = int(metadata.get("recovery_count", 0)) + 1
            metadata.update(
                {
                    "recovery_count": recovery_count,
                    "last_recovery_reason": reason,
                    "last_recovered_at": self._datetime_value(now),
                    "previous_worker_id": previous_worker_id,
                    "previous_state": result.previous.value,
                    "new_state": result.current.value,
                    "max_attempts": max_attempts,
                    "attempt_count": attempt_count,
                }
            )

            job.status = target_state
            job.worker_id = None
            job.reserved_at = None
            job.heartbeat_at = None
            job.last_state_change_at = now
            job.recovery_metadata = metadata

            db.add(
                AuditLog(
                    entity_type="comfy_job",
                    entity_id=job.id,
                    action=action,
                    details={
                        "previous_state": result.previous.value,
                        "new_state": result.current.value,
                        "reason": reason,
                        "actor": "system",
                        "previous_worker_id": previous_worker_id,
                        "attempt_count": attempt_count,
                        "max_attempts": max_attempts,
                        "recovery_count": recovery_count,
                    },
                )
            )
            recovered_jobs.append(job)

        db.commit()
        for job in recovered_jobs:
            db.refresh(job)
        return recovered_jobs

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

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _datetime_value(value: datetime | None) -> str | None:
        if value is None:
            return None
        return QueueService._as_utc(value).isoformat()
