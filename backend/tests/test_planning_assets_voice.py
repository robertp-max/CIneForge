"""Tests for planning asset registration (IDs/URIs only)."""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base, PlanningMediaAsset, Project
from backend.app.schemas.voice import PlanningAssetRegisterRequest
from backend.app.services.planning_assets import (
    PlanningAssetError,
    register_planning_asset,
    register_voice_preview_asset,
)


@pytest.fixture
def asset_db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(
        bind=engine,
        tables=[Project.__table__, PlanningMediaAsset.__table__],
    )
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_register_rejects_data_uri():
    with pytest.raises(ValidationError):
        PlanningAssetRegisterRequest(
            project_id=uuid.uuid4(),
            kind="voice_preview",
            source_type="test",
            managed_uri="data:audio/wav;base64,AAAA",
        )


def test_register_rejects_embedded_metadata_payloads():
    with pytest.raises(ValidationError):
        PlanningAssetRegisterRequest(
            project_id=uuid.uuid4(),
            kind="voice_preview",
            source_type="test",
            managed_uri="file://preview.wav",
            metadata={"audio_base64": "AAAA"},
        )


def test_register_voice_preview_asset_stores_uri_only(asset_db):
    asset = register_voice_preview_asset(
        asset_db,
        project_id=uuid.uuid4(),
        managed_uri="/storage/voice_previews/demo.wav",
        sha256="a" * 64,
        mime_type="audio/wav",
        provider="qwen",
        model="demo",
        extra_metadata={"preview_kind": "generated_audio"},
    )
    assert asset.kind == "voice_preview"
    assert asset.managed_uri.endswith("demo.wav")
    assert "audio" not in (asset.metadata_json or {})
    assert asset.metadata_json.get("provider") == "qwen"


@pytest.mark.parametrize(
    ("managed_uri", "mime_type"),
    [
        ("/storage/voice_previews/demo.json", "application/json"),
        ("/storage/voice_previews/demo.json", "audio/wav"),
        ("/storage/voice_previews/demo.wav", None),
    ],
)
def test_register_voice_preview_asset_rejects_false_success_markers(
    asset_db,
    managed_uri,
    mime_type,
):
    with pytest.raises(PlanningAssetError, match="must reference generated audio"):
        register_voice_preview_asset(
            asset_db,
            project_id=uuid.uuid4(),
            managed_uri=managed_uri,
            mime_type=mime_type,
            provider="qwen",
            model="demo",
        )


def test_register_planning_asset_happy_path(asset_db):
    payload = PlanningAssetRegisterRequest(
        project_id=uuid.uuid4(),
        kind="voice_source",
        source_type="upload",
        managed_uri="planning://assets/abc",
        sha256="b" * 64,
        mime_type="audio/wav",
        size_bytes=12,
        metadata={"note": "ref-only"},
    )
    asset = register_planning_asset(asset_db, payload)
    assert asset.sha256 == "b" * 64
    assert asset.metadata_json["note"] == "ref-only"
