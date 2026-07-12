"""Safety contract for the public Storyboard Phase 1 voice API."""
from __future__ import annotations

import subprocess
from collections.abc import Generator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.routes import voices as voice_routes
from backend.app.db.base import (
    Base,
    GpuResourceLease,
    PlanningMediaAsset,
    Project,
    Story,
    VoicePreview,
    VoiceProfile,
)
from backend.app.db.session import get_db
from backend.app.schemas.voice import PARLER_UNAVAILABLE_MESSAGE
from backend.app.services.comfy.client import ComfyUIClient
from backend.app.services.ffmpeg.service import FFmpegService
from backend.app.services.runtime import gpu_leases
from backend.app.services.voice_design.providers.elevenlabs import (
    ElevenLabsVoiceDesignProvider,
)
from backend.app.services.voice_design.providers.existing import ExistingProviderVoiceProvider
from backend.app.services.voice_design.providers.parler import ParlerLocalVoiceDesignProvider
from backend.app.services.voice_design.providers.placeholder import (
    ManualVoiceProvider,
    PlaceholderVoiceProvider,
)
from backend.app.services.voice_design.providers.qwen import (
    QwenCustomVoiceProvider,
    QwenVoiceDesignProvider,
)
from backend.app.services.voice_design.providers.user_provided import (
    UserProvidedConsentedProvider,
)
from backend.app.workers import voice_preview


@dataclass
class VoiceApiHarness:
    client: TestClient
    story_id: UUID
    sessions: sessionmaker[Session]


@pytest.fixture
def voice_api(tmp_path) -> Generator[VoiceApiHarness, None, None]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'voice-api.db').as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    sessions = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    Base.metadata.create_all(engine)

    with sessions() as db:
        project = Project(name="Voice safety project", description=None)
        db.add(project)
        db.flush()
        story = Story(
            project_id=project.id,
            title="Voice safety story",
            base_story="A bounded planning-only story.",
            target_duration_sec=60,
        )
        db.add(story)
        db.commit()
        story_id = story.id

    app = FastAPI()
    app.include_router(voice_routes.router)

    def override_get_db() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield VoiceApiHarness(client=client, story_id=story_id, sessions=sessions)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_profile(voice_api: VoiceApiHarness, payload: dict) -> dict:
    response = voice_api.client.post(
        f"/voices/stories/{voice_api.story_id}/profiles",
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _forbid_preview_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        pytest.fail("A public voice preview request attempted an execution side effect.")

    monkeypatch.setattr(voice_preview, "run_voice_preview_job", forbidden)
    monkeypatch.setattr(gpu_leases, "acquire_voice_preview_lease", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(FFmpegService, "ffprobe_asset", forbidden)
    monkeypatch.setattr(FFmpegService, "save_probe_json", forbidden)
    monkeypatch.setattr(ComfyUIClient, "submit_prompt", forbidden)
    monkeypatch.setattr(ComfyUIClient, "upload_image", forbidden)

    provider_types = (
        PlaceholderVoiceProvider,
        ManualVoiceProvider,
        ExistingProviderVoiceProvider,
        QwenVoiceDesignProvider,
        QwenCustomVoiceProvider,
        ElevenLabsVoiceDesignProvider,
        ParlerLocalVoiceDesignProvider,
        UserProvidedConsentedProvider,
    )
    for provider_type in provider_types:
        monkeypatch.setattr(provider_type, "generate_preview", forbidden)


def test_public_router_excludes_internal_asset_and_gpu_controls(voice_api):
    paths = {route.path for route in voice_routes.router.routes}
    assert not any(path.startswith("/voices/planning-assets") for path in paths)
    assert not any(path.startswith("/voices/gpu-leases") for path in paths)

    assert voice_api.client.post("/voices/planning-assets", json={}).status_code == 404
    assert voice_api.client.get(f"/voices/planning-assets/{uuid4()}").status_code == 404
    assert voice_api.client.post("/voices/gpu-leases", json={}).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Placeholder", "setup_mode": "placeholder"},
        {"name": "Manual", "setup_mode": "manual"},
        {
            "name": "Existing provider",
            "setup_mode": "existing_provider_voice",
            "provider": "elevenlabs",
            "provider_voice_reference": "approved-library-voice",
        },
    ],
)
def test_non_generating_profile_setup_modes_remain_available(voice_api, payload):
    created = _create_profile(voice_api, payload)
    assert created["setup_mode"] == payload["setup_mode"]
    assert created["provider_configuration_status"] == "available"


