"""Read-only local MVP readiness checkpoint schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class LocalMVPCheckpointStatus(StrEnum):
    checkpoint_only = "checkpoint_only"
    blocked = "blocked"


class M4PreflightSummary(BaseModel):
    phase: Literal["M4"] = "M4"
    status: str
    hardware_operator_probe_allowed: bool
    live_actions_executed: bool = False
    public_generation_enabled: bool = False
    public_prompt_enabled: bool = False
    check_count: int
    passed_check_count: int
    blocking_reasons: list[str]
    next_allowed_action: str


class M5PostProductionReadinessSummary(BaseModel):
    phase: Literal["M5"] = "M5"
    recipe_catalog_count: int
    recipe_template_ids: list[str] = Field(default_factory=list)
    ffmpeg_recipes_read_only: bool
    ffmpeg_recipes_execute_from_catalog: bool
    user_authored_ffmpeg_commands_allowed: bool
    ffmpeg_execution_endpoint_present: bool = False
    recipe_command_routes_read_only: bool = True
    live_ffmpeg_probe_or_execute_performed: bool = False
    safe_metadata_source: str = "backend.app.services.ffmpeg.service.ffmpeg_command_template_catalog"


class LocalMVPReadinessCheck(BaseModel):
    code: str
    passed: bool
    severity: Literal["info", "warning", "blocker"]
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class LocalMVPReadinessReport(BaseModel):
    checkpoint_id: Literal["local_mvp_readiness"] = "local_mvp_readiness"
    status: LocalMVPCheckpointStatus
    local_only_target: bool = True
    public_generation_disabled: bool
    autonomous_generation_disabled: bool
    generation_enabled: bool
    public_generation_enabled: bool
    queue_worker_enabled: bool
    hardware_operator_enabled: bool
    live_execution_performed_by_endpoint: bool = False
    live_execution_approved_by_endpoint: bool = False
    local_operator_live_runs_allowed_by_endpoint: bool = False
    m4_preflight: M4PreflightSummary
    m5_post_production: M5PostProductionReadinessSummary
    checks: list[LocalMVPReadinessCheck]
    remaining_blockers_before_local_operator_live_runs: list[str]
    safe_metadata_sources: list[str]
    safety_note: str = (
        "This checkpoint is read-only. It does not run FFmpeg/ffprobe, contact ComfyUI, "
        "acquire GPU leases, submit prompts, render media, benchmark, create jobs, or enable public generation."
    )
