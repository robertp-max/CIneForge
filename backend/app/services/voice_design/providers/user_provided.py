"""User-provided consented voice adapter (managed asset id only)."""
from __future__ import annotations

from typing import Any

from backend.app.services.voice_design.providers.base import (
    PreviewResult,
    ProviderCapability,
    VoiceDesignProvider,
    register_provider,
)


class UserProvidedConsentedProvider(VoiceDesignProvider):
    name = "user_provided_consented"

    def discover(self) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            available=True,
            status="available",
            evidence_level="built_in",
            evidence_source="voice_design.user_provided_consented",
            message="User-provided voices require consent and a managed source asset id.",
            details={"requires_gpu": False, "stores_audio_bytes": False},
        )

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        if not design_metadata.get("consent_confirmed"):
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model,
                error_message="User-provided voice previews require confirmed consent.",
            )
        source_asset_id = design_metadata.get("source_asset_id")
        if not source_asset_id:
            return PreviewResult(
                success=False,
                provider=self.name,
                model=model,
                error_message="User-provided voice previews require source_asset_id (managed asset).",
            )
        return PreviewResult(
            success=True,
            provider=self.name,
            model=model,
            managed_uri=f"planning://user_provided/{source_asset_id}",
            mime_type="application/x-cineforge-user-provided-voice",
            metadata={
                "source_asset_id": str(source_asset_id),
                "consent_confirmed": True,
                "preview_text_chars": len(preview_text),
                "note": "References managed asset id only; no audio/base64.",
            },
        )


register_provider(UserProvidedConsentedProvider())
