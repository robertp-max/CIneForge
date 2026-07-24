"""Tests for managed reference / planning media assets."""

from __future__ import annotations

import hashlib
import io
import struct
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    AuditLog,
    Base,
    Chapter,
    Character,
    CharacterReferenceAsset,
    PlanningMediaAsset,
    Project,
    Scene,
    Shot,
    Story,
    VoicePreview,
    VoiceProfile,
)
from backend.app.api.routes.assets import router as assets_router
from backend.app.db.session import get_db
from backend.app.services import reference_assets as assets
from backend.app.services import storyboard as storyboard_service


# Minimal valid 1x1 PNG
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01"  # width 1
    b"\x00\x00\x00\x01"  # height 1
    b"\x08\x02"  # bit depth / color type
    b"\x00\x00\x00"
    b"\x90wS\xde"  # placeholder CRC — header parse only needs IHDR layout
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_png(width: int = 2, height: int = 3) -> bytes:
    # Build a structurally valid PNG with correct IHDR CRC so Pillow/header parsers work.
    import binascii
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    # Raw image data: filter byte + RGB pixels per row
    raw = b""
    for _ in range(height):
        raw += b"\x00" + (b"\xff\x00\x00" * width)
    compressed = zlib.compress(raw)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(
        b"IEND", b""
    )


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()

    class _Settings:
        storage_root = Path(tmp_path)

    monkeypatch.setattr(assets, "get_settings", lambda: _Settings())

    project = Project(name="P1", description=None)
    session.add(project)
    session.commit()
    session.refresh(project)

    yield session, project
    session.close()


def _create_story_with_shot(session, project, *, asset_id, approval_state="approved"):
    story = Story(
        project_id=project.id,
        title="Asset-linked story",
        base_story="base",
        target_duration_sec=8,
        approval_state=approval_state,
    )
    session.add(story)
    session.flush()
    chapter = Chapter(story_id=story.id, order_index=0, title="Chapter")
    session.add(chapter)
    session.flush()
    scene = Scene(chapter_id=chapter.id, order_index=0, title="Scene")
    session.add(scene)
    session.flush()
    shot = Shot(
        scene_id=scene.id,
        order_index=0,
        title="Shot",
        duration_sec=8,
        starting_image_required=True,
        starting_image_asset_id=asset_id,
    )
    session.add(shot)
    session.commit()
    session.refresh(story)
    return story


def test_upload_character_reference_generates_managed_name_and_sha(db):
    session, project = db
    png = _make_png(4, 5)
    asset, created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="character_reference",
        data=png,
        original_filename="../../evil/portrait.PNG",
        content_type="image/png",
    )
    assert created is True
    assert asset.sha256 == hashlib.sha256(png).hexdigest()
    assert asset.width == 4
    assert asset.height == 5
    assert asset.original_filename == "portrait.PNG" or asset.original_filename == "portrait.PNG".replace(
        "..", ""
    )
    # Path components stripped — no traversal in stored original name.
    assert ".." not in (asset.original_filename or "")
    assert "/" not in (asset.original_filename or "")
    assert asset.managed_uri.startswith("cineforge-planning://")
    assert str(project.id) in asset.managed_uri
    path = assets.resolve_managed_path(asset)
    assert path.exists()
    assert path.name.endswith(".png")
    # Generated name is not the user-supplied name.
    assert path.name != "portrait.PNG"
    assert path.read_bytes() == png

    public = assets.to_public_dict(asset)
    assert "id" in public
    assert str(path) not in str(public.values())


def test_duplicate_sha_never_clones(db):
    session, project = db
    png = _make_png(2, 2)
    first, created1 = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="a.png",
        content_type="image/png",
    )
    second, created2 = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="b.png",
        content_type="image/png",
    )
    assert created1 is True
    assert created2 is False
    assert first.id == second.id
    # Only one DB row and one file.
    rows = list(session.query(PlanningMediaAsset).all()) if hasattr(session, "query") else list(
        session.scalars(session.query(PlanningMediaAsset) if False else __import__("sqlalchemy").select(PlanningMediaAsset))
    )
    from sqlalchemy import select

    rows = list(session.scalars(select(PlanningMediaAsset)))
    assert len(rows) == 1
    root = assets.managed_root()
    files = list(root.rglob("*.png"))
    assert len(files) == 1


