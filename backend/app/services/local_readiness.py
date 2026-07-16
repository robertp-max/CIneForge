"""Read-only readiness rollups for local archetype and preset planning.

The service only summarizes catalog, registry, admission, and production-gate
metadata. It deliberately does not contact ComfyUI, run benchmarks, execute
FFmpeg/ffprobe, submit prompts, render media, create jobs, or enable generation.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.local_archetypes import LocalArchetype
from backend.app.schemas.local_presets import LocalPreset
from backend.app.schemas.local_readiness import (
    LocalArchetypeReadinessRecord,
    LocalArchetypeReadinessReport,
    LocalArchetypeReadinessSummary,
    LocalPresetReadinessRecord,
    LocalPresetReadinessReport,
    LocalPresetReadinessSummary,
    LocalReadinessReason,
    LocalReadinessStatus,
    ProductionGateReadinessSnapshot,
    WorkflowAdmissionReadinessSnapshot,
    WorkflowRegistryReadinessSnapshot,
)
from backend.app.schemas.production import CanonicalWorkflowRecord
from backend.app.services.local_archetypes import LocalArchetypeCatalogService
from backend.app.services.local_presets import LocalPresetCatalogService
from backend.app.services.workflows.admission import AdmissionResult, WorkflowAdmissionService
from backend.app.services.workflows.registry import WorkflowRegistryService


_SAFE_METADATA_SOURCES = [
    "backend.app.services.local_archetypes.LocalArchetypeCatalogService.load",
    "backend.app.services.local_presets.LocalPresetCatalogService.load",
    "backend.app.services.workflows.registry.WorkflowRegistryService.load",
    "backend.app.services.workflows.admission.WorkflowAdmissionService.evaluate",
    "backend.app.services.production_gates.ProductionGateService production-ready gate criteria",
]


class LocalReadinessService:
    def __init__(
        self,
        settings: Settings | None = None,
        archetypes: LocalArchetypeCatalogService | None = None,
        presets: LocalPresetCatalogService | None = None,
        registry: WorkflowRegistryService | None = None,
        admission: WorkflowAdmissionService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.archetypes = archetypes or LocalArchetypeCatalogService(self.settings)
        self.presets = presets or LocalPresetCatalogService(self.settings)
        self.registry = registry or WorkflowRegistryService(self.settings)
        self.admission = admission or WorkflowAdmissionService(self.registry)

    def archetype_report(self) -> LocalArchetypeReadinessReport:
        catalog = self.archetypes.load()
        registry_records, registry_issue = self._registry_records()
        catalog_archetypes = {archetype.archetype_id: archetype for archetype in catalog.archetypes}
        records = [
            self._archetype_record(
                archetype,
                registry_records.get(archetype.archetype_id),
                registry_issue=registry_issue,
            )
            for archetype in catalog.archetypes
        ]
        records.extend(
            self._archetype_record(
                self._registry_only_archetype(record),
                record,
                registry_issue=registry_issue,
                catalog_present=False,
            )
            for archetype_id, record in registry_records.items()
            if archetype_id not in catalog_archetypes
        )
        return LocalArchetypeReadinessReport(
            catalog_version=catalog.catalog_version,
            records=records,
            summary=self._archetype_summary(records),
            safe_metadata_sources=list(_SAFE_METADATA_SOURCES),
        )

    def get_archetype_readiness(self, archetype_id: str) -> LocalArchetypeReadinessRecord | None:
        catalog = self.archetypes.load()
        archetype = next((item for item in catalog.archetypes if item.archetype_id == archetype_id), None)
        registry_records, registry_issue = self._registry_records()
        if archetype is None:
            record = registry_records.get(archetype_id)
            if record is None:
                return None
            return self._archetype_record(
                self._registry_only_archetype(record),
                record,
                registry_issue=registry_issue,
                catalog_present=False,
            )
        return self._archetype_record(
            archetype,
            registry_records.get(archetype.archetype_id),
            registry_issue=registry_issue,
        )

    def preset_report(self) -> LocalPresetReadinessReport:
        catalog = self.presets.load()
        archetype_records = {record.archetype_id: record for record in self.archetype_report().records}
        records = [self._preset_record(preset, archetype_records.get(preset.default_archetype_id)) for preset in catalog.presets]
        return LocalPresetReadinessReport(
            catalog_version=catalog.catalog_version,
            records=records,
            summary=self._preset_summary(records),
            safe_metadata_sources=list(_SAFE_METADATA_SOURCES),
        )

    def get_preset_readiness(self, preset_id: str) -> LocalPresetReadinessRecord | None:
        catalog = self.presets.load()
        preset = next((item for item in catalog.presets if item.preset_id == preset_id), None)
        if preset is None:
            return None
        archetype_records = {record.archetype_id: record for record in self.archetype_report().records}
        return self._preset_record(preset, archetype_records.get(preset.default_archetype_id))

    def _registry_records(self) -> tuple[dict[str, CanonicalWorkflowRecord], LocalReadinessReason | None]:
        try:
            return {record.archetype_id: record for record in self.registry.load()}, None
        except FileNotFoundError as exc:
            return {}, self._reason(
                "workflow_registry_missing",
                "blocker",
                f"Configured workflow registry not found: {exc.filename}",
                "workflow_registry",
            )
        except ValidationError as exc:
            return {}, self._reason(
                "workflow_registry_invalid",
                "blocker",
                f"Configured workflow registry is invalid: {exc}",
                "workflow_registry",
            )

    def _archetype_record(
        self,
        archetype: LocalArchetype,
        record: CanonicalWorkflowRecord | None,
        *,
        registry_issue: LocalReadinessReason | None,
        catalog_present: bool = True,
    ) -> LocalArchetypeReadinessRecord:
        reasons: list[LocalReadinessReason] = []
        hard_blockers: list[str] = []
        promotion_gaps: list[str] = []

        if not catalog_present:
            hard_blockers.append("catalog_record_missing")
            reasons.append(
                self._reason(
                    "catalog_record_missing",
                    "blocker",
                    "Workflow registry archetype is not present in the local archetype catalog; it cannot be promoted from registry evidence alone.",
                    "local_archetype_catalog",
                    archetype_id=archetype.archetype_id,
                )
            )
        if not archetype.enabled:
            reasons.append(
                self._reason(
                    "catalog_disabled",
                    "info",
                    "Catalog entry remains disabled; this endpoint does not enable local or public generation.",
                    "local_archetype_catalog",
                    enabled=archetype.enabled,
                )
            )
        if archetype.readiness == "blocked":
            hard_blockers.append("catalog_readiness_blocked")
            reasons.append(
                self._reason(
                    "catalog_blocked",
                    "blocker",
                    "Catalog marks this archetype as blocked.",
                    "local_archetype_catalog",
                    readiness=str(archetype.readiness),
                )
            )
        elif archetype.readiness == "benchmark_required":
            promotion_gaps.append("catalog_benchmark_required")
            reasons.append(
                self._reason(
                    "catalog_benchmark_required",
                    "warning",
                    "Catalog marks this archetype as requiring benchmark evidence before promotion.",
                    "local_archetype_catalog",
                    readiness=str(archetype.readiness),
                )
            )
        elif archetype.readiness != "ready":
            hard_blockers.append(f"catalog_readiness_{archetype.readiness}")

        if archetype.source_path and not archetype.source_exists:
            reasons.append(
                self._reason(
                    "catalog_source_missing",
                    "warning",
                    "Catalog source path is not present on this machine; registry templates may still provide planning metadata.",
                    "local_archetype_catalog",
                    source_path=str(archetype.source_path),
                )
            )

        if registry_issue is not None:
            hard_blockers.append(registry_issue.code)
            reasons.append(registry_issue)

        workflow_snapshot = self._workflow_snapshot(record, registry_available=registry_issue is None)
        production_snapshot = self._production_snapshot(record)
        admission_snapshot = self._admission_snapshot(archetype.archetype_id, record, registry_issue=registry_issue)

        if record is None:
            hard_blockers.append("workflow_registry_record_missing")
            reasons.append(
                self._reason(
                    "workflow_registry_record_missing",
                    "blocker",
                    "No workflow registry record exists for this catalog archetype.",
                    "workflow_registry",
                    archetype_id=archetype.archetype_id,
                )
            )
        else:
            record_hard, record_gaps, record_reasons = self._record_gate_reasons(record)
            hard_blockers.extend(record_hard)
            promotion_gaps.extend(record_gaps)
            reasons.extend(record_reasons)
            admission_hard = self._hard_admission_codes(admission_snapshot.finding_codes, record)
            hard_blockers.extend(admission_hard)

        production_ready = self._production_ready(record)
        catalog_ready = archetype.readiness == "ready" and archetype.enabled
        if production_ready and catalog_ready and not hard_blockers:
            status = LocalReadinessStatus.ready
        elif hard_blockers:
            status = LocalReadinessStatus.blocked
        else:
            status = LocalReadinessStatus.benchmark_required
            if not promotion_gaps:
                reasons.append(
                    self._reason(
                        "promotion_evidence_required",
                        "warning",
                        "Promotion still requires explicit benchmark/recovery/human evidence before readiness can advance.",
                        "production_gates",
                    )
                )

        return LocalArchetypeReadinessRecord(
            archetype_id=archetype.archetype_id,
            name=archetype.name,
            modality=archetype.modality,
            quality_profiles=list(archetype.quality_profiles),
            catalog_present=catalog_present,
            catalog_readiness=str(archetype.readiness),
            catalog_enabled=archetype.enabled,
            source_exists=archetype.source_exists,
            status=status,
            public_generation_enabled=False,
            live_execution_required_for_promotion=status != LocalReadinessStatus.ready,
            admitted_for_local_execution=admission_snapshot.admitted_for_local_execution,
            production_ready=production_ready and catalog_ready,
            workflow_registry=workflow_snapshot,
            admission=admission_snapshot,
            production_gates=production_snapshot,
            reasons=self._dedupe_reasons(reasons),
        )

    def _preset_record(
        self,
        preset: LocalPreset,
        archetype_record: LocalArchetypeReadinessRecord | None,
    ) -> LocalPresetReadinessRecord:
        reasons: list[LocalReadinessReason] = []
        hard_blockers: list[str] = []
        promotion_gaps: list[str] = []

        if not preset.enabled:
            reasons.append(
                self._reason(
                    "catalog_disabled",
                    "info",
                    "Preset remains disabled; this endpoint does not enable local or public generation.",
                    "local_preset_catalog",
                    enabled=preset.enabled,
                )
            )
        if preset.readiness in {"blocked", "retired"}:
            hard_blockers.append(f"preset_{preset.readiness}")
            reasons.append(
                self._reason(
                    f"preset_{preset.readiness}",
                    "blocker",
                    f"Preset catalog marks this preset as {preset.readiness}.",
                    "local_preset_catalog",
                    readiness=str(preset.readiness),
                )
            )
        elif preset.readiness == "benchmark_required":
            promotion_gaps.append("preset_benchmark_required")
            reasons.append(
                self._reason(
                    "preset_benchmark_required",
                    "warning",
                    "Preset catalog marks this preset as requiring benchmark evidence before promotion.",
                    "local_preset_catalog",
                    readiness=str(preset.readiness),
                )
            )
        elif preset.readiness != "ready":
            hard_blockers.append(f"preset_readiness_{preset.readiness}")

        if archetype_record is None:
            hard_blockers.append("default_archetype_missing")
            reasons.append(
                self._reason(
                    "default_archetype_missing",
                    "blocker",
                    "Preset default archetype is not present in the local archetype readiness catalog.",
                    "local_preset_catalog",
                    default_archetype_id=preset.default_archetype_id,
                )
            )
            workflow_snapshot = WorkflowRegistryReadinessSnapshot(registry_available=False, archetype_id=preset.default_archetype_id)
            admission_snapshot = WorkflowAdmissionReadinessSnapshot(evaluated=False)
            production_snapshot = ProductionGateReadinessSnapshot(
                production_ready=False,
                missing_gates=["default_archetype_missing"],
            )
            default_status = None
        else:
            default_status = archetype_record.status
            workflow_snapshot = archetype_record.workflow_registry
            admission_snapshot = archetype_record.admission
            production_snapshot = archetype_record.production_gates
            if archetype_record.status == LocalReadinessStatus.blocked:
                hard_blockers.append("default_archetype_blocked")
                reasons.append(
                    self._reason(
                        "default_archetype_blocked",
                        "blocker",
                        f"Default archetype {preset.default_archetype_id} is blocked.",
                        "archetype_readiness",
                        default_archetype_id=preset.default_archetype_id,
                    )
                )
            elif archetype_record.status == LocalReadinessStatus.benchmark_required:
                promotion_gaps.append("default_archetype_benchmark_required")
                reasons.append(
                    self._reason(
                        "default_archetype_benchmark_required",
                        "warning",
                        f"Default archetype {preset.default_archetype_id} still requires benchmark/human promotion evidence.",
                        "archetype_readiness",
                        default_archetype_id=preset.default_archetype_id,
                    )
                )
            reasons.extend(
                self._reason(
                    f"default_archetype_{reason.code}",
                    reason.severity,
                    reason.message,
                    reason.source,
                    **reason.evidence,
                )
                for reason in archetype_record.reasons
                if reason.severity in {"blocker", "warning"}
            )

        preset_ready = preset.readiness == "ready" and preset.enabled
        archetype_ready = archetype_record is not None and archetype_record.production_ready
        if preset_ready and archetype_ready and not hard_blockers:
            status = LocalReadinessStatus.ready
        elif hard_blockers:
            status = LocalReadinessStatus.blocked
        else:
            status = LocalReadinessStatus.benchmark_required
            if not promotion_gaps:
                reasons.append(
                    self._reason(
                        "promotion_evidence_required",
                        "warning",
                        "Preset promotion still requires explicit benchmark/recovery/human evidence before readiness can advance.",
                        "production_gates",
                    )
                )

        return LocalPresetReadinessRecord(
            preset_id=preset.preset_id,
            name=preset.name,
            modality=preset.modality,
            model_key=preset.model_key,
            quality_profile=str(preset.quality_profile),
            default_archetype_id=preset.default_archetype_id,
            catalog_readiness=str(preset.readiness),
            catalog_enabled=preset.enabled,
            status=status,
            public_generation_enabled=False,
            live_execution_required_for_promotion=status != LocalReadinessStatus.ready,
            admitted_for_local_execution=admission_snapshot.admitted_for_local_execution,
            production_ready=preset_ready and archetype_ready,
            default_archetype_status=default_status,
            workflow_registry=workflow_snapshot,
            admission=admission_snapshot,
            production_gates=production_snapshot,
            reasons=self._dedupe_reasons(reasons),
        )

    @staticmethod
    def _registry_only_archetype(record: CanonicalWorkflowRecord) -> LocalArchetype:
        return LocalArchetype(
            archetype_id=record.archetype_id,
            name=record.name,
            modality=record.modality,
            source_path=record.source_path,
            source_exists=bool(record.source_path and Path(record.source_path).is_file()),
            quality_profiles=[str(profile) for profile in record.supported_profiles],
            readiness=record.readiness,
            enabled=False,
            notes="Workflow registry record without a matching local archetype catalog entry.",
        )

    def _workflow_snapshot(
        self,
        record: CanonicalWorkflowRecord | None,
        *,
        registry_available: bool,
    ) -> WorkflowRegistryReadinessSnapshot:
        if record is None:
            return WorkflowRegistryReadinessSnapshot(registry_available=registry_available)
        missing_deps = [
            dep.key
            for dep in record.dependencies
            if dep.required and dep.path and dep.present is False
        ]
        return WorkflowRegistryReadinessSnapshot(
            registry_available=registry_available,
            archetype_id=record.archetype_id,
            version=record.version,
            readiness=record.readiness,
            implemented=record.implemented,
            dependency_verified=record.dependency_verified,
            locally_tested=record.locally_tested,
            benchmark_passed=record.benchmark_passed,
            human_approved=record.human_approved,
            publicly_enabled=record.publicly_enabled,
            supported_modes=list(record.supported_modes),
            supported_profiles=[str(profile) for profile in record.supported_profiles],
            required_classes_count=len(record.required_classes),
            dependency_count=len(record.dependencies),
            missing_required_dependencies=missing_deps,
            blocked_reasons=list(record.blocked_reasons),
        )

    def _admission_snapshot(
        self,
        archetype_id: str,
        record: CanonicalWorkflowRecord | None,
        *,
        registry_issue: LocalReadinessReason | None,
    ) -> WorkflowAdmissionReadinessSnapshot:
        if record is None or registry_issue is not None:
            return WorkflowAdmissionReadinessSnapshot(evaluated=False)
        try:
            result = self.admission.evaluate(archetype_id)
        except (FileNotFoundError, ValidationError) as exc:
            reason = self._reason(
                "admission_evaluation_failed",
                "blocker",
                f"Workflow admission evaluation failed: {exc}",
                "workflow_admission",
            )
            return WorkflowAdmissionReadinessSnapshot(
                evaluated=True,
                admitted_for_local_execution=False,
                finding_codes=[reason.code],
                findings=[reason],
            )
        return WorkflowAdmissionReadinessSnapshot(
            evaluated=True,
            admitted_for_local_execution=result.admitted_for_local_execution,
            finding_codes=[finding.code for finding in result.findings],
            findings=self._admission_reasons(result),
        )

    def _admission_reasons(self, result: AdmissionResult) -> list[LocalReadinessReason]:
        reasons: list[LocalReadinessReason] = []
        for finding in result.findings:
            severity = "blocker" if finding.severity == "blocker" else "warning"
            if finding.code == "BLOCKED":
                severity = "warning"
            reasons.append(
                self._reason(
                    f"admission_{finding.code.lower()}",
                    severity,
                    finding.message,
                    "workflow_admission",
                    archetype_id=result.archetype_id,
                    finding_code=finding.code,
                )
            )
        return reasons

    def _production_snapshot(self, record: CanonicalWorkflowRecord | None) -> ProductionGateReadinessSnapshot:
        if record is None:
            return ProductionGateReadinessSnapshot(
                production_ready=False,
                missing_gates=["workflow_registry_record_missing"],
            )
        missing = [
            gate
            for gate in ("implemented", "dependency_verified", "locally_tested", "benchmark_passed", "human_approved")
            if not getattr(record, gate, False)
        ]
        if record.readiness != "ready":
            missing.append(f"readiness={record.readiness}")
        return ProductionGateReadinessSnapshot(
            production_ready=self._production_ready(record),
            missing_gates=missing,
            blocked_reasons=list(record.blocked_reasons),
        )

    def _record_gate_reasons(
        self,
        record: CanonicalWorkflowRecord,
    ) -> tuple[list[str], list[str], list[LocalReadinessReason]]:
        hard_blockers: list[str] = []
        promotion_gaps: list[str] = []
        reasons: list[LocalReadinessReason] = []

        gate_specs = [
            ("implemented", "missing_implementation", "Workflow registry does not mark this archetype as implemented."),
            ("dependency_verified", "missing_dependency", "Workflow registry dependency evidence is incomplete."),
            ("locally_tested", "missing_local_test", "Workflow registry local execution evidence is incomplete."),
            ("benchmark_passed", "missing_benchmark", "Workflow registry benchmark evidence is missing."),
            ("human_approved", "missing_human_approval", "Workflow registry human approval is missing."),
        ]
        for field, code, message in gate_specs:
            if getattr(record, field, False):
                continue
            if field in {"implemented", "dependency_verified"}:
                hard_blockers.append(code)
                severity = "blocker"
            else:
                promotion_gaps.append(code)
                severity = "warning"
            reasons.append(
                self._reason(
                    code,
                    severity,
                    message,
                    "workflow_registry",
                    archetype_id=record.archetype_id,
                    gate=field,
                )
            )

        if record.publicly_enabled:
            hard_blockers.append("public_generation_enabled_forbidden")
            reasons.append(
                self._reason(
                    "public_generation_enabled_forbidden",
                    "blocker",
                    "Workflow registry publicly_enabled must remain false for safe local planning.",
                    "workflow_registry",
                    archetype_id=record.archetype_id,
                )
            )

        if record.readiness == "blocked":
            hard_blockers.append("workflow_registry_blocked")
            severity = "blocker"
        elif record.readiness == "benchmark_required":
            promotion_gaps.append("workflow_registry_benchmark_required")
            severity = "warning"
        elif record.readiness == "ready":
            severity = "info"
        else:
            hard_blockers.append(f"workflow_registry_readiness_{record.readiness}")
            severity = "blocker"
        reasons.append(
            self._reason(
                "workflow_registry_readiness",
                severity,
                f"Workflow registry readiness is {record.readiness}.",
                "workflow_registry",
                archetype_id=record.archetype_id,
                readiness=record.readiness,
            )
        )

        for blocked_reason in record.blocked_reasons:
            reasons.append(
                self._reason(
                    "workflow_registry_blocked_reason",
                    "blocker" if record.readiness == "blocked" else "warning",
                    blocked_reason,
                    "workflow_registry",
                    archetype_id=record.archetype_id,
                )
            )

        if record.modality in {"video", "image"} and record.api_graph_path is None:
            hard_blockers.append("api_graph_missing")
            reasons.append(
                self._reason(
                    "api_graph_missing",
                    "blocker",
                    "Executable API graph is missing for this generation archetype.",
                    "workflow_registry",
                    archetype_id=record.archetype_id,
                )
            )
        if record.api_graph_path is not None and not Path(record.api_graph_path).is_file():
            hard_blockers.append("api_graph_missing")
            reasons.append(
                self._reason(
                    "api_graph_missing",
                    "blocker",
                    f"Executable API graph is missing: {record.api_graph_path}",
                    "workflow_registry",
                    archetype_id=record.archetype_id,
                )
            )

        return hard_blockers, promotion_gaps, reasons

    @staticmethod
    def _production_ready(record: CanonicalWorkflowRecord | None) -> bool:
        if record is None:
            return False
        return bool(
            record.implemented
            and record.dependency_verified
            and record.locally_tested
            and record.benchmark_passed
            and record.human_approved
            and record.readiness == "ready"
            and not record.blocked_reasons
        )

    @staticmethod
    def _hard_admission_codes(codes: Iterable[str], record: CanonicalWorkflowRecord) -> list[str]:
        hard_codes = {
            "NOT_IMPLEMENTED",
            "WORKFLOW_NOT_ADMITTED",
            "BINDINGS_MISSING",
            "DUPLICATE_SEMANTIC_TITLE",
            "DEPENDENCY_MISSING",
            "FORBIDDEN_WORKFLOW_NODE",
            "FORBIDDEN_WORKFLOW_INPUT",
            "FORBIDDEN_WORKFLOW_URL",
            "UNMANAGED_WORKFLOW_PATH",
            "PUBLIC_ENABLEMENT_FORBIDDEN",
            "WORKFLOW_STATIC_SCAN_FAILED",
        }
        blockers = [f"admission_{code.lower()}" for code in codes if code in hard_codes]
        if record.readiness == "blocked" and "BLOCKED" in set(codes):
            blockers.append("admission_blocked")
        return blockers

    @staticmethod
    def _dedupe_reasons(reasons: list[LocalReadinessReason]) -> list[LocalReadinessReason]:
        deduped: dict[tuple[str, str, str], LocalReadinessReason] = {}
        for reason in reasons:
            deduped.setdefault((reason.code, reason.source, reason.message), reason)
        return list(deduped.values())

    @staticmethod
    def _reason(
        code: str,
        severity: Literal["info", "warning", "blocker"],
        message: str,
        source: str,
        **evidence,
    ) -> LocalReadinessReason:
        return LocalReadinessReason(
            code=code,
            severity=severity,
            message=message,
            source=source,
            evidence={key: value for key, value in evidence.items() if value is not None},
        )

    @staticmethod
    def _archetype_summary(records: list[LocalArchetypeReadinessRecord]) -> LocalArchetypeReadinessSummary:
        return LocalArchetypeReadinessSummary(
            total=len(records),
            blocked=sum(1 for record in records if record.status == LocalReadinessStatus.blocked),
            benchmark_required=sum(1 for record in records if record.status == LocalReadinessStatus.benchmark_required),
            ready=sum(1 for record in records if record.status == LocalReadinessStatus.ready),
        )

    @staticmethod
    def _preset_summary(records: list[LocalPresetReadinessRecord]) -> LocalPresetReadinessSummary:
        return LocalPresetReadinessSummary(
            total=len(records),
            blocked=sum(1 for record in records if record.status == LocalReadinessStatus.blocked),
            benchmark_required=sum(1 for record in records if record.status == LocalReadinessStatus.benchmark_required),
            ready=sum(1 for record in records if record.status == LocalReadinessStatus.ready),
        )
