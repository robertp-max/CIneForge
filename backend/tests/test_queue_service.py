from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import AuditLog, Base, ComfyJob, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.queue.state_machine import InvalidTransition, JobState
from backend.app.services.ai_orchestration.schemas import AIProposal
from backend.app.services.ai_orchestration.validator import ProposalValidator
from backend.app.services.queue.service import QueueJobNotFound, QueueService


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_path = tmp_path / "cineforge_queue_service_test.db"
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
        name=f"queue-test-template-{uuid4()}",
        version="1",
        workflow_api_json={"nodes": []},
        manifest_json={"name": "queue-test-template"},
        sha256="test-sha256",
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


def test_queue_service_valid_transition_persists_status(db_session):
    job = create_comfy_job(db_session)

    QueueService().transition_job(db_session, job.id, JobState.reserved, "worker reservation")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.reserved


def test_queue_service_invalid_transition_rolls_back(db_session):
    job = create_comfy_job(db_session)

    with pytest.raises(InvalidTransition):
        QueueService().transition_job(db_session, job.id, JobState.complete, "cannot skip lifecycle")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.pending
    assert audit_logs(db_session) == []


def test_queue_transition_writes_audit_log(db_session):
    job = create_comfy_job(db_session)

    QueueService().transition_job(
        db_session,
        job.id,
        QueueStatus.reserved,
        "worker reservation",
        actor="test-suite",
    )

    logs = audit_logs(db_session)
    assert len(logs) == 1
    assert logs[0].entity_type == "comfy_job"
    assert logs[0].entity_id == job.id
    assert logs[0].action == "queue_transition"
    assert logs[0].details == {
        "previous_state": "pending",
        "new_state": "reserved",
        "reason": "worker reservation",
        "actor": "test-suite",
    }


def test_reserve_job_persists_reserved_status(db_session):
    job = create_comfy_job(db_session)

    QueueService().reserve_job(db_session, job.id, "worker-1", "claim for validation")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    logs = audit_logs(db_session)

    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.reserved
    assert len(logs) == 1
    assert logs[0].details["worker_id"] == "worker-1"


def test_reserve_job_writes_worker_ownership_fields(db_session):
    job = create_comfy_job(db_session)

    QueueService().reserve_job(db_session, job.id, "worker-1", "claim for validation")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)

    assert persisted_job is not None
    assert persisted_job.worker_id == "worker-1"
    assert persisted_job.reserved_at is not None
    assert persisted_job.heartbeat_at is not None
    assert persisted_job.attempt_count == 1
    assert persisted_job.last_state_change_at is not None
    assert persisted_job.recovery_metadata == {}


def test_reserve_next_job_skips_non_pending_jobs(db_session):
    create_comfy_job(db_session, QueueStatus.reserved)

    claimed_job = QueueService().claim_next_pending_job(db_session, "worker-1")

    assert claimed_job is None
    assert audit_logs(db_session) == []


def test_reserve_next_job_writes_worker_ownership(db_session):
    job = create_comfy_job(db_session)

    claimed_job = QueueService().claim_next_pending_job(db_session, "worker-1")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)

    assert claimed_job is not None
    assert claimed_job.id == job.id
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.reserved
    assert persisted_job.worker_id == "worker-1"
    assert persisted_job.reserved_at is not None
    assert persisted_job.heartbeat_at is not None
    assert persisted_job.attempt_count == 1
    assert persisted_job.last_state_change_at is not None
    assert persisted_job.recovery_metadata == {}


def test_reserve_next_job_writes_audit_log(db_session):
    job = create_comfy_job(db_session)

    QueueService().claim_next_pending_job(db_session, "worker-1", "claim for validation")

    logs = audit_logs(db_session)
    assert len(logs) == 1
    assert logs[0].entity_type == "comfy_job"
    assert logs[0].entity_id == job.id
    assert logs[0].action == "worker_claim"
    assert logs[0].details == {
        "previous_state": "pending",
        "new_state": "reserved",
        "reason": "claim for validation",
        "actor": "system",
        "worker_id": "worker-1",
        "attempt_count": 1,
    }


def test_reserve_next_job_returns_none_when_no_pending_jobs(db_session):
    claimed_job = QueueService().claim_next_pending_job(db_session, "worker-1")

    assert claimed_job is None
    assert audit_logs(db_session) == []


def test_queue_audit_details_include_worker_metadata_when_present(db_session):
    job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "claim for validation")
    db_session.expire_all()

    QueueService().transition_job(db_session, job.id, JobState.validating, "begin validation")

    logs = audit_logs(db_session)
    assert len(logs) == 2
    assert logs[1].details["worker_id"] == "worker-1"
    assert logs[1].details["previous_state"] == "reserved"
    assert logs[1].details["new_state"] == "validating"


def test_reserve_missing_job_raises_not_found(db_session):
    with pytest.raises(QueueJobNotFound):
        QueueService().reserve_job(db_session, uuid4(), "worker-1", "missing job")

    assert audit_logs(db_session) == []


def test_ai_proposal_cannot_request_queue_mutation():
    proposal = AIProposal(
        proposal_type="retry_failed_shot",
        summary="bad",
        payload={"queue_mutation": {"to": "running"}},
    )

    result = ProposalValidator().validate(proposal)

    assert not result.accepted