def test_duplicate_reuse_repairs_missing_managed_file(db):
    session, project = db
    png = _make_png(7, 5)
    original, created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="character_reference",
        data=png,
        original_filename="hero.png",
        content_type="image/png",
    )
    path = assets.resolve_managed_path(original)
    path.unlink()

    repaired, created_again = assets.upload_asset(
        session,
        project_id=project.id,
        kind="character_reference",
        data=png,
        original_filename="hero-copy.png",
        content_type="image/png",
    )

    assert created is True
    assert created_again is False
    assert repaired.id == original.id
    assert path.read_bytes() == png
    assert repaired.size_bytes == len(png)
    assert (repaired.width, repaired.height) == (7, 5)
    assert len(list(session.scalars(__import__("sqlalchemy").select(PlanningMediaAsset)))) == 1
    repairs = list(
        session.scalars(
            __import__("sqlalchemy").select(AuditLog).where(
                AuditLog.action == "planning_media_asset_bytes_repaired"
            )
        )
    )
    assert len(repairs) == 1
    assert repairs[0].entity_id == original.id
    assert repairs[0].details["repair_reasons"] == ["managed_file_missing"]


def test_duplicate_reuse_repairs_corrupt_managed_file(db):
    session, project = db
    png = _make_png(9, 6)
    original, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="frame.png",
        content_type="image/png",
    )
    path = assets.resolve_managed_path(original)
    path.write_bytes(b"corrupt image bytes")

    repaired, created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="frame-copy.png",
        content_type="image/png",
    )

    assert created is False
    assert repaired.id == original.id
    assert path.read_bytes() == png
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original.sha256
    assert assets._image_bytes_are_decodable(path.read_bytes(), repaired.mime_type)
    repairs = list(
        session.scalars(
            __import__("sqlalchemy").select(AuditLog).where(
                AuditLog.action == "planning_media_asset_bytes_repaired"
            )
        )
    )
    assert repairs[-1].entity_id == original.id
    assert repairs[-1].details["repair_reasons"] == ["sha256_mismatch"]


def test_healthy_duplicate_reuse_does_not_rewrite_bytes(db):
    session, project = db
    png = _make_png(4, 4)
    original, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="healthy.png",
        content_type="image/png",
    )
    path = assets.resolve_managed_path(original)
    original_mtime = path.stat().st_mtime_ns

    reused, created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="healthy-copy.png",
        content_type="image/png",
    )

    assert created is False
    assert reused.id == original.id
    assert path.stat().st_mtime_ns == original_mtime
    actions = list(session.scalars(__import__("sqlalchemy").select(AuditLog.action)))
    assert "planning_media_asset_duplicate_reused" in actions
    assert "planning_media_asset_bytes_repaired" not in actions


def test_asset_content_returns_decodable_image_after_duplicate_repair(db):
    session, project = db
    png = _make_png(6, 4)
    original, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="stream.png",
        content_type="image/png",
    )
    assets.resolve_managed_path(original).unlink()
    repaired, created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="stream-copy.png",
        content_type="image/png",
    )
    assert created is False

    app = FastAPI()
    app.include_router(assets_router)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).get(f"/assets/{repaired.id}/content")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == png
    assert assets._image_bytes_are_decodable(response.content, response.headers["content-type"].split(";")[0])


def test_asset_content_fails_closed_when_file_sha_mismatches(db):
    session, project = db
    png = _make_png(5, 4)
    asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="corrupt-stream.png",
        content_type="image/png",
    )
    path = assets.resolve_managed_path(asset)
    path.write_bytes(b"wrong existing bytes")

    app = FastAPI()
    app.include_router(assets_router)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).get(f"/assets/{asset.id}/content")

    assert response.status_code == 422
    assert "failed SHA-256 verification" in response.json()["detail"]
    assert path.read_bytes() == b"wrong existing bytes"


def test_same_bytes_in_different_asset_kinds_remain_distinct(db):
    session, project = db
    png = _make_png(3, 3)

    starting_image, starting_created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="shot.png",
        content_type="image/png",
    )
    character_reference, reference_created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="character_reference",
        data=png,
        original_filename="hero.png",
        content_type="image/png",
    )

    starting_reuse, starting_recreated = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="shot-copy.png",
        content_type="image/png",
    )
    reference_reuse, reference_recreated = assets.upload_asset(
        session,
        project_id=project.id,
        kind="character_reference",
        data=png,
        original_filename="hero-copy.png",
        content_type="image/png",
    )

    assert starting_created is True
    assert reference_created is True
    assert starting_image.id != character_reference.id
    assert starting_image.kind == "starting_image"
    assert character_reference.kind == "character_reference"
    assert starting_recreated is False
    assert reference_recreated is False
    assert starting_reuse.id == starting_image.id
    assert reference_reuse.id == character_reference.id

    from sqlalchemy import select

    rows = list(session.scalars(select(PlanningMediaAsset)))
    assert {(row.kind, row.sha256) for row in rows} == {
        ("starting_image", hashlib.sha256(png).hexdigest()),
        ("character_reference", hashlib.sha256(png).hexdigest()),
    }
    assert assets.resolve_managed_path(starting_image).is_file()
    assert assets.resolve_managed_path(character_reference).is_file()


