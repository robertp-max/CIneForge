"""Fail-closed public-release readiness report schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LocalPublicReadinessSummary(BaseModel):
    total: int
    blocked: int
    benchmark_required: int
    ready: int
    public_generation_enabled: bool = False


class LocalPublicReadinessCheck(BaseModel):
    code: str
    passed: bool
    severity: Literal["info", "warning", "blocker"]
    message: str
    evidence: dict[str, object] = Field(default_factory=dict)


class LocalPublicReadinessReport(BaseModel):
    checkpoint_id: Literal["local_public_release_readiness"] = "local_public_release_readiness"
    status: Literal["blocked"] = "blocked"
    public_release_ready: bool = False
    public_generation_enabled: bool = False
    public_prompt_enabled: bool = False
    internet_facing_enabled: bool = False
    autonomous_generation_enabled: bool = False
    live_execution_performed_by_endpoint: bool = False
    live_execution_approved_by_endpoint: bool = False
    archetype_summary: LocalPublicReadinessSummary
    preset_summary: LocalPublicReadinessSummary
    local_mvp_status: str
    m4_hardware_probe_allowed: bool
    m5_ffmpeg_execution_endpoint_present: bool
    checks: list[LocalPublicReadinessCheck]
    remaining_public_release_blockers: list[str]
    safe_metadata_sources: list[str]
    safety_note: str = (
        "This fail-closed report is read-only. It does not run FFmpeg/ffprobe, contact ComfyUI, "
        "probe GPU/runtime health, submit prompts, create jobs, render media, benchmark, approve live work, "
        "or enable public generation."
    )
