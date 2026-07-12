"""Tests for planning asset registration (IDs/URIs only)."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.app.schemas.voice import PlanningAssetRegisterRequest
from backend.app.services.planning_assets import (
    PlanningAssetError,
    register_planning_asset,
    register_voice_preview_asset,
)


class _MemDB:
    def __init__(self):
        self.rows: dict[uuid.UUID, object] = {}
        self.pending: list[object] = []

    def add(self, obj):
        self.pending.append(obj)

    def commit(self):
        for obj in self.pending:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            self.rows[obj.id] = obj
        self.pending.clear()

    def refresh(self, obj):
        return obj

    def get(self, model, ident):  # noqa: ANN001
        return self.rows.get(ident)

    def scalars(self, stmt):  # noqa: ANN001
        class _R:
            def __init__(self, items):
                self._items = items

            def first(self):
                return self._items[0] if self._items else None

        return _R([])


@pytest.fixture
def asset_db(monkeypatch):
    from backend.app.services import planning_assets as pa

    def factory(**kwargs):
        obj = SimpleNamespace(**kwargs)
        obj.id = None
        return obj

    monkeypatch.setattr(pa, "PlanningMediaAsset", factory)
    return _MemDB()


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
        managed_uri="/storage/voice_previews/demo.json",
        sha256="a" * 64,
        mime_type="application/json",
        provider="qwen",
        model="demo",
        extra_metadata={"preview_kind": "marker"},
    )
    assert asset.kind == "voice_preview"
    assert asset.managed_uri.endswith("demo.json")
    assert "audio" not in (asset.metadata_json or {})
    assert asset.metadata_json.get("provider") == "qwen"


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