def test_rejects_bad_mime_extension_and_oversize(db):
    session, project = db
    with pytest.raises(assets.ReferenceAssetError, match="Extension"):
        assets.upload_asset(
            session,
            project_id=project.id,
            kind="character_reference",
            data=_make_png(),
            original_filename="x.exe",
            content_type="image/png",
        )
    with pytest.raises(assets.ReferenceAssetError, match="MIME"):
        assets.upload_asset(
            session,
            project_id=project.id,
            kind="character_reference",
            data=_make_png(),
            original_filename="x.png",
            content_type="application/octet-stream",
        )
    with pytest.raises(assets.ReferenceAssetError, match="maximum size"):
        assets.upload_asset(
            session,
            project_id=project.id,
            kind="story_document",
            data=b"x" * (10 * 1024 * 1024 + 1),
            original_filename="big.txt",
            content_type="text/plain",
        )


def test_voice_source_requires_consent(db):
    session, project = db
    # Minimal WAV header-ish bytes won't fully parse duration, but allowlist is wav.
    wav = b"RIFF" + struct.pack("<I", 36) + b"WAVEfmt " + (b"\x00" * 24) + b"data" + struct.pack("<I", 0)
    with pytest.raises(assets.ReferenceAssetError, match="consent"):
        assets.upload_asset(
            session,
            project_id=project.id,
            kind="voice_source",
            data=wav,
            original_filename="voice.wav",
            content_type="audio/wav",
            consent_confirmed=False,
        )


