"""End-to-end acceptance coverage for the explicit Storyboard Phase-1 fixture."""

from __future__ import annotations

import copy
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    AIProposalRecord,
    AuditLog,
    Base,
    Chapter,
    Character,
    ComfyJob,
    FFmpegJob,
    ModelVariant,
    Project,
    ProjectStoryboardSettings,
    ProviderProfile,
    Scene,
    Shot,
    ShotCharacter,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
    Story,
    StoryboardVersion,
    TaskProviderAssignment,
    VoiceProfile,
    WorkflowRun,
)
from backend.app.db.session import enable_sqlite_foreign_keys
from backend.app.schemas.orchestration import (
    CreateOrchestrationRunRequest,
    RoutingMode,
    RunStatus,
)
from backend.app.schemas.proposals import (
    ProposalApplyRequest,
    ProposalCreateRequest,
    ProposalReviewRequest,
    StoryboardProposalPayload,
)
from backend.app.services import (
    proposal_apply,
    proposal_service,
    storyboard,
    storyboard_mutations,
    storyboard_snapshot as snapshot_service,
)
from backend.app.services.ai_orchestration.schemas import ProposalType
from backend.app.services.planning.engine import PlanningEngine
from backend.app.services.planning.provider import MockPlanningProvider
from backend.tests.fixtures.phase1_acceptance import (
    CHAPTER_DURATION_ROLLUPS,
    PHASE1_PLANNING_TASKS,
    SCENE_DURATION_ROLLUPS,
    TARGET_DURATION_SEC,
    build_phase1_acceptance_payload,
    seed_phase1_acceptance_fixture,
)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _count(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _canonical_shots(db: Session, story_id) -> list[Shot]:
    return list(
        db.scalars(
            select(Shot)
            .join(Scene, Shot.scene_id == Scene.id)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .where(Chapter.story_id == story_id)
            .order_by(Chapter.order_index, Scene.order_index, Shot.order_index)
        )
    )


def _task_outputs(detail: dict) -> dict[str, dict]:
    return {
        step.task_type: step.metadata_json["result_payload"]
        for step in detail["steps"]
        if step.status == "completed"
    }


def _proposal_without_run_id(record: AIProposalRecord) -> dict:
    payload = copy.deepcopy(record.payload)
    payload.pop("orchestration_run_id", None)
    return payload


def test_phase1_acceptance_fixture_contract_is_exact() -> None:
    parsed = StoryboardProposalPayload.model_validate(build_phase1_acceptance_payload())
    assert parsed.story.title == "A New Journey"
    assert parsed.story.target_duration_sec == TARGET_DURATION_SEC
    assert len(parsed.story.characters) == 4
    assert len(parsed.story.chapters) == 3

    scenes = [scene for chapter in parsed.story.chapters for scene in chapter.scenes]
    shots = [shot for scene in scenes for shot in scene.shots]
    assert len(scenes) == 6
    assert len(shots) == 27
    assert all(6.0 <= shot.duration_sec <= 12.0 for shot in shots)

    scene_rollups = tuple(sum(shot.duration_sec for shot in scene.shots) for scene in scenes)
    chapter_rollups = tuple(
        sum(shot.duration_sec for scene in chapter.scenes for shot in scene.shots)
        for chapter in parsed.story.chapters
    )
    assert scene_rollups == SCENE_DURATION_ROLLUPS
    assert chapter_rollups == CHAPTER_DURATION_ROLLUPS
    assert sum(chapter_rollups) == TARGET_DURATION_SEC

    character_ids = {character.client_id for character in parsed.story.characters}
    voice_ids = {voice.client_id for voice in parsed.story.voices}
    ordered_shot_ids = [shot.client_id for shot in shots]
    positions = {shot_id: index for index, shot_id in enumerate(ordered_shot_ids)}
    for index, shot in enumerate(shots):
        assert shot.characters
        assert all(link.character_client_id in character_ids for link in shot.characters)
        assert bool(shot.narration.narration_text) ^ bool(shot.narration.narration_exception_reason)
        if shot.narration.voice_client_id:
            assert shot.narration.voice_client_id in voice_ids
        assert shot.prompt_package.image_prompt or shot.prompt_package.video_prompt
        assert len(shot.model_recommendations) == 1
        recommendation = shot.model_recommendations[0]
        assert recommendation.recommends_qwen_voice is False
        assert recommendation.native_voice_capability == "supported"
        if index == 0:
            assert shot.continuity_source_shot_client_id is None
        else:
            source = shot.continuity_source_shot_client_id
            assert source in positions
            assert positions[source] < positions[shot.client_id]


def test_phase1_acceptance_apply_rolls_back_the_entire_graph(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = seed_phase1_acceptance_fixture(db_session)
    request = ProposalCreateRequest(
        proposal_type=ProposalType.storyboard_full_plan.value,
        summary="Rollback proof for the explicit Phase-1 fixture.",
        payload=fixture.payload,
        story_id=fixture.story_id,
    )
    stored = proposal_service.create_proposal(db_session, request)
    proposal_service.review_proposal(
        db_session,
        stored.id,
        ProposalReviewRequest(reviewed_by="phase1-rollback-reviewer"),
    )

    original_upsert = storyboard_mutations._upsert_prompt_package

    def fail_after_flushing_a_prompt(db: Session, shot: Shot, package: dict | None) -> None:
        original_upsert(db, shot, package)
        raise storyboard_mutations.MutationError("forced mid-graph acceptance failure")

    monkeypatch.setattr(
        storyboard_mutations,
        "_upsert_prompt_package",
        fail_after_flushing_a_prompt,
    )

    with pytest.raises(
        proposal_service.ProposalStateError,
        match="forced mid-graph acceptance failure",
    ):
        proposal_apply.apply_proposal(
            db_session,
            stored.id,
            ProposalApplyRequest(applied_by="phase1-rollback-reviewer"),
        )

    db_session.expire_all()
    unchanged_story = db_session.get(Story, fixture.story_id)
    unchanged_proposal = db_session.get(AIProposalRecord, stored.id)
    assert unchanged_story is not None
    assert unchanged_story.base_story == (
        "Acceptance fixture awaiting a reviewed production-plan proposal."
    )
    assert unchanged_proposal is not None
    assert unchanged_proposal.status == "validated"
    assert unchanged_proposal.applied_at is None
    assert unchanged_proposal.applied_storyboard_version_id is None
    assert _count(db_session, StoryboardVersion) == 0
    assert _count(db_session, Chapter) == 0
    assert _count(db_session, Scene) == 0
    assert _count(db_session, Shot) == 0
    assert _count(db_session, Character) == 0
    assert _count(db_session, VoiceProfile) == 0
    assert _count(db_session, ShotNarration) == 0
    assert _count(db_session, ShotPromptPackage) == 0
    assert _count(db_session, ShotModelRecommendation) == 0
    assert _count(db_session, ShotCharacter) == 0
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.entity_type == "ai_proposal_record",
                AuditLog.entity_id == stored.id,
                AuditLog.action == "proposal_applied",
            )
        )
        == 0
    )


