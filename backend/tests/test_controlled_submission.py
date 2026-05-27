from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import AuditLog, Base, ComfyJob, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.main import app
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.comfy.submission import ControlledComfySubmissionService, WorkerSubmissionContext
from backend.app.services.queue.worker import QueueWorker
from backend.app.services.workflows.template_service import sha256_json


class FakePromptSubmissionAdapter:
    def __init__(self, response: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.response = response or {"prompt_id": "prompt-123", "number": 7, "node_errors": {}}
        self.error = error
        self.calls: list[tuple[dict[str, Any], str]] = []

    async def submit_prompt(self, prompt: dict[str, Any], client_id: str) -> dict[str, Any]:
        self.calls.append((prompt, client_id))
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_path = tmp_path / "cineforge_controlled_submission_test.db"
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


def _ready_workflow() -> dict:
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 1}},
    }


def _ready_manifest_json(workflow: dict) -> dict:
    return {
        "template_id": "controlled-submission-template",
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


def create_ready_reserved_job(
    db: Session,
    *,
    status: QueueStatus = QueueStatus.reserved,
    worker_id: str | None = "worker-1",
) -> ComfyJob:
    workflow = _ready_workflow()
    template = WorkflowTemplate(
        name=f"controlled-submission-template-{uuid4()}",
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

    job = ComfyJob(
        workflow_run_id=workflow_run.id,
        status=status,
        worker_id=worker_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def audit_logs_for_action(db: Session, action: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)).all())


@pytest.mark.asyncio
async def test_controlled_submission_submits_ready_worker_owned_job(db_session):
    job = create_ready_reserved_job(db_session)
    adapter = FakePromptSubmissionAdapter()
    service = ControlledComfySubmissionService(submission_adapter=adapter)

    result = await service.submit_reserved_job(
        db_session,
        WorkerSubmissionContext(
            job_id=job.id,
            worker_id="worker-1",
            client_id="client-1",
            object_info_cache=ObjectInfoCacheService(_ready_object_info()),
        ),
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert result.submitted is True
    assert result.prompt_id == "prompt-123"
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.submitted
    assert persisted_job.prompt_id == "prompt-123"
    assert persisted_job.queue_number == 7
    assert persisted_job.client_id == "client-1"
    assert persisted_job.submitted_at is not None
    assert persisted_job.completed_at is None
    assert adapter.calls == [(_ready_workflow(), "client-1")]
    assert len(audit_logs_for_action(db_session, "worker_prompt_submission")) == 1


@pytest.mark.asyncio
async def test_controlled_submission_requires_readiness_before_prompt_call(db_session):
    job = create_ready_reserved_job(db_session, status=QueueStatus.pending, worker_id=None)
    adapter = FakePromptSubmissionAdapter()
    service = ControlledComfySubmissionService(submission_adapter=adapter)

    result = await service.submit_reserved_job(
        db_session,
        WorkerSubmissionContext(
            job_id=job.id,
            worker_id="worker-1",
            client_id="client-1",
            object_info_cache=ObjectInfoCacheService(_ready_object_info()),
        ),
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert result.submitted is False
    assert result.code == "preflight_failed"
    assert adapter.calls == []
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.pending
    assert persisted_job.prompt_id is None
    assert persisted_job.completed_at is None


@pytest.mark.asyncio
async def test_controlled_submission_node_errors_do_not_false_success(db_session):
    job = create_ready_reserved_job(db_session)
    adapter = FakePromptSubmissionAdapter(response={"node_errors": {"3": "bad seed"}})
    service = ControlledComfySubmissionService(submission_adapter=adapter)

    result = await service.submit_reserved_job(
        db_session,
        WorkerSubmissionContext(
            job_id=job.id,
            worker_id="worker-1",
            client_id="client-1",
            object_info_cache=ObjectInfoCacheService(_ready_object_info()),
        ),
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert result.submitted is False
    assert result.code == "node_errors"
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.validation_failed
    assert persisted_job.prompt_id is None
    assert persisted_job.completed_at is None
    assert "node_errors" in (persisted_job.error_message or "")
    assert len(audit_logs_for_action(db_session, "worker_prompt_node_errors")) == 1


@pytest.mark.asyncio
async def test_controlled_submission_rejection_is_classified_safely(db_session):
    job = create_ready_reserved_job(db_session)
    adapter = FakePromptSubmissionAdapter(error=RuntimeError("comfy rejected prompt"))
    service = ControlledComfySubmissionService(submission_adapter=adapter)

    result = await service.submit_reserved_job(
        db_session,
        WorkerSubmissionContext(
            job_id=job.id,
            worker_id="worker-1",
            client_id="client-1",
            object_info_cache=ObjectInfoCacheService(_ready_object_info()),
        ),
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert result.submitted is False
    assert result.code == "comfy_rejected"
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.comfy_rejected
    assert persisted_job.prompt_id is None
    assert persisted_job.completed_at is None
    assert persisted_job.error_message == "comfy rejected prompt"
    assert len(audit_logs_for_action(db_session, "worker_prompt_rejected")) == 1


@pytest.mark.asyncio
async def test_worker_controlled_submission_once_is_approved_context(db_session):
    job = create_ready_reserved_job(db_session)
    adapter = FakePromptSubmissionAdapter()
    service = ControlledComfySubmissionService(submission_adapter=adapter)

    result = await QueueWorker("worker-1").controlled_submission_once(
        db_session,
        job.id,
        "client-1",
        ObjectInfoCacheService(_ready_object_info()),
        service,
    )

    assert result.submitted is True
    assert result.status == QueueStatus.submitted.value
    assert adapter.calls == [(_ready_workflow(), "client-1")]


def test_public_prompt_route_remains_unavailable():
    response = TestClient(app).post("/prompt", json={"prompt": {}, "client_id": "public"})

    assert response.status_code == 404