def test_raw_body_upload_route_needs_no_multipart_dependency(db):
    session, project = db
    app = FastAPI()
    app.include_router(assets_router)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    response = client.post(
        f"/assets/projects/{project.id}/upload",
        params={"kind": "story_document", "original_filename": "notes.md"},
        content=b"# Managed story notes\n",
        headers={"Content-Type": "text/markdown"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["asset"]["managed_uri"].startswith("cineforge-planning://")
    assert "storage_root" not in response.text

    duplicate = client.post(
        f"/assets/projects/{project.id}/upload",
        params={"kind": "story_document", "original_filename": "copy.md"},
        content=b"# Managed story notes\n",
        headers={"Content-Type": "text/markdown"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate_of_existing"] is True


def test_story_document_upload_and_archive_delete_policy(db):
    session, project = db
    text = b"# Story notes\nOnce upon a time.\n"
    asset, created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="story_document",
        data=text,
        original_filename="notes.md",
        content_type="text/markdown",
    )
    assert created is True

    with pytest.raises(assets.ReferenceAssetError, match="archived"):
        assets.delete_asset(session, asset.id)

    archived = assets.archive_asset(session, asset.id, reason="cleanup")
    assert archived.archived_at is not None
    assert archived.approval_state == "archived"

    path = assets.resolve_managed_path(archived)
    assert path.exists()
    assets.delete_asset(session, asset.id, reason="purge")
    assert session.get(PlanningMediaAsset, asset.id) is None
    assert not path.exists()

    audits = list(session.scalars(__import__("sqlalchemy").select(AuditLog)))
    actions = {a.action for a in audits}
    assert "planning_media_asset_uploaded" in actions
    assert "planning_media_asset_archived" in actions
    assert "planning_media_asset_deleted" in actions


def test_starting_image_approval_transitions_same_managed_record_with_audit(db):
    session, project = db
    asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=_make_png(8, 6),
        original_filename="candidate.png",
        content_type="image/png",
    )
    asset_id = asset.id
    managed_uri = asset.managed_uri
    managed_path = assets.resolve_managed_path(asset)
    story = _create_story_with_shot(session, project, asset_id=asset.id)

    reviewed = assets.transition_starting_image_approval(
        session,
        asset.id,
        approval_state="in_review",
        expected_approval_state="draft",
        reason="Ready for producer review",
        changed_by="test-reviewer",
    )
    approved = assets.transition_starting_image_approval(
        session,
        asset.id,
        approval_state="approved",
        expected_approval_state="in_review",
        reason="Approved in Starting Images",
        changed_by="test-reviewer",
    )

    assert reviewed.id == approved.id == asset_id
    assert approved.managed_uri == managed_uri
    assert assets.resolve_managed_path(approved) == managed_path
    assert managed_path.is_file()
    assert approved.approval_state == "approved"
    session.refresh(story)
    assert story.approval_state == "draft"

    aggregate = storyboard_service.aggregate(session, story.id)
    aggregate_shot = aggregate["chapters"][0]["scenes"][0]["shots"][0]
    assert aggregate_shot["starting_image_required"] is True
    assert aggregate_shot["starting_image_asset_id"] == str(asset_id)

    audits = list(
        session.scalars(
            __import__("sqlalchemy").select(AuditLog).where(
                AuditLog.action == "planning_media_asset_approval_transitioned"
            )
        )
    )
    assert [row.details["approval_state"] for row in audits] == ["in_review", "approved"]
    assert audits[-1].details["previous_approval_state"] == "in_review"
    assert audits[-1].details["changed_by"] == "test-reviewer"

    with pytest.raises(assets.ReferenceAssetConflictError, match="Refresh and retry"):
        assets.transition_starting_image_approval(
            session,
            asset.id,
            approval_state="blocked",
            expected_approval_state="draft",
        )
    assert assets.get_asset(session, asset.id).approval_state == "approved"


def test_starting_image_approval_route_rejects_wrong_kind_and_archived_asset(db):
    session, project = db
    image, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=_make_png(),
        original_filename="candidate.png",
        content_type="image/png",
    )
    document, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="story_document",
        data=b"notes",
        original_filename="notes.txt",
        content_type="text/plain",
    )

    app = FastAPI()
    app.include_router(assets_router)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    approved = client.patch(
        f"/assets/{image.id}/starting-image-approval",
        json={
            "approval_state": "approved",
            "expected_approval_state": "draft",
            "reason": "Explicit UI approval",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["id"] == str(image.id)
    assert approved.json()["approval_state"] == "approved"

    stale = client.patch(
        f"/assets/{image.id}/starting-image-approval",
        json={"approval_state": "blocked", "expected_approval_state": "draft"},
    )
    assert stale.status_code == 409
    assert "Refresh and retry" in stale.json()["detail"]

    wrong_kind = client.patch(
        f"/assets/{document.id}/starting-image-approval",
        json={"approval_state": "approved", "expected_approval_state": "draft"},
    )
    assert wrong_kind.status_code == 422
    assert "Only starting_image assets" in wrong_kind.json()["detail"]

    assets.archive_asset(session, image.id, reason="Retired candidate")
    archived = client.patch(
        f"/assets/{image.id}/starting-image-approval",
        json={"approval_state": "draft", "expected_approval_state": "approved"},
    )
    assert archived.status_code == 409
    session.refresh(image)
    assert image.approval_state == "archived"
    assert image.archived_at is not None


def test_path_escape_rejected_on_resolve(db):
    session, project = db
    asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=_make_png(),
        original_filename="ok.png",
        content_type="image/png",
    )
    asset.managed_uri = f"cineforge-planning://{project.id}/starting_image/../../etc/passwd"
    session.commit()
    with pytest.raises(assets.ReferenceAssetError):
        assets.resolve_managed_path(asset)


def test_character_reference_link_and_project_guard(db):
    session, project = db
    story = Story(
        project_id=project.id,
        title="T",
        base_story="base",
        target_duration_sec=60,
        approval_state="approved",
    )
    session.add(story)
    session.commit()
    session.refresh(story)
    character = Character(story_id=story.id, name="Hero")
    session.add(character)
    session.commit()
    session.refresh(character)

    asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="character_reference",
        data=_make_png(),
        original_filename="hero.png",
        content_type="image/png",
    )
    link = assets.link_character_reference(
        session,
        character_id=character.id,
        asset_id=asset.id,
        reference_role="primary",
        order_index=0,
    )
    assert link.asset_id == asset.id
    session.refresh(story)
    assert story.approval_state == "draft"
    listed = assets.list_character_references(session, character.id)
    assert len(listed) == 1

    with pytest.raises(assets.ReferenceAssetConflictError):
        assets.link_character_reference(
            session,
            character_id=character.id,
            asset_id=asset.id,
            order_index=0,
        )

    # Wrong kind cannot link.
    doc, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="story_document",
        data=b"hello",
        original_filename="a.txt",
        content_type="text/plain",
    )
    with pytest.raises(assets.ReferenceAssetError, match="character_reference"):
        assets.link_character_reference(
            session,
            character_id=character.id,
            asset_id=doc.id,
            order_index=1,
        )

    story.approval_state = "approved"
    session.commit()
    assets.unlink_character_reference(session, link.id)
    session.refresh(story)
    assert story.approval_state == "draft"
    assert assets.list_character_references(session, character.id) == []


