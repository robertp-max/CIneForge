from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import AuditLog, Base, ComfyJob, GpuResourceLease, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.schemas.voice import GpuLeaseAcquireRequest
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.queue.service import QueueService, SubmissionReadinessResult
from backend.app.services.queue.worker import QueueWorker
from backend.app.services.runtime.gpu_leases import acquire_lease


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_path = tmp_path / "cineforge_queue_worker_test.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    Base.metadata.create_all(engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_comfy_job(db: Session, status: QueueStatus = QueueStatus.pending, worker_id: str | None = None) -> ComfyJob:
    template = WorkflowTemplate(
        name=f"worker-test-template-{uuid4()}",
        version="1",
        workflow_api_json={"nodes": []},
        manifest_json={"name": "worker-test-template"},
        sha256=f"worker-test-sha256-{uuid4()}",
    )
    db.add(template)
    db.flush()

    workflow_run = WorkflowRun(
        workflow_template_id=template.id,
        patched_workflow_json={"nodes": []},
        patch_payload_json={"inputs": {}},
        status="queued",
    )
    db.add(workflow_run)
    db.flush()

    job = ComfyJob(workflow_run_id=workflow_run.id, status=status, worker_id=worker_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def bind_lease(db: Session, job: ComfyJob, *, worker_id: str = "worker-1") -> GpuResourceLease:
    lease = acquire_lease(
        db,
        GpuLeaseAcquireRequest(
            resource_key="gpu0",
            exclusive_group="gpu-shared",
            workload_type="comfy_job",
            workload_id=str(job.id),
            owner="queue-worker-test",
            worker_id=worker_id,
            ttl_seconds=300,
        ),
    )
    QueueService().bind_gpu_lease(db, job.id, lease.id, "queue worker test lease", worker_id=worker_id)
    return lease


def audit_logs(db: Session) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog)).all())


def test_worker_no_pending_job_returns_noop_result(db_session):
    result = QueueWorker("worker-1").run_once(db_session)

    assert not result.claimed
    assert result.claimed_job_id is None
    assert not result.handler_called
    assert result.handler_succeeded is None
    assert audit_logs(db_session) == []


def test_worker_one_pending_job_is_claimed(db_session):
    job = create_comfy_job(db_session)

    result = QueueWorker("worker-1").run_once(db_session)

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert result.claimed
    assert result.claimed_job_id == job.id
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.reserved
    assert persisted_job.worker_id == "worker-1"


def test_worker_non_pending_jobs_are_ignored(db_session):
    create_comfy_job(db_session, QueueStatus.reserved)

    result = QueueWorker("worker-1").run_once(db_session)

    assert not result.claimed
    assert result.claimed_job_id is None
    assert audit_logs(db_session) == []


def test_worker_bounded_batch_stops_at_max_jobs(db_session):
    create_comfy_job(db_session)
    create_comfy_job(db_session)
    create_comfy_job(db_session)

    results = QueueWorker("worker-1").run_batch(db_session, max_jobs=2)

    reserved_count = len(db_session.scalars(select(ComfyJob).where(ComfyJob.status == QueueStatus.reserved)).all())
    pending_count = len(db_session.scalars(select(ComfyJob).where(ComfyJob.status == QueueStatus.pending)).all())
    assert len(results) == 2
    assert all(result.claimed for result in results)
    assert reserved_count == 2
    assert pending_count == 1


def test_worker_bounded_batch_stops_when_no_jobs_remain(db_session):
    create_comfy_job(db_session)

    results = QueueWorker("worker-1").run_batch(db_session, max_jobs=5)

    assert len(results) == 1
    assert results[0].claimed
    assert len(audit_logs(db_session)) == 1


def test_worker_injected_handler_called_only_after_successful_claim(db_session):
    calls = []
    worker = QueueWorker("worker-1", handler=lambda job: calls.append(job.id))

    no_job_result = worker.run_once(db_session)
    job = create_comfy_job(db_session)
    claimed_result = worker.run_once(db_session)

    assert not no_job_result.claimed
    assert claimed_result.claimed
    assert claimed_result.handler_called
    assert claimed_result.handler_succeeded is True
    assert calls == [job.id]


def test_worker_handler_failure_has_no_generation_side_effects(db_session):
    job = create_comfy_job(db_session)

    def fail_handler(_job: ComfyJob) -> None:
        raise RuntimeError("handler failed before generation")

    result = QueueWorker("worker-1", handler=fail_handler).run_once(db_session)

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert result.claimed
    assert result.handler_called
    assert result.handler_succeeded is False
    assert result.error == "handler failed before generation"
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.reserved
    assert persisted_job.prompt_id is None
    assert persisted_job.submitted_at is None
    assert persisted_job.websocket_events == []
    assert persisted_job.completed_at is None


