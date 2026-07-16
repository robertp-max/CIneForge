"""Schemas for local operator run packets.

These packets prepare review metadata for future live M4/M5 operator actions.
They are not approvals and never represent execution.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class LocalOperatorRunMode(StrEnum):
    m4_hardware_ladder_probe = "m4_hardware_ladder_probe"
    m5_ffmpeg_probe_validation = "m5_ffmpeg_probe_validation"
    m5_ffmpeg_assembly_validation = "m5_ffmpeg_assembly_validation"


class LocalOperatorRunPacketCreate(BaseModel):
    mode: LocalOperatorRunMode
    requested_by: str = Field(min_length=1, max_length=200)
    target_ref: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2_000)
    acknowledge_no_execution: bool = False

    @model_validator(mode="after")
    def require_no_execution_acknowledgement(self) -> "LocalOperatorRunPacketCreate":
        if not self.acknowledge_no_execution:
            raise ValueError("acknowledge_no_execution must be true; packets never approve or start live work")
        return self


class LocalOperatorLocalMVPSummary(BaseModel):
    status: str
    local_only_target: bool
    public_generation_disabled: bool
    autonomous_generation_disabled: bool
    live_execution_approved_by_endpoint: bool = False
    local_operator_live_runs_allowed_by_endpoint: bool = False


class LocalOperatorM4PreflightSummary(BaseModel):
    status: str
    hardware_operator_probe_allowed: bool
    live_actions_executed: bool = False
    check_count: int
    passed_check_count: int
    blocking_reasons: list[str]
    next_allowed_action: str


class LocalOperatorM5RecipeSummary(BaseModel):
    recipe_catalog_count: int
    ffmpeg_recipes_read_only: bool
    ffmpeg_execution_endpoint_present: bool = False
    live_ffmpeg_probe_or_execute_performed: bool = False
    user_authored_ffmpeg_commands_allowed: bool = False


class LocalOperatorRunPacket(BaseModel):
    packet_id: UUID
    state: Literal["pending_explicit_operator_approval"] = "pending_explicit_operator_approval"
    created_at: datetime
    manifest_path: Path
    request: LocalOperatorRunPacketCreate
    approval_recorded: bool = False
    live_execution_started: bool = False
    generation_submitted: bool = False
    ffmpeg_submitted: bool = False
    comfy_prompt_id: str | None = None
    queue_job_id: UUID | None = None
    local_mvp: LocalOperatorLocalMVPSummary
    m4_preflight: LocalOperatorM4PreflightSummary | None = None
    m5_recipes: LocalOperatorM5RecipeSummary | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    operator_checklist: list[str] = Field(default_factory=list)
    safe_metadata_sources: list[str] = Field(default_factory=list)
    safety_note: str = (
        "This packet is review metadata only. It does not approve, run, submit, probe, render, "
        "benchmark, acquire GPU leases, or execute FFmpeg/ffprobe/ComfyUI work."
    )
