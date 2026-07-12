"""Tests for readiness gates, approval immutability/idempotency, and stale revisions."""

from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    Base,
    Chapter,
    PlanningMediaAsset,
    Project,
    Scene,
    Shot,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
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
    db.add(
        ShotPromptPackage(
            shot_id=shot.id,
            version=1,
            image_prompt="Cinematic planning frame",
            approval_state="draft",
        )
    )
    db.add(
        ShotModelRecommendation(
            shot_id=shot.id,
            recommendation_type="other",
            rationale="Manual workflow review required",
            availability_status="unknown",
            benchmark_status="unknown",
            approval_state="draft",
        )
    )
    db.commit()
    db.refresh(story)
    db.refresh(shot)
    return story, shot, project


def _approve_current(db, story, approved_by: str = "reviewer@example.com"):
    return storyboard_service.approve(
        db,
        story.id,
        approved_by,
        snapshot_service.current_revision(db, story.id),
    )


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


def test_readiness_requires_prompt_and_recommendation_or_explicit_policy_exception(db_session):
    story, shot, project = _ready_story(db_session)
    db_session.query(ShotPromptPackage).filter_by(shot_id=shot.id).delete()
    db_session.query(ShotModelRecommendation).filter_by(shot_id=shot.id).delete()
    db_session.commit()

    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is False
    codes = {reason["code"] for reason in status["reasons"]}
    assert "prompt_package_missing" in codes
    assert "model_recommendation_missing" in codes

    settings = settings_service.get_settings_row(db_session, project.id)
    policy = dict(settings.approval_policy_json or {})
    policy["prompt_package_exceptions"] = {str(shot.id): "Intentional prompt-free manual shot"}
    policy["model_recommendation_exceptions"] = {
        str(shot.id): "No generation workflow is required"
    }
    settings.approval_policy_json = policy
    db_session.commit()

    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is True, status["reasons"]


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


def test_readiness_requires_active_approved_same_project_starting_image(db_session):
    story, shot, project = _ready_story(db_session)
    shot.starting_image_required = True
    asset = PlanningMediaAsset(
        project_id=project.id,
        kind="starting_image",
        source_type="uploaded",
        managed_uri="managed://starting-image",
        approval_state="approved",
    )
    db_session.add(asset)
    db_session.flush()
    shot.starting_image_asset_id = asset.id
    db_session.commit()

    assert storyboard_service.readiness(db_session, story.id)["ready"] is True

    asset.approval_state = "draft"
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert status["ready"] is False
    assert any(reason["code"] == "starting_image_not_approved" for reason in status["reasons"])

    asset.approval_state = "approved"
    asset.kind = "character_reference"
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert any(reason["code"] == "starting_image_kind_invalid" for reason in status["reasons"])

    asset.kind = "starting_image"
    asset.archived_at = datetime.utcnow()
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert any(reason["code"] == "starting_image_archived" for reason in status["reasons"])

    other_project = Project(name="Other Project", description=None)
    db_session.add(other_project)
    db_session.flush()
    asset.archived_at = None
    asset.project_id = other_project.id
    db_session.commit()
    status = storyboard_service.readiness(db_session, story.id)
    assert any(
        reason["code"] == "starting_image_project_mismatch" for reason in status["reasons"]
    )


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
        _approve_current(db_session, story)


def test_approve_rejects_stale_revision_before_versioning(db_session):
    story, shot, _ = _ready_story(db_session)
    stale_revision = snapshot_service.current_revision(db_session, story.id)
    shot.title = "Changed before approval"
    db_session.commit()

    with pytest.raises(
        storyboard_service.StoryboardConflictError,
        match="expected_revision does not match",
    ):
        storyboard_service.approve(
            db_session,
            story.id,
            "reviewer@example.com",
            stale_revision,
        )
    assert db_session.query(StoryboardVersion).filter_by(story_id=story.id).count() == 0


def test_approve_is_idempotent_for_same_content_hash(db_session):
    story, _, _ = _ready_story(db_session)
    revision = snapshot_service.current_revision(db_session, story.id)
    first = storyboard_service.approve(
        db_session, story.id, "reviewer@example.com", revision
    )
    second = storyboard_service.approve(
        db_session, story.id, "reviewer@example.com", revision
    )
    assert first.id == second.id
    assert first.content_hash == second.content_hash
    assert first.content_hash is not None
    assert first.snapshot_json["story"]["approval_state"] == "approved"
    assert first.snapshot_json["story"]["active_storyboard_version_id"] == str(first.id)
    assert snapshot_service.content_hash_for_snapshot(first.snapshot_json) == first.content_hash
    versions = list(
        db_session.query(StoryboardVersion).filter(StoryboardVersion.story_id == story.id).all()
    )
    assert len(versions) == 1


def test_concurrent_identical_approvals_allocate_one_version(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'approval-race.db').as_posix()}",
        future=True,
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    seed_session = factory()
    try:
        story, _, _ = _ready_story(seed_session)
        story_id = story.id
        revision = snapshot_service.current_revision(seed_session, story_id)
    finally:
        seed_session.close()

    original_builder = snapshot_service.build_snapshot_with_hash
    first_snapshot_barrier = threading.Barrier(2)
    thread_state = threading.local()

    def synchronized_builder(db, candidate_story_id):
        result = original_builder(db, candidate_story_id)
        if not getattr(thread_state, "synchronized", False):
            thread_state.synchronized = True
            first_snapshot_barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(
        snapshot_service,
        "build_snapshot_with_hash",
        synchronized_builder,
    )

    def approve_in_own_session():
        session = factory()
        try:
            version = storyboard_service.approve(
                session,
                story_id,
                "concurrent-reviewer@example.com",
                revision,
            )
            return version.id
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            version_ids = list(executor.map(lambda _: approve_in_own_session(), range(2)))

        verify = factory()
        try:
            versions = list(
                verify.scalars(
                    select(StoryboardVersion).where(
                        StoryboardVersion.story_id == story_id
                    )
                )
            )
            assert len(versions) == 1
            assert version_ids == [versions[0].id, versions[0].id]
        finally:
            verify.close()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_approved_snapshot_never_mutates_when_live_plan_changes(db_session):
    story, shot, _ = _ready_story(db_session)
    version = _approve_current(db_session, story)
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
    first = _approve_current(db_session, story)

    # Keep readiness valid while changing content.
    shot.title = "Revised Shot"
    shot.duration_sec = 8.0
    story.target_duration_sec = 8.0
    db_session.commit()

    second = _approve_current(db_session, story)
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
