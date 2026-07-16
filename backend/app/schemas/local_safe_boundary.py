"""Read-only safe/local boundary validation report schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LocalSafeBoundaryFinding(BaseModel):
    code: str
    path: str
    detail: str


class LocalSafeBoundaryReport(BaseModel):
    checkpoint_id: Literal["local_safe_boundary"] = "local_safe_boundary"
    passed: bool
    finding_count: int
    findings: list[LocalSafeBoundaryFinding] = Field(default_factory=list)
    live_execution_performed_by_endpoint: bool = False
    live_execution_approved_by_endpoint: bool = False
    public_generation_enabled: bool = False
    safety_note: str = (
        "This read-only report performs static file checks only. It does not run FFmpeg/ffprobe, "
        "contact ComfyUI, probe GPU/runtime health, submit prompts, create jobs, render media, "
        "benchmark, approve live work, or enable public generation."
    )