def test_archive_and_delete_revoke_story_using_starting_image(db):
    session, project = db
    png = _make_png()
    asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="linked.png",
        content_type="image/png",
    )
    story = _create_story_with_shot(session, project, asset_id=asset.id)

    assets.archive_asset(session, asset.id, reason="Retire linked image")
    session.refresh(story)
    assert story.approval_state == "draft"

    story.approval_state = "approved"
    session.commit()
    reused, created = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=png,
        original_filename="linked-reuse.png",
        content_type="image/png",
    )
    assert created is False
    assert reused.id == asset.id
    assert reused.archived_at is None
    session.refresh(story)
    assert story.approval_state == "draft"

    assets.archive_asset(session, asset.id, reason="Retire linked image again")
    story.approval_state = "approved"
    session.commit()
    assets.delete_asset(session, asset.id, reason="Remove linked image")
    session.refresh(story)
    assert story.approval_state == "draft"


def test_archive_resolves_voice_source_selected_asset_and_preview_story(db):
    session, project = db
    wav = b"RIFF" + struct.pack("<I", 36) + b"WAVEfmt " + (b"\x00" * 24) + b"data" + struct.pack("<I", 0)
    source_asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="voice_source",
        data=wav,
        original_filename="source.wav",
        content_type="audio/wav",
        consent_confirmed=True,
    )
    preview_asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="voice_source",
        data=wav + b"preview",
        original_filename="preview.wav",
        content_type="audio/wav",
        consent_confirmed=True,
    )
    story = Story(
        project_id=project.id,
        title="Voice asset story",
        base_story="base",
        target_duration_sec=10,
        approval_state="approved",
    )
    session.add(story)
    session.flush()
    profile = VoiceProfile(
        story_id=story.id,
        name="Narrator",
        source_type="user_provided_consented",
        source_asset_id=source_asset.id,
        selected_preview_asset_id=preview_asset.id,
        consent_required=True,
        consent_confirmed=True,
        approval_state="approved",
    )
    session.add(profile)
    session.flush()
    preview = VoicePreview(
        voice_profile_id=profile.id,
        planning_media_asset_id=preview_asset.id,
        selected=True,
        rejected=False,
    )
    session.add(preview)
    session.commit()

    assets.archive_asset(session, source_asset.id, reason="Retire source")
    session.refresh(story)
    assert story.approval_state == "draft"

    story.approval_state = "approved"
    session.commit()
    assets.archive_asset(session, preview_asset.id, reason="Retire preview")
    session.refresh(story)
    assert story.approval_state == "draft"


def test_unreferenced_upload_does_not_revoke_story_approval(db):
    session, project = db
    story = Story(
        project_id=project.id,
        title="Unaffected story",
        base_story="base",
        target_duration_sec=10,
        approval_state="approved",
    )
    session.add(story)
    session.commit()

    assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=_make_png(),
        original_filename="unreferenced.png",
        content_type="image/png",
    )
    session.refresh(story)
    assert story.approval_state == "approved"


def test_upload_from_fileobj_bounds_read(db):
    session, project = db
    data = b"hello world document"
    asset, created = assets.upload_asset_from_fileobj(
        session,
        project_id=project.id,
        kind="story_document",
        fileobj=io.BytesIO(data),
        original_filename="doc.txt",
        content_type="text/plain",
    )
    assert created is True
    assert asset.size_bytes == len(data)

    huge = io.BytesIO(b"x" * (10 * 1024 * 1024 + 50))
    with pytest.raises(assets.ReferenceAssetError, match="maximum size"):
        assets.upload_asset_from_fileobj(
            session,
            project_id=project.id,
            kind="story_document",
            fileobj=huge,
            original_filename="huge.txt",
            content_type="text/plain",
        )


def test_open_stream_by_asset_id_only(db):
    session, project = db
    asset, _ = assets.upload_asset(
        session,
        project_id=project.id,
        kind="starting_image",
        data=_make_png(1, 1),
        original_filename="frame.png",
        content_type="image/png",
    )
    got, path = assets.open_asset_for_stream(session, asset.id)
    assert got.id == asset.id
    assert path.is_file()

    assets.archive_asset(session, asset.id)
    with pytest.raises(assets.ReferenceAssetNotFoundError):
        assets.open_asset_for_stream(session, asset.id)
