"""Read-only M4 hardware-operator preflight report schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class M4PreflightStatus(StrEnum):
    blocked = "blocked"
    operator_probe_ready = "operator_probe_ready"


class M4PreflightCheck(BaseModel):
    code: str
    passed: bool
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class M4HardwarePreflightReport(BaseModel):
    phase: Literal["M4"] = "M4"
    status: M4PreflightStatus
    hardware_operator_probe_allowed: bool
    live_actions_executed: bool = False
    public_generation_enabled: bool = False
    public_prompt_enabled: bool = False
    required_submission_mode: Literal["hardware_operator"] = "hardware_operator"
    queue_worker_enabled: bool
    hardware_operator_enabled: bool
    m4_hardware_probe_approved: bool
    checks: list[M4PreflightCheck]
    blocking_reasons: list[str]
    next_allowed_action: str
    safety_note: str = (
        "This is a read-only gate report. It never launches ComfyUI, loads models, "
        "submits prompts, runs GPU work, renders media, benchmarks, installs nodes, "
        "downloads files, or enables public generation."
    )
