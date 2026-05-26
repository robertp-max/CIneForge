from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base, ComfyJob, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.db.session import get_db
from backend.app.main import app


@pytest.fixture
def db_client(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    db_path = tmp_path / "cineforge_jobs_test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_comfy_job(db: Session) -> ComfyJob:
    template = WorkflowTemplate(
        name="offline-test-template",
        version="1",
        workflow_api_json={"nodes": []},
        manifest_json={"name": "offline-test-template"},
        sha256="test-sha256",
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
        prompt_id="prompt-123",
        status=QueueStatus.running,
        error_message="waiting for progress",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_get_job_reads_comfy_job(db_client):
    client, SessionLocal = db_client
    with SessionLocal() as db:
        job = create_comfy_job(db)
        job_id = str(job.id)
        workflow_run_id = str(job.workflow_run_id)

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": job_id,
        "status": "running",
        "detail": "Job read from database.",
        "workflow_run_id": workflow_run_id,
        "comfy_prompt_id": "prompt-123",
        "error_message": "waiting for progress",
    }


def test_get_missing_job_returns_404(db_client):
    client, _SessionLocal = db_client

    response = client.get(f"/jobs/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."


def test_jobs_route_does_not_submit_to_comfyui(db_client, monkeypatch):
    client, SessionLocal = db_client
    with SessionLocal() as db:
        job = create_comfy_job(db)
        job_id = str(job.id)

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("GET /jobs must not submit prompts to ComfyUI")

    monkeypatch.setattr("backend.app.services.comfy.client.ComfyUIClient.submit_prompt", fail_if_called)

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
