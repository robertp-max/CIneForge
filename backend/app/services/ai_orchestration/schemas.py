from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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


class AIProposal(BaseModel):
    proposal_type: ProposalType
    summary: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProposalValidationResult(BaseModel):
    accepted: bool
    errors: list[str] = Field(default_factory=list)

