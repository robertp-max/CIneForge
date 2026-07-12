"""Storyboard Phase 1 voice configuration schemas.

These models describe setup modes, recipes, previews, discovery, and routing.
They store managed asset IDs and metadata only — never audio bytes, base64, or raw provider responses.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VoiceSetupMode(StrEnum):
    placeholder = "placeholder"
    manual = "manual"
    existing_provider_voice = "existing_provider_voice"
    qwen_voice_design = "qwen_voice_design"
    qwen_custom_voice = "qwen_custom_voice"
    elevenlabs_voice_design = "elevenlabs_voice_design"
    parler_local_voice_design = "parler_local_voice_design"
    user_provided_consented = "user_provided_consented"


class NativeVoiceCapability(StrEnum):
    supported = "supported"
    unsupported = "unsupported"
    unknown = "unknown"


class ProviderConfigurationStatus(StrEnum):
    unknown = "unknown"
    available = "available"
    unavailable = "unavailable"
    not_configured = "not_configured"
    not_approved = "not_approved"


class VoiceApprovalState(StrEnum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    blocked = "blocked"


class PreviewJobStatus(StrEnum):
    pending = "pending"
    reserved = "reserved"
    running = "running"
    complete = "complete"
    failed = "failed"
    canceled = "canceled"


class VoiceRoutingAction(StrEnum):
    none = "none"
    recommend_qwen = "recommend_qwen"
    keep_native = "keep_native"
    keep_approved = "keep_approved"


SUPPORTED_SETUP_MODES: tuple[str, ...] = tuple(mode.value for mode in VoiceSetupMode)

# Exact unavailable message required for Parler (optional local provider).
PARLER_UNAVAILABLE_MESSAGE = "Parler-TTS is not installed or approved."


class VoiceDesignAttributes(BaseModel):
    """Shared design attributes for recipe/profile metadata."""

    language: str | None = None
    accent: str | None = None
    presentation: str | None = None
    gender_presentation: str | None = None
    tone: str | None = None
    style: str | None = None
    pitch: str | None = None
    pacing: str | None = None
    energy: str | None = None
    speaking_directions: str | None = None
    pronunciation_notes: str | None = None


class VoiceProfileSetupCreate(BaseModel):
    """Create a voice profile with an explicit Phase 1 setup mode."""

    name: str = Field(min_length=1, max_length=200)
    setup_mode: VoiceSetupMode
    character_id: UUID | None = None

    # Common provider / reference fields
    provider: str | None = None
    provider_voice_reference: str | None = None
    provider_model_id: str | None = None

    # Manual / design description fields
    recipe_name: str | None = None
    recipe_description: str | None = None
    design_description: str | None = None
    preview_text: str | None = None

    language: str | None = None
    accent: str | None = None
    presentation: str | None = None
    gender_presentation: str | None = None
    tone: str | None = None
    style: str | None = None
    pitch: str | None = None
    pacing: str | None = None
    energy: str | None = None
    speaking_directions: str | None = None
    pronunciation_notes: str | None = None

    # Managed asset references only (never audio bytes).
    source_asset_id: UUID | None = None
    selected_preview_asset_id: UUID | None = None

    source_description: str | None = None
    usage_notes: str | None = None

    consent_required: bool = False
    consent_confirmed: bool = False
    consent_notes: str | None = None

    # qwen_custom_voice: preset speaker id only — never cloning / reference audio.
    custom_voice_speaker: str | None = Field(
        default=None,
        description="Preset CustomVoice speaker identifier. Cloning and reference audio are forbidden.",
    )

    design_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mode_constraints(self) -> VoiceProfileSetupCreate:
        mode = self.setup_mode

        if mode == VoiceSetupMode.user_provided_consented:
            if not self.consent_confirmed:
                raise ValueError("User-provided voice profiles require confirmed consent.")
            if self.source_asset_id is None and not (self.source_description or "").strip():
                raise ValueError(
                    "User-provided voice profiles require a managed source_asset_id or source_description."
                )

        if mode == VoiceSetupMode.existing_provider_voice:
            if not (self.provider or "").strip():
                raise ValueError("existing_provider_voice requires provider.")
            if not (self.provider_voice_reference or "").strip():
                raise ValueError("existing_provider_voice requires provider_voice_reference.")

        if mode == VoiceSetupMode.qwen_custom_voice:
            if not (self.custom_voice_speaker or "").strip():
                raise ValueError(
                    "qwen_custom_voice requires custom_voice_speaker (preset speaker only; no cloning)."
                )
            # Explicitly reject any attempt to smuggle reference-audio cloning.
            forbidden_keys = {
                "reference_audio",
                "reference_audio_id",
                "clone_audio",
                "clone_audio_id",
                "voice_clone",
                "reference_wav",
                "prompt_audio",
            }
            meta_keys = {str(k).lower() for k in (self.design_metadata or {})}
            hit = forbidden_keys.intersection(meta_keys)
            if hit:
                raise ValueError(
                    f"qwen_custom_voice forbids cloning/reference audio fields: {sorted(hit)}"
                )

        if mode in {
            VoiceSetupMode.qwen_voice_design,
            VoiceSetupMode.elevenlabs_voice_design,
            VoiceSetupMode.parler_local_voice_design,
        }:
            if not (self.design_description or self.recipe_description or "").strip():
                raise ValueError(f"{mode.value} requires design_description or recipe_description.")

        return self


class VoiceProfileSetupUpdate(BaseModel):
    """Partial update for a draft/in_review voice profile setup."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    setup_mode: VoiceSetupMode | None = None
    character_id: UUID | None = None

    provider: str | None = None
    provider_voice_reference: str | None = None
    provider_model_id: str | None = None

    recipe_name: str | None = None
    recipe_description: str | None = None
    design_description: str | None = None
    preview_text: str | None = None

    language: str | None = None
    accent: str | None = None
    presentation: str | None = None
    gender_presentation: str | None = None
    tone: str | None = None
    style: str | None = None
    pitch: str | None = None
    pacing: str | None = None
    energy: str | None = None
    speaking_directions: str | None = None
    pronunciation_notes: str | None = None

    source_asset_id: UUID | None = None
    selected_preview_asset_id: UUID | None = None
    source_description: str | None = None
    usage_notes: str | None = None

    consent_required: bool | None = None
    consent_confirmed: bool | None = None
    consent_notes: str | None = None

    custom_voice_speaker: str | None = None
    design_metadata: dict | None = None
    approval_state: VoiceApprovalState | None = None


class VoiceProfileSetupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    story_id: UUID
    character_id: UUID | None = None
    name: str
    setup_mode: str
    source_type: str
    provider: str | None = None
    provider_voice_reference: str | None = None
    provider_model_id: str | None = None
    recipe_name: str | None = None
    recipe_description: str | None = None
    design_description: str | None = None
    design_metadata_json: dict = Field(default_factory=dict)
    preview_text: str | None = None
    language: str | None = None
    accent: str | None = None
    presentation: str | None = None
    gender_presentation: str | None = None
    tone: str | None = None
    style: str | None = None
    pitch: str | None = None
    pacing: str | None = None
    energy: str | None = None
    speaking_directions: str | None = None
    pronunciation_notes: str | None = None
    source_asset_id: UUID | None = None
    selected_preview_asset_id: UUID | None = None
    source_description: str | None = None
    usage_notes: str | None = None
    consent_required: bool
    consent_confirmed: bool
    consent_notes: str | None = None
    approval_state: str
    provider_configuration_status: str
    created_at: datetime
    updated_at: datetime


class VoiceRecipeCreate(BaseModel):
    """Create a voice design recipe (metadata only)."""

    provider: str = Field(min_length=1, max_length=80)
    model: str | None = None
    recipe_name: str | None = None
    description: str | None = None
    seed: int | None = None
    design_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def forbid_audio_payloads(self) -> VoiceRecipeCreate:
        forbidden = {
            "audio",
            "audio_base64",
            "base64",
            "raw_response",
            "wav_bytes",
            "mp3_bytes",
            "reference_audio",
            "clone_audio",
        }
        keys = {str(k).lower() for k in (self.design_metadata or {})}
        hit = forbidden.intersection(keys)
        if hit:
            raise ValueError(f"Voice recipes must not store audio/raw payload fields: {sorted(hit)}")
        return self


class VoiceRecipeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    voice_profile_id: UUID
    provider: str
    model: str | None = None
    recipe_name: str | None = None
    description: str | None = None
    seed: int | None = None
    design_metadata_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class VoicePreviewRequest(BaseModel):
    """Explicit preview request. Previews are never generated implicitly."""

    recipe_id: UUID | None = None
    preview_text: str = Field(min_length=1, max_length=2000)
    provider: str | None = None
    model: str | None = None
    # Optional design overrides for this explicit preview only.
    design_metadata: dict = Field(default_factory=dict)
    owner: str = Field(default="voice-preview-api", min_length=1, max_length=200)

    @model_validator(mode="after")
    def forbid_audio_in_request(self) -> VoicePreviewRequest:
        forbidden = {"audio", "audio_base64", "base64", "raw_response", "reference_audio", "clone_audio"}
        keys = {str(k).lower() for k in (self.design_metadata or {})}
        hit = forbidden.intersection(keys)
        if hit:
            raise ValueError(f"Preview requests must not include audio/raw payload fields: {sorted(hit)}")
        return self


class VoicePreviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    voice_profile_id: UUID
    voice_recipe_id: UUID | None = None
    planning_media_asset_id: UUID | None = None
    provider: str | None = None
    model: str | None = None
    preview_text: str | None = None
    selected: bool
    rejected: bool
    created_at: datetime
    updated_at: datetime


