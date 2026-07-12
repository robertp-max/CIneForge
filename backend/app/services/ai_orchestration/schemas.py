from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProposalType(StrEnum):
    create_shot_list = "create_shot_list"
    revise_prompt = "revise_prompt"
    retry_failed_shot = "retry_failed_shot"
    continuity_fix = "continuity_fix"
    benchmark_recommendation = "benchmark_recommendation"
    assembly_note = "assembly_note"
    autonomy_plan = "autonomy_plan"
    qa_review = "qa_review"
    batch_plan = "batch_plan"
    # Storyboard Phase 1 proposal types (review-gated; never auto-execute).
    storyboard_full_plan = "storyboard_full_plan"
    storyboard_revision = "storyboard_revision"
    storyboard_character_voice_plan = "storyboard_character_voice_plan"


STORYBOARD_PROPOSAL_TYPES = frozenset(
    {
        ProposalType.storyboard_full_plan,
        ProposalType.storyboard_revision,
        ProposalType.storyboard_character_voice_plan,
    }
)

STORYBOARD_PROPOSAL_SCHEMA_NAME = "storyboard_proposal_v1"


class AIProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_type: ProposalType
    summary: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_name: str | None = None
    story_id: str | None = None
    base_storyboard_version_id: str | None = None
    base_content_hash: str | None = None


class ProposalValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_status: str = "valid"  # valid | invalid | needs_review
    content_hash: str | None = None
    report: dict[str, Any] = Field(default_factory=dict)
