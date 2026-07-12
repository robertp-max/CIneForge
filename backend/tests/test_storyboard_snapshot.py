"""Tests for deterministic storyboard snapshots and content hashing."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base, Chapter, Project, Scene, Shot, ShotNarration, Story
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
