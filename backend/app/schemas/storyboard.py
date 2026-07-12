from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovalState(StrEnum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    blocked = "blocked"


class VoiceSourceType(StrEnum):
    placeholder = "placeholder"
    synthetic = "synthetic"
    user_provided_consented = "user_provided_consented"


class ProviderIdentifier(StrEnum):
    openai = "openai"
    anthropic = "anthropic"
    xai = "xai"
    qwen = "qwen"
    local_cli = "local_cli"
    custom = "custom"


class StoryCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=300)
    base_story: str = Field(min_length=1)
    target_duration_sec: float = Field(gt=0)
    logline: str | None = None
    synopsis: str | None = None
    audience: str | None = None
    tone: str | None = None
    genre: str | None = None
    visual_style: str | None = None
    point_of_view: str | None = None
    production_notes: str | None = None


class StoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    base_story: str | None = Field(default=None, min_length=1)
    target_duration_sec: float | None = Field(default=None, gt=0)
    logline: str | None = None
    synopsis: str | None = None
    audience: str | None = None
    tone: str | None = None
    genre: str | None = None
    visual_style: str | None = None
    point_of_view: str | None = None
    production_notes: str | None = None
    approval_state: ApprovalState | None = None
    # Optimistic concurrency: either token may be supplied by Phase A clients.
    expected_updated_at: datetime | None = None
    expected_revision: str | None = Field(default=None, min_length=1, max_length=64)


class StoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    base_story: str
    target_duration_sec: float
    logline: str | None = None
    synopsis: str | None = None
    audience: str | None = None
    tone: str | None = None
    genre: str | None = None
    visual_style: str | None = None
    point_of_view: str | None = None
    production_notes: str | None = None
    approval_state: str
    active_storyboard_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = None
    age_range: str | None = None
    physical_description: str | None = None
    personality: str | None = None
    speaking_style: str | None = None
    wardrobe: str | None = None
    consistency_prompt: str | None = None
    negative_identity_prompt: str | None = None
    identity_method: str | None = None


class CharacterRead(CharacterCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_id: UUID
    approval_state: str
    assigned_voice_profile_id: UUID | None = None


class VoiceProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: VoiceSourceType
    character_id: UUID | None = None
    provider: str | None = None
    provider_voice_reference: str | None = None
    language: str | None = None
    accent: str | None = None
    presentation: str | None = None
    tone: str | None = None
    speaking_directions: str | None = None
    pacing: str | None = None
    energy: str | None = None
    pronunciation_notes: str | None = None
    source_asset_id: UUID | None = None
    source_description: str | None = None
    consent_required: bool = False
    consent_confirmed: bool = False
    consent_notes: str | None = None
    usage_notes: str | None = None

    @model_validator(mode="after")
    def require_consent_for_user_voice(self):
        if self.source_type == VoiceSourceType.user_provided_consented and not self.consent_confirmed:
            raise ValueError("User-provided voice profiles require confirmed consent.")
        return self


class VoiceProfileRead(VoiceProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_id: UUID
    approval_state: str


class ChapterCreate(BaseModel):
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = None


class ChapterRead(ChapterCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_id: UUID
    approval_state: str


class SceneCreate(BaseModel):
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = None
    narrative_purpose: str | None = None
    location: str | None = None
    conflict_or_beat: str | None = None


class SceneRead(SceneCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    chapter_id: UUID
    approval_state: str


class ShotCreate(BaseModel):
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    duration_sec: float = Field(gt=0)
    duration_override_reason: str | None = None
    story_purpose: str | None = None
    visual_description: str | None = None
    location: str | None = None
    continuity_source_type: str = "none"
    continuity_source_shot_id: UUID | None = None
    starting_image_required: bool = False
    starting_image_asset_id: UUID | None = None

    @model_validator(mode="after")
    def check_duration_policy(self):
        # Product default: 6–12 seconds unless a reasoned override is supplied.
        if not 6 <= self.duration_sec <= 12 and not (self.duration_override_reason or "").strip():
            raise ValueError("Shots outside 6–12 seconds require a duration override reason.")
        return self


class ShotUpdate(ShotCreate):
    pass


class ShotRead(ShotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scene_id: UUID
    approval_state: str
    production_status: str
    blocked_reason: str | None = None


class ReorderRequest(BaseModel):
    ordered_ids: list[UUID] = Field(min_length=1)


class ReadinessReason(BaseModel):
    code: str
    message: str
    entity_id: UUID | None = None
    blocking: bool = True


class StoryboardReadiness(BaseModel):
    ready: bool
    planned_duration_sec: float
    target_duration_sec: float
    discrepancy_sec: float
    reasons: list[ReadinessReason]


class StoryboardVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_id: UUID
    version_number: int
    status: str
    snapshot_json: dict
    content_hash: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None


class ApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=200)


class ProposalCreate(BaseModel):
    proposal_type: str = Field(min_length=1, max_length=80)
    payload: dict


class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    proposal_type: str
    payload: dict
    status: str
    validation_errors: list


class PhaseASnapshot(BaseModel):
    """Revision-aware live Phase A plan for frontend clients."""

    revision: str
    content_hash: str
    planned_duration_sec: float
    target_duration_sec: float
    discrepancy_sec: float
    story: dict
    settings: dict | None = None
    readiness: StoryboardReadiness
    chapters: list
    characters: list
    voices: list
    active_storyboard_version_id: UUID | None = None
