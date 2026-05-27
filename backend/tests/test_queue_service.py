import copy
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import AuditLog, Base, ComfyJob, QueueStatus, WorkflowRun, WorkflowTemplate
from backend.app.queue.state_machine import InvalidTransition, JobState
from backend.app.services.ai_orchestration.schemas import AIProposal
from backend.app.services.ai_orchestration.validator import ProposalValidator
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.queue.service import QueueJobNotFound, QueueService
from backend.app.services.workflows.template_service import sha256_json


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


def _ready_workflow() -> dict:
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 1}},
    }


def _ready_manifest_json(workflow: dict) -> dict:
    return {
        "template_id": "submission-readiness-template",
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


def create_ready_comfy_job(
    db: Session,
    *,
    status: QueueStatus = QueueStatus.reserved,
    worker_id: str = "worker-1",
    prompt_id: str | None = None,
    workflow: dict | None = None,
    patched_workflow: dict | None = None,
    manifest_json: dict | None = None,
) -> ComfyJob:
    workflow = workflow or _ready_workflow()
    patched_workflow = patched_workflow or workflow
    template = WorkflowTemplate(
        name=f"readiness-test-template-{uuid4()}",
        version="1",
        workflow_api_json=workflow,
        manifest_json=manifest_json if manifest_json is not None else _ready_manifest_json(workflow),
        sha256=sha256_json(workflow),
    )
    db.add(template)
    db.flush()

    workflow_run = WorkflowRun(
        workflow_template_id=template.id,
        patched_workflow_json=patched_workflow,
        patch_payload_json={"inputs": {}},
        status="queued",
    )
    db.add(workflow_run)
    db.flush()

    job = ComfyJob(
        workflow_run_id=workflow_run.id,
        status=status,
        worker_id=worker_id,
        prompt_id=prompt_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def audit_logs(db: Session) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog)).all())


def audit_logs_for_action(db: Session, action: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)).all())


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


def test_heartbeat_succeeds_for_correct_worker_on_reserved_job(db_session):
    job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "claim for heartbeat")
    db_session.expire_all()
    reserved_job = db_session.get(ComfyJob, job.id)
    assert reserved_job is not None
    previous_heartbeat_at = reserved_job.heartbeat_at

    heartbeat_job = QueueService().heartbeat_job(db_session, job.id, "worker-1")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    heartbeat_logs = audit_logs_for_action(db_session, "worker_heartbeat")
    assert heartbeat_job is not None
    assert persisted_job is not None
    assert persisted_job.heartbeat_at is not None
    assert persisted_job.heartbeat_at != previous_heartbeat_at
    assert persisted_job.status == QueueStatus.reserved
    assert len(heartbeat_logs) == 1
    assert heartbeat_logs[0].details["worker_id"] == "worker-1"


def test_heartbeat_noops_for_wrong_worker(db_session):
    job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "claim for heartbeat")
    db_session.expire_all()
    reserved_job = db_session.get(ComfyJob, job.id)
    assert reserved_job is not None
    previous_heartbeat_at = reserved_job.heartbeat_at

    heartbeat_job = QueueService().heartbeat_job(db_session, job.id, "worker-2")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert heartbeat_job is None
    assert persisted_job is not None
    assert persisted_job.heartbeat_at == previous_heartbeat_at
    assert audit_logs_for_action(db_session, "worker_heartbeat") == []


def test_heartbeat_wrong_worker_noop_does_not_commit_unrelated_pending_changes(db_session):
    job = create_comfy_job(db_session)
    unrelated_job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "claim for heartbeat")
    unrelated_job.error_message = "uncommitted unrelated change"

    heartbeat_job = QueueService().heartbeat_job(db_session, job.id, "worker-2")
    db_session.rollback()

    persisted_unrelated_job = db_session.get(ComfyJob, unrelated_job.id)
    assert heartbeat_job is None
    assert persisted_unrelated_job is not None
    assert persisted_unrelated_job.error_message is None


@pytest.mark.parametrize(
    "status",
    [
        QueueStatus.pending,
        QueueStatus.validating,
        QueueStatus.complete,
        QueueStatus.runtime_failed,
        QueueStatus.canceled,
    ],
)
def test_heartbeat_ignores_completed_failed_and_canceled_jobs(db_session, status):
    job = create_comfy_job(db_session, status)
    job.worker_id = "worker-1"
    job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()
    db_session.refresh(job)
    previous_heartbeat_at = job.heartbeat_at

    heartbeat_job = QueueService().heartbeat_job(db_session, job.id, "worker-1")

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert heartbeat_job is None
    assert persisted_job is not None
    assert persisted_job.heartbeat_at == previous_heartbeat_at
    assert audit_logs_for_action(db_session, "worker_heartbeat") == []


