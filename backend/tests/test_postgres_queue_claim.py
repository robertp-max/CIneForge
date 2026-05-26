from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, select
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


def _create_stale_reserved_job(db: Session, attempt_count: int = 1) -> ComfyJob:
    job = _create_comfy_job(db)
    QueueService().reserve_job(db, job.id, "worker-stale", "claim before stale recovery")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    job.reserved_at = stale_time
    job.heartbeat_at = stale_time
    job.attempt_count = attempt_count
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


def test_postgres_skip_locked_does_not_claim_locked_pending_job(postgres_session_factory):
    with postgres_session_factory() as setup_session:
        job = _create_comfy_job(setup_session)

    lock_session = postgres_session_factory()
    lock_transaction = lock_session.begin()
    try:
        locked_job = lock_session.scalars(
            select(ComfyJob)
            .where(ComfyJob.id == job.id, ComfyJob.status == QueueStatus.pending)
            .with_for_update()
        ).one()
        assert locked_job.id == job.id

        with postgres_session_factory() as competing_session:
            skipped_job = QueueService().claim_next_pending_job(
                competing_session,
                "worker-2",
                "skip locked claim",
            )

        assert skipped_job is None

        with postgres_session_factory() as verify_session:
            persisted_job = verify_session.get(ComfyJob, job.id)
            logs = verify_session.query(AuditLog).all()

        assert persisted_job is not None
        assert persisted_job.status == QueueStatus.pending
        assert persisted_job.worker_id is None
        assert logs == []
    finally:
        lock_transaction.rollback()
        lock_session.close()

    with postgres_session_factory() as claim_session:
        claimed_job = QueueService().claim_next_pending_job(
            claim_session,
            "worker-1",
            "claim after lock release",
        )

    assert claimed_job is not None
    assert claimed_job.id == job.id
    assert claimed_job.worker_id == "worker-1"


def test_postgres_concurrent_recovery_recovers_stale_reserved_job_once(postgres_session_factory):
    with postgres_session_factory() as setup_session:
        job = _create_stale_reserved_job(setup_session)

    def recover(reason: str):
        with postgres_session_factory() as db:
            recovered_jobs = QueueService().recover_stale_reserved_jobs(
                db,
                stale_before=datetime.now(UTC) - timedelta(hours=1),
                max_attempts=3,
                reason=reason,
            )
            return [recovered_job.id for recovered_job in recovered_jobs]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(recover, ["concurrent recovery 1", "concurrent recovery 2"]))

    recovered_results = [result for result in results if result]
    assert recovered_results == [[job.id]]

    with postgres_session_factory() as verify_session:
        persisted_job = verify_session.get(ComfyJob, job.id)
        recovery_logs = list(
            verify_session.scalars(
                select(AuditLog).where(
                    AuditLog.entity_id == job.id,
                    AuditLog.action == "worker_recovery",
                )
            ).all()
        )

    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.pending
    assert persisted_job.recovery_metadata["recovery_count"] == 1
    assert len(recovery_logs) == 1


def test_postgres_skip_locked_does_not_recover_locked_stale_reserved_job(postgres_session_factory):
    with postgres_session_factory() as setup_session:
        job = _create_stale_reserved_job(setup_session)

    lock_session = postgres_session_factory()
    lock_transaction = lock_session.begin()
    try:
        locked_job = lock_session.scalars(
            select(ComfyJob)
            .where(ComfyJob.id == job.id, ComfyJob.status == QueueStatus.reserved)
            .with_for_update()
        ).one()
        assert locked_job.id == job.id

        with postgres_session_factory() as competing_session:
            skipped_jobs = QueueService().recover_stale_reserved_jobs(
                competing_session,
                stale_before=datetime.now(UTC) - timedelta(hours=1),
                max_attempts=3,
                reason="skip locked stale recovery",
            )

        assert skipped_jobs == []

        with postgres_session_factory() as verify_session:
            persisted_job = verify_session.get(ComfyJob, job.id)
            recovery_logs = list(
                verify_session.scalars(
                    select(AuditLog).where(
                        AuditLog.entity_id == job.id,
                        AuditLog.action == "worker_recovery",
                    )
                ).all()
            )

        assert persisted_job is not None
        assert persisted_job.status == QueueStatus.reserved
        assert persisted_job.worker_id == "worker-stale"
        assert recovery_logs == []
    finally:
        lock_transaction.rollback()
        lock_session.close()

    with postgres_session_factory() as recovery_session:
        recovered_jobs = QueueService().recover_stale_reserved_jobs(
            recovery_session,
            stale_before=datetime.now(UTC) - timedelta(hours=1),
            max_attempts=3,
            reason="recover after lock release",
        )

    assert [recovered_job.id for recovered_job in recovered_jobs] == [job.id]

    with postgres_session_factory() as verify_session:
        persisted_job = verify_session.get(ComfyJob, job.id)
        recovery_logs = list(
            verify_session.scalars(
                select(AuditLog).where(
                    AuditLog.entity_id == job.id,
                    AuditLog.action == "worker_recovery",
                )
            ).all()
        )

    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.pending
    assert len(recovery_logs) == 1
