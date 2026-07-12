"""Tests for remaining Storyboard Phase 1 planning CRUD services."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    AIProposalRecord,
    Base,
    Chapter,
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
