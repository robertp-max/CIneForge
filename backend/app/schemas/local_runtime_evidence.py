"""Read-only local runtime evidence schemas."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class LocalSmokeOutputEvidence(BaseModel):
    prompt_id: str
    path: Path
    sha256: str
    size_bytes: int
    video_codec: str
    width: int
    height: int
    frames: int
    fps: str
    audio_codec: str | None = None
    elapsed_sec: float | None = None
    peak_memory_used_mib: int | None = None
    peak_gpu_util_percent: int | None = None
    peak_temperature_c: int | None = None


class LocalRuntimeEvidence(BaseModel):
    evidence_id: str
    archetype_id: str
    template_id: str
    template_version: str
    readiness_after_evidence: str
    model_key: str
    checkpoint_filename: str
    text_encoder_filename: str
    workflow_api_sha256: str
    comfyui_version: str
    ltxvideo_node_sha: str
    res4lyf_sha: str | None = None
    runtime_args: list[str] = Field(default_factory=list)
    object_info_path: Path
    object_info_required_classes_missing: list[str] = Field(default_factory=list)
    smoke_parameters: dict[str, int]
    outputs: list[LocalSmokeOutputEvidence]
    post_free_vram_free_bytes: int | None = None
    queue_empty_after: bool
    docs_path: Path
    remaining_gates: list[str]