class VoicePreviewSelectRequest(BaseModel):
    selected: bool = True


class VoicePreviewJobRead(BaseModel):
    """Status of an explicit preview job (asset id only on success)."""

    job_id: str
    voice_profile_id: UUID
    status: PreviewJobStatus
    provider: str | None = None
    model: str | None = None
    preview_id: UUID | None = None
    planning_media_asset_id: UUID | None = None
    lease_id: UUID | None = None
    error_message: str | None = None
    message: str | None = None


class VoiceApproveRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=200)
    # When True, unavailable optional preview providers do not block approval for
    # modes that allow approval without preview (placeholder/manual and similar).
    allow_without_preview: bool = True


class VoiceApproveResult(BaseModel):
    voice_profile_id: UUID
    approval_state: str
    approved_by: str
    preview_required: bool
    preview_present: bool
    warnings: list[str] = Field(default_factory=list)


class ProviderEvidenceRead(BaseModel):
    """Factual discovery evidence — never loads models."""

    provider: str
    capability: str
    status: ProviderConfigurationStatus
    evidence_level: str
    evidence_source: str | None = None
    details: dict = Field(default_factory=dict)
    message: str | None = None
    checked_at: datetime | None = None


class VoiceProviderDiscoveryRead(BaseModel):
    providers: list[ProviderEvidenceRead]
    notes: list[str] = Field(default_factory=list)


class NativeSpeechCapabilityRead(BaseModel):
    model_variant_id: UUID | None = None
    family: str | None = None
    variant_name: str | None = None
    native_voice_capability: NativeVoiceCapability
    source: str | None = None
    metadata: dict = Field(default_factory=dict)
    checked_at: datetime | None = None


class VoiceRoutingRequest(BaseModel):
    story_id: UUID
    model_variant_id: UUID | None = None
    generation_family: str | None = None
    # When an assignment is already approved, routing must never overwrite it.
    existing_assignment_approved: bool = False
    existing_provider: str | None = None


class VoiceRoutingRecommendation(BaseModel):
    action: VoiceRoutingAction
    recommend_qwen: bool
    rationale: str
    native_voice_capability: NativeVoiceCapability
    blocked_reason: str | None = None
    provider_suggestion: str | None = None


class PlanningAssetRegisterRequest(BaseModel):
    """Register a managed planning asset by URI/hash — never accept raw audio bytes."""

    project_id: UUID
    kind: str = Field(min_length=1, max_length=48)
    source_type: str = Field(min_length=1, max_length=48)
    managed_uri: str = Field(min_length=1)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    mime_type: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    duration_sec: float | None = Field(default=None, gt=0)
    original_filename: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def forbid_embedded_payloads(self) -> PlanningAssetRegisterRequest:
        forbidden = {"audio", "audio_base64", "base64", "data", "bytes", "raw_response"}
        keys = {str(k).lower() for k in (self.metadata or {})}
        hit = forbidden.intersection(keys)
        if hit:
            raise ValueError(f"Planning assets must not embed payload fields: {sorted(hit)}")
        if self.managed_uri.strip().lower().startswith("data:"):
            raise ValueError("Planning assets must not use data: URIs (no embedded base64).")
        return self


class PlanningAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    kind: str
    source_type: str
    managed_uri: str
    sha256: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    approval_state: str
    metadata_json: dict = Field(default_factory=dict)
    original_filename: str | None = None
    size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime


class GpuLeaseAcquireRequest(BaseModel):
    resource_key: str = Field(min_length=1, max_length=128)
    exclusive_group: str | None = Field(default="gpu-shared", max_length=128)
    workload_type: str = Field(min_length=1, max_length=64)
    workload_id: str | None = Field(default=None, max_length=128)
    owner: str = Field(min_length=1)
    worker_id: str | None = None
    ttl_seconds: int = Field(default=300, ge=1, le=3600)
    metadata: dict = Field(default_factory=dict)


class GpuLeaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_key: str
    exclusive_group: str | None = None
    workload_type: str
    workload_id: str | None = None
    owner: str
    worker_id: str | None = None
    status: str
    acquired_at: datetime
    heartbeat_at: datetime | None = None
    expires_at: datetime | None = None
    released_at: datetime | None = None
    metadata_json: dict = Field(default_factory=dict)


class GpuLeaseHeartbeatRequest(BaseModel):
    extend_seconds: int = Field(default=300, ge=1, le=3600)


def source_type_for_setup_mode(mode: VoiceSetupMode | str) -> str:
    """Map setup mode to legacy VoiceProfile.source_type values."""
    value = mode.value if isinstance(mode, VoiceSetupMode) else str(mode)
    if value == VoiceSetupMode.placeholder.value:
        return "placeholder"
    if value == VoiceSetupMode.user_provided_consented.value:
        return "user_provided_consented"
    return "synthetic"
