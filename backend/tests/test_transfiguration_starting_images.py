from __future__ import annotations

import binascii
import csv
import hashlib
import struct
import zlib
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    AuditLog,
    Base,
    Chapter,
    PlanningMediaAsset,
    Project,
    Scene,
    Shot,
    Story,
)
from backend.app.services import reference_assets
from backend.app.services.transfiguration_starting_images import (
    KNOWN_REFERENCE_KINDS,
    PROJECT_ID,
    STORY_ID,
    PreflightRecord,
    StartingImageImportError,
    preflight_inventory,
    run_import,
)


SHOT_CODES = (
    "S01A", "S01B", "S01C", "S01D", "S01E", "S01F",
    "S02A", "S02B", "S02C", "S02D",
    "S03A", "S03B", "S03C", "S03D", "S03E",
    "S04A", "S04B", "S04C", "S04D", "S04E", "S04F",
    "S05A", "S05B", "S05C", "S05D", "S05E",
    "S06A", "S06B", "S06C", "S06D",
    "S07A", "S07B", "S07C", "S07D", "S07E", "S07F",
    "S08A", "S08B", "S08C", "S08D",
)


def _png(width: int, height: int = 2, value: int = 1) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixel = bytes((value % 256, (value * 3) % 256, (value * 7) % 256))
    raw = b"".join(b"\x00" + pixel * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _write_inventory(root: Path, count: int = 56) -> tuple[Path, tuple[str, ...]]:
    names = tuple(f"review-{index:02}.png" for index in range(count))
    fields = (
        "source_filename", "extension", "sha256", "detected_mime", "width", "height",
        "classification", "suggested_shot_code", "confidence", "visual_rationale",
        "existing_or_reused_asset_id",
    )
    rows = []
    for index, name in enumerate(names, 1):
        data = _png(index + 1, value=index)
        (root / name).write_bytes(data)
        rows.append(
            {
                "source_filename": name,
                "extension": ".png",
                "sha256": hashlib.sha256(data).hexdigest(),
                "detected_mime": "image/png",
                "width": index + 1,
                "height": 2,
                "classification": "alternate candidate for a shot",
                "suggested_shot_code": "S01A",
                "confidence": "0.80",
                "visual_rationale": "Test candidate",
                "existing_or_reused_asset_id": "",
            }
        )
    path = root / "inventory.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path, names


def test_preflight_enforces_explicit_allowlist_and_exact_56_count(tmp_path):
    inventory, names = _write_inventory(tmp_path)
    records = preflight_inventory(inventory, tmp_path, expected_allowlist=names)
    assert len(records) == 56

    with inventory.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    rows[0]["source_filename"] = "not-allowlisted.png"
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(StartingImageImportError, match="explicit allowlist"):
        preflight_inventory(inventory, tmp_path, expected_allowlist=names)


def test_preflight_rejects_source_byte_mutation(tmp_path):
    inventory, names = _write_inventory(tmp_path)
    (tmp_path / names[10]).write_bytes(_png(99, value=99))
    with pytest.raises(StartingImageImportError, match="SHA-256 changed"):
        preflight_inventory(inventory, tmp_path, expected_allowlist=names)


@pytest.fixture
def import_db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = factory()

    class Settings:
        storage_root = tmp_path

    monkeypatch.setattr(reference_assets, "get_settings", lambda: Settings())
    project = Project(id=PROJECT_ID, name="Transfiguration", description=None)
    story = Story(
        id=STORY_ID,
        project_id=PROJECT_ID,
        title="Transfiguration",
        base_story="Source",
        target_duration_sec=300,
        approval_state="draft",
    )
    db.add_all((project, story))
    db.flush()
    chapter = Chapter(story_id=STORY_ID, order_index=0, title="Chapter", approval_state="draft")
    db.add(chapter)
    db.flush()
    scene = Scene(chapter_id=chapter.id, order_index=0, title="Scene", approval_state="draft")
    db.add(scene)
    db.flush()
    shots = []
    for index, code in enumerate(SHOT_CODES):
        shot = Shot(
            scene_id=scene.id,
            order_index=index,
            title=f"{code} — Test shot",
            duration_sec=7.5,
            starting_image_required=True,
            approval_state="draft",
        )
        db.add(shot)
        shots.append(shot)
    db.flush()

    records = []
    for index, (filename, kind) in enumerate(KNOWN_REFERENCE_KINDS.items(), 1):
        data = _png(index + 1, value=index)
        asset, _, _ = reference_assets.stage_asset_for_transaction(
            db,
            project_id=PROJECT_ID,
            kind=kind,
            data=data,
            original_filename=filename,
            content_type="image/png",
        )
        records.append(
            PreflightRecord(
                filename=filename,
                path=tmp_path / filename,
                data=data,
                sha256=hashlib.sha256(data).hexdigest(),
                mime_type="image/png",
                width=index + 1,
                height=2,
                classification=(
                    "character reference" if kind == "character_reference" else "art-direction reference"
                ),
                suggested_shot_code=None,
                confidence=1,
                rationale="Known reference",
                existing_asset_id=asset.id,
            )
        )
    candidate_data = _png(8, value=8)
    records.append(
        PreflightRecord(
            filename="candidate.png",
            path=tmp_path / "candidate.png",
            data=candidate_data,
            sha256=hashlib.sha256(candidate_data).hexdigest(),
            mime_type="image/png",
            width=8,
            height=2,
            classification="clean single-shot starting-image candidate",
            suggested_shot_code="S01A",
            confidence=0.95,
            rationale="Exact test composition",
            existing_asset_id=None,
        )
    )
    db.commit()
    mapping = {
        "schema_name": "cineforge.transfiguration_starting_image_mapping.v1",
        "project_id": str(PROJECT_ID),
        "entries": [
            {
                "shot_id": str(shot.id),
                "shot_code": code,
                "shot_title": shot.title,
                "selected_source_filename": "candidate.png" if index == 0 else None,
                "selected_sha256": records[-1].sha256 if index == 0 else None,
                "asset_id": None,
                "confidence": 0.95 if index == 0 else 0,
            }
            for index, (code, shot) in enumerate(zip(SHOT_CODES, shots))
        ],
    }
    yield db, records, mapping, shots, tmp_path
    db.close()
    engine.dispose()


def test_known_reference_and_collage_cannot_be_selected(import_db):
    db, records, mapping, _, _ = import_db
    mapping["entries"][0]["selected_source_filename"] = records[0].filename
    mapping["entries"][0]["selected_sha256"] = records[0].sha256
    with pytest.raises(StartingImageImportError, match="non-clean"):
        run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=False)

    mapping["entries"][0]["selected_source_filename"] = "candidate.png"
    mapping["entries"][0]["selected_sha256"] = records[-1].sha256
    records[-1] = PreflightRecord(
        **{**records[-1].__dict__, "classification": "collage/contact sheet/multi-panel board"}
    )
    with pytest.raises(StartingImageImportError, match="non-clean"):
        run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=False)


