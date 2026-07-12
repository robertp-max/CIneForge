"""Strict Storyboard Phase 1 proposal contracts.

Nested shape: Project → Story → Characters/Voices/Chapters → Scenes → Shots.
All models use extra='forbid'. Client IDs are stable proposal-local identifiers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NativeVoiceCapability(StrEnum):
    supported = "supported"
    unsupported = "unsupported"
    unknown = "unknown"


class ContinuitySourceType(StrEnum):
    none = "none"
    previous_shot = "previous_shot"
    shot_ref = "shot_ref"
    starting_image = "starting_image"


class VoiceSetupMode(StrEnum):
    placeholder = "placeholder"
    manual = "manual"
    existing_provider_voice = "existing_provider_voice"
    qwen_voice_design = "qwen_voice_design"
    qwen_custom_voice = "qwen_custom_voice"
    elevenlabs_voice_design = "elevenlabs_voice_design"
    parler_local_voice_design = "parler_local_voice_design"
    user_provided_consented = "user_provided_consented"


class ProposalStatus(StrEnum):
    pending_review = "pending_review"
    validated = "validated"
    needs_review = "needs_review"
    rejected = "rejected"
    applied = "applied"
    superseded = "superseded"


class ValidationStatus(StrEnum):
    valid = "valid"
    invalid = "invalid"
    needs_review = "needs_review"


class ProposedNarration(StrictModel):
    client_id: str = Field(min_length=1, max_length=128)
    narration_text: str | None = None
    voice_client_id: str | None = Field(default=None, max_length=128)
    start_offset_sec: float = Field(default=0, ge=0)
    expected_duration_sec: float | None = Field(default=None, gt=0)
    narration_exception_reason: str | None = None

    @model_validator(mode="after")
    def require_text_or_exception(self) -> ProposedNarration:
        text = (self.narration_text or "").strip()
        exception = (self.narration_exception_reason or "").strip()
        if not text and not exception:
            raise ValueError("narration_text or narration_exception_reason is required")
        return self


class ProposedPromptPackage(StrictModel):
    image_prompt: str | None = None
    video_prompt: str | None = None
    negative_prompt: str | None = None
    continuity_instructions: str | None = None
    style_lock_prompt: str | None = None
    provider_profile_id: UUID | None = None
    provider_model_id: str | None = None

    @model_validator(mode="after")
    def require_prompt(self) -> ProposedPromptPackage:
        if not (self.image_prompt or "").strip() and not (self.video_prompt or "").strip():
            raise ValueError("image_prompt or video_prompt is required")
        return self


class ProposedModelRecommendation(StrictModel):
    recommendation_type: str = Field(min_length=1, max_length=64)
    generation_model_variant_id: UUID | None = None
    workflow_template_id: UUID | None = None
    provider_profile_id: UUID | None = None
    provider_identifier: str | None = Field(default=None, max_length=80)
    provider_model_id: str | None = None
    rationale: str | None = None
    availability_status: str = Field(default="unknown", max_length=32)
    benchmark_status: str = Field(default="unknown", max_length=32)
    risk_status: str | None = Field(default=None, max_length=32)
    recommends_qwen_voice: bool = False
    native_voice_capability: NativeVoiceCapability | None = None


class ProposedShotCharacter(StrictModel):
    character_client_id: str = Field(min_length=1, max_length=128)
    role_in_shot: str | None = None
    order_index: int = Field(default=0, ge=0)
    continuity_notes: str | None = None


class ProposedShot(StrictModel):
    client_id: str = Field(min_length=1, max_length=128)
    existing_id: UUID | None = None
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    duration_sec: float = Field(gt=0)
    duration_override_reason: str | None = None
    story_purpose: str | None = None
    visual_description: str | None = None
    location: str | None = None
    continuity_source_type: ContinuitySourceType = ContinuitySourceType.none
    continuity_source_shot_client_id: str | None = Field(default=None, max_length=128)
    starting_image_required: bool = False
    starting_image_asset_id: UUID | None = None
    characters: list[ProposedShotCharacter] = Field(default_factory=list)
    narration: ProposedNarration
    prompt_package: ProposedPromptPackage
    model_recommendations: list[ProposedModelRecommendation] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_duration_and_continuity(self) -> ProposedShot:
        if not 6 <= self.duration_sec <= 12 and not (self.duration_override_reason or "").strip():
            raise ValueError("Shots outside 6–12 seconds require duration_override_reason")
        if self.continuity_source_type == ContinuitySourceType.none:
            if self.continuity_source_shot_client_id:
                raise ValueError(
                    "continuity_source_shot_client_id must be omitted when continuity_source_type is none"
                )
        elif self.continuity_source_type in {
            ContinuitySourceType.previous_shot,
            ContinuitySourceType.shot_ref,
        }:
            if not self.continuity_source_shot_client_id:
                raise ValueError("continuity_source_shot_client_id is required")
        return self


class ProposedScene(StrictModel):
    client_id: str = Field(min_length=1, max_length=128)
    existing_id: UUID | None = None
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = None
    narrative_purpose: str | None = None
    location: str | None = None
    conflict_or_beat: str | None = None
    shots: list[ProposedShot] = Field(default_factory=list)

    @field_validator("shots")
    @classmethod
    def shots_unique_and_ordered(cls, shots: list[ProposedShot]) -> list[ProposedShot]:
        ids = [s.client_id for s in shots]
        if len(ids) != len(set(ids)):
            raise ValueError("shot client_id values must be unique within a scene")
        indexes = sorted(s.order_index for s in shots)
        if shots and indexes != list(range(len(shots))):
            raise ValueError("shot order_index values must be contiguous from 0")
        return shots


class ProposedChapter(StrictModel):
    client_id: str = Field(min_length=1, max_length=128)
    existing_id: UUID | None = None
    order_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = None
    scenes: list[ProposedScene] = Field(default_factory=list)

    @field_validator("scenes")
    @classmethod
    def scenes_unique_and_ordered(cls, scenes: list[ProposedScene]) -> list[ProposedScene]:
        ids = [s.client_id for s in scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("scene client_id values must be unique within a chapter")
        indexes = sorted(s.order_index for s in scenes)
        if scenes and indexes != list(range(len(scenes))):
            raise ValueError("scene order_index values must be contiguous from 0")
        return scenes


class ProposedCharacter(StrictModel):
    client_id: str = Field(min_length=1, max_length=128)
    existing_id: UUID | None = None
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
    assigned_voice_client_id: str | None = Field(default=None, max_length=128)
    reference_asset_ids: list[UUID] = Field(default_factory=list)
    approval_state: str = Field(default="draft", max_length=32)


class ProposedVoice(StrictModel):
    client_id: str = Field(min_length=1, max_length=128)
    existing_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(min_length=1, max_length=48)
    character_client_id: str | None = Field(default=None, max_length=128)
    provider: str | None = Field(default=None, max_length=80)
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
    setup_mode: VoiceSetupMode = VoiceSetupMode.manual
    provider_model_id: str | None = None
    recipe_name: str | None = None
    recipe_description: str | None = None
    design_description: str | None = None
    approval_state: str = Field(default="draft", max_length=32)

    @model_validator(mode="after")
    def require_consent_for_user_voice(self) -> ProposedVoice:
        if self.source_type == "user_provided_consented" and not self.consent_confirmed:
            raise ValueError("user_provided_consented requires consent_confirmed")
        return self


class ProposedStory(StrictModel):
    client_id: str = Field(min_length=1, max_length=128)
    existing_id: UUID | None = None
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
    characters: list[ProposedCharacter] = Field(default_factory=list)
    voices: list[ProposedVoice] = Field(default_factory=list)
    chapters: list[ProposedChapter] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_nested_identity_and_duration(self) -> ProposedStory:
        char_ids = [c.client_id for c in self.characters]
        if len(char_ids) != len(set(char_ids)):
            raise ValueError("character client_id values must be unique")
        voice_ids = [v.client_id for v in self.voices]
        if len(voice_ids) != len(set(voice_ids)):
            raise ValueError("voice client_id values must be unique")
        chapter_ids = [c.client_id for c in self.chapters]
        if len(chapter_ids) != len(set(chapter_ids)):
            raise ValueError("chapter client_id values must be unique")
        chapter_indexes = sorted(c.order_index for c in self.chapters)
        if self.chapters and chapter_indexes != list(range(len(self.chapters))):
            raise ValueError("chapter order_index values must be contiguous from 0")

        voice_set = set(voice_ids)
        for character in self.characters:
            if character.assigned_voice_client_id and character.assigned_voice_client_id not in voice_set:
                raise ValueError(
                    f"character '{character.client_id}' assigned_voice_client_id does not resolve"
                )

        planned = 0.0
        shot_ids: list[str] = []
        for chapter in self.chapters:
            for scene in chapter.scenes:
                for shot in scene.shots:
                    planned += float(shot.duration_sec)
                    shot_ids.append(shot.client_id)
        if len(shot_ids) != len(set(shot_ids)):
            raise ValueError("shot client_id values must be unique across the story")
        if round(planned - float(self.target_duration_sec), 4) != 0:
            raise ValueError(
                f"exact duration mismatch: planned {planned:g}s != target {self.target_duration_sec:g}s"
            )
        return self


class StoryboardProposalPayload(StrictModel):
    """Root Project→Story proposal payload."""

    schema_name: str = Field(default="storyboard_proposal_v1")
    project_id: UUID
    story: ProposedStory
    base_storyboard_version_id: UUID | None = None
    base_content_hash: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("schema_name")
    @classmethod
    def schema_must_be_v1(cls, value: str) -> str:
        if value != "storyboard_proposal_v1":
            raise ValueError("schema_name must be storyboard_proposal_v1")
        return value


class ProposalCreateRequest(StrictModel):
    proposal_type: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=2000)
    payload: dict[str, Any]
    story_id: UUID | None = None
    orchestration_run_id: UUID | None = None
    base_storyboard_version_id: UUID | None = None
    schema_name: str | None = Field(default="storyboard_proposal_v1", max_length=128)


class ProposalRejectRequest(StrictModel):
    rejected_by: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=4000)


class ProposalReviewRequest(StrictModel):
    reviewed_by: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class ProposalApplyRequest(StrictModel):
    applied_by: str = Field(min_length=1, max_length=200)
    expected_base_version_id: UUID | None = None
    expected_base_content_hash: str | None = Field(default=None, min_length=64, max_length=64)


class ProposalDiffOp(StrictModel):
    op: str  # add | remove | replace
    path: str
    before: Any | None = None
    after: Any | None = None


class ProposalDiffResponse(StrictModel):
    proposal_id: UUID
    base_storyboard_version_id: UUID | None = None
    base_content_hash: str | None = None
    proposed_content_hash: str
    ops: list[ProposalDiffOp]


class ProposalValidationResponse(StrictModel):
    accepted: bool
    validation_status: ValidationStatus
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    report: dict[str, Any] = Field(default_factory=dict)


class ProposalRead(StrictModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    proposal_type: str
    payload: dict[str, Any]
    status: str
    validation_errors: list = Field(default_factory=list)
    story_id: UUID | None = None
    orchestration_run_id: UUID | None = None
    base_storyboard_version_id: UUID | None = None
    schema_name: str | None = None
    content_hash: str | None = None
    validation_status: str | None = None
    validation_report_json: dict[str, Any] = Field(default_factory=dict)
    warnings_json: list = Field(default_factory=list)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    applied_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime | None = None


class ProposalApplyResult(StrictModel):
    proposal_id: UUID
    story_id: UUID
    new_storyboard_version_id: UUID
    version_number: int
    content_hash: str
    status: str