def test_worker_heartbeat_once_delegates_safely(db_session):
    job = create_comfy_job(db_session)
    worker = QueueWorker("worker-1")
    worker.run_once(db_session)
    db_session.expire_all()
    claimed_job = db_session.get(ComfyJob, job.id)
    assert claimed_job is not None
    previous_heartbeat_at = claimed_job.heartbeat_at

    heartbeat_result = worker.heartbeat_once(db_session, job.id)

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert heartbeat_result is True
    assert persisted_job is not None
    assert persisted_job.heartbeat_at != previous_heartbeat_at
    assert persisted_job.prompt_id is None
    assert persisted_job.submitted_at is None
    assert persisted_job.websocket_events == []


def test_worker_acquires_and_heartbeats_gpu_lease_for_owned_reserved_job(db_session):
    job = create_comfy_job(db_session, QueueStatus.reserved, worker_id="worker-1")
    worker = QueueWorker("worker-1")

    lease = worker.acquire_gpu_lease_once(db_session, job.id, ttl_seconds=120)
    assert lease is not None
    first_heartbeat = lease.heartbeat_at
    persisted_job = db_session.get(ComfyJob, job.id)
    assert persisted_job is not None
    assert (persisted_job.recovery_metadata or {}).get("gpu_lease_id") == str(lease.id)

    refreshed = worker.heartbeat_gpu_lease_once(db_session, job.id, extend_seconds=240)

    db_session.expire_all()
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert refreshed is not None
    assert persisted_lease is not None
    assert persisted_lease.status == "active"
    assert persisted_lease.heartbeat_at >= first_heartbeat
    assert any(log.action == "gpu_lease_heartbeat" for log in audit_logs(db_session))


def test_worker_gpu_lease_acquisition_ignores_unowned_job(db_session):
    job = create_comfy_job(db_session, QueueStatus.reserved, worker_id="worker-2")

    lease = QueueWorker("worker-1").acquire_gpu_lease_once(db_session, job.id)

    assert lease is None
    assert db_session.scalars(select(GpuResourceLease)).first() is None


def test_worker_timeout_job_once_marks_terminal_and_releases_lease(db_session):
    job = create_comfy_job(db_session, QueueStatus.running, worker_id="worker-1")
    lease = bind_lease(db_session, job)

    result = QueueWorker("worker-1").timeout_job_once(db_session, job.id, "timeout during mock run")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert result is not None
    assert result.status == QueueStatus.timeout
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.timeout
    assert persisted_job.completed_at is not None
    assert persisted_job.error_message == "timeout during mock run"
    assert persisted_lease is not None
    assert persisted_lease.status == "released"


def test_worker_interrupt_and_cancel_terminal_helpers(db_session):
    running = create_comfy_job(db_session, QueueStatus.running, worker_id="worker-1")
    pending = create_comfy_job(db_session, QueueStatus.pending, worker_id="worker-1")
    bind_lease(db_session, running)

    interrupted = QueueWorker("worker-1").interrupt_job_once(db_session, running.id, "operator interrupted")
    bind_lease(db_session, pending, worker_id="worker-1")
    canceled = QueueWorker("worker-1").cancel_job_once(db_session, pending.id, "operator canceled")

    db_session.expire_all()
    assert interrupted is not None
    assert canceled is not None
    assert db_session.get(ComfyJob, running.id).status == QueueStatus.interrupted
    assert db_session.get(ComfyJob, pending.id).status == QueueStatus.canceled


class FakeRuntimeClient:
    def __init__(self) -> None:
        self.calls = []

    async def interrupt(self, *, permit):
        self.calls.append(("interrupt", permit.worker_id, permit.job_id, permit.prompt_id))
        return {"interrupt": "ok"}

    async def delete_queue_items(self, delete_ids, *, permit):
        self.calls.append(("delete_queue_items", list(delete_ids), permit.worker_id, permit.prompt_id))
        return {"queue": "ok"}

    async def free_memory(self, *, permit):
        self.calls.append(("free_memory", permit.worker_id, permit.prompt_id))
        return {"free": "ok"}

    async def connect_progress_websocket(self, client_id, *, permit):
        self.calls.append(("connect_progress_websocket", client_id, permit.worker_id, permit.prompt_id))
        return {"connected": client_id}


