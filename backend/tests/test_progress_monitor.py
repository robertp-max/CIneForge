from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base, ComfyJob, GpuResourceLease, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.schemas.voice import GpuLeaseAcquireRequest
from backend.app.services.comfy.progress_monitor import (
    ComfyJobProgressRecorder,
    ProgressEventKind,
    ProgressEventParser,
    ProgressMonitor,
)
from backend.app.services.runtime.gpu_leases import acquire_lease


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_path = tmp_path / "cineforge_progress_monitor_test.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_submitted_job(db: Session, *, worker_id: str = "worker-1") -> ComfyJob:
    template = WorkflowTemplate(
        name=f"progress-template-{uuid4()}",
        version="1",
        workflow_api_json={"nodes": []},
        manifest_json={"name": "progress-template"},
        sha256=f"progress-sha-{uuid4()}",
    )
    db.add(template)
    db.flush()
    workflow_run = WorkflowRun(
        workflow_template_id=template.id,
        patched_workflow_json={"nodes": []},
        patch_payload_json={"inputs": {}},
        status="submitted",
    )
    db.add(workflow_run)
    db.flush()
    job = ComfyJob(
        workflow_run_id=workflow_run.id,
        status=QueueStatus.submitted,
        worker_id=worker_id,
        prompt_id="prompt-1",
        recovery_metadata={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def bind_lease(db: Session, job: ComfyJob, *, worker_id: str = "worker-1") -> GpuResourceLease:
    from backend.app.services.queue.service import QueueService

    lease = acquire_lease(
        db,
        GpuLeaseAcquireRequest(
            resource_key="gpu0",
            exclusive_group="gpu-shared",
            workload_type="comfy_job",
            workload_id=str(job.id),
            owner="progress-test",
            worker_id=worker_id,
            ttl_seconds=300,
        ),
    )
    QueueService().bind_gpu_lease(db, job.id, lease.id, "progress test lease", worker_id=worker_id)
    return lease


def test_progress_parser_execution_start():
    event = ProgressEventParser().parse(
        {"type": "execution_start", "data": {"prompt_id": "prompt-1"}}
    )

    assert event.kind == ProgressEventKind.execution_start
    assert event.prompt_id == "prompt-1"
    assert event.node_id is None
    assert not event.is_completion_signal


def test_progress_parser_progress_update():
    event = ProgressEventParser().parse(
        {"type": "progress", "data": {"prompt_id": "prompt-1", "node": "3", "value": 4, "max": 10}}
    )

    assert event.kind == ProgressEventKind.progress
    assert event.prompt_id == "prompt-1"
    assert event.node_id == "3"
    assert event.value == 4
    assert event.max_value == 10


def test_progress_parser_executing_complete_signal():
    event = ProgressEventParser().parse(
        {"type": "executing", "data": {"prompt_id": "prompt-1", "node": None}}
    )

    assert event.kind == ProgressEventKind.executing
    assert event.prompt_id == "prompt-1"
    assert event.node_id is None
    assert event.is_completion_signal


def test_progress_parser_error_event():
    event = ProgressEventParser().parse(
        {
            "type": "execution_error",
            "data": {
                "prompt_id": "prompt-1",
                "node": "8",
                "exception_type": "RuntimeError",
                "exception_message": "CUDA out of memory",
            },
        }
    )

    assert event.kind == ProgressEventKind.execution_error
    assert event.prompt_id == "prompt-1"
    assert event.node_id == "8"
    assert event.is_runtime_failure_candidate
    assert event.error == "CUDA out of memory"


def test_progress_parser_preserves_unknown_event():
    payload = {"type": "custom_node_metric", "data": {"prompt_id": "prompt-1", "value": "kept"}}

    event = ProgressEventParser().parse(payload)

    assert event.kind == ProgressEventKind.unknown
    assert event.raw_type == "custom_node_metric"
    assert event.raw == payload
    assert event.prompt_id == "prompt-1"


@pytest.mark.asyncio
async def test_monitor_interface_uses_history_fallback_boundary():
    class FakeClient:
        async def get_history(self, prompt_id: str):
            return {prompt_id: {"outputs": {"9": {"videos": []}}}}

    result = await ProgressMonitor().history_fallback(FakeClient(), "prompt-1")

    assert result.prompt_id == "prompt-1"
    assert result.history == {"prompt-1": {"outputs": {"9": {"videos": []}}}}


def test_progress_recorder_maps_execution_start_to_running(db_session):
    job = create_submitted_job(db_session)
    lease = bind_lease(db_session, job)

    event = ComfyJobProgressRecorder().record_event(
        db_session,
        job.id,
        "worker-1",
        {"type": "execution_start", "data": {"prompt_id": "prompt-1"}},
    )

    db_session.expire_all()
    persisted = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert event.kind == ProgressEventKind.execution_start
    assert persisted is not None
    assert persisted.status == QueueStatus.running
    assert persisted.websocket_events[-1]["kind"] == "execution_start"
    assert persisted_lease is not None
    assert persisted_lease.status == "active"


def test_progress_recorder_maps_completion_to_collecting_outputs(db_session):
    job = create_submitted_job(db_session)
    lease = bind_lease(db_session, job)

    ComfyJobProgressRecorder().record_event(
        db_session,
        job.id,
        "worker-1",
        {"type": "executing", "data": {"prompt_id": "prompt-1", "node": None}},
    )

    db_session.expire_all()
    persisted = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert persisted is not None
    assert persisted.status == QueueStatus.collecting_outputs
    assert persisted.websocket_events[-1]["is_completion_signal"] is True
    assert persisted_lease is not None
    assert persisted_lease.status == "active"


def test_progress_recorder_maps_oom_to_terminal_and_releases_lease(db_session):
    job = create_submitted_job(db_session)
    lease = bind_lease(db_session, job)

    ComfyJobProgressRecorder().record_event(
        db_session,
        job.id,
        "worker-1",
        {
            "type": "execution_error",
            "data": {
                "prompt_id": "prompt-1",
                "node": "8",
                "exception_type": "RuntimeError",
                "exception_message": "CUDA out of memory",
            },
        },
    )

    db_session.expire_all()
    persisted = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert persisted is not None
    assert persisted.status == QueueStatus.oom
    assert persisted.completed_at is not None
    assert persisted.error_message == "CUDA out of memory"
    assert persisted.websocket_events[-1]["is_runtime_failure_candidate"] is True
    assert persisted.recovery_metadata["gpu_lease_released_at"]
    assert persisted_lease is not None
    assert persisted_lease.status == "released"
