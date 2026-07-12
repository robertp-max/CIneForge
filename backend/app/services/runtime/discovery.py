"""Factual provider/runtime discovery without loading models or downloading.

Discovery only inspects configuration evidence, module presence, and approval
flags. It never installs packages, pulls weights, or initializes GPU models.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.schemas.voice import PARLER_UNAVAILABLE_MESSAGE, ProviderConfigurationStatus
from backend.app.services.runtime.evidence import EvidenceRecord, evidence


@dataclass(frozen=True)
class RuntimeEvidence:
    provider: str
    available: bool
    status: str
    evidence_level: str
    evidence_source: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_record(self, capability: str = "voice") -> EvidenceRecord:
        return evidence(
            provider=self.provider,
            capability=capability,
            status=self.status,
            evidence_level=self.evidence_level,
            available=self.available,
            evidence_source=self.evidence_source,
            message=self.message,
            details=self.details,
        )


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "approved"}


def _complete_qwen_model(path: Path) -> bool:
    return path.is_dir() and (path / "config.json").is_file() and (path / "model.safetensors").is_file()


def _complete_hf_snapshot(repository: Path) -> bool:
    snapshots = repository / "snapshots"
    if not snapshots.is_dir():
        return False
    try:
        return any(_complete_qwen_model(candidate) for candidate in snapshots.iterdir())
    except OSError:
        return False


def _discover_existing_local_qwen() -> dict[str, Any] | None:
    """Inspect only the approved, bounded Qwen locations on this workstation.

    The paths may be overridden for another approved installation.  Detection
    only checks directories and model manifests; it never imports Qwen, starts
    Python, loads weights, or contacts Hugging Face.
    """
    ai_root = Path(os.environ.get("CINEFORGE_LOCAL_AI_ROOT", "C:/AI"))
    runtime_dir = Path(
        os.environ.get("CINEFORGE_QWEN_LOCAL_RUNTIME", str(ai_root / "Qwen3-TTS"))
    )
    venv_dir = Path(
        os.environ.get("CINEFORGE_QWEN_LOCAL_VENV", str(ai_root / "qwen3-tts-env"))
    )
    base_model = Path(
        os.environ.get(
            "CINEFORGE_QWEN_LOCAL_MODEL",
            str(ai_root / "Qwen3-TTS-12Hz-1.7B-Base"),
        )
    )
    hf_root = Path.home() / ".cache" / "huggingface" / "hub"
    voice_design_repo = hf_root / "models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    custom_voice_repo = hf_root / "models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice"

    runtime_present = runtime_dir.is_dir() and (runtime_dir / "qwen_tts").is_dir()
    venv_present = (venv_dir / "Scripts" / "python.exe").is_file()
    base_model_present = _complete_qwen_model(base_model)
    voice_design_present = _complete_hf_snapshot(voice_design_repo)
    custom_voice_present = _complete_hf_snapshot(custom_voice_repo)
    model_present = base_model_present or voice_design_present or custom_voice_present
    if not (runtime_present and venv_present and model_present):
        return None

    return {
        "runtime_ref": str(runtime_dir),
        "configured_model": "Qwen3-TTS-12Hz-1.7B-local",
        "runtime_present": runtime_present,
        "venv_present": venv_present,
        "base_model_present": base_model_present,
        "voice_design_model_present": voice_design_present,
        "custom_voice_model_present": custom_voice_present,
        "bounded_local_discovery": True,
    }


def discover_qwen_runtime() -> RuntimeEvidence:
    """Reuse only the configured existing Qwen runtime.

    Looks for configuration references already present in the environment.
    Does not load models, start servers, or download weights.
    """
    runtime_ref = (
        os.environ.get("CINEFORGE_QWEN_RUNTIME_REF")
        or os.environ.get("QWEN_RUNTIME_REF")
        or os.environ.get("CINEFORGE_QWEN_BASE_URL")
        or os.environ.get("QWEN_BASE_URL")
    )
    model = (
        os.environ.get("CINEFORGE_QWEN_VOICE_MODEL")
        or os.environ.get("QWEN_VOICE_MODEL")
        or os.environ.get("CINEFORGE_QWEN_MODEL")
        or os.environ.get("QWEN_MODEL")
    )
    enabled_flag = os.environ.get("CINEFORGE_QWEN_ENABLED") or os.environ.get("QWEN_ENABLED")

    local = _discover_existing_local_qwen() if not runtime_ref and not model else None
    if local:
        runtime_ref = str(local["runtime_ref"])
        model = str(local["configured_model"])

    details: dict[str, Any] = {
        "runtime_ref_present": bool(runtime_ref),
        "runtime_ref": runtime_ref,
        "configured_model": model,
        "enabled_flag": enabled_flag,
        "loads_models_on_discover": False,
        "will_install_or_download": False,
        "reuse_existing_runtime_only": True,
        **({key: value for key, value in local.items() if key != "runtime_ref"} if local else {}),
    }

    # If explicitly disabled, report unavailable.
    if enabled_flag is not None and not _truthy(enabled_flag):
        return RuntimeEvidence(
            provider="qwen",
            available=False,
            status=ProviderConfigurationStatus.unavailable.value,
            evidence_level="configuration_evidence",
            evidence_source="env:CINEFORGE_QWEN_ENABLED|QWEN_ENABLED",
            message="Configured Qwen runtime is disabled.",
            details=details,
        )

    if not runtime_ref and not model:
        return RuntimeEvidence(
            provider="qwen",
            available=False,
            status=ProviderConfigurationStatus.not_configured.value,
            evidence_level="configuration_evidence",
            evidence_source="env:CINEFORGE_QWEN_*|QWEN_*",
            message="No configured Qwen runtime reference found.",
            details=details,
        )

    # Explicit enablement alone is never sufficient: runtime and model evidence
    # must both exist.  We never probe the network or load weights here.
    available = bool(runtime_ref) and bool(model)
    if not available:
        return RuntimeEvidence(
            provider="qwen",
            available=False,
            status=ProviderConfigurationStatus.not_configured.value,
            evidence_level="configuration_evidence",
            evidence_source="env:CINEFORGE_QWEN_*|QWEN_*",
            message="Qwen requires both an existing runtime reference and model evidence.",
            details=details,
        )

    return RuntimeEvidence(
        provider="qwen",
        available=True,
        status=ProviderConfigurationStatus.available.value,
        evidence_level="configuration_evidence",
        evidence_source=(
            "bounded existing local installation"
            if local
            else "env:CINEFORGE_QWEN_*|QWEN_*"
        ),
        message="Existing Qwen runtime and model evidence found (not loaded).",
        details=details,
    )


def discover_elevenlabs() -> RuntimeEvidence:
    key_present = bool(
        os.environ.get("CINEFORGE_ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY")
    )
    model = os.environ.get("CINEFORGE_ELEVENLABS_VOICE_MODEL") or os.environ.get(
        "ELEVENLABS_VOICE_MODEL"
    )
    details = {
        "api_key_configured": key_present,
        "configured_model": model,
        "loads_models_on_discover": False,
        "network_call_on_discover": False,
        "will_install_or_download": False,
    }
    if not key_present:
        return RuntimeEvidence(
            provider="elevenlabs",
            available=False,
            status=ProviderConfigurationStatus.not_configured.value,
            evidence_level="configuration_evidence",
            evidence_source="env:CINEFORGE_ELEVENLABS_API_KEY|ELEVENLABS_API_KEY",
            message="ElevenLabs is not configured.",
            details=details,
        )
    return RuntimeEvidence(
        provider="elevenlabs",
        available=True,
        status=ProviderConfigurationStatus.available.value,
        evidence_level="configuration_evidence",
        evidence_source="env:CINEFORGE_ELEVENLABS_API_KEY|ELEVENLABS_API_KEY",
        message="ElevenLabs API key is configured (presence only).",
        details=details,
    )


def discover_parler() -> RuntimeEvidence:
    # Lazy import of the provider helper to keep the exact unavailable message centralized.
    from backend.app.services.voice_design.providers.parler import discover_parler as _discover

    cap = _discover()
    return RuntimeEvidence(
        provider="parler",
        available=cap.available,
        status=cap.status,
        evidence_level=cap.evidence_level,
        evidence_source=cap.evidence_source,
        message=cap.message if not cap.available else cap.message,
        details=dict(cap.details),
    )


def discover_builtin(provider: str) -> RuntimeEvidence:
    return RuntimeEvidence(
        provider=provider,
        available=True,
        status=ProviderConfigurationStatus.available.value,
        evidence_level="built_in",
        evidence_source=f"runtime.discovery.{provider}",
        message=f"{provider} requires no external runtime.",
        details={"loads_models_on_discover": False, "requires_gpu": False},
    )


def discover_provider(name: str) -> RuntimeEvidence:
    key = (name or "").strip().lower()
    if key in {"qwen", "qwen_voice_design"}:
        base = discover_qwen_runtime()
        if (
            base.available
            and base.details.get("bounded_local_discovery")
            and not base.details.get("voice_design_model_present")
        ):
            return RuntimeEvidence(
                provider="qwen",
                available=False,
                status=ProviderConfigurationStatus.not_configured.value,
                evidence_level=base.evidence_level,
                evidence_source=base.evidence_source,
                message="Existing Qwen VoiceDesign model evidence was not found.",
                details=base.details,
                checked_at=base.checked_at,
            )
        return base
    if key in {"qwen_custom_voice", "qwen-custom-voice"}:
        base = discover_qwen_runtime()
        details = {
            **base.details,
            "custom_voice_mode": "preset_speaker_only",
            "supports_cloning": False,
            "supports_reference_audio": False,
        }
        custom_available = base.available and (
            not base.details.get("bounded_local_discovery")
            or bool(base.details.get("custom_voice_model_present"))
        )
        return RuntimeEvidence(
            provider="qwen_custom_voice",
            available=custom_available,
            status=(
                base.status
                if custom_available or not base.available
                else ProviderConfigurationStatus.not_configured.value
            ),
            evidence_level=base.evidence_level,
            evidence_source=base.evidence_source,
            message=(
                base.message
                if custom_available or not base.available
                else "Existing Qwen CustomVoice model evidence was not found."
            ),
            details=details,
            checked_at=base.checked_at,
        )
    if key in {"elevenlabs", "eleven_labs"}:
        return discover_elevenlabs()
    if key in {"parler", "parler_local", "parler-tts", "parler_tts"}:
        ev = discover_parler()
        # Guarantee exact unavailable message.
        if not ev.available:
            return RuntimeEvidence(
                provider="parler",
                available=False,
                status=ev.status,
                evidence_level=ev.evidence_level,
                evidence_source=ev.evidence_source,
                message=PARLER_UNAVAILABLE_MESSAGE,
                details=ev.details,
                checked_at=ev.checked_at,
            )
        return ev
    if key in {
        "placeholder",
        "manual",
        "existing_provider_voice",
        "user_provided_consented",
    }:
        return discover_builtin(key)

    return RuntimeEvidence(
        provider=key or "unknown",
        available=False,
        status=ProviderConfigurationStatus.unknown.value,
        evidence_level="none",
        evidence_source=None,
        message=f"No discovery handler for provider {name!r}.",
        details={"loads_models_on_discover": False},
    )


def discover_all_voice_providers() -> list[RuntimeEvidence]:
    names = [
        "placeholder",
        "manual",
        "existing_provider_voice",
        "qwen",
        "qwen_custom_voice",
        "elevenlabs",
        "parler",
        "user_provided_consented",
    ]
    return [discover_provider(name) for name in names]