@pytest.mark.asyncio
async def test_worker_runtime_control_wrappers_require_owned_active_job_and_release_on_interrupt(db_session):
    job = create_comfy_job(db_session, QueueStatus.running, worker_id="worker-1")
    job.prompt_id = "prompt-1"
    job.client_id = "client-1"
    db_session.commit()
    lease = bind_lease(db_session, job)
    runtime_client = FakeRuntimeClient()

    worker = QueueWorker("worker-1")
    progress = await worker.connect_progress_once(db_session, job.id, runtime_client)
    cleanup = await worker.cleanup_runtime_queue_once(db_session, job.id, runtime_client)
    free = await worker.free_runtime_memory_once(db_session, job.id, runtime_client)
    interrupted = await worker.interrupt_runtime_once(db_session, job.id, runtime_client, "operator stopped runtime")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert progress == {"connected": "client-1"}
    assert cleanup == {"queue": "ok"}
    assert free == {"free": "ok"}
    assert interrupted == {"interrupt": "ok"}
    assert runtime_client.calls == [
        ("connect_progress_websocket", "client-1", "worker-1", "prompt-1"),
        ("delete_queue_items", ["prompt-1"], "worker-1", "prompt-1"),
        ("free_memory", "worker-1", "prompt-1"),
        ("interrupt", "worker-1", str(job.id), "prompt-1"),
    ]
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.interrupted
    assert persisted_job.error_message == "operator stopped runtime"
    assert persisted_lease is not None
    assert persisted_lease.status == "released"


@pytest.mark.asyncio
async def test_worker_runtime_control_wrappers_ignore_unowned_or_not_submitted_jobs(db_session):
    unowned = create_comfy_job(db_session, QueueStatus.running, worker_id="worker-2")
    pending = create_comfy_job(db_session, QueueStatus.pending, worker_id="worker-1")
    runtime_client = FakeRuntimeClient()
    worker = QueueWorker("worker-1")

    assert await worker.interrupt_runtime_once(db_session, unowned.id, runtime_client) is None
    assert await worker.cleanup_runtime_queue_once(db_session, pending.id, runtime_client) is None
    assert await worker.free_runtime_memory_once(db_session, pending.id, runtime_client) is None
    assert await worker.connect_progress_once(db_session, pending.id, runtime_client) is None
    assert runtime_client.calls == []


def test_worker_terminal_helpers_ignore_jobs_owned_by_other_workers(db_session):
    job = create_comfy_job(db_session, QueueStatus.running, worker_id="worker-2")
    lease = bind_lease(db_session, job, worker_id="worker-2")

    result = QueueWorker("worker-1").timeout_job_once(db_session, job.id, "wrong worker")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert result is None
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.running
    assert persisted_lease is not None
    assert persisted_lease.status == "active"


def test_worker_preflight_submission_once_delegates_only(db_session):
    job_id = uuid4()
    calls = []

    class FakeQueueService:
        def evaluate_submission_readiness(self, db, queued_job_id, worker_id, object_info_cache):
            calls.append((db, queued_job_id, worker_id, object_info_cache))
            return SubmissionReadinessResult(
                ready=True,
                job_id=queued_job_id,
                worker_id=worker_id,
                code="ready",
                errors=[],
                checked_at=datetime.now(UTC),
            )

    object_info_cache = ObjectInfoCacheService({})
    worker = QueueWorker("worker-1", queue_service=FakeQueueService())

    result = worker.preflight_submission_once(db_session, job_id, object_info_cache)

    assert result.ready
    assert result.job_id == job_id
    assert result.worker_id == "worker-1"
    assert calls == [(db_session, job_id, "worker-1", object_info_cache)]
    assert audit_logs(db_session) == []


def test_worker_recover_stale_once_delegates_safely(db_session):
    job = create_comfy_job(db_session)
    worker = QueueWorker("worker-1")
    worker.run_once(db_session)
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    job.reserved_at = stale_time
    job.heartbeat_at = stale_time
    db_session.commit()

    recovered_job_ids = worker.recover_stale_once(
        db_session,
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        max_attempts=3,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert recovered_job_ids == [job.id]
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.pending
    assert persisted_job.worker_id is None
    assert persisted_job.prompt_id is None
    assert persisted_job.submitted_at is None
    assert persisted_job.websocket_events == []


def test_worker_recover_stale_once_is_bounded(db_session):
    first_job = create_comfy_job(db_session)
    second_job = create_comfy_job(db_session)
    worker = QueueWorker("worker-1")
    worker.run_batch(db_session, max_jobs=2)
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    for job in [first_job, second_job]:
        persisted_job = db_session.get(ComfyJob, job.id)
        assert persisted_job is not None
        persisted_job.reserved_at = stale_time
        persisted_job.heartbeat_at = stale_time
    db_session.commit()

    recovered_job_ids = worker.recover_stale_once(
        db_session,
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        max_attempts=3,
        limit=1,
    )

    pending_count = len(db_session.scalars(select(ComfyJob).where(ComfyJob.status == QueueStatus.pending)).all())
    reserved_count = len(db_session.scalars(select(ComfyJob).where(ComfyJob.status == QueueStatus.reserved)).all())
    assert len(recovered_job_ids) == 1
    assert pending_count == 1
    assert reserved_count == 1
