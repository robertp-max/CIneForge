"""Placeholder and manual voice providers.

These modes never require GPU work or external runtimes. They always work so
that approval is not blocked by unavailable preview providers.
"""
from __future__ import annotations

from typing import Any

from backend.app.services.voice_design.providers.base import (
    PreviewResult,
    ProviderCapability,
    VoiceDesignProvider,
    register_provider,
)


class PlaceholderVoiceProvider(VoiceDesignProvider):
    name = "placeholder"

    def discover(self) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            available=True,
            status="available",
            evidence_level="built_in",
            evidence_source="voice_design.placeholder",
            message="Placeholder voices require no runtime.",
            details={"requires_gpu": False, "requires_preview": False},
        )

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        # Explicit preview for placeholder is a no-op success marker (no audio bytes).
        return PreviewResult(
            success=True,
            provider=self.name,
            model=model,
            managed_uri=f"planning://placeholder/{abs(hash(preview_text)) % (10**12)}",
            mime_type="application/x-cineforge-placeholder-voice",
            metadata={
                "preview_text_chars": len(preview_text),
                "note": "placeholder_preview_marker",
                "design_keys": sorted(design_metadata.keys()),
            },
        )


class ManualVoiceProvider(VoiceDesignProvider):
    name = "manual"

    def discover(self) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            available=True,
            status="available",
            evidence_level="built_in",
            evidence_source="voice_design.manual",
            message="Manual voice configuration requires no runtime.",
            details={"requires_gpu": False, "requires_preview": False},
        )

    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        return PreviewResult(
            success=True,
            provider=self.name,
            model=model,
            managed_uri=f"planning://manual/{abs(hash(preview_text)) % (10**12)}",
            mime_type="application/x-cineforge-manual-voice",
            metadata={
                "preview_text_chars": len(preview_text),
                "note": "manual_preview_marker",
                "design_keys": sorted(design_metadata.keys()),
            },
        )


register_provider(PlaceholderVoiceProvider())
register_provider(ManualVoiceProvider())
