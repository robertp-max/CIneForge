"""Schemas for local file-backed Comfy job manifests.

Creating one of these records prepares local state and output folders only. It
never submits to ComfyUI.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field


class LocalJobCreate(BaseModel):
    project_key: str = Field(min_length=1, max_length=120)
    run_stem: str = Field(min_length=1, max_length=120)
    preset_id: str = Field(default="CF-PRESET-001", min_length=1, max_length=120)
    model_key: str = "ltx2_3_22b_distilled_1_1_fp8"
    quality_profile: str = "draft"
    prompt: str = Field(default="", max_length=20_000)
    negative_prompt: str = Field(default="", max_length=20_000)
    seed: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=512, ge=64, le=16_384)
    height: int | None = Field(default=288, ge=64, le=16_384)
    frames: int | None = Field(default=17, ge=1, le=4_096)
    fps: int | None = Field(default=24, ge=1, le=120)
    steps: int | None = Field(default=4, ge=1, le=10_000)


class LocalJobManifest(BaseModel):
    job_id: UUID
    state: str = "pending"
    created_at: datetime
    project_key: str
    project_folder: str
    run_stem: str
    output_root: Path
    project_output_dir: Path
    filename_prefix: str
    manifest_path: Path
    preset_id: str
    preset_readiness: str
    archetype_id: str
    model_key: str
    quality_profile: str
    fp8_artifact_sha256: str
    generation_submitted: bool = False
    comfy_prompt_id: str | None = None
    workflow_template_id: str | None = None
    workflow_template_version: str | None = None
    workflow_snapshot_path: Path | None = None
    runtime_patch_payload: dict[str, object] | None = None
    prompt: str = ""
    negative_prompt: str = ""
    seed: int | None = None
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    fps: int | None = None
    steps: int | None = None
