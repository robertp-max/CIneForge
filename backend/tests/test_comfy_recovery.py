from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base, ComfyJob, GpuResourceLease, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.schemas.voice import GpuLeaseAcquireRequest
from backend.app.services.comfy.recovery import ComfyRuntimeRecoveryService
from backend.app.services.queue.service import QueueService
from backend.app.services.runtime.gpu_leases import acquire_lease


class FakeSupervisor:
    def __init__(self, health_status: str = "ok") -> None:
        self.health_status = health_status
        self.calls: list[tuple[str, str | None]] = []

    def terminate_process_tree(self, reason: str) -> dict:
        self.calls.append(("terminate", reason))
        return {"terminated": True, "reason": reason}

    def restart_pinned_runtime(self) -> dict:
        self.calls.append(("restart", None))
        return {"started": True}

    def health_check(self) -> dict:
        self.calls.append(("health", None))
        return {"status": self.health_status}


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_path = tmp_path / "cineforge_comfy_recovery_test.db"
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


def create_running_job(db: Session, *, worker_id: str = "worker-1") -> ComfyJob:
    template = WorkflowTemplate(
        name=f"recovery-template-{uuid4()}",
        version="1",
        workflow_api_json={"nodes": []},
        manifest_json={"name": "recovery-template"},
        sha256=f"recovery-sha-{uuid4()}",
    )
    db.add(template)
    db.flush()
    workflow_run = WorkflowRun(
        workflow_template_id=template.id,
        patched_workflow_json={"nodes": []},
        patch_payload_json={"inputs": {}},
        status="running",
    )
    db.add(workflow_run)
    db.flush()
    job = ComfyJob(
        workflow_run_id=workflow_run.id,
        status=QueueStatus.running,
        worker_id=worker_id,
        prompt_id="prompt-1",
        recovery_metadata={},
    )
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
            owner="recovery-test",
            worker_id=worker_id,
            ttl_seconds=300,
        ),
    )
    QueueService().bind_gpu_lease(db, job.id, lease.id, "recovery test lease", worker_id=worker_id)
    return lease


def test_runtime_recovery_marks_terminal_releases_lease_and_runs_supervisor(db_session):
    job = create_running_job(db_session)
    lease = bind_lease(db_session, job)
    supervisor = FakeSupervisor()

    result = ComfyRuntimeRecoveryService().recover_failed_runtime(
        db_session,
        job.id,
        "worker-1",
        supervisor,
        reason="runtime process crashed",
        terminal_status=QueueStatus.runtime_failed,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    workflow_run = db_session.get(WorkflowRun, job.workflow_run_id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert result.recovered is True
    assert result.terminal_status == QueueStatus.runtime_failed.value
    assert supervisor.calls == [("terminate", "runtime process crashed"), ("restart", None), ("health", None)]
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.runtime_failed
    assert persisted_job.completed_at is not None
    assert persisted_job.error_message == "runtime process crashed"
    assert workflow_run is not None
    assert workflow_run.status == QueueStatus.runtime_failed.value
    assert workflow_run.ended_at is not None
    assert persisted_lease is not None
    assert persisted_lease.status == "released"


def test_runtime_recovery_reports_failed_health_without_overclaiming(db_session):
    job = create_running_job(db_session)
    bind_lease(db_session, job)
    supervisor = FakeSupervisor(health_status="unavailable")

    result = ComfyRuntimeRecoveryService().recover_failed_runtime(
        db_session,
        job.id,
        "worker-1",
        supervisor,
        reason="oom recovery",
        terminal_status=QueueStatus.oom,
    )

    assert result.recovered is False
    assert result.health_ok is False
    assert result.health == {"status": "unavailable"}


def test_runtime_recovery_rejects_non_runtime_terminal_status(db_session):
    job = create_running_job(db_session)
    bind_lease(db_session, job)

    with pytest.raises(ValueError, match="Unsupported"):
        ComfyRuntimeRecoveryService().recover_failed_runtime(
            db_session,
            job.id,
            "worker-1",
            FakeSupervisor(),
            reason="not a runtime recovery",
            terminal_status=QueueStatus.canceled,
        )
