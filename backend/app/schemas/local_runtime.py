"""Schemas for DB-free local CineForge runtime state.

These schemas describe the operator-owned local ComfyUI runtime and output
policy. They do not imply that generation has been benchmarked or enabled.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class LocalReadiness(StrEnum):
    candidate = "candidate"
    benchmark_required = "benchmark_required"
    ready = "ready"
    blocked = "blocked"


class ArtifactRole(StrEnum):
    source = "source"
    selected_fp8 = "selected_fp8"
    secondary_candidate = "secondary_candidate"


class LocalArtifactRecord(BaseModel):
    key: str
    role: ArtifactRole
    path: Path
    path_exists: bool
    size_bytes: int | None = None
    expected_size_bytes: int | None = None
    sha256: str | None = None
    precision: str
    fp8_method: str | None = None
    header_identity: str | None = None
    readiness: LocalReadiness
    notes: str | None = None


class OutputPolicy(BaseModel):
    output_root: Path
    project_folder_shape: str = "<project-folder>"
    filename_prefix_shape: str = "<project-folder>/<run-stem>"
    one_folder_per_project: bool = True
    create_project_folder: bool = True
    user_supplied_output_paths_allowed: bool = False
    rejects_absolute_paths: bool = True
    rejects_traversal: bool = True
    rejects_backslashes: bool = True
    rejects_deeper_trees: bool = True


class LocalRuntimeCatalog(BaseModel):
    model_key: str = "ltx2_3_22b_distilled_1_1_fp8"
    display_name: str = "LTX-2.3 22B Distilled 1.1 FP8"
    default_video_model: bool = True
    fp8_method: str = "converted_derivative"
    generation_enabled: bool = False
    public_generation_enabled: bool = False
    queue_worker_enabled: bool = False
    database_required: bool = False
    readiness: LocalReadiness = LocalReadiness.benchmark_required
    artifacts: list[LocalArtifactRecord] = Field(default_factory=list)
    output_policy: OutputPolicy
    evidence_note: str = (
        "Local artifact and output-root evidence only. This endpoint does not "
        "launch ComfyUI, load models, submit prompts, download files, or claim "
        "hardware readiness."
    )
