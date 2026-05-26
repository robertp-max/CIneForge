from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.base import ComfyJob
from backend.app.services.queue.service import QueueService


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
