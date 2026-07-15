"""Contracts for CineForge's seven-phase lifecycle and local production lane."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PhaseLifecycleState = Literal[
    "not_started",
    "drafting",
    "qa_pending",
    "needs_revision",
    "ready_for_review",
    "approved",
    "blocked",
]

PhaseVersionSource = Literal[
    "baseline",
    "manual",
    "generated",
    "revision",
    "imported",
]

PhaseOneBaselineKey = Literal["transfiguration_phase_one"]


class PhaseOneGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_prompt: str = Field(min_length=1)
    target_duration_sec: float = Field(gt=0, le=21_600)
    audience: str | None = None
    genre: str | None = None
    tone: str | None = None
    language: str = Field(default="English", min_length=1, max_length=100)
    visual_style: str | None = None
    narration_dialogue_preference: str | None = None
    source_fidelity_constraints: str | None = None
    content_constraints: str | None = None
    comparison_baseline: PhaseOneBaselineKey | None = None
    requested_by: str | None = Field(default=None, max_length=200)


class PhaseOneRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version_number: int = Field(gt=0)
    project_title: str = Field(min_length=1, max_length=300)
    logline: str = Field(min_length=1)
    short_synopsis: str = Field(min_length=1)
    detailed_treatment: str = Field(min_length=1)
    complete_script: str = Field(min_length=1)
    narration_script: str = ""
    dialogue_script: str = ""
    non_dialogue_action: list[str] = Field(default_factory=list)
    silent_visual_beats: list[str] = Field(default_factory=list)
    emotional_progression: list[str] = Field(default_factory=list)
    dramatic_escalation: list[str] = Field(default_factory=list)
    source_fidelity_notes: list[str] = Field(default_factory=list)
    creative_assumptions: list[str] = Field(default_factory=list)
    requested_by: str | None = Field(default=None, max_length=200)


class PhaseVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=300)
    notes: str = Field(default="", max_length=4000)
    requested_by: str | None = Field(default=None, max_length=200)


class PhaseVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    label: str
    notes: str
    source: PhaseVersionSource
    lifecycle_state: PhaseLifecycleState
    completed: bool
    snapshot_schema_version: int
    input_hash: str
    output_hash: str
    created_by: str | None = None
    previous_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class PhaseVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    label: str = ""
    notes: str = ""
    source: PhaseVersionSource = "manual"
    snapshot_schema_version: int = 1
    lifecycle_state: PhaseLifecycleState
    completed: bool
    input_snapshot_json: dict[str, Any]
    output_json: dict[str, Any]
    input_hash: str
    output_hash: str
    created_by: str | None = None
    previous_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    verified: bool = True


class PhaseVersionDetail(PhaseVersionRead):
    story_id: UUID
    project_id: UUID
    phase_number: int
    phase_name: str


class QAReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    entity_id: UUID | None = None
    report_json: dict
    created_at: datetime


class ProductionPhaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phase_number: int
    name: str
    lifecycle_state: PhaseLifecycleState
    current_version_number: int | None = None
    version_count: int = 0
    is_locked: bool
    locked_reason: str | None = None
    is_stale: bool
    stale_reason: str | None = None
    generation_completed_at: datetime | None = None
    approved_at: datetime | None = None
    latest_version: PhaseVersionRead | None = None
    latest_qa_report: QAReportRead | None = None


class ProductionPipelineRead(BaseModel):
    story_id: UUID
    project_id: UUID
    exact_phase_count: Literal[7] = 7
    phases: list[ProductionPhaseRead]
    completion_message: str | None = None


class PhaseOneMutationResponse(BaseModel):
    pipeline: ProductionPipelineRead
    phase: ProductionPhaseRead
    completion_message: str


class PhaseVersionCreateResponse(BaseModel):
    version: PhaseVersionDetail
    pipeline: ProductionPipelineRead


class PhaseHistoryExportIntegrity(BaseModel):
    verified: Literal[True] = True
    iteration_count: int
    snapshot_count: int
    phase_counts: dict[str, int]
    hashes: list[str]


class PhaseHistoryExport(BaseModel):
    schema_name: Literal["cineforge.phase-history"] = "cineforge.phase-history"
    version: Literal[1] = 1
    project_id: UUID
    story_id: UUID
    exported_at: datetime
    integrity: PhaseHistoryExportIntegrity
    iterations: list[PhaseVersionDetail]


class AspectRatio(StrEnum):
    widescreen_16_9 = "16:9"
    vertical_9_16 = "9:16"
    square_1_1 = "1:1"
    classic_4_3 = "4:3"
    scope_239_1 = "2.39:1"


class OutputProfile(StrEnum):
    draft = "draft"
    review = "review"
    final_candidate = "final_candidate"
    controlled = "controlled"
    lipdub = "lipdub"


class WorkflowState(StrEnum):
    implemented = "implemented"
    dependency_verified = "dependency_verified"
    locally_tested = "locally_tested"
    benchmark_passed = "benchmark_passed"
    human_approved = "human_approved"
    publicly_enabled = "publicly_enabled"


class GateCode(StrEnum):
    preproduction_incomplete = "PREPRODUCTION_INCOMPLETE"
    character_references_missing = "CHARACTER_REFERENCES_MISSING"
    storyboard_not_approved = "STORYBOARD_NOT_APPROVED"
    start_frame_missing = "START_FRAME_MISSING"
    continuity_conditioning_missing = "CONTINUITY_CONDITIONING_MISSING"
    workflow_not_admitted = "WORKFLOW_NOT_ADMITTED"
    smoke_workflow_forbidden = "SMOKE_WORKFLOW_FORBIDDEN"
    preset_benchmark_required = "PRESET_BENCHMARK_REQUIRED"
    invalid_model_frame_count = "INVALID_MODEL_FRAME_COUNT"
    invalid_aspect_ratio_profile = "INVALID_ASPECT_RATIO_PROFILE"
    upscale_stage_missing = "UPSCALE_STAGE_MISSING"
    timeline_duration_invalid = "TIMELINE_DURATION_INVALID"
    untracked_direct_comfy_submission = "UNTRACKED_DIRECT_COMFY_SUBMISSION"
    narration_decision_missing = "NARRATION_DECISION_MISSING"
    vram_preflight_required = "VRAM_PREFLIGHT_REQUIRED"


class BlockingReason(BaseModel):
    code: GateCode
    message: str
    subject: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class GeometryProfile(BaseModel):
    aspect_ratio: AspectRatio
    quality_profile: OutputProfile
    generation_width: int = Field(ge=64)
    generation_height: int = Field(ge=64)
    preview_width: int = Field(ge=64)
    preview_height: int = Field(ge=64)
    delivery_width: int = Field(ge=64)
    delivery_height: int = Field(ge=64)
    upscale_factor: int = Field(default=1, ge=1)
    divisibility: int = Field(default=32, ge=1)
    crop_pad_strategy: str = "center_crop_or_pad_after_generation"


class LtxFramePlan(BaseModel):
    requested_duration_sec: float = Field(gt=0)
    fps: int = Field(ge=1)
    frame_count: int = Field(ge=1)
    realizable_duration_sec: float = Field(gt=0)
    model_family_rule: str = "8n+1"

    @field_validator("frame_count")
    @classmethod
    def validate_ltx_frame_rule(cls, value: int) -> int:
        if (value - 1) % 8 != 0:
            raise ValueError("LTX frame_count must satisfy 8n+1")
        return value


class ProductionBriefRequest(BaseModel):
    project_key: str = Field(default="local-production", min_length=1, max_length=120)
    title: str = Field(default="Untitled Production", min_length=1, max_length=240)
    brief: str = Field(min_length=1, max_length=50_000)
    target_duration_sec: float = Field(gt=0, le=3600)
    aspect_ratio: AspectRatio = AspectRatio.widescreen_16_9
    quality_profile: OutputProfile = OutputProfile.draft
    fps: int = Field(default=24, ge=1, le=120)
    max_model_clip_duration_sec: float = Field(default=5.0, gt=0, le=12)
    min_model_clip_duration_sec: float = Field(default=2.0, gt=0, le=12)
    transition_sec: float = Field(default=0.0, ge=0, le=2)
    character_names: list[str] = Field(default_factory=list)
    narration_required: bool = False
    no_narration_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_narration_decision(self) -> "ProductionBriefRequest":
        if not self.narration_required and not (self.no_narration_reason or "").strip():
            # The gate service also reports this, but keep plan creation usable by
            # filling a factual default rather than rejecting decomposition.
            self.no_narration_reason = "No narration requested for this local production plan."
        if self.min_model_clip_duration_sec > self.max_model_clip_duration_sec:
            raise ValueError("min_model_clip_duration_sec cannot exceed max_model_clip_duration_sec")
        return self


class CharacterReferenceRequest(BaseModel):
    kind: Literal["portrait", "headshot", "full_body", "front", "profile", "three_quarter", "wardrobe", "expression", "pose"]
    prompt: str
    negative_prompt: str
    seed: int
    workflow_archetype_id: str = "CF-IMG-01"
    workflow_state: str = "required_not_rendered"
    asset_id: str | None = None
    approved: bool = False


class CharacterPackage(BaseModel):
    character_id: str
    name: str
    canonical_description: str
    character_generation_prompt: str
    negative_prompt: str
    reference_requests: list[CharacterReferenceRequest]
    primary_identity_asset_id: str | None = None
    identity_adapter: str | None = None
    redux_or_pulid_config: dict[str, Any] = Field(default_factory=dict)
    approval_state: Literal["draft", "references_required", "approved"] = "references_required"
    workflow_provenance: dict[str, Any] = Field(default_factory=dict)

    @property
    def ready_for_character_video(self) -> bool:
        return bool(self.primary_identity_asset_id and self.approval_state == "approved")


class StoryboardFrame(BaseModel):
    storyboard_frame_id: str
    shot_id: str
    first_frame_asset_id: str | None = None
    last_frame_asset_id: str | None = None
    image_workflow_archetype_id: str = "CF-IMG-01"
    workflow_provenance: dict[str, Any] = Field(default_factory=dict)
    approval_state: Literal["missing", "draft", "approved"] = "missing"


class ContinuityDependency(BaseModel):
    shot_id: str
    depends_on_shot_id: str | None = None
    kind: Literal["none", "previous_end_frame", "first_last_bridge", "v2v_continuation", "control_image"] = "none"
    required_asset_ids: list[str] = Field(default_factory=list)
    resolved: bool = True
    workflow_archetype_id: str | None = None


class ShotPlan(BaseModel):
    shot_id: str
    scene_id: str
    order_index: int = Field(ge=0)
    title: str
    prompt: str
    negative_prompt: str
    start_sec: float = Field(ge=0)
    duration_sec: float = Field(gt=0)
    source_handle_start_sec: float = Field(default=0, ge=0)
    source_handle_end_sec: float = Field(default=0, ge=0)
    transition_in_sec: float = Field(default=0, ge=0)
    transition_out_sec: float = Field(default=0, ge=0)
    frame_plan: LtxFramePlan
    geometry: GeometryProfile
    character_ids: list[str] = Field(default_factory=list)
    camera_intent: str = "medium cinematic coverage"
    lens_intent: str = "natural perspective"
    blocking: str = "subject action staged for one model-safe shot"
    location_environment: str = "environment derived from brief"
    storyboard: StoryboardFrame
    continuity: ContinuityDependency
    video_archetype_id: str = "CF-VID-01"
    generation_mode: Literal["t2v", "i2v", "control", "lipdub", "continuation"] = "i2v"
    narration_start_offset_sec: float | None = None
    narration_expected_duration_sec: float | None = None


class ScenePlan(BaseModel):
    scene_id: str
    order_index: int = Field(ge=0)
    title: str
    start_sec: float = Field(ge=0)
    duration_sec: float = Field(gt=0)
    narrative_beat: str
    shots: list[ShotPlan]


class TimelinePlan(BaseModel):
    requested_final_duration_sec: float = Field(gt=0)
    calculated_final_duration_sec: float = Field(gt=0)
    total_source_duration_sec: float = Field(gt=0)
    transition_overlap_sec: float = Field(ge=0)
    exact_duration_preserved: bool


class ProductionPlan(BaseModel):
    project_key: str
    title: str
    brief: str
    target_duration_sec: float
    aspect_ratio: AspectRatio
    quality_profile: OutputProfile
    fps: int
    geometry: GeometryProfile
    scenes: list[ScenePlan]
    characters: list[CharacterPackage]
    timeline: TimelinePlan
    narration_required: bool
    no_narration_reason: str | None = None


class SemanticGenerationRequest(BaseModel):
    preset_id: str
    archetype_id: str
    quality_profile: OutputProfile
    mode: Literal["t2v", "i2v", "control", "lipdub", "continuation"] = "i2v"
    prompt: str
    negative_prompt: str = ""
    reference_image_asset_ids: list[str] = Field(default_factory=list)
    first_image_asset_id: str | None = None
    last_image_asset_id: str | None = None
    source_video_asset_id: str | None = None
    mask_or_control_asset_id: str | None = None
    character_reference_ids: list[str] = Field(default_factory=list)
    seed: int = Field(default=0, ge=0)
    aspect_ratio: AspectRatio = AspectRatio.widescreen_16_9
    width: int = Field(ge=64)
    height: int = Field(ge=64)
    frame_count: int = Field(ge=1)
    fps: int = Field(default=24, ge=1)
    target_duration_sec: float = Field(gt=0)
    upscale_factor: int = Field(default=1, ge=1)
    output_profile: OutputProfile = OutputProfile.draft
    output_prefix: str
    production: bool = True


class ProductionGateReport(BaseModel):
    allowed: bool
    blocking_reasons: list[BlockingReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkflowDependencyRecord(BaseModel):
    key: str
    kind: str
    filename: str | None = None
    path: str | None = None
    sha256: str | None = None
    required: bool = True
    present: bool | None = None
    notes: str | None = None


class SemanticBindingRecord(BaseModel):
    semantic_key: str
    semantic_title: str
    node_id: str | None = None
    class_type: str
    input_name: str
    runtime_parameter: str
    value_type: str
    required: bool = True
    min_value: float | None = None
    max_value: float | None = None


class CanonicalWorkflowRecord(BaseModel):
    archetype_id: str
    version: str
    name: str
    modality: str
    source_url: str | None = None
    source_repository: str | None = None
    source_commit: str | None = None
    source_path: Path | None = None
    template_dir: Path | None = None
    ui_graph_path: Path | None = None
    api_graph_path: Path | None = None
    ui_sha256: str | None = None
    api_sha256: str | None = None
    required_classes: list[str] = Field(default_factory=list)
    dependencies: list[WorkflowDependencyRecord] = Field(default_factory=list)
    bindings: list[SemanticBindingRecord] = Field(default_factory=list)
    supported_modes: list[str] = Field(default_factory=list)
    supported_profiles: list[OutputProfile] = Field(default_factory=list)
    implemented: bool = False
    dependency_verified: bool = False
    locally_tested: bool = False
    benchmark_passed: bool = False
    human_approved: bool = False
    publicly_enabled: bool = False
    readiness: str = "blocked"
    blocked_reasons: list[str] = Field(default_factory=list)


class CompiledWorkflow(BaseModel):
    archetype_id: str
    template_id: str
    template_version: str
    workflow_api_sha256: str
    patch_payload: dict[str, Any]
    patched_workflow: dict[str, Any]
    output_prefix: str
    production: bool


class OutputDiscoveryRecord(BaseModel):
    path: Path
    filename: str
    subfolder: str
    sha256: str
    size_bytes: int
    probe_json: dict[str, Any] | None = None


class FFmpegAssemblyInput(BaseModel):
    path: Path
    duration_sec: float = Field(gt=0)
    start_sec: float = Field(ge=0)
    timeline_duration_sec: float = Field(gt=0)
    transition_out_sec: float = Field(default=0, ge=0)
    sha256: str | None = None
    probe_json: dict[str, Any] | None = None


class FFmpegAssemblyPlan(BaseModel):
    target_duration_sec: float = Field(gt=0)
    aspect_ratio: AspectRatio
    delivery_width: int = Field(ge=64)
    delivery_height: int = Field(ge=64)
    fps: int = Field(ge=1)
    clips: list[FFmpegAssemblyInput]
    command_template_id: str = "assemble_exact_duration_h264_v1"
    calculated_duration_sec: float
    exact_duration_preserved: bool
    output_path: Path | None = None
    input_hashes: list[str] = Field(default_factory=list)
