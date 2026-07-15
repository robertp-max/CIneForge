from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.core.errors import ValidationError
from backend.app.db.base import Base, ComfyJob, FileOutput, GeneratedAsset, GpuResourceLease, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.schemas.voice import GpuLeaseAcquireRequest
from backend.app.services.output_collector import OutputCollector
from backend.app.services.queue.service import QueueService
from backend.app.services.runtime.gpu_leases import acquire_lease


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_path = tmp_path / "cineforge_output_collector_test.db"
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


def create_collecting_job(db: Session, *, worker_id: str = "worker-1") -> ComfyJob:
    template = WorkflowTemplate(
        name=f"collector-template-{uuid4()}",
        version="1",
        workflow_api_json={"nodes": []},
        manifest_json={"name": "collector-template"},
        sha256=f"collector-sha-{uuid4()}",
    )
    db.add(template)
    db.flush()
    workflow_run = WorkflowRun(
        workflow_template_id=template.id,
        patched_workflow_json={"nodes": []},
        patch_payload_json={"inputs": {}},
        status="collecting_outputs",
    )
    db.add(workflow_run)
    db.flush()
    job = ComfyJob(
        workflow_run_id=workflow_run.id,
        status=QueueStatus.collecting_outputs,
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
            owner="output-collector-test",
            worker_id=worker_id,
            ttl_seconds=300,
        ),
    )
    QueueService().bind_gpu_lease(db, job.id, lease.id, "collector test lease", worker_id=worker_id)
    return lease


def test_output_collector_discovers_persists_completes_and_releases_lease(tmp_path: Path, db_session):
    output_root = tmp_path / "comfy-output"
    project_dir = output_root / "Project_A"
    project_dir.mkdir(parents=True)
    output_file = project_dir / "run_01_00001_.mp4"
    output_file.write_bytes(b"fake-video-bytes")
    settings = Settings(comfyui_output_root=output_root, storage_root=tmp_path / "storage")
    job = create_collecting_job(db_session)
    lease = bind_lease(db_session, job)

    records = OutputCollector(settings).collect_for_job(
        db_session,
        job.id,
        "Project A",
        "run 01",
        worker_id="worker-1",
        probe=False,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    workflow_run = db_session.get(WorkflowRun, job.workflow_run_id)
    file_outputs = list(db_session.scalars(select(FileOutput)).all())
    assets = list(db_session.scalars(select(GeneratedAsset)).all())

    assert [record.filename for record in records] == ["run_01_00001_.mp4"]
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.complete
    assert persisted_job.completed_at is not None
    assert workflow_run is not None
    assert workflow_run.status == QueueStatus.complete.value
    assert workflow_run.ended_at is not None
    assert persisted_lease is not None
    assert persisted_lease.status == "released"
    assert len(file_outputs) == 1
    assert file_outputs[0].filename_prefix == "Project_A/run_01"
    assert file_outputs[0].filename == "run_01_00001_.mp4"
    assert file_outputs[0].type == "video"
    assert len(assets) == 1
    assert assets[0].kind == "video"
    assert assets[0].sha256 == records[0].sha256


def test_output_collector_missing_outputs_marks_postprocess_failed_and_releases_lease(tmp_path: Path, db_session):
    settings = Settings(comfyui_output_root=tmp_path / "comfy-output", storage_root=tmp_path / "storage")
    job = create_collecting_job(db_session)
    lease = bind_lease(db_session, job)

    records = OutputCollector(settings).collect_for_job(
        db_session,
        job.id,
        "Project A",
        "run 01",
        worker_id="worker-1",
        probe=False,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    persisted_lease = db_session.get(GpuResourceLease, lease.id)
    assert records == []
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.postprocess_failed
    assert "No managed ComfyUI outputs" in (persisted_job.error_message or "")
    assert persisted_lease is not None
    assert persisted_lease.status == "released"
    assert list(db_session.scalars(select(FileOutput)).all()) == []
    assert list(db_session.scalars(select(GeneratedAsset)).all()) == []


def test_output_collector_rejects_wrong_job_state(tmp_path: Path, db_session):
    settings = Settings(comfyui_output_root=tmp_path / "comfy-output", storage_root=tmp_path / "storage")
    job = create_collecting_job(db_session)
    job.status = QueueStatus.running
    db_session.commit()

    with pytest.raises(ValidationError, match="collecting_outputs"):
        OutputCollector(settings).collect_for_job(db_session, job.id, "Project A", "run 01", probe=False)
