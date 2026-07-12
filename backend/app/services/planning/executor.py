"""Bounded, controller-owned execution for durable planning runs.

The API request only claims a run.  Actual planning happens on a bounded
thread pool with a fresh SQLAlchemy session, so request sessions never cross
thread boundaries.  Run checkpoints remain the source of truth; submitting a
``running`` run after a controller restart safely resumes it.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
import time
from typing import Callable
from uuid import UUID, uuid4

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.schemas.orchestration import ActorType, EventType, FailureCategory, RunStatus
from backend.app.services.planning.engine import PlanningEngine
from backend.app.services.planning.errors import sanitize_message
from backend.app.services.planning.repository import PlanningRepository
from backend.app.services.planning.state_machine import is_run_terminal


EngineFactory = Callable[[Session], PlanningEngine]
ExecutionKey = tuple[int, UUID]


class ExecutionCapacityError(RuntimeError):
    """Raised when the controller's bounded submission capacity is full."""


class ExecutionSubmissionError(RuntimeError):
    """Raised after a controller submission failure is durably recorded."""


@dataclass(frozen=True, slots=True)
class ExecutionSubmission:
    scheduled: bool
    already_active: bool


class PlanningExecutionController:
    """Own a bounded set of in-process planning workers.

    This controller launches no subprocesses and has no render/media hooks.
    The ``run_id`` registry prevents duplicate execution inside this process;
    persisted run status and checkpoints provide restart/resume behavior.
    """

    def __init__(self, *, max_workers: int = 4, max_in_flight: int = 8) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        if max_in_flight < max_workers:
            raise ValueError("max_in_flight must be at least max_workers")
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="cineforge-planning",
        )
        self._max_in_flight = max_in_flight
        self._lock = Lock()
        self._active: dict[ExecutionKey, Future[None]] = {}
        self.owner_id = f"controller-{uuid4().hex}"

    @staticmethod
    def new_claim_token() -> str:
        return uuid4().hex

    def submit(
        self,
        run_id: UUID,
        *,
        bind: Engine | Connection,
        engine_factory: EngineFactory = PlanningEngine,
        resumed: bool = False,
        owner_id: str | None = None,
        claim_token: str | None = None,
        lease_seconds: int = 600,
    ) -> ExecutionSubmission:
        """Schedule one run, returning an idempotent duplicate result."""

        durable_bind: Engine = bind.engine if isinstance(bind, Connection) else bind
        execution_key = (id(durable_bind), run_id)
        session_factory = sessionmaker(
            bind=durable_bind,
            autoflush=False,
            autocommit=False,
            future=True,
        )

        with self._lock:
            existing = self._active.get(execution_key)
            if existing is not None and not existing.done():
                return ExecutionSubmission(scheduled=False, already_active=True)
            if existing is not None:
                self._active.pop(execution_key, None)
            if len(self._active) >= self._max_in_flight:
                raise ExecutionCapacityError("Planning execution capacity is full; retry shortly")

            try:
                future = self._pool.submit(
                    self._execute,
                    run_id,
                    session_factory,
                    engine_factory,
                    resumed,
                    owner_id,
                    claim_token,
                    lease_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                self._record_boundary_failure(session_factory, run_id, exc)
                raise ExecutionSubmissionError(
                    "Planning execution could not be scheduled"
                ) from exc
            self._active[execution_key] = future
            future.add_done_callback(
                lambda completed, key=execution_key: self._discard(key, completed)
            )
            return ExecutionSubmission(scheduled=True, already_active=False)

    def is_active(self, run_id: UUID, *, bind: Engine | Connection) -> bool:
        durable_bind: Engine = bind.engine if isinstance(bind, Connection) else bind
        execution_key = (id(durable_bind), run_id)
        with self._lock:
            future = self._active.get(execution_key)
            if future is None:
                return False
            if future.done():
                self._active.pop(execution_key, None)
                return False
            return True

    def wait(
        self,
        run_id: UUID,
        *,
        bind: Engine | Connection,
        timeout: float = 10.0,
    ) -> None:
        """Test/controlled-shutdown helper; never used by request handlers."""

        durable_bind: Engine = bind.engine if isinstance(bind, Connection) else bind
        execution_key = (id(durable_bind), run_id)
        with self._lock:
            future = self._active.get(execution_key)
        if future is not None:
            future.result(timeout=timeout)

    def wait_for_idle(self, *, timeout: float = 10.0) -> None:
        """Wait for currently submitted work; intended for tests/shutdown."""

        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                futures = list(self._active.values())
            if not futures:
                return
            for future in futures:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Planning execution controller did not become idle")
                future.result(timeout=remaining)

    def _discard(self, execution_key: ExecutionKey, future: Future[None]) -> None:
        with self._lock:
            if self._active.get(execution_key) is future:
                self._active.pop(execution_key, None)

    @staticmethod
    def _execute(
        run_id: UUID,
        session_factory: sessionmaker[Session],
        engine_factory: EngineFactory,
        resumed: bool,
        owner_id: str | None,
        claim_token: str | None,
        lease_seconds: int,
    ) -> None:
        db = session_factory()
        try:
            engine = engine_factory(db)
            engine.execute_claimed_run(
                run_id,
                resumed=resumed,
                owner_id=owner_id,
                claim_token=claim_token,
                lease_seconds=lease_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - persist only a sanitized boundary failure
            db.rollback()
            PlanningExecutionController._record_boundary_failure(
                session_factory,
                run_id,
                exc,
            )
        finally:
            db.close()

    @staticmethod
    def _record_boundary_failure(
        session_factory: sessionmaker[Session],
        run_id: UUID,
        error: Exception,
    ) -> None:
        """Persist an unexpected controller/engine boundary failure."""

        failure_db = session_factory()
        try:
            repo = PlanningRepository(failure_db)
            run = repo.get_run(run_id)
            if is_run_terminal(run.status):
                return
            message = sanitize_message(f"Planning worker failed: {error}")
            repo.transition_run(
                run,
                RunStatus.failed,
                failure_category=FailureCategory.internal.value,
                failure_message=message,
            )
            repo.add_event(
                run_id=run.id,
                event_type=EventType.run_failed,
                actor_type=ActorType.system,
                details={
                    "category": FailureCategory.internal.value,
                    "message": message,
                    "boundary": "planning_execution_controller",
                },
            )
            repo.commit()
        except Exception:  # noqa: BLE001 - preserve the original boundary failure
            failure_db.rollback()
        finally:
            failure_db.close()


planning_execution_controller = PlanningExecutionController()
