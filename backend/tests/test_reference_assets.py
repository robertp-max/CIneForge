"""Tests for managed reference / planning media assets."""

from __future__ import annotations

import hashlib
import io
import struct
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    AuditLog,
    Base,
    Character,
    CharacterReferenceAsset,
    PlanningMediaAsset,
    Project,
    Story,
)
from backend.app.services import reference_assets as assets


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

    assets.unlink_character_reference(session, link.id)
    assert assets.list_character_references(session, character.id) == []


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
