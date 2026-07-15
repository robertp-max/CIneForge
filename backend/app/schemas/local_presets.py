"""Schemas for local file-backed CineForge preset catalog."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class QualityProfile(StrEnum):
    draft = "draft"
    review = "review"
    final_candidate = "final_candidate"
    controlled = "controlled"
    lipdub = "lipdub"


class PresetReadiness(StrEnum):
    benchmark_required = "benchmark_required"
    blocked = "blocked"
    ready = "ready"
    retired = "retired"


class LocalPreset(BaseModel):
    preset_id: str = Field(pattern=r"^CF-PRESET-[0-9]{3}$")
    name: str
    modality: str = "video"
    model_key: str = "ltx2_3_22b_distilled_1_1_fp8"
    default_archetype_id: str
    quality_profile: QualityProfile
    readiness: PresetReadiness
    enabled: bool = False
    notes: str = ""


class LocalPresetCatalog(BaseModel):
    catalog_version: str
    source_path: Path | None = None
    presets: list[LocalPreset]

    @field_validator("presets")
    @classmethod
    def exactly_64_unique_presets(cls, presets: list[LocalPreset]) -> list[LocalPreset]:
        if len(presets) != 64:
            raise ValueError("Local preset catalog must contain exactly 64 presets")
        ids = [preset.preset_id for preset in presets]
        if len(set(ids)) != 64:
            raise ValueError("Local preset catalog contains duplicate preset IDs")
        expected = [f"CF-PRESET-{index:03d}" for index in range(1, 65)]
        if ids != expected:
            raise ValueError("Local preset IDs must be contiguous CF-PRESET-001..064")
        return presets
