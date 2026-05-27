from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.core.errors import CineForgeError
from backend.app.db.base import AuditLog, ComfyJob, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.queue.state_machine import InvalidTransition, JobState, transition
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.workflows.template_service import WorkflowManifest


class QueueJobNotFound(CineForgeError):
    pass


DEFAULT_RECOVERY_LIMIT = 100


@dataclass(frozen=True)
class SubmissionReadinessResult:
    ready: bool
    job_id: UUID
    worker_id: str
    code: str
    errors: list[str]
    checked_at: datetime


class QueueService:
    def evaluate_submission_readiness(
        self,
        db: Session,
        job_id: UUID,
        worker_id: str,
        object_info_cache: ObjectInfoCacheService,
    ) -> SubmissionReadinessResult:
        checked_at = datetime.now(UTC)
        job = db.get(ComfyJob, job_id)
        if job is None:
            return SubmissionReadinessResult(
                ready=False,
                job_id=job_id,
                worker_id=worker_id,
                code="job_not_found",
                errors=[f"ComfyJob not found: {job_id}"],
                checked_at=checked_at,
            )

        errors: list[str] = []
        if job.status != QueueStatus.reserved:
            errors.append(f"Job status must be reserved, got {self._status_value(job.status)}")
        if job.worker_id != worker_id:
            errors.append("Job is not reserved by the requesting worker")
        if job.prompt_id:
            errors.append("Job already has a ComfyUI prompt_id")

        workflow_run = db.get(WorkflowRun, job.workflow_run_id)
        if workflow_run is None:
            errors.append(f"WorkflowRun not found: {job.workflow_run_id}")
            return self._submission_readiness_result(job_id, worker_id, checked_at, errors)
        if not workflow_run.patched_workflow_json:
            errors.append("WorkflowRun is missing patched_workflow_json")

        workflow_template = db.get(WorkflowTemplate, workflow_run.workflow_template_id)
        if workflow_template is None:
            errors.append(f"WorkflowTemplate not found: {workflow_run.workflow_template_id}")
            return self._submission_readiness_result(job_id, worker_id, checked_at, errors)
        if not workflow_template.manifest_json:
            errors.append("WorkflowTemplate is missing manifest_json")

        if workflow_run.patched_workflow_json and workflow_template.manifest_json:
            try:
                manifest = WorkflowManifest.model_validate(workflow_template.manifest_json)
                object_info_cache.validate_patched_workflow_manifest(workflow_run.patched_workflow_json, manifest)
            except Exception as exc:
                errors.append(f"Object info compatibility check failed: {exc}")

        return self._submission_readiness_result(job_id, worker_id, checked_at, errors)

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

        candidate_query = (
            select(ComfyJob)
            .where(
                ComfyJob.status == QueueStatus.reserved,
                or_(
                    ComfyJob.heartbeat_at < stale_before,
                    and_(ComfyJob.heartbeat_at.is_(None), ComfyJob.reserved_at < stale_before),
                    and_(ComfyJob.heartbeat_at.is_(None), ComfyJob.reserved_at.is_(None)),
                ),
            )
            .order_by(ComfyJob.id)
            .limit(limit)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            candidate_query = candidate_query.with_for_update(skip_locked=True)

        candidates = list(db.scalars(candidate_query).all())
        recovered_jobs: list[ComfyJob] = []
        now = datetime.now(UTC)
        for job in candidates:
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
    def _submission_readiness_result(
        job_id: UUID,
        worker_id: str,
        checked_at: datetime,
        errors: list[str],
    ) -> SubmissionReadinessResult:
        if errors:
            return SubmissionReadinessResult(
                ready=False,
                job_id=job_id,
                worker_id=worker_id,
                code="preflight_failed",
                errors=errors,
                checked_at=checked_at,
            )
        return SubmissionReadinessResult(
            ready=True,
            job_id=job_id,
            worker_id=worker_id,
            code="ready",
            errors=[],
            checked_at=checked_at,
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
