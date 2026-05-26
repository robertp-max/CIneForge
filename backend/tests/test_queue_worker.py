from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import AuditLog, Base, ComfyJob, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.services.queue.worker import QueueWorker


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


def create_comfy_job(db: Session, status: QueueStatus = QueueStatus.pending) -> ComfyJob:
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

    job = ComfyJob(workflow_run_id=workflow_run.id, status=status)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


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
