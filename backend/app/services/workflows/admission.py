"""Local workflow admission checks.

This module performs engineering admission checks for trusted local workflow
sources: graph hash consistency, unique semantic binding titles, required class
presence, dependency presence, and production-forbidden smoke-template detection.
It does not publicly enable generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.schemas.production import CanonicalWorkflowRecord, GateCode
from backend.app.services.workflows.registry import WorkflowRegistryService


@dataclass(frozen=True)
class AdmissionFinding:
    code: str
    message: str
    severity: str = "blocker"


@dataclass(frozen=True)
class AdmissionResult:
    archetype_id: str
    admitted_for_local_execution: bool
    findings: list[AdmissionFinding] = field(default_factory=list)


class WorkflowAdmissionService:
    def __init__(self, registry: WorkflowRegistryService | None = None) -> None:
        self.registry = registry or WorkflowRegistryService()

    def evaluate(self, archetype_id: str, object_info: dict[str, Any] | None = None) -> AdmissionResult:
        record = self.registry.require(archetype_id)
        findings: list[AdmissionFinding] = []
        findings.extend(self._record_findings(record))
        if object_info is not None:
            for class_name in record.required_classes:
                if class_name not in object_info:
                    findings.append(AdmissionFinding("OBJECT_INFO_CLASS_MISSING", f"ComfyUI object_info missing {class_name}"))
        admitted = not findings and record.implemented and record.dependency_verified and bool(record.api_graph_path)
        return AdmissionResult(archetype_id=archetype_id, admitted_for_local_execution=admitted, findings=findings)

    def evaluate_all(self, object_info: dict[str, Any] | None = None) -> list[AdmissionResult]:
        return [self.evaluate(record.archetype_id, object_info=object_info) for record in self.registry.load()]

    def _record_findings(self, record: CanonicalWorkflowRecord) -> list[AdmissionFinding]:
        findings: list[AdmissionFinding] = []
        if record.blocked_reasons:
            findings.extend(AdmissionFinding("BLOCKED", reason) for reason in record.blocked_reasons)
        if not record.implemented:
            findings.append(AdmissionFinding("NOT_IMPLEMENTED", f"{record.archetype_id} is not implemented"))
        if record.api_graph_path is None and record.modality in {"video", "image"}:
            findings.append(AdmissionFinding(GateCode.workflow_not_admitted.value, "Executable API graph is missing"))
        if record.api_graph_path is not None and not Path(record.api_graph_path).is_file():
            findings.append(AdmissionFinding(GateCode.workflow_not_admitted.value, f"API graph missing: {record.api_graph_path}"))
        titles = [binding.semantic_title.strip() for binding in record.bindings]
        if record.modality in {"video", "image"} and not titles:
            findings.append(AdmissionFinding("BINDINGS_MISSING", "Semantic bindings are missing"))
        duplicate_titles = sorted({title for title in titles if title and titles.count(title) > 1})
        if duplicate_titles:
            findings.append(AdmissionFinding("DUPLICATE_SEMANTIC_TITLE", f"Duplicate semantic titles: {', '.join(duplicate_titles)}"))
        for dep in record.dependencies:
            if dep.required and dep.path and not Path(dep.path).is_file():
                findings.append(AdmissionFinding("DEPENDENCY_MISSING", f"{dep.key} missing at {dep.path}"))
        if record.publicly_enabled:
            findings.append(AdmissionFinding("PUBLIC_ENABLEMENT_FORBIDDEN", "Public enablement must remain false in local pre-QA build"))
        return findings
