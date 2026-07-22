"""Schemas for local semantic generation manifests and explicit queue handoff.

The manifest creation path is offline. Promotion to the durable worker queue
requires an explicit acknowledgement and a default-off operator gate; no
public raw prompt-submission contract is exposed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.production import OutputProfile, ProductionGateReport, SemanticGenerationRequest


class SemanticCompiledWorkflowMetadata(BaseModel):
    archetype_id: str
    template_id: str
    template_version: str
    workflow_api_sha256: str
    patch_payload: dict[str, object]
    output_prefix: str
    production: bool


class SemanticGenerationRequestManifest(BaseModel):
    request_id: UUID
    state: Literal[
        "blocked_by_gates",
        "prepared_offline",
        "queued",
        "submitted",
        "running",
        "collecting_outputs",
        "complete",
        "failed",
    ]
    created_at: datetime
    manifest_path: Path
    request: SemanticGenerationRequest
    gate_report: ProductionGateReport
    generation_submitted: bool = False
    comfy_prompt_id: str | None = None
    queue_job_id: UUID | None = None
    workflow_snapshot_path: Path | None = None
    compiled_workflow_metadata: SemanticCompiledWorkflowMetadata | None = None


class SemanticQueueRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=200)
    acknowledge_local_gpu_execution: Literal[True]


class StoryboardHandoffRequest(BaseModel):
    """Explicit local-only bridge from an approved storyboard to semantic manifests."""

    model_config = ConfigDict(extra="forbid")

    story_id: UUID
    shot_id: UUID | None = None
    preset_id: str = Field(default="CF-PRESET-001", min_length=1, max_length=80)
    archetype_id: str = Field(default="CF-VID-01", min_length=1, max_length=80)
    quality_profile: OutputProfile = OutputProfile.draft
    mode: Literal["t2v", "i2v", "control", "lipdub", "continuation"] = "t2v"
    output_project_key: str | None = Field(default=None, min_length=1, max_length=120)
    run_stem: str | None = Field(default=None, min_length=1, max_length=120)


class StoryboardHandoffManifestSummary(BaseModel):
    shot_id: UUID
    request_id: UUID
    state: Literal["blocked_by_gates", "prepared_offline"]
    gate_allowed: bool
    blocking_codes: list[str]
    generation_submitted: bool = False


class StoryboardHandoffReport(BaseModel):
    story_id: UUID
    active_storyboard_version_id: UUID | None = None
    active_storyboard_content_hash: str | None = None
    selected_shot_count: int = 0
    created_manifests: list[StoryboardHandoffManifestSummary] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    generation_submitted: bool = False
    execution_started: bool = False
    automatic_from_approval: bool = False
    safety_note: str = (
        "Explicit local/offline handoff only; no ComfyUI submission, queue execution, "
        "GPU lease, render, or runtime health call was started."
    )