def test_list_profiles_and_patch_revalidate_complete_mode_contract(voice_api):
    profile = _create_profile(
        voice_api,
        {"name": "Draft manual", "setup_mode": "manual"},
    )

    listed = voice_api.client.get(f"/voices/stories/{voice_api.story_id}/profiles")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [profile["id"]]

    missing_provider_reference = voice_api.client.patch(
        f"/voices/profiles/{profile['id']}",
        json={"setup_mode": "existing_provider_voice"},
    )
    assert missing_provider_reference.status_code == 422
    assert "provider" in missing_provider_reference.text

    missing_preset_speaker = voice_api.client.patch(
        f"/voices/profiles/{profile['id']}",
        json={"setup_mode": "qwen_custom_voice"},
    )
    assert missing_preset_speaker.status_code == 422
    assert "custom_voice_speaker" in missing_preset_speaker.text


def test_approval_revalidates_persisted_mode_invariants(voice_api):
    profile = _create_profile(
        voice_api,
        {"name": "Draft manual", "setup_mode": "manual"},
    )
    with voice_api.sessions() as db:
        row = db.get(VoiceProfile, UUID(profile["id"]))
        assert row is not None
        row.setup_mode = "existing_provider_voice"
        row.provider = None
        row.provider_voice_reference = None
        db.commit()

    response = voice_api.client.post(
        f"/voices/profiles/{profile['id']}/approve",
        json={"approved_by": "Producer", "allow_without_preview": True},
    )
    assert response.status_code == 422
    assert "existing_provider_voice requires provider" in response.text


def test_provider_discovery_remains_read_only_with_exact_parler_absence(
    voice_api,
    monkeypatch,
):
    _forbid_preview_side_effects(monkeypatch)
    monkeypatch.setenv("CINEFORGE_PARLER_APPROVED", "0")
    monkeypatch.setenv("CINEFORGE_QWEN_RUNTIME_REF", "C:/private/local/qwen-runtime")
    monkeypatch.setattr(
        "backend.app.services.voice_design.providers.parler._parler_installed",
        lambda: False,
    )

    response = voice_api.client.get("/voices/providers/discovery")

    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()["providers"]}
    assert set(providers) == {
        "placeholder",
        "manual",
        "existing_provider_voice",
        "qwen",
        "qwen_custom_voice",
        "elevenlabs",
        "parler",
        "user_provided_consented",
    }
    assert providers["parler"]["message"] == PARLER_UNAVAILABLE_MESSAGE
    assert providers["qwen"]["details"]["runtime_ref_present"] is True
    assert "runtime_ref" not in providers["qwen"]["details"]
    assert "C:/private/local/qwen-runtime" not in response.text


def test_preview_request_is_truthfully_unavailable_and_has_no_side_effects(
    voice_api,
    monkeypatch,
):
    _forbid_preview_side_effects(monkeypatch)
    profile = _create_profile(
        voice_api,
        {
            "name": "Qwen design",
            "setup_mode": "qwen_voice_design",
            "design_description": "Warm and grounded",
        },
    )

    response = voice_api.client.post(
        f"/voices/profiles/{profile['id']}/previews",
        json={"preview_text": "This must not execute."},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": voice_routes.PREVIEW_WORKER_UNAVAILABLE_MESSAGE}
    assert response.headers["content-type"].startswith("application/json")
    assert "planning_media_asset_id" not in response.json()

    with voice_api.sessions() as db:
        assert db.scalar(select(func.count()).select_from(VoicePreview)) == 0
        assert db.scalar(select(func.count()).select_from(PlanningMediaAsset)) == 0
        assert db.scalar(select(func.count()).select_from(GpuResourceLease)) == 0


def test_parler_preview_request_uses_exact_unavailable_message(
    voice_api,
    monkeypatch,
):
    _forbid_preview_side_effects(monkeypatch)
    monkeypatch.setenv("CINEFORGE_PARLER_APPROVED", "0")
    monkeypatch.setattr(
        "backend.app.services.voice_design.providers.parler._parler_installed",
        lambda: False,
    )
    profile = _create_profile(
        voice_api,
        {
            "name": "Optional Parler",
            "setup_mode": "parler_local_voice_design",
            "design_description": "Calm local narrator",
        },
    )

    response = voice_api.client.post(
        f"/voices/profiles/{profile['id']}/previews",
        json={"preview_text": "This also must not execute."},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": PARLER_UNAVAILABLE_MESSAGE}
