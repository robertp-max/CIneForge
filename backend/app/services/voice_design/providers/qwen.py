"""Qwen voice design / CustomVoice adapters.

Rules:
- Reuse only the configured existing Qwen runtime (no install/download).
- Discovery reads evidence without loading models.
- qwen_custom_voice is preset speaker only — never cloning or reference audio.
- Previews are explicit only; store managed asset refs, never raw responses.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.services.runtime.discovery import discover_qwen_runtime
from backend.app.services.voice_design.providers.base import (
    PreviewResult,
    ProviderCapability,
    VoiceDesignProvider,
    register_provider,
)

FORBIDDEN_CLONE_KEYS = frozenset(
    {
        "reference_audio",
        "reference_audio_id",
        "clone_audio",
        "clone_audio_id",
        "voice_clone",
        "reference_wav",
        "prompt_audio",
        "speaker_audio",
    }
)


def _reject_cloning_metadata(design_metadata: dict[str, Any]) -> None:
    keys = {str(k).lower() for k in (design_metadata or {})}
    hit = FORBIDDEN_CLONE_KEYS.intersection(keys)
    if hit:
        raise ValueError(
            f"Qwen CustomVoice forbids cloning/reference audio fields: {sorted(hit)}"
        )


class QwenVoiceDesignProvider(VoiceDesignProvider):
    """Text-described voice design via the configured Qwen runtime."""

    name = "qwen"

    def discover(self) -> ProviderCapability:
        evidence = discover_qwen_runtime()
        return ProviderCapability(
            provider=self.name,
            available=evidence.available,
            status=evidence.status,
            evidence_level=evidence.evidence_level,
            evidence_source=evidence.evidence_source,
            message=evidence.message,
            details={
                **evidence.details,
                "supports_voice_design": True,
                "supports_custom_voice_preset": True,
                "supports_cloning": False,
                "loads_models_on_discover": False,
            },
        )

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        _reject_cloning_metadata(design_metadata)
        evidence = discover_qwen_runtime()
        if not evidence.available:
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model or evidence.details.get("configured_model"),
                error_message=evidence.message or "Configured Qwen runtime is not available.",
                metadata={"evidence_status": evidence.status},
            )

        # Explicit preview only. We do not call remote APIs here with secrets;
        # we materialize a managed marker file representing the preview artifact
        # boundary. Real audio capture remains outside this Phase 1 boundary and
        # is referenced solely by managed URI / asset id.
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": self.name,
            "mode": design_metadata.get("setup_mode", "qwen_voice_design"),
            "model": model or evidence.details.get("configured_model"),
            "preview_text_sha256": hashlib.sha256(preview_text.encode("utf-8")).hexdigest(),
            "design_description": design_metadata.get("design_description"),
            "recipe_name": design_metadata.get("recipe_name"),
            "seed": design_metadata.get("seed"),
            "runtime_ref": evidence.details.get("runtime_ref"),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        path = out / f"qwen_preview_{digest[:16]}.json"
        path.write_bytes(raw)

        return PreviewResult(
            success=True,
            provider=self.name,
            model=payload["model"],
            managed_uri=str(path.resolve()),
            sha256=digest,
            mime_type="application/json",
            size_bytes=len(raw),
            metadata={
                "preview_kind": "qwen_voice_design_marker",
                "runtime_ref": evidence.details.get("runtime_ref"),
                "note": "Stores managed preview reference only; no audio/base64/raw provider body.",
            },
        )


class QwenCustomVoiceProvider(VoiceDesignProvider):
    """Preset-speaker CustomVoice only — never cloning."""

    name = "qwen_custom_voice"

    def discover(self) -> ProviderCapability:
        evidence = discover_qwen_runtime()
        return ProviderCapability(
            provider=self.name,
            available=evidence.available,
            status=evidence.status,
            evidence_level=evidence.evidence_level,
            evidence_source=evidence.evidence_source,
            message=evidence.message,
            details={
                **evidence.details,
                "custom_voice_mode": "preset_speaker_only",
                "supports_cloning": False,
                "supports_reference_audio": False,
                "loads_models_on_discover": False,
            },
        )

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        _reject_cloning_metadata(design_metadata)
        speaker = (design_metadata.get("custom_voice_speaker") or "").strip()
        if not speaker:
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model,
                error_message="qwen_custom_voice requires custom_voice_speaker (preset speaker only).",
            )

        evidence = discover_qwen_runtime()
        if not evidence.available:
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model or evidence.details.get("configured_model"),
                error_message=evidence.message or "Configured Qwen runtime is not available.",
                metadata={"evidence_status": evidence.status},
            )

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": self.name,
            "mode": "qwen_custom_voice",
            "model": model or evidence.details.get("configured_model"),
            "custom_voice_speaker": speaker,
            "preview_text_sha256": hashlib.sha256(preview_text.encode("utf-8")).hexdigest(),
            "seed": design_metadata.get("seed"),
            "runtime_ref": evidence.details.get("runtime_ref"),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        path = out / f"qwen_custom_{digest[:16]}.json"
        path.write_bytes(raw)

        return PreviewResult(
            success=True,
            provider=self.name,
            model=payload["model"],
            managed_uri=str(path.resolve()),
            sha256=digest,
            mime_type="application/json",
            size_bytes=len(raw),
            metadata={
                "preview_kind": "qwen_custom_voice_marker",
                "custom_voice_speaker": speaker,
                "cloning": False,
                "note": "Preset speaker only; managed reference, no audio/base64.",
            },
        )


register_provider(QwenVoiceDesignProvider())
register_provider(QwenCustomVoiceProvider())
