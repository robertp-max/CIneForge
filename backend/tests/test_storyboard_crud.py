"""Tests for remaining Storyboard Phase 1 planning CRUD services."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    AIProposalRecord,
    Base,
    Chapter,
    Character,
    Model,
    ModelVariant,
    Project,
    ProviderProfile,
    Scene,
    Shot,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
    Story,
    StoryboardVersion,
    TaskProviderAssignment,
    VoiceProfile,
    WorkflowTemplate,
)
from backend.app.schemas.storyboard_crud import (
    ProposalCreateExtended,
    ProposalUpdate,
    ProviderProfileCreate,
    ProviderProfileUpdate,
    RecommendationType,
    ShotModelRecommendationCreate,
    ShotModelRecommendationUpdate,
    ShotNarrationCreate,
    ShotNarrationUpdate,
    ShotPromptPackageCreate,
    ShotPromptPackageUpdate,
    TaskProviderAssignmentCreate,
    TaskProviderAssignmentUpdate,
)
from backend.app.schemas.storyboard import ShotCharacterLinkCreate, ShotCreate
from backend.app.services import storyboard as storyboard_service
from backend.app.services import storyboard_crud as crud


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()

    project = Project(name="P", description=None)
    session.add(project)
    session.flush()
    story = Story(
        project_id=project.id,
        title="Story",
        base_story="Once",
        target_duration_sec=60,
    )
    session.add(story)
    session.flush()
    chapter = Chapter(story_id=story.id, order_index=0, title="C1")
    session.add(chapter)
    session.flush()
    scene = Scene(chapter_id=chapter.id, order_index=0, title="S1")
    session.add(scene)
    session.flush()
    shot = Shot(
        scene_id=scene.id,
        order_index=0,
        title="Shot A",
        duration_sec=8,
    )
    session.add(shot)
    voice = VoiceProfile(
        story_id=story.id,
        name="Narrator",
        source_type="placeholder",
    )
    session.add(voice)
    session.commit()
    session.refresh(project)
    session.refresh(story)
    session.refresh(shot)
    session.refresh(voice)

    yield session, project, story, shot, voice
    session.close()


def test_narration_upsert_requires_text_or_exception(db):
    session, project, story, shot, voice = db
    with pytest.raises(ValueError):
        ShotNarrationCreate(narration_text=None, narration_exception_reason=None)

    row = crud.upsert_narration(
        session,
        shot.id,
        ShotNarrationCreate(
            narration_text="Hello there.",
            voice_profile_id=voice.id,
            start_offset_sec=0.5,
        ),
    )
    assert row.shot_id == shot.id
    assert row.narration_text == "Hello there."

    updated = crud.upsert_narration(
        session,
        shot.id,
        ShotNarrationUpdate(narration_text="Updated line."),
        partial=True,
    )
    assert updated.id == row.id
    assert updated.narration_text == "Updated line."

    # Clearing both text and exception is rejected.
    with pytest.raises(crud.StoryboardCrudError):
        crud.upsert_narration(
            session,
            shot.id,
            ShotNarrationUpdate(narration_text="", narration_exception_reason=""),
            partial=True,
        )

    crud.delete_narration(session, shot.id)
    assert crud.get_narration(session, shot.id) is None


def test_prompt_package_versioning(db):
    session, project, story, shot, voice = db
    v1 = crud.create_prompt_package(
        session,
        shot.id,
        ShotPromptPackageCreate(image_prompt="hero stands", video_prompt="slow push"),
    )
    assert v1.version == 1
    v2 = crud.create_prompt_package(
        session,
        shot.id,
        ShotPromptPackageCreate(image_prompt="hero sits"),
    )
    assert v2.version == 2

    with pytest.raises(crud.StoryboardCrudConflictError):
        crud.create_prompt_package(
            session,
            shot.id,
            ShotPromptPackageCreate(image_prompt="dup", version=1),
        )

    listed = crud.list_prompt_packages(session, shot.id)
    assert [p.version for p in listed] == [2, 1]

    got = crud.get_prompt_package_version(session, shot.id, 2)
    assert got.id == v2.id

    patched = crud.update_prompt_package(
        session, v2.id, ShotPromptPackageUpdate(negative_prompt="blurry")
    )
    assert patched.negative_prompt == "blurry"


def test_recommendations_provider_assignments_and_profiles(db):
    session, project, story, shot, voice = db

    model = Model(
        family="f",
        name="m",
        evidence_level="catalog_only",
    )
    session.add(model)
    session.flush()
    variant = ModelVariant(
        model_id=model.id,
        variant_name="v1",
        compatible_24gb_status="unknown",
        native_voice_capability="unknown",
    )
    session.add(variant)
    wf = WorkflowTemplate(
        name="wf",
        version="1",
        workflow_api_json={"1": {}},
        manifest_json={"template_id": "wf"},
        sha256="c" * 64,
    )
    session.add(wf)
    session.commit()
    session.refresh(variant)
    session.refresh(wf)

    rec = crud.create_recommendation(
        session,
        shot.id,
        ShotModelRecommendationCreate(
            recommendation_type=RecommendationType.generation,
            generation_model_variant_id=variant.id,
            workflow_template_id=wf.id,
            rationale="fits tone",
            availability_status="unknown",
            benchmark_status="unknown",
        ),
    )
    assert rec.availability_status == "unknown"
    assert rec.benchmark_status == "unknown"
    assert rec.acknowledged_at is None

    rec2 = crud.update_recommendation(
        session,
        rec.id,
        ShotModelRecommendationUpdate(acknowledge=True, rationale="reviewed"),
    )
    assert rec2.acknowledged_at is not None
    assert rec2.rationale == "reviewed"

    profile = crud.create_provider_profile(
        session,
        ProviderProfileCreate(
            provider_identifier="openai",
            display_name="OpenAI",
            availability_status="unknown",
        ),
    )
    assert profile.execution_mode == "disabled"
    assert profile.availability_status == "unknown"

    assignment = crud.create_task_assignment(
        session,
        story.id,
        TaskProviderAssignmentCreate(
            task_type="story_outline",
            provider_profile_id=profile.id,
            rationale="default planning",
        ),
    )
    assert assignment.enabled is True

    with pytest.raises(crud.StoryboardCrudConflictError):
        crud.create_task_assignment(
            session,
            story.id,
            TaskProviderAssignmentCreate(
                task_type="story_outline",
                provider_profile_id=profile.id,
            ),
        )

    updated = crud.update_task_assignment(
        session,
        assignment.id,
        TaskProviderAssignmentUpdate(enabled=False, priority=10),
    )
    assert updated.enabled is False
    assert updated.priority == 10

    with pytest.raises(crud.StoryboardCrudConflictError):
        crud.delete_provider_profile(session, profile.id)

    crud.delete_task_assignment(session, assignment.id)
    crud.delete_provider_profile(session, profile.id)
    crud.delete_recommendation(session, rec.id)

    assert session.get(ShotModelRecommendation, rec.id) is None
    assert session.get(ProviderProfile, profile.id) is None


def test_proposals_and_storyboard_versions(db):
    session, project, story, shot, voice = db

    proposal = crud.create_proposal(
        session,
        ProposalCreateExtended(
            proposal_type="chapter_plan",
            payload={"chapters": [{"title": "One"}]},
            story_id=story.id,
            schema_name="chapter_plan.v1",
        ),
    )
    assert proposal.status == "pending_review"
    assert proposal.content_hash
    assert proposal.story_id == story.id

    listed = crud.list_proposals(session, story_id=story.id)
    assert len(listed) == 1

    reviewed = crud.update_proposal(
        session,
        proposal.id,
        ProposalUpdate(status="rejected", reviewed_by="editor", rejection_reason="off tone"),
    )
    assert reviewed.status == "rejected"
    assert reviewed.rejected_at is not None
    assert reviewed.reviewed_by == "editor"

    version = StoryboardVersion(
        story_id=story.id,
        version_number=1,
        status="approved",
        snapshot_json={"story": {"title": "Story"}},
        content_hash="d" * 64,
        created_by="editor",
        approved_by="editor",
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    versions = crud.list_storyboard_versions(session, story.id)
    assert len(versions) == 1
    assert versions[0].version_number == 1

    got = crud.get_storyboard_version_for_story(session, story.id, version.id)
    assert got.snapshot_json["story"]["title"] == "Story"

    with pytest.raises(crud.StoryboardCrudNotFoundError):
        crud.get_storyboard_version_for_story(session, story.id, uuid.uuid4())


def test_voice_profile_must_match_story_for_narration(db):
    session, project, story, shot, voice = db
    other_story = Story(
        project_id=project.id,
        title="Other",
        base_story="x",
        target_duration_sec=30,
    )
    session.add(other_story)
    session.flush()
    foreign_voice = VoiceProfile(
        story_id=other_story.id,
        name="Foreign",
        source_type="placeholder",
    )
    session.add(foreign_voice)
    session.commit()
    session.refresh(foreign_voice)

    with pytest.raises(crud.StoryboardCrudError, match="same story"):
        crud.upsert_narration(
            session,
            shot.id,
            ShotNarrationCreate(
                narration_text="Nope",
                voice_profile_id=foreign_voice.id,
            ),
        )


def _approve_story_for_edit_test(session, story):
    story.approval_state = "approved"
    session.commit()
    assert session.get(Story, story.id).approval_state == "approved"


def _model_variant(session):
    model = Model(family="lifecycle", name=f"model-{uuid.uuid4()}", evidence_level="catalog_only")
    session.add(model)
    session.flush()
    variant = ModelVariant(
        model_id=model.id,
        variant_name="default",
        compatible_24gb_status="unknown",
        native_voice_capability="unknown",
    )
    session.add(variant)
    session.commit()
    return variant


def test_content_edits_reopen_approved_story_in_same_transaction(db):
    session, _, story, shot, _ = db

    _approve_story_for_edit_test(session, story)
    narration = crud.upsert_narration(
        session, shot.id, ShotNarrationCreate(narration_text="First line")
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.upsert_narration(
        session,
        shot.id,
        ShotNarrationUpdate(narration_text="Revised line"),
        partial=True,
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.delete_narration(session, shot.id)
    assert session.get(Story, story.id).approval_state == "draft"
    assert session.get(ShotNarration, narration.id) is None

    _approve_story_for_edit_test(session, story)
    prompt = crud.create_prompt_package(
        session, shot.id, ShotPromptPackageCreate(image_prompt="Original prompt")
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.update_prompt_package(
        session, prompt.id, ShotPromptPackageUpdate(image_prompt="Revised prompt")
    )
    assert session.get(Story, story.id).approval_state == "draft"

    variant = _model_variant(session)
    _approve_story_for_edit_test(session, story)
    recommendation = crud.create_recommendation(
        session,
        shot.id,
        ShotModelRecommendationCreate(
            recommendation_type=RecommendationType.generation,
            generation_model_variant_id=variant.id,
        ),
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.update_recommendation(
        session,
        recommendation.id,
        ShotModelRecommendationUpdate(rationale="Reviewed recommendation"),
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.delete_recommendation(session, recommendation.id)
    assert session.get(Story, story.id).approval_state == "draft"


def test_archived_shot_or_ancestor_rejects_content_read_and_update(db):
    session, _, _, shot, _ = db
    scene = session.get(Scene, shot.scene_id)
    chapter = session.get(Chapter, scene.chapter_id)
    crud.upsert_narration(session, shot.id, ShotNarrationCreate(narration_text="Line"))
    prompt = crud.create_prompt_package(
        session, shot.id, ShotPromptPackageCreate(image_prompt="Prompt")
    )
    variant = _model_variant(session)
    recommendation = crud.create_recommendation(
        session,
        shot.id,
        ShotModelRecommendationCreate(
            recommendation_type=RecommendationType.generation,
            generation_model_variant_id=variant.id,
        ),
    )
    update = ShotCreate(
        order_index=shot.order_index,
        title="Updated",
        duration_sec=float(shot.duration_sec),
    )

    for archived in (shot, scene, chapter):
        archived.archived_at = datetime.utcnow()
        session.commit()

        with pytest.raises(crud.StoryboardCrudNotFoundError):
            crud.get_narration(session, shot.id)
        with pytest.raises(crud.StoryboardCrudNotFoundError):
            crud.get_prompt_package(session, prompt.id)
        with pytest.raises(crud.StoryboardCrudNotFoundError):
            crud.get_recommendation(session, recommendation.id)
        with pytest.raises(storyboard_service.StoryboardDomainError):
            storyboard_service.update_shot(session, shot.id, update)

        session.rollback()
        archived.archived_at = None
        session.commit()


def test_reorder_uses_active_siblings_only_and_reopens_approval(db):
    session, _, story, shot, _ = db
    first_scene = session.get(Scene, shot.scene_id)
    first_chapter = session.get(Chapter, first_scene.chapter_id)

    second_chapter = Chapter(story_id=story.id, order_index=1, title="C2")
    second_scene = Scene(chapter_id=first_chapter.id, order_index=1, title="S2")
    second_shot = Shot(
        scene_id=first_scene.id,
        order_index=1,
        title="Shot B",
        duration_sec=8,
    )
    archived_shot = Shot(
        scene_id=first_scene.id,
        order_index=2,
        title="Archived",
        duration_sec=8,
        archived_at=datetime.utcnow(),
    )
    session.add_all((second_chapter, second_scene, second_shot, archived_shot))
    session.commit()

    _approve_story_for_edit_test(session, story)
    storyboard_service.reorder(
        session, Chapter, "story_id", story.id, [second_chapter.id, first_chapter.id]
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    storyboard_service.reorder(
        session, Scene, "chapter_id", first_chapter.id, [second_scene.id, first_scene.id]
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    storyboard_service.reorder(
        session, Shot, "scene_id", first_scene.id, [second_shot.id, shot.id]
    )
    assert session.get(Story, story.id).approval_state == "draft"
    assert session.get(Shot, archived_shot.id).order_index == 2

    with pytest.raises(storyboard_service.StoryboardDomainError, match="archived or mismatched"):
        storyboard_service.reorder(
            session,
            Shot,
            "scene_id",
            first_scene.id,
            [second_shot.id, shot.id, archived_shot.id],
        )

    first_scene.archived_at = datetime.utcnow()
    session.commit()
    with pytest.raises(storyboard_service.StoryboardDomainError, match="Scene not found"):
        storyboard_service.reorder(
            session, Shot, "scene_id", first_scene.id, [second_shot.id, shot.id]
        )

    session.rollback()
    first_scene.archived_at = None
    first_chapter.archived_at = datetime.utcnow()
    session.commit()
    with pytest.raises(storyboard_service.StoryboardDomainError, match="Chapter not found"):
        storyboard_service.reorder(
            session, Scene, "chapter_id", first_chapter.id, [second_scene.id, first_scene.id]
        )


def test_routing_content_mutations_reopen_referenced_story(db):
    session, _, story, shot, _ = db
    profile = crud.create_provider_profile(
        session,
        ProviderProfileCreate(
            provider_identifier="openai",
            display_name="Routing Provider",
        ),
    )

    _approve_story_for_edit_test(session, story)
    assignment = crud.create_task_assignment(
        session,
        story.id,
        TaskProviderAssignmentCreate(
            task_type="story_outline",
            provider_profile_id=profile.id,
        ),
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.update_provider_profile(
        session, profile.id, ProviderProfileUpdate(display_name="Updated Provider")
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.update_task_assignment(
        session, assignment.id, TaskProviderAssignmentUpdate(priority=5)
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.delete_task_assignment(session, assignment.id)
    assert session.get(Story, story.id).approval_state == "draft"

    crud.create_prompt_package(
        session,
        shot.id,
        ShotPromptPackageCreate(
            image_prompt="Provider-linked prompt",
            provider_profile_id=profile.id,
        ),
    )
    story.default_provider_profile_id = profile.id
    session.commit()
    _approve_story_for_edit_test(session, story)
    crud.update_provider_profile(
        session, profile.id, ProviderProfileUpdate(display_name="Referenced Provider")
    )
    assert session.get(Story, story.id).approval_state == "draft"

    _approve_story_for_edit_test(session, story)
    crud.delete_provider_profile(session, profile.id)
    assert session.get(Story, story.id).approval_state == "draft"
    assert session.get(ProviderProfile, profile.id) is None


def test_shot_character_links_reject_archived_and_cross_story_characters(db):
    session, project, story, shot, _ = db
    character = Character(story_id=story.id, name="Active")
    other_story = Story(
        project_id=project.id,
        title="Other",
        base_story="Other",
        target_duration_sec=8,
    )
    session.add_all((character, other_story))
    session.flush()
    foreign = Character(story_id=other_story.id, name="Foreign")
    session.add(foreign)
    session.commit()

    _approve_story_for_edit_test(session, story)
    links = storyboard_service.replace_shot_characters(
        session,
        shot.id,
        [ShotCharacterLinkCreate(character_id=character.id, order_index=0)],
    )
    assert links[0].character_id == character.id
    assert session.get(Story, story.id).approval_state == "draft"

    with pytest.raises(storyboard_service.StoryboardDomainError, match="same story"):
        storyboard_service.replace_shot_characters(
            session,
            shot.id,
            [ShotCharacterLinkCreate(character_id=foreign.id, order_index=0)],
        )

    character.archived_at = datetime.utcnow()
    session.commit()
    with pytest.raises(storyboard_service.StoryboardDomainError, match="active"):
        storyboard_service.replace_shot_characters(
            session,
            shot.id,
            [ShotCharacterLinkCreate(character_id=character.id, order_index=0)],
        )
