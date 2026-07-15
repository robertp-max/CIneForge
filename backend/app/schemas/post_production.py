"""Schemas for offline post-production plan manifests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.schemas.production import FFmpegAssemblyInput, FFmpegAssemblyPlan, GeometryProfile


class PostProductionAssemblyPlanCreate(BaseModel):
    clips: list[FFmpegAssemblyInput] = Field(min_length=1)
    target_duration_sec: float = Field(gt=0)
    geometry: GeometryProfile
    fps: int = Field(ge=1, le=120)
    output_path: Path



class PostProductionPlanSuccessRecord(BaseModel):
    output_sha256: str
    final_probe_json: dict[str, Any]
    ffmpeg_job_id: UUID | None = None


class PostProductionPlanErrorRecord(BaseModel):
    error_message: str = Field(min_length=1, max_length=10_000)
    ffmpeg_job_id: UUID | None = None


class PostProductionRecipeCommandSuccessRecord(BaseModel):
    output_sha256: str
    final_probe_json: dict[str, Any]
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class PostProductionRecipeCommandErrorRecord(BaseModel):
    error: str | None = Field(default=None, max_length=10_000)
    error_message: str | None = Field(default=None, max_length=10_000)
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class PostProductionPlanManifest(BaseModel):
    plan_id: UUID
    state: str = "planned_offline"
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
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
    final_probe_json: dict[str, Any] | None = None
    error_message: str | None = None
    plan: FFmpegAssemblyPlan


class PostProductionRecipeCommandManifest(BaseModel):
    plan_id: UUID
    state: str = "planned_offline"
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    manifest_path: Path
    command_template_id: str
    command: list[str] = Field(min_length=1)
    input_paths: list[Path] = Field(min_length=1)
    input_hashes: list[str] = Field(min_length=1)
    output_path: Path | None = None
    execution_submitted: bool = False
    output_sha256: str | None = None
    final_probe_json: dict[str, Any] | None = None
    error: str | None = None
