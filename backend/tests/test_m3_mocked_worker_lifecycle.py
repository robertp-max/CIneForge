from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.db.base import Base, ComfyJob, FileOutput, GeneratedAsset, GpuResourceLease, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.schemas.voice import GpuLeaseAcquireRequest
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.comfy.progress_monitor import ComfyJobProgressRecorder
from backend.app.services.comfy.submission import ControlledComfySubmissionService, WorkerSubmissionContext
from backend.app.services.output_collector import OutputCollector
from backend.app.services.runtime.gpu_leases import acquire_lease
from backend.app.services.workflows.template_service import sha256_json


class FakePromptSubmissionAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str]] = []

    async def submit_prompt(self, prompt: dict[str, Any], client_id: str) -> dict[str, Any]:
        self.calls.append((prompt, client_id))
        return {"prompt_id": "prompt-1", "number": 1, "node_errors": {}}


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_path = tmp_path / "cineforge_m3_lifecycle_test.db"
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


def _ready_workflow() -> dict:
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 1}},
    }


def _ready_manifest_json(workflow: dict) -> dict:
    return {
        "template_id": "m3-lifecycle-template",
        "version": "1",
        "original_workflow_sha256": sha256_json(workflow),
        "comfyui_snapshot_ref": "test-object-info",
        "nodes": {
            "positive_prompt": {
                "node_id": "6",
                "class_type": "CLIPTextEncode",
                "input": "text",
                "runtime_parameter": "positive_prompt",
                "value_schema": {"type": "string"},
                "required": True,
            },
            "seed": {
                "node_id": "3",
                "class_type": "KSampler",
                "input": "seed",
                "runtime_parameter": "seed",
                "value_schema": {"type": "integer"},
                "required": True,
            },
        },
    }


def _ready_object_info() -> dict:
    return {
        "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}}},
        "KSampler": {"input": {"required": {"seed": ["INT", {}]}}},
    }


def create_reserved_job(db: Session, *, worker_id: str = "worker-1") -> ComfyJob:
    workflow = _ready_workflow()
    template = WorkflowTemplate(
        name=f"m3-lifecycle-template-{uuid4()}",
        version="1",
        workflow_api_json=workflow,
        manifest_json=_ready_manifest_json(workflow),
        sha256=sha256_json(workflow),
    )
    db.add(template)
    db.flush()
    workflow_run = WorkflowRun(
        workflow_template_id=template.id,
        patched_workflow_json=workflow,
        patch_payload_json={"inputs": {}},
        status="queued",
    )
    db.add(workflow_run)
    db.flush()
    job = ComfyJob(workflow_run_id=workflow_run.id, status=QueueStatus.reserved, worker_id=worker_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def acquire_job_lease(db: Session, job: ComfyJob, *, worker_id: str = "worker-1") -> GpuResourceLease:
    return acquire_lease(
        db,
        GpuLeaseAcquireRequest(
            resource_key="gpu0",
            exclusive_group="gpu-shared",
            workload_type="comfy_job",
            workload_id=str(job.id),
            owner="m3-lifecycle-test",
            worker_id=worker_id,
            ttl_seconds=300,
        ),
    )


@pytest.mark.asyncio
async def test_m3_mocked_worker_lifecycle_submits_tracks_collects_and_releases(tmp_path: Path, db_session):
    settings = Settings(
        storage_root=tmp_path / "storage",
        comfyui_output_root=tmp_path / "comfy-output",
        hardware_operator_enabled=False,
        queue_worker_enabled=True,
    )
    job = create_reserved_job(db_session)
    lease = acquire_job_lease(db_session, job)
    adapter = FakePromptSubmissionAdapter()

    submission = await ControlledComfySubmissionService(
        submission_adapter=adapter,
        settings=settings,
    ).submit_reserved_job(
        db_session,
        WorkerSubmissionContext(
            job_id=job.id,
            worker_id="worker-1",
            client_id="client-1",
            object_info_cache=ObjectInfoCacheService(_ready_object_info()),
            gpu_lease_id=lease.id,
        ),
    )

    assert submission.submitted is True
    assert adapter.calls == [(_ready_workflow(), "client-1")]
    ComfyJobProgressRecorder().record_event(
        db_session,
        job.id,
        "worker-1",
        {"type": "execution_start", "data": {"prompt_id": "prompt-1"}},
    )
    ComfyJobProgressRecorder().record_event(
        db_session,
        job.id,
        "worker-1",
        {"type": "executing", "data": {"prompt_id": "prompt-1", "node": None}},
    )

    output_dir = settings.comfyui_output_root / "Project_A"
    output_dir.mkdir(parents=True)
    (output_dir / "run_01_00001_.mp4").write_bytes(b"fake-video")

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
    assert [record.filename for record in records] == ["run_01_00001_.mp4"]
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.complete
    assert persisted_job.prompt_id == "prompt-1"
    assert persisted_job.completed_at is not None
    assert [event["kind"] for event in persisted_job.websocket_events] == ["execution_start", "executing"]
    assert workflow_run is not None
    assert workflow_run.status == QueueStatus.complete.value
    assert workflow_run.ended_at is not None
    assert persisted_lease is not None
    assert persisted_lease.status == "released"
    assert len(db_session.scalars(select(FileOutput)).all()) == 1
    assert len(db_session.scalars(select(GeneratedAsset)).all()) == 1
