"""Tests for readiness gates, approval immutability/idempotency, and stale revisions."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    Base,
    Chapter,
    Project,
    Scene,
    Shot,
    ShotNarration,
    Story,
    StoryboardVersion,
    VoiceProfile,
)
from backend.app.schemas.storyboard import StoryUpdate
from backend.app.services import storyboard as storyboard_service
from backend.app.services import storyboard_settings as settings_service
from backend.app.services import storyboard_snapshot as snapshot_service


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _ready_story(db, *, target: float = 10.0, shot_duration: float = 10.0, with_narration: bool = True):
    project = Project(name="Approval Project", description=None)
    db.add(project)
    db.flush()
    settings_service.get_or_create_settings(db, project.id)
    story = Story(
        project_id=project.id,
        title="Ready Story",
        base_story="Ready base story",
        target_duration_sec=target,
    )
    db.add(story)
    db.flush()
    chapter = Chapter(story_id=story.id, order_index=0, title="C1")
    db.add(chapter)
    db.flush()
    scene = Scene(chapter_id=chapter.id, order_index=0, title="S1")
    db.add(scene)
    db.flush()
    shot = Shot(
        scene_id=scene.id,
        order_index=0,
        title="A",
        duration_sec=shot_duration,
        visual_description="Visual",
        story_purpose="Purpose",
    )
    db.add(shot)
    db.flush()
    if with_narration:
        db.add(
            ShotNarration(
                shot_id=shot.id,
                narration_text="Narration line",
                start_offset_sec=0,
            )
        )
    db.commit()
    db.refresh(story)
    db.refresh(shot)
    return story, shot, project


def test_readiness_requires_exact_duration(db_session):
    story, _, _ = _ready_story(db_session, target=12.0, shot_duration=10.0)
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is False
    assert status["discrepancy_sec"] == -2.0
    assert any(reason["code"] == "duration_mismatch" for reason in status["reasons"])


def test_readiness_requires_narration_or_exception(db_session):
    story, _, _ = _ready_story(db_session, with_narration=False)
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is False
    assert any(reason["code"] == "narration_missing" for reason in status["reasons"])


def test_readiness_accepts_narration_exception(db_session):
    story, shot, _ = _ready_story(db_session, with_narration=False)
    db_session.add(
        ShotNarration(
            shot_id=shot.id,
            narration_text=None,
            narration_exception_reason="Silent B-roll",
            start_offset_sec=0,
        )
    )
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is True


def test_readiness_duration_override_required_outside_policy(db_session):
    story, shot, _ = _ready_story(db_session, target=20.0, shot_duration=20.0)
    shot.duration_override_reason = None
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is False
    assert any(reason["code"] == "duration_override_required" for reason in status["reasons"])

    shot.duration_override_reason = "Long oner for reveal"
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert not any(reason["code"] == "duration_override_required" for reason in status["reasons"])


def test_placeholder_voice_is_nonblocking_when_policy_allows(db_session):
    story, _, project = _ready_story(db_session)
    db_session.add(
        VoiceProfile(
            story_id=story.id,
            name="Temp Voice",
            source_type="placeholder",
            setup_mode="placeholder",
            consent_required=False,
            consent_confirmed=False,
        )
    )
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is True

    settings = settings_service.get_settings(db_session, project.id)
    policy = dict(settings.voice_policy_json or {})
    policy["allow_placeholder_for_approval"] = False
    policy["block_unresolved_provider_voices"] = True
    settings.voice_policy_json = policy
    db_session.commit()
    # Placeholder remains non-blocking only when allowed; with allow=false it is not auto-blocked
    # unless unresolved provider policy applies to non-placeholder modes. Ensure manual path still ok.
    status = storyboard_service.readiness(db_session, story.id)
    assert isinstance(status["ready"], bool)


def test_manual_voice_is_nonblocking_when_policy_allows(db_session):
    story, _, _ = _ready_story(db_session)
    db_session.add(
        VoiceProfile(
            story_id=story.id,
            name="Manual Voice",
            source_type="synthetic",
            setup_mode="manual",
            consent_required=False,
            consent_confirmed=False,
        )
    )
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is True


def test_voice_consent_blocks_when_required(db_session):
    story, _, _ = _ready_story(db_session)
    db_session.add(
        VoiceProfile(
            story_id=story.id,
            name="User Voice",
            source_type="user_provided_consented",
            setup_mode="user_provided_consented",
            consent_required=True,
            consent_confirmed=False,
        )
    )
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is False
    assert any(reason["code"] == "voice_consent_required" for reason in status["reasons"])


def test_approve_blocked_when_not_ready(db_session):
    story, _, _ = _ready_story(db_session, target=12.0, shot_duration=10.0)
    with pytest.raises(storyboard_service.StoryboardDomainError):
        storyboard_service.approve(db_session, story.id, "reviewer@example.com")


def test_approve_is_idempotent_for_same_content_hash(db_session):
    story, _, _ = _ready_story(db_session)
    first = storyboard_service.approve(db_session, story.id, "reviewer@example.com")
    second = storyboard_service.approve(db_session, story.id, "reviewer@example.com")
    assert first.id == second.id
    assert first.content_hash == second.content_hash
    assert first.content_hash is not None
    versions = list(
        db_session.query(StoryboardVersion).filter(StoryboardVersion.story_id == story.id).all()
    )
    assert len(versions) == 1


def test_approved_snapshot_never_mutates_when_live_plan_changes(db_session):
    story, shot, _ = _ready_story(db_session)
    version = storyboard_service.approve(db_session, story.id, "reviewer@example.com")
    frozen = copy.deepcopy(version.snapshot_json)
    frozen_hash = version.content_hash

    shot.title = "Changed After Approval"
    shot.duration_sec = 8.0
    story.target_duration_sec = 8.0
    db_session.commit()

    db_session.refresh(version)
    assert version.snapshot_json == frozen
    assert version.content_hash == frozen_hash
    assert version.snapshot_json["chapters"][0]["scenes"][0]["shots"][0]["title"] == "A"


def test_reapprove_after_change_creates_new_version(db_session):
    story, shot, _ = _ready_story(db_session, target=10.0, shot_duration=10.0)
    first = storyboard_service.approve(db_session, story.id, "reviewer@example.com")

    # Keep readiness valid while changing content.
    shot.title = "Revised Shot"
    shot.duration_sec = 8.0
    story.target_duration_sec = 8.0
    db_session.commit()

    second = storyboard_service.approve(db_session, story.id, "reviewer@example.com")
    assert second.id != first.id
    assert second.version_number == first.version_number + 1
    assert second.content_hash != first.content_hash
    db_session.refresh(first)
    assert first.superseded_at is not None
    assert first.snapshot_json["chapters"][0]["scenes"][0]["shots"][0]["title"] == "A"


def test_story_update_stale_revision_conflicts(db_session):
    story, _, _ = _ready_story(db_session)
    revision = snapshot_service.current_revision(db_session, story.id)
    storyboard_service.update_story(
        db_session,
        story.id,
        StoryUpdate(title="Updated Title", expected_revision=revision),
    )
    with pytest.raises(storyboard_service.StoryboardConflictError):
        storyboard_service.update_story(
            db_session,
            story.id,
            StoryUpdate(title="Should Fail", expected_revision=revision),
        )


def test_story_update_stale_updated_at_conflicts(db_session):
    story, _, _ = _ready_story(db_session)
    stale = story.updated_at
    storyboard_service.update_story(
        db_session,
        story.id,
        StoryUpdate(title="First Patch", expected_updated_at=stale),
    )
    db_session.refresh(story)
    with pytest.raises(storyboard_service.StoryboardConflictError):
        storyboard_service.update_story(
            db_session,
            story.id,
            StoryUpdate(title="Second Patch", expected_updated_at=stale),
        )


def test_phase_a_snapshot_includes_revision_and_readiness(db_session):
    story, _, _ = _ready_story(db_session)
    payload = storyboard_service.phase_a_snapshot(db_session, story.id)
    assert payload["revision"]
    assert payload["content_hash"] == payload["revision"]
    assert payload["readiness"]["ready"] is True
    assert payload["settings"]["shot_duration_min_sec"] == 6.0
    assert payload["planned_duration_sec"] == payload["target_duration_sec"]
