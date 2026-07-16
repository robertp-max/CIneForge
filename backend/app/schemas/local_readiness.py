"""Read-only local archetype/preset readiness rollup schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class LocalReadinessStatus(StrEnum):
    blocked = "blocked"
    benchmark_required = "benchmark_required"
    ready = "ready"


class LocalReadinessReason(BaseModel):
    code: str
    severity: Literal["info", "warning", "blocker"]
    message: str
    source: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class WorkflowRegistryReadinessSnapshot(BaseModel):
    registry_available: bool
    archetype_id: str | None = None
    version: str | None = None
    readiness: str | None = None
    implemented: bool = False
    dependency_verified: bool = False
    locally_tested: bool = False
    benchmark_passed: bool = False
    human_approved: bool = False
    publicly_enabled: bool = False
    supported_modes: list[str] = Field(default_factory=list)
    supported_profiles: list[str] = Field(default_factory=list)
    required_classes_count: int = 0
    dependency_count: int = 0
    missing_required_dependencies: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)


class WorkflowAdmissionReadinessSnapshot(BaseModel):
    evaluated: bool
    admitted_for_local_execution: bool = False
    finding_codes: list[str] = Field(default_factory=list)
    findings: list[LocalReadinessReason] = Field(default_factory=list)


class ProductionGateReadinessSnapshot(BaseModel):
    production_ready: bool
    missing_gates: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)


class LocalArchetypeReadinessRecord(BaseModel):
    archetype_id: str
    name: str
    modality: str
    quality_profiles: list[str] = Field(default_factory=list)
    catalog_present: bool = True
    catalog_readiness: str
    catalog_enabled: bool
    source_exists: bool
    status: LocalReadinessStatus
    public_generation_enabled: bool = False
    live_execution_required_for_promotion: bool
    admitted_for_local_execution: bool = False
    production_ready: bool = False
    workflow_registry: WorkflowRegistryReadinessSnapshot
    admission: WorkflowAdmissionReadinessSnapshot
    production_gates: ProductionGateReadinessSnapshot
    reasons: list[LocalReadinessReason] = Field(default_factory=list)


class LocalArchetypeReadinessSummary(BaseModel):
    total: int
    blocked: int
    benchmark_required: int
    ready: int
    public_generation_enabled: bool = False


class LocalArchetypeReadinessReport(BaseModel):
    catalog_version: str
    public_generation_enabled: bool = False
    live_execution_performed_by_endpoint: bool = False
    records: list[LocalArchetypeReadinessRecord]
    summary: LocalArchetypeReadinessSummary
    safe_metadata_sources: list[str]
    safety_note: str = (
        "This read-only endpoint does not run FFmpeg/ffprobe, contact ComfyUI, acquire GPU leases, "
        "submit prompts, render media, benchmark, create jobs, or enable public generation."
    )


class LocalPresetReadinessRecord(BaseModel):
    preset_id: str
    name: str
    modality: str
    model_key: str
    quality_profile: str
    default_archetype_id: str
    catalog_readiness: str
    catalog_enabled: bool
    status: LocalReadinessStatus
    public_generation_enabled: bool = False
    live_execution_required_for_promotion: bool
    admitted_for_local_execution: bool = False
    production_ready: bool = False
    default_archetype_status: LocalReadinessStatus | None = None
    workflow_registry: WorkflowRegistryReadinessSnapshot
    admission: WorkflowAdmissionReadinessSnapshot
    production_gates: ProductionGateReadinessSnapshot
    reasons: list[LocalReadinessReason] = Field(default_factory=list)


class LocalPresetReadinessSummary(BaseModel):
    total: int
    blocked: int
    benchmark_required: int
    ready: int
    public_generation_enabled: bool = False


class LocalPresetReadinessReport(BaseModel):
    catalog_version: str
    public_generation_enabled: bool = False
    live_execution_performed_by_endpoint: bool = False
    records: list[LocalPresetReadinessRecord]
    summary: LocalPresetReadinessSummary
    safe_metadata_sources: list[str]
    safety_note: str = (
        "This read-only endpoint does not run FFmpeg/ffprobe, contact ComfyUI, acquire GPU leases, "
        "submit prompts, render media, benchmark, create jobs, or enable public generation."
    )
