"""Optional Parler-TTS local voice design adapter.

When unavailable, returns exactly:
    "Parler-TTS is not installed or approved."

Never installs or downloads packages/models.
"""
from __future__ import annotations

import importlib.util
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


def _approved_local_artifact(env_name: str, approval_env_name: str) -> bool:
    """Require an explicit approval flag and an existing local artifact.

    A package import alone is not proof that an approved runtime or model is
    usable.  Phase 1 intentionally accepts only bounded, pre-existing local
    evidence and never searches, installs, or downloads anything.
    """
    reference = (os.environ.get(env_name) or "").strip()
    approved = (os.environ.get(approval_env_name) or "").strip().lower()
    return approved in {"1", "true", "yes", "approved"} and bool(reference) and Path(reference).exists()


def discover_parler() -> ProviderCapability:
    installed = _parler_installed()
    approved = _parler_approved()
    runtime_approved = _approved_local_artifact(
        "CINEFORGE_PARLER_RUNTIME_REF",
        "CINEFORGE_PARLER_RUNTIME_APPROVED",
    )
    model_approved = _approved_local_artifact(
        "CINEFORGE_PARLER_MODEL_REF",
        "CINEFORGE_PARLER_MODEL_APPROVED",
    )
    available = installed and approved and runtime_approved and model_approved
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
        evidence_level="approved_local_runtime_and_model",
        evidence_source="module + explicit runtime/model references and approvals",
        message=message,
        details={
            "installed": installed,
            "approved": approved,
            "runtime_approved": runtime_approved,
            "model_approved": model_approved,
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

        # Discovery readiness is not execution.  A durable, isolated preview
        # worker is intentionally out of scope for this API, so never emit a
        # JSON marker and report it as generated audio.
        return PreviewResult(
            success=False,
            provider=self.name,
            model=model,
            metadata={
                "runtime_approved": capability.details.get("runtime_approved"),
                "model_approved": capability.details.get("model_approved"),
            },
            error_message="Parler-TTS preview execution is not configured for Phase 1.",
        )


register_provider(ParlerLocalVoiceDesignProvider())
