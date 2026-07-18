from __future__ import annotations

import copy
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    AuditLog,
    Base,
    Campaign,
    Chapter,
    PlanningMediaAsset,
    Project,
    Scene,
    Shot,
    Story,
    TimelineSlot,
    Track,
)
from backend.app.services import reference_assets
from backend.app.services.transfiguration_project_bundle import (
    ASSET_MANIFEST_PATH,
    _import_assets,
    _load_json,
    migrate_legacy_storyboard_assets,
    repair_manifest_assets,
)


PROJECT_ID = UUID("1823e5da-e926-5b61-9d45-4bf9bea10c94")


@pytest.fixture()
def repair_db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()

    class _Settings:
        storage_root = Path(tmp_path).resolve()

    monkeypatch.setattr(reference_assets, "get_settings", lambda: _Settings())
    project = Project(id=PROJECT_ID, name="Transfiguration repair test")
    session.add(project)
    session.commit()
    manifest = _load_json(ASSET_MANIFEST_PATH)
    mapping = _import_assets(session, PROJECT_ID, manifest)
    try:
        yield session, manifest, mapping
    finally:
        session.close()
        engine.dispose()


def _seed_non_asset_state(session):
    story = Story(
        project_id=PROJECT_ID,
        title="Do not mutate",
        base_story="Stable hierarchy",
        target_duration_sec=8,
        approval_state="approved",
    )
    session.add(story)
    session.flush()
    chapter = Chapter(
        story_id=story.id,
        order_index=0,
        title="Chapter",
        approval_state="approved",
    )
    session.add(chapter)
    session.flush()
    scene = Scene(
        chapter_id=chapter.id,
        order_index=0,
        title="Scene",
        approval_state="approved",
    )
    session.add(scene)
    session.flush()
    shot = Shot(
        scene_id=scene.id,
        order_index=0,
        title="Shot",
        duration_sec=8,
        starting_image_required=True,
        starting_image_asset_id=None,
        approval_state="approved",
    )
    session.add(shot)
    campaign = Campaign(
        project_id=PROJECT_ID,
        name="Campaign",
        target_duration_sec=8,
    )
    session.add(campaign)
    session.flush()
    track = Track(campaign_id=campaign.id, name="Video", kind="video", sort_order=0)
    session.add(track)
    session.flush()
    slot = TimelineSlot(track_id=track.id, slot_index=0, start_sec=0, duration_sec=8)
    session.add(slot)
    session.commit()


def _non_asset_snapshot(session) -> dict:
    return {
        "stories": [
            (str(row.id), row.title, row.base_story, row.approval_state)
            for row in session.scalars(select(Story).order_by(Story.id))
        ],
        "chapters": [
            (str(row.id), str(row.story_id), row.order_index, row.title, row.approval_state)
            for row in session.scalars(select(Chapter).order_by(Chapter.id))
        ],
        "scenes": [
            (str(row.id), str(row.chapter_id), row.order_index, row.title, row.approval_state)
            for row in session.scalars(select(Scene).order_by(Scene.id))
        ],
        "shots": [
            (
                str(row.id),
                str(row.scene_id),
                row.order_index,
                row.title,
                str(row.starting_image_asset_id) if row.starting_image_asset_id else None,
                row.approval_state,
            )
            for row in session.scalars(select(Shot).order_by(Shot.id))
        ],
        "campaigns": [
            (str(row.id), row.name, float(row.target_duration_sec))
            for row in session.scalars(select(Campaign).order_by(Campaign.id))
        ],
        "timeline": [
            (str(row.id), str(row.track_id), row.slot_index, float(row.duration_sec))
            for row in session.scalars(select(TimelineSlot).order_by(TimelineSlot.id))
        ],
    }


def test_repair_assets_only_rehydrates_missing_bytes_idempotently(repair_db):
    session, manifest, mapping = repair_db
    _seed_non_asset_state(session)
    asset = session.get(PlanningMediaAsset, mapping["character_jesus_sheet"])
    assert asset is not None
    asset.approval_state = "in_review"
    session.commit()
    path = reference_assets.resolve_managed_path(asset)
    expected_sha = asset.sha256
    path.unlink()
    before = copy.deepcopy(_non_asset_snapshot(session))

    first = repair_manifest_assets(session, PROJECT_ID, manifest)
    second = repair_manifest_assets(session, PROJECT_ID, manifest)

    assert first["asset_count"] == 14
    assert first["repaired_count"] == 1
    assert first["repaired_asset_ids"] == [str(asset.id)]
    assert second["repaired_count"] == 0
    assert reference_assets.sha256_file(path) == expected_sha
    session.refresh(asset)
    assert asset.id == mapping["character_jesus_sheet"]
    assert asset.approval_state == "in_review"
    assert _non_asset_snapshot(session) == before
    audits = list(
        session.scalars(
            select(AuditLog).where(
                AuditLog.action == "planning_media_asset_bytes_rehydrated",
                AuditLog.entity_id == asset.id,
            )
        )
    )
    assert len(audits) == 1
    assert audits[0].details["source_label"] == "verified_bundled_archive"


def test_repair_assets_only_fails_closed_for_mismatched_existing_bytes(repair_db):
    session, manifest, mapping = repair_db
    asset = session.get(PlanningMediaAsset, mapping["scene_01_storyboard"])
    assert asset is not None
    path = reference_assets.resolve_managed_path(asset)
    path.write_bytes(b"mismatched existing bytes")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        repair_manifest_assets(session, PROJECT_ID, manifest)

    assert path.read_bytes() == b"mismatched existing bytes"
    failure = session.scalar(
        select(AuditLog)
        .where(
            AuditLog.action == "planning_media_asset_integrity_failure",
            AuditLog.entity_id == asset.id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    assert failure is not None
    assert failure.details["fail_closed"] is True


def test_storyboard_semantic_migration_preserves_asset_id_and_clears_shot_binding(repair_db):
    session, manifest, mapping = repair_db
    _seed_non_asset_state(session)
    asset = session.get(PlanningMediaAsset, mapping["scene_01_storyboard"])
    assert asset is not None
    art_path = reference_assets.resolve_managed_path(asset)
    legacy_dir = reference_assets.managed_root() / str(PROJECT_ID) / "starting_image"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = legacy_dir / art_path.name
    art_path.replace(legacy_path)
    asset.kind = "starting_image"
    asset.managed_uri = reference_assets.build_managed_uri(
        PROJECT_ID, "starting_image", legacy_path.name
    )
    asset.approval_state = "in_review"
    shot = session.scalar(select(Shot))
    assert shot is not None
    shot.starting_image_asset_id = asset.id
    session.commit()
    original_id = asset.id
    original_sha = asset.sha256

    result = migrate_legacy_storyboard_assets(session, PROJECT_ID, manifest)

    session.refresh(asset)
    session.refresh(shot)
    assert result["migrated_asset_ids"] == [str(original_id)]
    assert result["cleared_shot_ids"] == [str(shot.id)]
    assert asset.id == original_id
    assert asset.kind == "art_direction_reference"
    assert asset.approval_state == "in_review"
    assert shot.starting_image_asset_id is None
    migrated_path = reference_assets.resolve_managed_path(asset)
    assert migrated_path.is_file()
    assert reference_assets.sha256_file(migrated_path) == original_sha
    assert not legacy_path.exists()
