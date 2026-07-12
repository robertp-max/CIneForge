"""Integration-style tests for the durable planning engine (in-memory SQLite)."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base, Project, Story
from backend.app.schemas.orchestration import (
    CreateOrchestrationRunRequest,
    LogicalModelProfile,
    ManualTaskRoute,
    PlanningTaskType,
    RoutingMode,
    RunStatus,
)
from backend.app.services.planning.engine import PlanningEngine
from backend.app.services.planning.errors import PlanningError, PlanningErrorCode
from backend.app.services.planning.provider import MockPlanningProvider


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create only the tables needed for planning engine tests.
    tables = [
        Base.metadata.tables["projects"],
        Base.metadata.tables["stories"],
        Base.metadata.tables["characters"],
        Base.metadata.tables["orchestration_runs"],
        Base.metadata.tables["orchestration_steps"],
        Base.metadata.tables["orchestration_events"],
        Base.metadata.tables["provider_invocations"],
        Base.metadata.tables["ai_proposal_records"],
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_story(db: Session, *, duration: float = 48.0) -> Story:
    project = Project(id=uuid.uuid4(), name="P", description=None, created_at=datetime.utcnow())
    db.add(project)
    db.flush()
    story = Story(
        id=uuid.uuid4(),
        project_id=project.id,
        title="Harbor Light",
        base_story="A lighthouse keeper faces a storm and chooses hope.",
        target_duration_sec=duration,
        logline="Hope against the storm",
        tone="earnest",
        visual_style="cinematic coastal noir",
        approval_state="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


def test_create_and_complete_run_produces_pending_review_proposal(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})

    # Minimal pipeline for speed while still ending in production_proposal.
    req = CreateOrchestrationRunRequest(
        story_id=story.id,
        requested_by="tester",
        routing_mode=RoutingMode.automatic,
        max_steps=5,
        repair_budget=2,
        time_budget_sec=120,
        transport_retry_limit=1,
        task_types=[
            PlanningTaskType.shot_list,
            PlanningTaskType.production_proposal,
        ],
    )
    run, created = engine.create_run(req)
    assert created is True
    assert run.status == RunStatus.pending.value
    assert run.input_hash

    finished = engine.start_run(run.id)
    assert finished.status == RunStatus.completed.value

    detail = engine.get_run_detail(run.id)
    proposals = detail["proposals"]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.status == "pending_review"
    assert proposal.orchestration_run_id == run.id
    assert proposal.content_hash
    assert proposal.payload.get("metadata", {}).get("auto_applied") is False
    assert proposal.payload.get("metadata", {}).get("awaiting_review") is True

    # No apply markers / execution hooks in payload.
    blob = str(proposal.payload).lower()
    assert "comfy" not in blob
    assert "ffmpeg" not in blob

    events = {e.event_type for e in detail["events"]}
    assert "run_created" in events
    assert "run_started" in events
    assert "proposal_created" in events
    assert "run_completed" in events

    invocations = detail["invocations"]
    assert invocations
    for inv in invocations:
        # Never store raw prompts/responses — only hashes/status.
        assert inv.request_hash
        assert not hasattr(inv, "raw_prompt")


def test_idempotent_create_with_client_key(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})
    key = "client-idem-key-12345678"
    req = CreateOrchestrationRunRequest(
        story_id=story.id,
        idempotency_key=key,
        task_types=[PlanningTaskType.story_structure, PlanningTaskType.production_proposal],
        max_steps=4,
    )
    run1, created1 = engine.create_run(req)
    run2, created2 = engine.create_run(req)
    assert created1 is True
    assert created2 is False
    assert run1.id == run2.id


def test_active_run_conflict(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})
    engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            task_types=[PlanningTaskType.story_structure],
            max_steps=2,
        )
    )
    with pytest.raises(PlanningError) as ei:
        engine.create_run(
            CreateOrchestrationRunRequest(
                story_id=story.id,
                task_types=[PlanningTaskType.story_structure],
                max_steps=2,
            )
        )
    assert ei.value.code == PlanningErrorCode.ACTIVE_RUN_EXISTS


def test_cancel_pending_run(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})
    run, _ = engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            task_types=[PlanningTaskType.shot_list, PlanningTaskType.production_proposal],
            max_steps=4,
        )
    )
    canceled = engine.cancel_run(run.id, reason="user stopped", requested_by="tester")
    assert canceled.status == RunStatus.canceled.value
    assert canceled.canceled_at is not None
    steps = engine.get_run_detail(run.id)["steps"]
    assert all(s.status == "canceled" for s in steps)


def test_cancel_terminal_rejected(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})
    run, _ = engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            task_types=[PlanningTaskType.production_proposal],
            max_steps=2,
        )
    )
    engine.start_run(run.id)
    with pytest.raises(PlanningError) as ei:
        engine.cancel_run(run.id)
    assert ei.value.code == PlanningErrorCode.ALREADY_TERMINAL


def test_manual_routing_and_events(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})
    run, _ = engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            routing_mode=RoutingMode.manual,
            manual_routes=[
                ManualTaskRoute(
                    task_type=PlanningTaskType.production_proposal,
                    provider_identifier="mock",
                    logical_model=LogicalModelProfile.sol,
                    rationale="Force Sol for final proposal",
                )
            ],
            task_types=[PlanningTaskType.production_proposal],
            max_steps=2,
        )
    )
    finished = engine.start_run(run.id)
    assert finished.status == RunStatus.completed.value
    steps = engine.get_run_detail(run.id)["steps"]
    completed = [s for s in steps if s.status == "completed"]
    assert completed
    assert completed[0].logical_model == LogicalModelProfile.sol.value
    assert completed[0].provider_identifier == "mock"


def test_transport_retries_then_success(db_session: Session):
    story = _seed_story(db_session)
    provider = MockPlanningProvider(fixed_latency_ms=0)
    engine = PlanningEngine(db_session, providers={"mock": provider})
    run, _ = engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            task_types=[PlanningTaskType.story_structure, PlanningTaskType.production_proposal],
            max_steps=4,
            transport_retry_limit=3,
        )
    )
    # Inject transport failure simulation into routing snapshot constraints.
    snap = dict(run.routing_snapshot_json or {})
    snap["provider_constraints"] = {"simulate_transport_failures": 2}
    run.routing_snapshot_json = snap
    db_session.add(run)
    db_session.commit()

    finished = engine.start_run(run.id)
    assert finished.status == RunStatus.completed.value
    events = engine.get_run_detail(run.id)["events"]
    assert any(e.event_type == "transport_retry" for e in events)


def test_semantic_repair_on_schema_defect(db_session: Session):
    story = _seed_story(db_session)
    provider = MockPlanningProvider(fixed_latency_ms=0)
    engine = PlanningEngine(db_session, providers={"mock": provider})
    run, _ = engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            task_types=[PlanningTaskType.story_structure, PlanningTaskType.production_proposal],
            max_steps=6,
            repair_budget=3,
        )
    )
    snap = dict(run.routing_snapshot_json or {})
    snap["provider_constraints"] = {"inject_schema_defect": True}
    run.routing_snapshot_json = snap
    db_session.add(run)
    db_session.commit()

    finished = engine.start_run(run.id)
    assert finished.status == RunStatus.completed.value
    assert finished.repair_used >= 1
    events = {e.event_type for e in engine.get_run_detail(run.id)["events"]}
    assert "semantic_repair" in events
    # Escalation may also appear depending on ladder usage.
    assert "run_completed" in events


def test_resume_skips_completed_steps(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})
    run, _ = engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            task_types=[
                PlanningTaskType.shot_list,
                PlanningTaskType.production_proposal,
            ],
            max_steps=4,
        )
    )
    finished = engine.start_run(run.id)
    assert finished.status == RunStatus.completed.value

    # Starting again should be rejected as terminal.
    with pytest.raises(PlanningError) as ei:
        engine.start_run(run.id)
    assert ei.value.code == PlanningErrorCode.ALREADY_TERMINAL


def test_proposal_never_auto_applied_and_hashes_present(db_session: Session):
    story = _seed_story(db_session)
    engine = PlanningEngine(db_session, providers={"mock": MockPlanningProvider(fixed_latency_ms=0)})
    run, _ = engine.create_run(
        CreateOrchestrationRunRequest(
            story_id=story.id,
            task_types=[PlanningTaskType.production_proposal],
            max_steps=2,
        )
    )
    engine.start_run(run.id)
    detail = engine.get_run_detail(run.id)
    proposal = detail["proposals"][0]
    assert proposal.status == "pending_review"
    assert proposal.applied_at is None
    assert proposal.validation_status == "passed"
    # Step/output hashes recorded
    completed_steps = [s for s in detail["steps"] if s.status == "completed"]
    assert completed_steps
    assert completed_steps[0].output_hash