def test_phase1_acceptance_end_to_end_is_review_gated_and_render_free(
    db_session: Session,
) -> None:
    fixture = seed_phase1_acceptance_fixture(db_session)
    assert db_session.get(Project, fixture.project_id).name == "A New Journey"
    seeded_story = db_session.get(Story, fixture.story_id)
    assert seeded_story is not None
    assert seeded_story.title == "A New Journey"
    assert float(seeded_story.target_duration_sec) == TARGET_DURATION_SEC

    settings = db_session.scalar(
        select(ProjectStoryboardSettings).where(
            ProjectStoryboardSettings.project_id == fixture.project_id
        )
    )
    assert settings is not None
    assert settings.allow_rendering is False
    assert settings.allow_model_download is False

    assignments = list(
        db_session.scalars(
            select(TaskProviderAssignment).where(
                TaskProviderAssignment.story_id == fixture.story_id,
                TaskProviderAssignment.enabled.is_(True),
            )
        )
    )
    assert {assignment.task_type for assignment in assignments} == {
        task.value for task in PHASE1_PLANNING_TASKS
    }
    assert all(
        db_session.get(ProviderProfile, assignment.provider_profile_id) is not None
        for assignment in assignments
    )

    create_request = ProposalCreateRequest(
        proposal_type=ProposalType.storyboard_full_plan.value,
        summary="Explicit A New Journey Phase-1 acceptance plan.",
        payload=fixture.payload,
        story_id=fixture.story_id,
    )
    validation = proposal_service.validate_create_request(db_session, create_request)
    assert validation.accepted is True, validation.errors
    assert validation.errors == []
    assert validation.report["planned_duration_sec"] == TARGET_DURATION_SEC
    assert validation.report["shot_count"] == 27
    assert validation.report["character_count"] == 4

    stored = proposal_service.create_proposal(db_session, create_request)
    assert stored.validation_status == "valid"
    reviewed = proposal_service.review_proposal(
        db_session,
        stored.id,
        ProposalReviewRequest(
            reviewed_by="phase1-acceptance-reviewer",
            notes="Explicit fixture accepted for transactional apply.",
        ),
    )
    assert reviewed.reviewed_at is not None

    applied = proposal_apply.apply_proposal(
        db_session,
        stored.id,
        ProposalApplyRequest(applied_by="phase1-acceptance-reviewer"),
    )
    replay = proposal_apply.apply_proposal(
        db_session,
        stored.id,
        ProposalApplyRequest(applied_by="phase1-acceptance-reviewer"),
    )
    assert applied.status == "applied"
    assert replay.new_storyboard_version_id == applied.new_storyboard_version_id
    assert _count(db_session, StoryboardVersion) == 1
    assert _count(db_session, AuditLog) >= 1
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.entity_type == "ai_proposal_record",
                AuditLog.entity_id == stored.id,
                AuditLog.action == "proposal_applied",
            )
        )
        == 1
    )

    assert _count(db_session, Chapter) == 3
    assert _count(db_session, Scene) == 6
    assert _count(db_session, Shot) == 27
    assert _count(db_session, Character) == 4
    assert _count(db_session, VoiceProfile) == 4
    assert _count(db_session, ShotNarration) == 27
    assert _count(db_session, ShotPromptPackage) == 27
    assert _count(db_session, ShotModelRecommendation) == 27
    assert _count(db_session, ShotCharacter) >= 27

    aggregate = storyboard.aggregate(db_session, fixture.story_id)
    persisted_chapter_rollups = tuple(
        chapter["duration_sec"] for chapter in aggregate["chapters"]
    )
    persisted_scene_rollups = tuple(
        scene["duration_sec"]
        for chapter in aggregate["chapters"]
        for scene in chapter["scenes"]
    )
    assert persisted_chapter_rollups == fixture.chapter_duration_rollups
    assert persisted_scene_rollups == fixture.scene_duration_rollups
    assert aggregate["planned_duration_sec"] == TARGET_DURATION_SEC
    assert aggregate["discrepancy_sec"] == 0.0

    shots = _canonical_shots(db_session, fixture.story_id)
    positions = {shot.id: index for index, shot in enumerate(shots)}
    for index, shot in enumerate(shots):
        assert 6.0 <= float(shot.duration_sec) <= 12.0
        if index == 0:
            assert shot.continuity_source_shot_id is None
        else:
            source_id = shot.continuity_source_shot_id
            assert source_id in positions
            assert positions[source_id] < positions[shot.id]

    voice_ids = set(db_session.scalars(select(VoiceProfile.id)))
    narrations = list(db_session.scalars(select(ShotNarration)))
    assert all(
        bool(item.narration_text) ^ bool(item.narration_exception_reason)
        for item in narrations
    )
    assert all(
        item.voice_profile_id in voice_ids
        if item.narration_text
        else item.voice_profile_id is None
        for item in narrations
    )
    prompt_packages = list(db_session.scalars(select(ShotPromptPackage)))
    assert all(
        package.provider_profile_id == fixture.generation_provider_profile_id
        and db_session.get(ProviderProfile, package.provider_profile_id) is not None
        for package in prompt_packages
    )
    recommendations = list(db_session.scalars(select(ShotModelRecommendation)))
    assert all(
        recommendation.generation_model_variant_id == fixture.generation_model_variant_id
        and db_session.get(ModelVariant, recommendation.generation_model_variant_id) is not None
        for recommendation in recommendations
    )

    ready = storyboard.readiness(db_session, fixture.story_id)
    assert ready["ready"] is True, ready["reasons"]
    assert ready["planned_duration_sec"] == TARGET_DURATION_SEC
    assert ready["discrepancy_sec"] == 0.0

    planner = PlanningEngine(
        db_session,
        providers={"mock": MockPlanningProvider(fixed_latency_ms=0)},
    )

    def complete_planning_run(idempotency_key: str) -> tuple[dict, AIProposalRecord]:
        run, created = planner.create_run(
            CreateOrchestrationRunRequest(
                story_id=fixture.story_id,
                requested_by="phase1-acceptance-controller",
                routing_mode=RoutingMode.automatic,
                prefer_local_providers=True,
                prefer_hosted_providers=False,
                max_steps=16,
                repair_budget=2,
                time_budget_sec=120,
                transport_retry_limit=1,
                idempotency_key=idempotency_key,
                task_types=list(fixture.planning_task_types),
            )
        )
        assert created is True
        finished = planner.start_run(run.id)
        assert finished.status == RunStatus.completed.value
        detail = planner.get_run_detail(run.id)
        assert len(_task_outputs(detail)) == len(fixture.planning_task_types)
        assert all(
            step.provider_identifier == "mock" and step.resolved_model
            for step in detail["steps"]
            if step.status == "completed"
        )
        assert len(detail["proposals"]) == 1
        proposal = db_session.get(AIProposalRecord, detail["proposals"][0].id)
        assert proposal is not None
        assert proposal.status == "pending_review"
        assert proposal.validation_status in {"valid", "needs_review"}
        assert proposal.applied_at is None
        parsed = StoryboardProposalPayload.model_validate(proposal.payload)
        assert parsed.project_id == fixture.project_id
        assert parsed.story.existing_id == fixture.story_id
        assert proposal.proposal_type == ProposalType.storyboard_full_plan.value
        assert proposal.input_context_hash == proposal.base_content_hash
        return detail, proposal

    first_detail, first_planning_proposal = complete_planning_run(
        "phase1-acceptance-determinism-1"
    )
    second_detail, second_planning_proposal = complete_planning_run(
        "phase1-acceptance-determinism-2"
    )
    assert _task_outputs(first_detail) == _task_outputs(second_detail)
    assert _proposal_without_run_id(first_planning_proposal) == _proposal_without_run_id(
        second_planning_proposal
    )

    approval_revision = snapshot_service.current_revision(db_session, fixture.story_id)
    approved = storyboard.approve(
        db_session,
        fixture.story_id,
        "phase1-acceptance-approver",
        approval_revision,
    )
    approved_again = storyboard.approve(
        db_session,
        fixture.story_id,
        "phase1-acceptance-approver",
        approval_revision,
    )
    assert approved.status == "approved"
    assert approved_again.id == approved.id
    frozen_snapshot = copy.deepcopy(approved.snapshot_json)
    frozen_hash = approved.content_hash

    shots[0].title = "Changed only in the live editable plan"
    db_session.commit()
    db_session.refresh(approved)
    assert approved.snapshot_json == frozen_snapshot
    assert approved.content_hash == frozen_hash

    assert _count(db_session, ComfyJob) == 0
    assert _count(db_session, WorkflowRun) == 0
    assert _count(db_session, FFmpegJob) == 0
