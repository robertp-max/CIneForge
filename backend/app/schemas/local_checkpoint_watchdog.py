"""Read-only checkpoint watchdog report schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LocalCheckpointWatchdogReport(BaseModel):
    checkpoint_id: Literal["local_checkpoint_watchdog"] = "local_checkpoint_watchdog"
    last_commit: str
    tracked_worktree_clean: bool
    reminder: str
    invariants: list[str] = Field(default_factory=list)
    live_execution_performed_by_endpoint: bool = False
    live_execution_approved_by_endpoint: bool = False
    public_generation_enabled: bool = False
    safety_note: str = (
        "This read-only report inspects git metadata and prints the continuation reminder only. It does not run "
        "FFmpeg/ffprobe, contact ComfyUI, probe GPU/runtime health, submit prompts, create jobs, render media, "
        "benchmark, approve live work, or enable public generation."
    )
