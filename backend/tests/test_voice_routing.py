"""Tests for voice routing recommendations."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.app.schemas.voice import (
    NativeVoiceCapability,
    VoiceRoutingAction,
    VoiceRoutingRequest,
)
from backend.app.services.routing.voice_routing import (
    recommend_voice_routing,
    read_native_voice_capability,
)


@dataclass
class FakeModel:
    id: uuid.UUID
    family: str


@dataclass
class FakeVariant:
    id: uuid.UUID
    model_id: uuid.UUID
    variant_name: str
    native_voice_capability: str = "unknown"
    native_voice_capability_source: str | None = None
    native_voice_capability_metadata_json: dict = field(default_factory=dict)
    native_voice_capability_checked_at: datetime | None = None


class FakeDB:
    def __init__(self, objects: dict[uuid.UUID, Any]):
        self._objects = objects

    def get(self, model, ident):  # noqa: ANN001
        obj = self._objects.get(ident)
        if obj is None:
            return None
        # Light type gate by class name fragment.
        name = getattr(model, "__name__", str(model))
        if "ModelVariant" in name and not isinstance(obj, FakeVariant):
            return None
        if name == "Model" and not isinstance(obj, FakeModel):
            return None
        return obj


def test_unknown_capability_no_qwen_recommendation():
    variant_id = uuid.uuid4()
    model_id = uuid.uuid4()
    db = FakeDB(
        {
            variant_id: FakeVariant(
                id=variant_id,
                model_id=model_id,
                variant_name="demo",
                native_voice_capability="unknown",
            ),
            model_id: FakeModel(id=model_id, family="ltx"),
        }
    )
    result = recommend_voice_routing(
        db,
        VoiceRoutingRequest(story_id=uuid.uuid4(), model_variant_id=variant_id),
    )
    assert result.recommend_qwen is False
    assert result.action == VoiceRoutingAction.none
    assert result.native_voice_capability == NativeVoiceCapability.unknown
    assert result.blocked_reason == "native_speech_unknown"


def test_unsupported_recommends_qwen():
    variant_id = uuid.uuid4()
    model_id = uuid.uuid4()
    db = FakeDB(
        {
            variant_id: FakeVariant(
                id=variant_id,
                model_id=model_id,
                variant_name="silent-video",
                native_voice_capability="unsupported",
                native_voice_capability_source="catalog",
            ),
            model_id: FakeModel(id=model_id, family="wan"),
        }
    )
    result = recommend_voice_routing(
        db,
        VoiceRoutingRequest(story_id=uuid.uuid4(), model_variant_id=variant_id),
    )
    assert result.recommend_qwen is True
    assert result.action == VoiceRoutingAction.recommend_qwen
    assert result.provider_suggestion == "qwen"
    assert result.native_voice_capability == NativeVoiceCapability.unsupported


def test_supported_native_including_ltx_no_qwen():
    variant_id = uuid.uuid4()
    model_id = uuid.uuid4()
    db = FakeDB(
        {
            variant_id: FakeVariant(
                id=variant_id,
                model_id=model_id,
                variant_name="ltx-2-native",
                native_voice_capability="supported",
                native_voice_capability_source="vendor_docs",
            ),
            model_id: FakeModel(id=model_id, family="ltx"),
        }
    )
    result = recommend_voice_routing(
        db,
        VoiceRoutingRequest(story_id=uuid.uuid4(), model_variant_id=variant_id),
    )
    assert result.recommend_qwen is False
    assert result.action == VoiceRoutingAction.keep_native
    assert result.blocked_reason == "native_speech_supported"
    assert "LTX" in result.rationale or "native" in result.rationale.lower()


def test_approved_assignment_never_overwritten():
    db = FakeDB({})
    result = recommend_voice_routing(
        db,
        VoiceRoutingRequest(
            story_id=uuid.uuid4(),
            model_variant_id=None,
            existing_assignment_approved=True,
            existing_provider="elevenlabs",
        ),
    )
    assert result.recommend_qwen is False
    assert result.action == VoiceRoutingAction.keep_approved
    assert result.provider_suggestion == "elevenlabs"
    assert result.blocked_reason == "approved_assignment_immutable"


def test_read_native_missing_variant_is_unknown():
    db = FakeDB({})
    read = read_native_voice_capability(db, model_variant_id=uuid.uuid4())
    assert read.native_voice_capability == NativeVoiceCapability.unknown
