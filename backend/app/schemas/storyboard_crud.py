"""Schemas for remaining Storyboard Phase 1 planning CRUD entities."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovalState(StrEnum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    blocked = "blocked"


class RecommendationType(StrEnum):
    generation = "generation"
    workflow = "workflow"
    voice = "voice"
    other = "other"


class AssignmentMode(StrEnum):
    manual = "manual"
    default = "default"
    suggested = "suggested"


class ProviderExecutionMode(StrEnum):
    disabled = "disabled"
    manual = "manual"
    assisted = "assisted"
    automatic = "automatic"


# ---------------------------------------------------------------------------
# Shot narration
# ---------------------------------------------------------------------------


class ShotNarrationCreate(BaseModel):
    voice_profile_id: UUID | None = None
    narration_text: str | None = None
    start_offset_sec: float = Field(default=0, ge=0)
    expected_duration_sec: float | None = Field(default=None, gt=0)
    narration_exception_reason: str | None = None
    approval_state: ApprovalState = ApprovalState.draft

    @model_validator(mode="after")
    def require_text_or_exception(self):
        has_text = bool((self.narration_text or "").strip())
        has_exception = bool((self.narration_exception_reason or "").strip())
        if not has_text and not has_exception:
            raise ValueError("Narration requires text or an exception reason.")
        return self


class ShotNarrationUpdate(BaseModel):
    voice_profile_id: UUID | None = None
    narration_text: str | None = None
    start_offset_sec: float | None = Field(default=None, ge=0)
    expected_duration_sec: float | None = Field(default=None, gt=0)
    narration_exception_reason: str | None = None
    approval_state: ApprovalState | None = None


class ShotNarrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shot_id: UUID
    voice_profile_id: UUID | None = None
    narration_text: str | None = None
    start_offset_sec: float
    expected_duration_sec: float | None = None
    narration_exception_reason: str | None = None
    approval_state: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Prompt packages / versions
# ---------------------------------------------------------------------------


class ShotPromptPackageCreate(BaseModel):
    image_prompt: str | None = None
    video_prompt: str | None = None
    negative_prompt: str | None = None
    continuity_instructions: str | None = None
    style_lock_prompt: str | None = None
    provider_profile_id: UUID | None = None
    provider_model_id: str | None = None
    proposal_id: UUID | None = None
    approval_state: ApprovalState = ApprovalState.draft
    # If set, create as this explicit version (must not collide).
    version: int | None = Field(default=None, ge=1)


class ShotPromptPackageUpdate(BaseModel):
    image_prompt: str | None = None
    video_prompt: str | None = None
    negative_prompt: str | None = None
    continuity_instructions: str | None = None
    style_lock_prompt: str | None = None
    provider_profile_id: UUID | None = None
    provider_model_id: str | None = None
    proposal_id: UUID | None = None
    approval_state: ApprovalState | None = None


class ShotPromptPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shot_id: UUID
    version: int
    image_prompt: str | None = None
    video_prompt: str | None = None
    negative_prompt: str | None = None
    continuity_instructions: str | None = None
    style_lock_prompt: str | None = None
    provider_profile_id: UUID | None = None
    provider_model_id: str | None = None
    proposal_id: UUID | None = None
    approval_state: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Model / workflow recommendations
# ---------------------------------------------------------------------------


class ShotModelRecommendationCreate(BaseModel):
    recommendation_type: RecommendationType
    generation_model_variant_id: UUID | None = None
    workflow_template_id: UUID | None = None
    rationale: str | None = None
    availability_status: str = Field(default="unknown", max_length=32)
    benchmark_status: str = Field(default="unknown", max_length=32)
    risk_status: str | None = Field(default=None, max_length=32)
    approval_state: ApprovalState = ApprovalState.draft

    @model_validator(mode="after")
    def require_target(self):
        if self.generation_model_variant_id is None and self.workflow_template_id is None:
            raise ValueError("Recommendation requires a model variant and/or workflow template.")
        return self


class ShotModelRecommendationUpdate(BaseModel):
    recommendation_type: RecommendationType | None = None
    generation_model_variant_id: UUID | None = None
    workflow_template_id: UUID | None = None
    rationale: str | None = None
    availability_status: str | None = Field(default=None, max_length=32)
    benchmark_status: str | None = Field(default=None, max_length=32)
    risk_status: str | None = Field(default=None, max_length=32)
    approval_state: ApprovalState | None = None
    acknowledge: bool | None = None


class ShotModelRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shot_id: UUID
    recommendation_type: str
    generation_model_variant_id: UUID | None = None
    workflow_template_id: UUID | None = None
    rationale: str | None = None
    availability_status: str
    benchmark_status: str
    risk_status: str | None = None
    acknowledged_at: datetime | None = None
    approval_state: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Provider profiles
# ---------------------------------------------------------------------------


class ProviderProfileCreate(BaseModel):
    provider_identifier: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=200)
    provider_model_id: str | None = None
    execution_mode: ProviderExecutionMode = ProviderExecutionMode.disabled
    availability_status: str = Field(default="unknown", max_length=32)
    privacy_classification: str | None = Field(default=None, max_length=64)
    capabilities_json: dict = Field(default_factory=dict)
    configuration_reference: str | None = None
    capability_source: str | None = None


class ProviderProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    provider_model_id: str | None = None
    execution_mode: ProviderExecutionMode | None = None
    availability_status: str | None = Field(default=None, max_length=32)
    privacy_classification: str | None = Field(default=None, max_length=64)
    capabilities_json: dict | None = None
    configuration_reference: str | None = None
    capability_source: str | None = None


class ProviderProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_identifier: str
    display_name: str
    provider_model_id: str | None = None
    execution_mode: str
    availability_status: str
    privacy_classification: str | None = None
    capabilities_json: dict = Field(default_factory=dict)
    configuration_reference: str | None = None
    capabilities_checked_at: datetime | None = None
    health_checked_at: datetime | None = None
    capability_source: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Task provider assignments
# ---------------------------------------------------------------------------


class TaskProviderAssignmentCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=64)
    provider_profile_id: UUID
    assignment_mode: AssignmentMode = AssignmentMode.manual
    rationale: str | None = None
    priority: int = 0
    enabled: bool = True


class TaskProviderAssignmentUpdate(BaseModel):
    provider_profile_id: UUID | None = None
    assignment_mode: AssignmentMode | None = None
    rationale: str | None = None
    priority: int | None = None
    enabled: bool | None = None


class TaskProviderAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    story_id: UUID
    task_type: str
    provider_profile_id: UUID
    assignment_mode: str
    rationale: str | None = None
    priority: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


class ProposalCreateExtended(BaseModel):
    proposal_type: str = Field(min_length=1, max_length=80)
    payload: dict
    story_id: UUID | None = None
    orchestration_run_id: UUID | None = None
    base_storyboard_version_id: UUID | None = None
    schema_name: str | None = Field(default=None, max_length=128)


class ProposalUpdate(BaseModel):
    status: str | None = Field(default=None, min_length=1, max_length=64)
    validation_status: str | None = Field(default=None, max_length=32)
    validation_errors: list | None = None
    validation_report_json: dict | None = None
    warnings_json: list | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None


class ProposalReadExtended(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposal_type: str
    payload: dict
    status: str
    validation_errors: list = Field(default_factory=list)
    story_id: UUID | None = None
    orchestration_run_id: UUID | None = None
    base_storyboard_version_id: UUID | None = None
    schema_name: str | None = None
    content_hash: str | None = None
    validation_status: str | None = None
    validation_report_json: dict = Field(default_factory=dict)
    warnings_json: list = Field(default_factory=list)
    superseded_by_id: UUID | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    applied_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Storyboard versions (list / get)
# ---------------------------------------------------------------------------


class StoryboardVersionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    story_id: UUID
    version_number: int
    status: str
    content_hash: str | None = None
    created_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    superseded_at: datetime | None = None
    base_version_id: UUID | None = None
    source_proposal_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class StoryboardVersionDetail(StoryboardVersionListItem):
    snapshot_json: dict
