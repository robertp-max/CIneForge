"""Read-only benchmark ladder manifest schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class BenchmarkStageStatus(StrEnum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    blocked = "blocked"


class BenchmarkLadderStage(BaseModel):
    stage: int
    stage_id: str
    workload: str
    minimum_pass_condition: str
    archetypes: list[str] = Field(default_factory=list)
    profile: str | None = None
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    steps: int | None = None
    status: BenchmarkStageStatus = BenchmarkStageStatus.pending
    requires_operator_approval: bool = True
    requires_hardware_operator_mode: bool = True
    requires_exclusive_gpu_lease: bool = True
    requires_queue_empty_before: bool = True
    live_action_approved: bool = False
    public_generation_enabled: bool = False
    requires_stage_success: list[int] = Field(default_factory=list)


class BenchmarkLadderManifest(BaseModel):
    ladder_id: str
    phase: Literal["M4"] = "M4"
    name: str
    hardware_profile: str
    archetypes_in_scope: list[str]
    allowed_stage_numbers: list[int]
    deferred_stage_numbers: list[int] = Field(default_factory=list)
    public_generation_enabled: bool = False
    queue_worker_general_execution_enabled: bool = False
    requires_serial_execution: bool = True
    requires_hardware_operator_mode: bool = True
    stages: list[BenchmarkLadderStage]
    evidence_note: str = (
        "Read-only ladder manifest. Loading this manifest does not run ComfyUI, "
        "load models, submit prompts, render media, benchmark, mutate runtime, "
        "or approve live hardware execution."
    )