@pytest.mark.parametrize(
    "status",
    [
        QueueStatus.pending,
        QueueStatus.validating,
        QueueStatus.complete,
        QueueStatus.runtime_failed,
        QueueStatus.canceled,
    ],
)
def test_heartbeat_non_reserved_noop_does_not_commit_unrelated_pending_changes(db_session, status):
    job = create_comfy_job(db_session, status)
    unrelated_job = create_comfy_job(db_session)
    job.worker_id = "worker-1"
    db_session.commit()
    unrelated_job.error_message = "uncommitted unrelated change"

    heartbeat_job = QueueService().heartbeat_job(db_session, job.id, "worker-1")
    db_session.rollback()

    persisted_unrelated_job = db_session.get(ComfyJob, unrelated_job.id)
    assert heartbeat_job is None
    assert persisted_unrelated_job is not None
    assert persisted_unrelated_job.error_message is None


def test_stale_reserved_job_below_max_attempts_resets_to_pending(db_session):
    job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "claim before stale recovery")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    job.reserved_at = stale_time
    job.heartbeat_at = stale_time
    db_session.commit()

    recovered_jobs = QueueService().recover_stale_reserved_jobs(
        db_session,
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        max_attempts=3,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    recovery_logs = audit_logs_for_action(db_session, "worker_recovery")
    assert [recovered_job.id for recovered_job in recovered_jobs] == [job.id]
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.pending
    assert persisted_job.worker_id is None
    assert persisted_job.reserved_at is None
    assert persisted_job.heartbeat_at is None
    assert persisted_job.last_state_change_at is not None
    assert persisted_job.recovery_metadata["previous_worker_id"] == "worker-1"
    assert persisted_job.recovery_metadata["recovery_count"] == 1
    assert len(recovery_logs) == 1
    assert recovery_logs[0].details["new_state"] == "pending"


def test_fresh_reserved_job_is_not_recovered(db_session):
    job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "fresh claim")

    recovered_jobs = QueueService().recover_stale_reserved_jobs(
        db_session,
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        max_attempts=3,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert recovered_jobs == []
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.reserved
    assert persisted_job.worker_id == "worker-1"
    assert audit_logs_for_action(db_session, "worker_recovery") == []
    assert audit_logs_for_action(db_session, "worker_timeout") == []


def test_non_reserved_job_is_not_recovered(db_session):
    job = create_comfy_job(db_session, QueueStatus.submitted)
    job.worker_id = "worker-1"
    job.reserved_at = datetime.now(UTC) - timedelta(hours=2)
    job.heartbeat_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.commit()

    recovered_jobs = QueueService().recover_stale_reserved_jobs(
        db_session,
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        max_attempts=3,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert recovered_jobs == []
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.submitted
    assert persisted_job.worker_id == "worker-1"


def test_stale_reserved_job_at_max_attempts_becomes_timeout(db_session):
    job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "claim before timeout")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    job.reserved_at = stale_time
    job.heartbeat_at = stale_time
    job.attempt_count = 3
    db_session.commit()

    recovered_jobs = QueueService().recover_stale_reserved_jobs(
        db_session,
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        max_attempts=3,
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    timeout_logs = audit_logs_for_action(db_session, "worker_timeout")
    assert [recovered_job.id for recovered_job in recovered_jobs] == [job.id]
    assert persisted_job is not None
    assert persisted_job.status == QueueStatus.timeout
    assert persisted_job.worker_id is None
    assert persisted_job.recovery_metadata["new_state"] == "timeout"
    assert persisted_job.recovery_metadata["attempt_count"] == 3
    assert len(timeout_logs) == 1
    assert timeout_logs[0].details["new_state"] == "timeout"


def test_recovery_metadata_count_increments(db_session):
    job = create_comfy_job(db_session)
    QueueService().reserve_job(db_session, job.id, "worker-1", "claim before stale recovery")
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    job.reserved_at = stale_time
    job.heartbeat_at = stale_time
    job.recovery_metadata = {"recovery_count": 2}
    db_session.commit()

    QueueService().recover_stale_reserved_jobs(
        db_session,
        stale_before=datetime.now(UTC) - timedelta(hours=1),
        max_attempts=3,
        reason="test recovery metadata",
    )

    db_session.expire_all()
    persisted_job = db_session.get(ComfyJob, job.id)
    assert persisted_job is not None
    assert persisted_job.recovery_metadata["recovery_count"] == 3
    assert persisted_job.recovery_metadata["last_recovery_reason"] == "test recovery metadata"


def test_submission_readiness_rejects_missing_job(db_session):
    result = QueueService().evaluate_submission_readiness(
        db_session,
        uuid4(),
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert result.code == "job_not_found"
    assert result.worker_id == "worker-1"
    assert result.checked_at is not None


def test_submission_readiness_rejects_non_reserved_job(db_session):
    job = create_ready_comfy_job(db_session, status=QueueStatus.pending, worker_id=None)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert result.code == "preflight_failed"
    assert any("status must be reserved" in error for error in result.errors)


def test_submission_readiness_rejects_wrong_worker(db_session):
    job = create_ready_comfy_job(db_session, worker_id="worker-1")

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-2",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert any("requesting worker" in error for error in result.errors)


def test_submission_readiness_rejects_already_submitted_prompt_id(db_session):
    job = create_ready_comfy_job(db_session, prompt_id="prompt-123")

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert any("prompt_id" in error for error in result.errors)


def test_submission_readiness_rejects_missing_workflow_run(db_session):
    job = ComfyJob(
        workflow_run_id=uuid4(),
        status=QueueStatus.reserved,
        worker_id="worker-1",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert any("WorkflowRun not found" in error for error in result.errors)


def test_submission_readiness_rejects_missing_workflow_snapshot(db_session):
    job = create_ready_comfy_job(db_session)
    workflow_run = db_session.get(WorkflowRun, job.workflow_run_id)
    assert workflow_run is not None
    workflow_run.patched_workflow_json = {}
    db_session.commit()

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert any("patched_workflow_json" in error for error in result.errors)


def test_submission_readiness_rejects_missing_object_info(db_session):
    job = create_ready_comfy_job(db_session)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(),
    )

    assert not result.ready
    assert any("Object info compatibility check failed" in error for error in result.errors)


def test_submission_readiness_rejects_incompatible_object_info(db_session):
    job = create_ready_comfy_job(db_session)
    object_info = _ready_object_info()
    object_info.pop("KSampler")

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(object_info),
    )

    assert not result.ready
    assert any("missing class KSampler" in error for error in result.errors)


def test_submission_readiness_accepts_reserved_worker_owned_job(db_session):
    job = create_ready_comfy_job(db_session)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert result.ready
    assert result.job_id == job.id
    assert result.worker_id == "worker-1"
    assert result.code == "ready"
    assert result.errors == []


def test_readiness_accepts_patched_workflow_with_different_sha(db_session):
    original_workflow = _ready_workflow()
    patched_workflow = copy.deepcopy(original_workflow)
    patched_workflow["6"]["inputs"]["text"] = "patched prompt"
    patched_workflow["3"]["inputs"]["seed"] = 12345
    assert sha256_json(patched_workflow) != sha256_json(original_workflow)
    job = create_ready_comfy_job(
        db_session,
        workflow=original_workflow,
        patched_workflow=patched_workflow,
    )

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert result.ready
    assert result.code == "ready"
    assert result.errors == []


def test_readiness_rejects_patched_workflow_missing_required_node(db_session):
    patched_workflow = copy.deepcopy(_ready_workflow())
    patched_workflow.pop("3")
    job = create_ready_comfy_job(db_session, patched_workflow=patched_workflow)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert any("Missing workflow node for seed" in error for error in result.errors)


def test_readiness_rejects_patched_workflow_class_type_mismatch(db_session):
    patched_workflow = copy.deepcopy(_ready_workflow())
    patched_workflow["6"]["class_type"] = "WrongNode"
    job = create_ready_comfy_job(db_session, patched_workflow=patched_workflow)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert any("Class type mismatch for positive_prompt" in error for error in result.errors)


def test_readiness_rejects_patched_workflow_missing_required_input(db_session):
    patched_workflow = copy.deepcopy(_ready_workflow())
    patched_workflow["6"]["inputs"].pop("text")
    job = create_ready_comfy_job(db_session, patched_workflow=patched_workflow)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(_ready_object_info()),
    )

    assert not result.ready
    assert any("Missing input text for positive_prompt" in error for error in result.errors)


@pytest.mark.parametrize("missing_object_info", ["class", "input"])
def test_readiness_rejects_when_object_info_missing_required_class_or_input(db_session, missing_object_info):
    object_info = _ready_object_info()
    if missing_object_info == "class":
        object_info.pop("KSampler")
        expected_error = "Object info missing class KSampler"
    else:
        object_info["CLIPTextEncode"]["input"]["required"].pop("text")
        expected_error = "Object info class CLIPTextEncode missing input text"
    job = create_ready_comfy_job(db_session)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        ObjectInfoCacheService(object_info),
    )

    assert not result.ready
    assert any(expected_error in error for error in result.errors)


def test_submission_readiness_fails_closed_on_object_info_failure(db_session):
    class FailingObjectInfoCache(ObjectInfoCacheService):
        def validate_patched_workflow_manifest(self, workflow: dict, manifest) -> None:
            raise RuntimeError("object_info unavailable")

    job = create_ready_comfy_job(db_session)

    result = QueueService().evaluate_submission_readiness(
        db_session,
        job.id,
        "worker-1",
        FailingObjectInfoCache(_ready_object_info()),
    )

    assert not result.ready
    assert any("object_info unavailable" in error for error in result.errors)


def test_ai_proposal_cannot_request_queue_mutation():
    proposal = AIProposal(
        proposal_type="retry_failed_shot",
        summary="bad",
        payload={"queue_mutation": {"to": "running"}},
    )

    result = ProposalValidator().validate(proposal)

    assert not result.accepted
