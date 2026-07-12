"""Tests for deterministic storyboard snapshots and content hashing."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    Base,
    Chapter,
    Character,
    Project,
    Scene,
    Shot,
    ShotNarration,
    Story,
    VoiceProfile,
)
from backend.app.services import storyboard_mutations
from backend.app.services import storyboard_snapshot as snapshot_service
from backend.app.services.storyboard_snapshot import canonical_json_dumps, sha256_hex


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


def _seed_story(db, *, target: float = 10.0, shot_duration: float = 10.0):
    project = Project(name="Snap Project", description=None)
    db.add(project)
    db.flush()
    story = Story(
        project_id=project.id,
        title="Snapshot Story",
        base_story="A complete plan.",
        target_duration_sec=target,
    )
    db.add(story)
    db.flush()
    chapter = Chapter(story_id=story.id, order_index=0, title="Chapter 1")
    db.add(chapter)
    db.flush()
    scene = Scene(chapter_id=chapter.id, order_index=0, title="Scene 1")
    db.add(scene)
    db.flush()
    shot = Shot(
        scene_id=scene.id,
        order_index=0,
        title="Shot A",
        duration_sec=shot_duration,
        visual_description="Wide establishing shot",
    )
    db.add(shot)
    db.flush()
    narration = ShotNarration(
        shot_id=shot.id,
        narration_text="Once upon a time.",
        start_offset_sec=0,
    )
    db.add(narration)
    db.commit()
    db.refresh(story)
    db.refresh(shot)
    return story, shot


def test_canonical_json_is_key_sorted():
    payload = {"b": 1, "a": {"d": 2, "c": 3}}
    assert canonical_json_dumps(payload) == '{"a":{"c":3,"d":2},"b":1}'


def test_sha256_hex_is_stable():
    assert sha256_hex({"x": 1}) == sha256_hex({"x": 1})
    assert sha256_hex({"x": 1}) != sha256_hex({"x": 2})


def test_snapshot_hash_is_deterministic(db_session):
    story, _ = _seed_story(db_session)
    first, hash_a = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    second, hash_b = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    assert hash_a == hash_b
    assert first["schema"] == snapshot_service.SNAPSHOT_SCHEMA
    assert first["totals"]["planned_duration_sec"] == 10.0
    assert first["totals"]["shot_count"] == 1
    assert second["chapters"][0]["scenes"][0]["shots"][0]["narration"]["narration_text"] == (
        "Once upon a time."
    )


def test_snapshot_hash_changes_when_duration_changes(db_session):
    story, shot = _seed_story(db_session, target=12.0, shot_duration=10.0)
    _, before = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    shot.duration_sec = 12.0
    db_session.commit()
    _, after = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    assert before != after


def test_approved_snapshot_dict_is_not_aliased_to_live_graph(db_session):
    story, shot = _seed_story(db_session)
    snapshot, digest = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    frozen = copy.deepcopy(snapshot)
    shot.title = "Mutated Live Title"
    db_session.commit()
    live, live_digest = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    assert frozen["chapters"][0]["scenes"][0]["shots"][0]["title"] == "Shot A"
    assert live["chapters"][0]["scenes"][0]["shots"][0]["title"] == "Mutated Live Title"
    assert digest != live_digest
    # Content hash of the frozen copy remains stable even if live data mutates.
    assert snapshot_service.content_hash_for_snapshot(frozen) == digest


def test_full_plan_archives_omitted_shots_and_snapshot_excludes_them(db_session):
    story, retained = _seed_story(db_session, target=16.0, shot_duration=8.0)
    scene = db_session.get(Scene, retained.scene_id)
    chapter = db_session.get(Chapter, scene.chapter_id)
    omitted = Shot(
        scene_id=scene.id,
        order_index=1,
        title="Omitted Shot",
        duration_sec=8.0,
        visual_description="This shot will be replaced.",
    )
    db_session.add(omitted)
    db_session.commit()

    shots_by_client = storyboard_mutations.upsert_hierarchy(
        db_session,
        story.id,
        [
            {
                "client_id": "chapter-1",
                "existing_id": str(chapter.id),
                "order_index": 0,
                "title": chapter.title,
                "scenes": [
                    {
                        "client_id": "scene-1",
                        "existing_id": str(scene.id),
                        "order_index": 0,
                        "title": scene.title,
                        "shots": [
                            {
                                "client_id": "shot-retained",
                                "existing_id": str(retained.id),
                                "order_index": 0,
                                "title": retained.title,
                                "duration_sec": 8.0,
                            },
                            {
                                "client_id": "shot-replacement",
                                "order_index": 1,
                                "title": "Replacement Shot",
                                "duration_sec": 8.0,
                            },
                        ],
                    }
                ],
            }
        ],
        characters_by_client={},
        voices_by_client={},
    )
    db_session.commit()
    db_session.refresh(omitted)

    assert omitted.archived_at is not None
    assert shots_by_client["shot-replacement"].order_index == 1
    snapshot, _ = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    snapshot_shots = snapshot["chapters"][0]["scenes"][0]["shots"]
    assert [shot["title"] for shot in snapshot_shots] == [
        "Shot A",
        "Replacement Shot",
    ]
    assert snapshot["totals"]["shot_count"] == 2
    assert snapshot["totals"]["planned_duration_sec"] == 16.0


def _replace_with_existing_single_shot(
    db, story, shot, characters, voices, *, replace_identities=True
):
    scene = db.get(Scene, shot.scene_id)
    chapter = db.get(Chapter, scene.chapter_id)
    return storyboard_mutations.upsert_hierarchy(
        db,
        story.id,
        [
            {
                "client_id": "chapter-1",
                "existing_id": str(chapter.id),
                "order_index": 0,
                "title": chapter.title,
                "scenes": [
                    {
                        "client_id": "scene-1",
                        "existing_id": str(scene.id),
                        "order_index": 0,
                        "title": scene.title,
                        "shots": [
                            {
                                "client_id": "shot-1",
                                "existing_id": str(shot.id),
                                "order_index": 0,
                                "title": shot.title,
                                "duration_sec": float(shot.duration_sec),
                                "characters": [],
                            }
                        ],
                    }
                ],
            }
        ],
        characters_by_client=characters,
        voices_by_client=voices,
        replace_identities=replace_identities,
    )


def test_full_plan_archives_safe_omitted_identities_and_snapshot_excludes_them(db_session):
    story, shot = _seed_story(db_session)
    character = Character(story_id=story.id, name="Unused Character")
    voice = VoiceProfile(
        story_id=story.id,
        name="Unused Voice",
        source_type="placeholder",
        setup_mode="placeholder",
    )
    db_session.add_all((character, voice))
    db_session.commit()

    voices = storyboard_mutations.upsert_voices(db_session, story.id, [])
    characters = storyboard_mutations.upsert_characters(
        db_session, story.id, [], voices
    )
    _replace_with_existing_single_shot(db_session, story, shot, characters, voices)
    db_session.commit()
    db_session.refresh(character)
    db_session.refresh(voice)

    assert character.archived_at is not None
    assert voice.archived_at is not None
    snapshot, _ = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    assert snapshot["characters"] == []
    assert snapshot["voice_profiles"] == []


def test_revision_preserves_safe_omitted_identities(db_session):
    story, shot = _seed_story(db_session)
    character = Character(story_id=story.id, name="Existing Character")
    voice = VoiceProfile(
        story_id=story.id,
        name="Existing Voice",
        source_type="placeholder",
        setup_mode="placeholder",
    )
    db_session.add_all((character, voice))
    db_session.commit()

    voices = storyboard_mutations.upsert_voices(db_session, story.id, [])
    characters = storyboard_mutations.upsert_characters(
        db_session, story.id, [], voices
    )
    _replace_with_existing_single_shot(
        db_session,
        story,
        shot,
        characters,
        voices,
        replace_identities=False,
    )
    db_session.commit()
    db_session.refresh(character)
    db_session.refresh(voice)

    assert character.archived_at is None
    assert voice.archived_at is None
    snapshot, _ = snapshot_service.build_snapshot_with_hash(db_session, story.id)
    assert [item["id"] for item in snapshot["characters"]] == [str(character.id)]
    assert [item["id"] for item in snapshot["voice_profiles"]] == [str(voice.id)]


@pytest.mark.parametrize("identity_kind", ["character", "voice"])
def test_full_plan_rejects_omitted_approved_identity(db_session, identity_kind):
    story, shot = _seed_story(db_session)
    if identity_kind == "character":
        db_session.add(
            Character(story_id=story.id, name="Approved", approval_state="approved")
        )
    else:
        db_session.add(
            VoiceProfile(
                story_id=story.id,
                name="Approved",
                source_type="placeholder",
                setup_mode="placeholder",
                approval_state="approved",
            )
        )
    db_session.commit()

    voices = storyboard_mutations.upsert_voices(db_session, story.id, [])
    characters = storyboard_mutations.upsert_characters(
        db_session, story.id, [], voices
    )
    with pytest.raises(storyboard_mutations.MutationError, match=f"approved {identity_kind}"):
        _replace_with_existing_single_shot(db_session, story, shot, characters, voices)


def test_full_plan_rejects_omitted_voice_still_assigned_to_retained_character(db_session):
    story, shot = _seed_story(db_session)
    voice = VoiceProfile(
        story_id=story.id,
        name="Assigned Voice",
        source_type="placeholder",
        setup_mode="placeholder",
    )
    db_session.add(voice)
    db_session.flush()
    character = Character(
        story_id=story.id,
        name="Retained Character",
        assigned_voice_profile_id=voice.id,
    )
    db_session.add(character)
    db_session.commit()

    voices = storyboard_mutations.upsert_voices(db_session, story.id, [])
    characters = storyboard_mutations.upsert_characters(
        db_session,
        story.id,
        [
            {
                "client_id": "character-1",
                "existing_id": str(character.id),
                "name": character.name,
            }
        ],
        voices,
    )
    with pytest.raises(storyboard_mutations.MutationError, match="referenced voice"):
        _replace_with_existing_single_shot(db_session, story, shot, characters, voices)


def test_full_plan_rejects_omitted_character_referenced_by_retained_voice(db_session):
    story, shot = _seed_story(db_session)
    character = Character(story_id=story.id, name="Linked Character")
    db_session.add(character)
    db_session.flush()
    voice = VoiceProfile(
        story_id=story.id,
        character_id=character.id,
        name="Retained Voice",
        source_type="placeholder",
        setup_mode="placeholder",
    )
    db_session.add(voice)
    db_session.commit()

    voices = storyboard_mutations.upsert_voices(
        db_session,
        story.id,
        [
            {
                "client_id": "voice-1",
                "existing_id": str(voice.id),
                "name": voice.name,
                "source_type": voice.source_type,
                "setup_mode": voice.setup_mode,
            }
        ],
    )
    characters = storyboard_mutations.upsert_characters(
        db_session, story.id, [], voices
    )
    with pytest.raises(storyboard_mutations.MutationError, match="referenced character"):
        _replace_with_existing_single_shot(db_session, story, shot, characters, voices)
