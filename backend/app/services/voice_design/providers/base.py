"""Base protocol for voice design / preview providers.

Providers never return raw audio bytes to API callers. Successful previews yield
a managed planning asset reference (URI + metadata) that planning_assets stores.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    available: bool
    status: str
    evidence_level: str
    evidence_source: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreviewResult:
    """Result of an explicit preview generation.

    audio_path / managed_uri point at storage managed by planning_assets.
    Never include base64 or raw provider response bodies.
    """

    success: bool
    provider: str
    model: str | None = None
    managed_uri: str | None = None
    sha256: str | None = None
    mime_type: str | None = None
    duration_sec: float | None = None
    size_bytes: int | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class VoiceDesignProvider(ABC):
    name: str

    @abstractmethod
    def discover(self) -> ProviderCapability:
        """Factual availability check without loading models or downloading."""

    @abstractmethod
    def generate_preview(
        self,
        *,
        preview_text: str,
        design_metadata: dict[str, Any],
        model: str | None = None,
        output_dir: str,
    ) -> PreviewResult:
        """Generate a preview only when explicitly requested."""


_REGISTRY: dict[str, VoiceDesignProvider] = {}


def register_provider(provider: VoiceDesignProvider) -> None:
    _REGISTRY[provider.name] = provider


def get_provider(name: str) -> VoiceDesignProvider | None:
    return _REGISTRY.get(name)


def list_provider_names() -> list[str]:
    return sorted(_REGISTRY.keys())


def all_providers() -> list[VoiceDesignProvider]:
    return [_REGISTRY[name] for name in list_provider_names()]
