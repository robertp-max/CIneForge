"""Setup mode constants and helpers for Phase 1 voice design."""
from __future__ import annotations

from backend.app.schemas.voice import VoiceSetupMode

SUPPORTED_SETUP_MODES: frozenset[str] = frozenset(mode.value for mode in VoiceSetupMode)

# Modes that may be approved without a successful provider preview when allow_without_preview.
APPROVAL_WITHOUT_PREVIEW_MODES: frozenset[str] = frozenset(
    {
        VoiceSetupMode.placeholder.value,
        VoiceSetupMode.manual.value,
        VoiceSetupMode.existing_provider_voice.value,
        VoiceSetupMode.user_provided_consented.value,
    }
)

# Modes that use an explicit design recipe for previews.
DESIGN_RECIPE_MODES: frozenset[str] = frozenset(
    {
        VoiceSetupMode.qwen_voice_design.value,
        VoiceSetupMode.qwen_custom_voice.value,
        VoiceSetupMode.elevenlabs_voice_design.value,
        VoiceSetupMode.parler_local_voice_design.value,
    }
)

# Optional local providers that must never auto-install/download.
OPTIONAL_LOCAL_PROVIDERS: frozenset[str] = frozenset({"parler", "parler_local", "parler-tts"})

PROVIDER_FOR_MODE: dict[str, str | None] = {
    VoiceSetupMode.placeholder.value: None,
    VoiceSetupMode.manual.value: None,
    VoiceSetupMode.existing_provider_voice.value: None,  # caller-supplied
    VoiceSetupMode.qwen_voice_design.value: "qwen",
    VoiceSetupMode.qwen_custom_voice.value: "qwen",
    VoiceSetupMode.elevenlabs_voice_design.value: "elevenlabs",
    VoiceSetupMode.parler_local_voice_design.value: "parler",
    VoiceSetupMode.user_provided_consented.value: None,
}


def normalize_setup_mode(mode: str | VoiceSetupMode) -> str:
    value = mode.value if isinstance(mode, VoiceSetupMode) else str(mode)
    if value not in SUPPORTED_SETUP_MODES:
        raise ValueError(
            f"Unsupported setup_mode {value!r}. Supported: {sorted(SUPPORTED_SETUP_MODES)}"
        )
    return value


def default_provider_for_mode(mode: str | VoiceSetupMode, explicit: str | None = None) -> str | None:
    value = normalize_setup_mode(mode)
    if explicit:
        return explicit
    return PROVIDER_FOR_MODE.get(value)


def requires_preview_for_approval(mode: str | VoiceSetupMode, allow_without_preview: bool) -> bool:
    value = normalize_setup_mode(mode)
    if allow_without_preview and value in APPROVAL_WITHOUT_PREVIEW_MODES:
        return False
    # Design modes prefer a selected preview but optional providers must not hard-block
    # when allow_without_preview is set and the provider is unavailable.
    if allow_without_preview and value in DESIGN_RECIPE_MODES:
        return False
    return value in DESIGN_RECIPE_MODES
