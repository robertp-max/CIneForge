"""Existing provider voice adapter (reference an already-known provider voice)."""
from __future__ import annotations

from typing import Any

from backend.app.services.voice_design.providers.base import (
    PreviewResult,
    ProviderCapability,
    VoiceDesignProvider,
    register_provider,
)


class ExistingProviderVoiceProvider(VoiceDesignProvider):
    name = "existing_provider_voice"

    def discover(self) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            available=True,
            status="available",
            evidence_level="built_in",
            evidence_source="voice_design.existing_provider_voice",
            message="Existing provider voice references are always configurable.",
            details={"requires_gpu": False, "preview_optional": True},
        )

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        ref = (design_metadata.get("provider_voice_reference") or "").strip()
        provider = (design_metadata.get("provider") or "").strip() or "unknown"
        if not ref:
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model,
                error_message="existing_provider_voice requires provider_voice_reference.",
            )
        return PreviewResult(
            success=True,
            provider=self.name,
            model=model,
            managed_uri=f"planning://existing/{provider}/{abs(hash(ref + preview_text)) % (10**12)}",
            mime_type="application/x-cineforge-existing-provider-voice",
            metadata={
                "provider": provider,
                "provider_voice_reference": ref,
                "preview_text_chars": len(preview_text),
                "note": "existing_provider_voice_marker",
            },
        )


register_provider(ExistingProviderVoiceProvider())
