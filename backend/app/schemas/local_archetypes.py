"""Schemas for local file-backed workflow archetype catalog."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ArchetypeReadiness(StrEnum):
    candidate = "candidate"
    benchmark_required = "benchmark_required"
    blocked = "blocked"
    ready = "ready"


class LocalArchetype(BaseModel):
    archetype_id: str = Field(pattern=r"^CF-[A-Z]+-[0-9]{2}$")
    name: str
    modality: str
    source_kind: str = "external_comfyui_workflow"
    source_path: Path | None = None
    source_exists: bool = False
    default_model_key: str | None = None
    quality_profiles: list[str] = Field(default_factory=list)
    readiness: ArchetypeReadiness
    enabled: bool = False
    notes: str = ""


CANONICAL_REGISTRY_ARCHETYPE_IDS = frozenset(
    {
        "CF-IMG-01",
        "CF-IMG-02",
        "CF-IMG-03",
        "CF-IMG-04",
        "CF-IMG-05",
        "CF-VID-01",
        "CF-VID-02",
        "CF-VID-03",
        "CF-VID-04",
        "CF-VID-05",
        "CF-UTIL-01",
        "CF-POST-01",
    }
)


class LocalArchetypeCatalog(BaseModel):
    catalog_version: str
    source_path: Path | None = None
    archetypes: list[LocalArchetype]

    @field_validator("archetypes")
    @classmethod
    def required_archetypes_present(cls, archetypes: list[LocalArchetype]) -> list[LocalArchetype]:
        ids = {archetype.archetype_id for archetype in archetypes}
        missing = CANONICAL_REGISTRY_ARCHETYPE_IDS - ids
        if missing:
            raise ValueError(f"Missing required local archetypes: {sorted(missing)}")
        if len(ids) != len(archetypes):
            raise ValueError("Duplicate local archetype IDs")
        return archetypes
