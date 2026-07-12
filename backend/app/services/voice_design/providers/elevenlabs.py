"""ElevenLabs voice design adapter (explicit preview only; no install)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from backend.app.services.voice_design.providers.base import (
    PreviewResult,
    ProviderCapability,
    VoiceDesignProvider,
    register_provider,
)


def _elevenlabs_configured() -> tuple[bool, str, dict[str, Any]]:
    """Factual configuration evidence only — does not call the network or load models."""
    # Prefer project-prefixed env; never read secrets into stored metadata.
    key_present = bool(
        os.environ.get("CINEFORGE_ELEVENLABS_API_KEY")
        or os.environ.get("ELEVENLABS_API_KEY")
    )
    model = os.environ.get("CINEFORGE_ELEVENLABS_VOICE_MODEL") or os.environ.get(
        "ELEVENLABS_VOICE_MODEL"
    )
    details: dict[str, Any] = {
        "api_key_configured": key_present,
        "configured_model": model,
        "loads_models_on_discover": False,
        "network_call_on_discover": False,
    }
    if not key_present:
        return False, "not_configured", details
    return True, "available", details


class ElevenLabsVoiceDesignProvider(VoiceDesignProvider):
    name = "elevenlabs"

    def discover(self) -> ProviderCapability:
        available, status, details = _elevenlabs_configured()
        return ProviderCapability(
            provider=self.name,
            available=available,
            status=status,
            evidence_level="configuration_evidence",
            evidence_source="env:CINEFORGE_ELEVENLABS_API_KEY|ELEVENLABS_API_KEY",
            message=(
                "ElevenLabs API key is configured (presence only)."
                if available
                else "ElevenLabs is not configured."
            ),
            details=details,
        )

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        available, status, details = _elevenlabs_configured()
        if not available:
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model or details.get("configured_model"),
                error_message="ElevenLabs is not configured.",
                metadata={"evidence_status": status},
            )

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": self.name,
            "mode": "elevenlabs_voice_design",
            "model": model or details.get("configured_model"),
            "preview_text_sha256": hashlib.sha256(preview_text.encode("utf-8")).hexdigest(),
            "design_description": design_metadata.get("design_description"),
            "recipe_name": design_metadata.get("recipe_name"),
            "seed": design_metadata.get("seed"),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        path = out / f"elevenlabs_preview_{digest[:16]}.json"
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
                "preview_kind": "elevenlabs_voice_design_marker",
                "note": "Managed preview reference only; no audio/base64/raw API body stored.",
            },
        )


register_provider(ElevenLabsVoiceDesignProvider())