def test_mapping_rejects_duplicate_selection_and_unknown_shot(import_db):
    db, records, mapping, _, _ = import_db
    mapping["entries"][1]["selected_source_filename"] = "candidate.png"
    mapping["entries"][1]["selected_sha256"] = records[-1].sha256
    mapping["entries"][1]["confidence"] = 0.95
    with pytest.raises(StartingImageImportError, match="multiple shots"):
        run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=False)

    mapping["entries"][1]["selected_source_filename"] = None
    mapping["entries"][1]["selected_sha256"] = None
    mapping["entries"][1]["shot_id"] = str(uuid4())
    with pytest.raises(StartingImageImportError, match="unknown or duplicate shot"):
        run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=False)


def test_apply_preserves_draft_adds_audits_and_is_idempotent(import_db):
    db, records, mapping, shots, _ = import_db
    first = run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=True)
    asset = db.get(PlanningMediaAsset, shots[0].starting_image_asset_id)
    assert first["imported"] == 1
    assert first["assigned"] == 1
    assert first["audit_events_created"] > 0
    assert asset is not None and asset.approval_state == "draft"
    assert all(shot.approval_state == "draft" for shot in shots)
    audit_count = int(db.scalar(select(func.count()).select_from(AuditLog)) or 0)

    mapping["entries"][0]["asset_id"] = str(asset.id)
    second = run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=True)
    assert second["imported"] == 0
    assert second["reused"] == 1
    assert second["assigned"] == 0
    assert second["audit_events_created"] == 0
    assert int(db.scalar(select(func.count()).select_from(AuditLog)) or 0) == audit_count
    assert int(db.scalar(select(func.count()).select_from(PlanningMediaAsset)) or 0) == 4


def test_exact_sha_duplicate_is_reused_with_one_reuse_audit(import_db):
    db, records, mapping, _, _ = import_db
    candidate = records[-1]
    existing, created, _ = reference_assets.stage_asset_for_transaction(
        db,
        project_id=PROJECT_ID,
        kind="starting_image",
        data=candidate.data,
        original_filename=candidate.filename,
        content_type=candidate.mime_type,
    )
    assert created is True
    db.commit()

    result = run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=True)
    assert result["reused"] == 1
    assert result["source_asset_ids"][candidate.filename] == str(existing.id)
    assert len(list(db.scalars(select(AuditLog).where(
        AuditLog.action == "transfiguration_starting_image_candidate_reused"
    )))) == 1


def test_failure_rolls_back_rows_audits_assignments_and_new_bytes(import_db, monkeypatch):
    db, records, mapping, shots, tmp_path = import_db
    second_data = _png(9, value=9)
    records.insert(
        -1,
        PreflightRecord(
            filename="alternate.png",
            path=tmp_path / "alternate.png",
            data=second_data,
            sha256=hashlib.sha256(second_data).hexdigest(),
            mime_type="image/png",
            width=9,
            height=2,
            classification="alternate candidate for a shot",
            suggested_shot_code="S01A",
            confidence=0.8,
            rationale="Alternate",
            existing_asset_id=None,
        ),
    )
    original = reference_assets.stage_asset_for_transaction
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("forced staged import failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(reference_assets, "stage_asset_for_transaction", fail_second)
    with pytest.raises(RuntimeError, match="forced staged import failure"):
        run_import(db, project_id=PROJECT_ID, records=records, mapping=mapping, apply=True)

    assert shots[0].starting_image_asset_id is None
    assert int(db.scalar(select(func.count()).select_from(PlanningMediaAsset)) or 0) == 3
    assert int(db.scalar(select(func.count()).select_from(AuditLog)) or 0) == 0
    starting_dir = tmp_path / "planning_media" / str(PROJECT_ID) / "starting_image"
    assert not starting_dir.exists() or not list(starting_dir.iterdir())
