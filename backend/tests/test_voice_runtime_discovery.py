"""Tests for factual voice provider discovery (no model loading)."""
from __future__ import annotations

import os
from unittest import mock

from backend.app.schemas.voice import PARLER_UNAVAILABLE_MESSAGE
from backend.app.services.runtime.discovery import (
    discover_all_voice_providers,
    discover_parler,
    discover_provider,
    discover_qwen_runtime,
)


def test_discover_all_includes_supported_providers():
    results = discover_all_voice_providers()
    names = {item.provider for item in results}
    assert "placeholder" in names
    assert "manual" in names
    assert "qwen" in names
    assert "qwen_custom_voice" in names
    assert "elevenlabs" in names
    assert "parler" in names
    assert "user_provided_consented" in names
    for item in results:
        assert item.details.get("loads_models_on_discover") in {False, None} or (
            item.details.get("loads_models_on_discover") is False
        )


def test_placeholder_and_manual_always_available():
    for name in ("placeholder", "manual", "existing_provider_voice", "user_provided_consented"):
        ev = discover_provider(name)
        assert ev.available is True
        assert ev.status == "available"


def test_qwen_discovery_without_config_is_not_configured():
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("CINEFORGE_QWEN") and not k.startswith("QWEN_")
    }
    with mock.patch.dict(os.environ, env, clear=True):
        ev = discover_qwen_runtime()
    assert ev.available is False
    assert ev.status in {"not_configured", "unavailable"}
    assert ev.details.get("loads_models_on_discover") is False
    assert ev.details.get("will_install_or_download") is False
    assert ev.details.get("reuse_existing_runtime_only") is True


def test_qwen_discovery_reuses_configured_runtime_ref_only():
    with mock.patch.dict(
        os.environ,
        {
            "CINEFORGE_QWEN_RUNTIME_REF": "existing://qwen-runtime",
            "CINEFORGE_QWEN_VOICE_MODEL": "qwen-voice-demo",
        },
        clear=False,
    ):
        ev = discover_qwen_runtime()
    assert ev.available is True
    assert ev.status == "available"
    assert ev.details["runtime_ref"] == "existing://qwen-runtime"
    assert ev.details["configured_model"] == "qwen-voice-demo"
    assert ev.details["loads_models_on_discover"] is False


def test_qwen_custom_voice_discovery_marks_preset_only():
    with mock.patch.dict(
        os.environ,
        {"CINEFORGE_QWEN_RUNTIME_REF": "existing://qwen-runtime"},
        clear=False,
    ):
        ev = discover_provider("qwen_custom_voice")
    assert ev.provider == "qwen_custom_voice"
    assert ev.details.get("supports_cloning") is False
    assert ev.details.get("supports_reference_audio") is False
    assert ev.details.get("custom_voice_mode") == "preset_speaker_only"


def test_parler_unavailable_exact_message():
    with mock.patch.dict(os.environ, {"CINEFORGE_PARLER_APPROVED": "0"}, clear=False):
        with mock.patch(
            "backend.app.services.voice_design.providers.parler._parler_installed",
            return_value=False,
        ):
            ev = discover_parler()
    assert ev.available is False
    assert ev.message == PARLER_UNAVAILABLE_MESSAGE


def test_parler_installed_but_not_approved_exact_message():
    with mock.patch.dict(os.environ, {"CINEFORGE_PARLER_APPROVED": "false"}, clear=False):
        with mock.patch(
            "backend.app.services.voice_design.providers.parler._parler_installed",
            return_value=True,
        ):
            ev = discover_provider("parler")
    assert ev.available is False
    assert ev.message == PARLER_UNAVAILABLE_MESSAGE


def test_elevenlabs_without_key_not_configured():
    env = {
        k: v
        for k, v in os.environ.items()
        if "ELEVENLABS" not in k
    }
    with mock.patch.dict(os.environ, env, clear=True):
        ev = discover_provider("elevenlabs")
    assert ev.available is False
    assert ev.status == "not_configured"
