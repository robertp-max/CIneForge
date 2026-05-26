from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import AuditLog, ComfyJob, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.services.queue.service import QueueService


POSTGRES_URL_ENV = "CINEFORGE_TEST_POSTGRES_URL"


def _skip_without_postgres_url() -> str:
    url = os.environ.get(POSTGRES_URL_ENV)
    if not url:
        pytest.skip(f"{POSTGRES_URL_ENV} is not configured")
    return url


@pytest.fixture()
def postgres_session_factory():
    postgres_url = _skip_without_postgres_url()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")

    engine = create_engine(postgres_url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    _clear_queue_tables(engine)
    try:
        yield SessionLocal
    finally:
        _clear_queue_tables(engine)
        engine.dispose()


def _clear_queue_tables(engine) -> None:
    with engine.begin() as connection:
        connection.execute(delete(AuditLog))
        connection.execute(delete(ComfyJob))
        connection.execute(delete(WorkflowRun))
        connection.execute(delete(WorkflowTemplate))


def _create_comfy_job(db: Session, status: QueueStatus = QueueStatus.pending) -> ComfyJob:
    template = WorkflowTemplate(
        name=f"postgres-claim-template-{uuid4()}",
        version="1",
        workflow_api_json={"nodes": []},
        manifest_json={"name": "postgres-claim-template"},
        sha256=f"test-sha256-{uuid4()}",
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


def test_postgres_concurrent_reservation_claims_job_once(postgres_session_factory):
    with postgres_session_factory() as setup_session:
        job = _create_comfy_job(setup_session)

    def claim(worker_id: str):
        with postgres_session_factory() as db:
            claimed_job = QueueService().claim_next_pending_job(db, worker_id, "concurrent claim")
            return None if claimed_job is None else (claimed_job.id, claimed_job.worker_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, ["worker-1", "worker-2"]))

    claimed_results = [result for result in results if result is not None]
    assert len(claimed_results) == 1
    assert claimed_results[0][0] == job.id
    assert claimed_results[0][1] in {"worker-1", "worker-2"}

    with postgres_session_factory() as verify_session:
        persisted_job = verify_session.get(ComfyJob, job.id)
        logs = verify_session.query(AuditLog).all()

    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.reserved
    assert persisted_job.worker_id in {"worker-1", "worker-2"}
    assert persisted_job.attempt_count == 1
    assert len(logs) == 1
    assert logs[0].action == "worker_claim"
