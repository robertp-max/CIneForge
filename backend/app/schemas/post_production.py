"""Schemas for offline post-production plan manifests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from backend.app.schemas.production import FFmpegAssemblyPlan


class PostProductionPlanManifest(BaseModel):
    plan_id: UUID
    state: str = "planned_offline"
    created_at: datetime
    manifest_path: Path
    command_template_id: str
    command: list[str]
    input_paths: list[Path]
    input_hashes: list[str]
    probe_count: int
    output_path: Path
    target_duration_sec: float
    calculated_duration_sec: float
    exact_duration_preserved: bool
    execution_submitted: bool = False
    ffmpeg_job_id: UUID | None = None
    output_sha256: str | None = None
    final_probe_json: dict | None = None
    error_message: str | None = None
    plan: FFmpegAssemblyPlan
