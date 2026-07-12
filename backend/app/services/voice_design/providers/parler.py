"""Optional Parler-TTS local voice design adapter.

When unavailable, returns exactly:
    "Parler-TTS is not installed or approved."

Never installs or downloads packages/models.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from backend.app.schemas.voice import PARLER_UNAVAILABLE_MESSAGE
from backend.app.services.voice_design.providers.base import (
    PreviewResult,
    ProviderCapability,
    VoiceDesignProvider,
    register_provider,
)


def _parler_approved() -> bool:
    flag = (
        os.environ.get("CINEFORGE_PARLER_APPROVED")
        or os.environ.get("PARLER_TTS_APPROVED")
        or ""
    ).strip().lower()
    return flag in {"1", "true", "yes", "approved"}


def _parler_installed() -> bool:
    """Module presence only — never import heavyweight code paths or download."""
    # Check common module names without importing (avoids side effects).
    for mod in ("parler_tts", "parler-tts", "parler"):
        if importlib.util.find_spec(mod) is not None:
            return True
    return False


def discover_parler() -> ProviderCapability:
    installed = _parler_installed()
    approved = _parler_approved()
    available = installed and approved
    if available:
        status = "available"
        message = "Parler-TTS is installed and approved."
    else:
        status = "unavailable" if not installed else "not_approved"
        message = PARLER_UNAVAILABLE_MESSAGE
    return ProviderCapability(
        provider="parler",
        available=available,
        status=status,
        evidence_level="local_module_and_approval_flag",
        evidence_source="importlib.util.find_spec + CINEFORGE_PARLER_APPROVED",
        message=message,
        details={
            "installed": installed,
            "approved": approved,
            "loads_models_on_discover": False,
            "will_install_or_download": False,
        },
    )


class ParlerLocalVoiceDesignProvider(VoiceDesignProvider):
    name = "parler"

    def discover(self) -> ProviderCapability:
        return discover_parler()

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        capability = discover_parler()
        if not capability.available:
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model,
                error_message=PARLER_UNAVAILABLE_MESSAGE,
                metadata={
                    "evidence_status": capability.status,
                    "installed": capability.details.get("installed"),
                    "approved": capability.details.get("approved"),
                },
            )

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": self.name,
            "mode": "parler_local_voice_design",
            "model": model,
            "preview_text_sha256": hashlib.sha256(preview_text.encode("utf-8")).hexdigest(),
            "design_description": design_metadata.get("design_description"),
            "recipe_name": design_metadata.get("recipe_name"),
            "seed": design_metadata.get("seed"),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        path = out / f"parler_preview_{digest[:16]}.json"
        path.write_bytes(raw)

        return PreviewResult(
            success=True,
            provider=self.name,
            model=model,
            managed_uri=str(path.resolve()),
            sha256=digest,
            mime_type="application/json",
            size_bytes=len(raw),
            metadata={
                "preview_kind": "parler_local_voice_design_marker",
                "note": "Managed preview reference only; no audio/base64 stored.",
            },
        )


register_provider(ParlerLocalVoiceDesignProvider())
