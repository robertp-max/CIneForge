"""Local workflow admission checks.

This module performs engineering admission checks for trusted local workflow
sources: graph hash consistency, unique semantic binding titles, required class
presence, dependency presence, and production-forbidden smoke-template detection.
It does not publicly enable generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path, PurePosixPath
from typing import Any

from backend.app.core.errors import UnsafePathError
from backend.app.schemas.production import CanonicalWorkflowRecord, GateCode
from backend.app.utils.path_safety import sanitize_comfy_output_prefix
from backend.app.services.workflows.registry import WorkflowRegistryService


_FORBIDDEN_CLASS_TOKENS = (
    "python",
    "script",
    "shell",
    "command",
    "subprocess",
    "download",
    "url",
    "http",
    "webrequest",
    "gitclone",
    "pipinstall",
    "install",
)
_FORBIDDEN_INPUT_TOKENS = ("command", "cmd", "script", "python", "shell", "subprocess", "exec")
_PATHLIKE_INPUT_TOKENS = ("path", "file", "filename", "directory", "dir", "folder", "prefix", "output", "input")


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
        findings.extend(self._static_workflow_findings(record))
        admitted = not findings and record.implemented and record.dependency_verified and bool(record.api_graph_path)
        return AdmissionResult(archetype_id=archetype_id, admitted_for_local_execution=admitted, findings=findings)

    def static_workflow_findings_for_workflow(self, workflow: dict[str, Any]) -> list[AdmissionFinding]:
        findings: list[AdmissionFinding] = []
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("class_type") or "")
            class_lower = class_type.lower().replace("_", "")
            if any(token in class_lower for token in _FORBIDDEN_CLASS_TOKENS):
                findings.append(
                    AdmissionFinding(
                        "FORBIDDEN_WORKFLOW_NODE",
                        f"Node {node_id} class {class_type} appears to execute scripts, commands, downloads, installs, or URLs",
                    )
                )
            inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
            for input_name, value in inputs.items():
                findings.extend(self._scan_input_value(str(node_id), class_type, str(input_name), value))
        return findings

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

    def _static_workflow_findings(self, record: CanonicalWorkflowRecord) -> list[AdmissionFinding]:
        if record.api_graph_path is None:
            return []
        path = Path(record.api_graph_path)
        if not path.is_file():
            return []
        try:
            workflow = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return [AdmissionFinding("WORKFLOW_STATIC_SCAN_FAILED", f"Workflow API graph unreadable: {exc}")]
        return self.static_workflow_findings_for_workflow(workflow)

    def _scan_input_value(self, node_id: str, class_type: str, input_name: str, value: Any) -> list[AdmissionFinding]:
        findings: list[AdmissionFinding] = []
        lowered_name = input_name.lower()
        if isinstance(value, str):
            lowered_value = value.strip().lower()
            if any(token in lowered_name for token in _FORBIDDEN_INPUT_TOKENS):
                findings.append(
                    AdmissionFinding(
                        "FORBIDDEN_WORKFLOW_INPUT",
                        f"Node {node_id} {class_type}.{input_name} is a command/script execution input",
                    )
                )
            if "url" in lowered_name or lowered_value.startswith(("http://", "https://")) or "://" in lowered_value:
                findings.append(
                    AdmissionFinding(
                        "FORBIDDEN_WORKFLOW_URL",
                        f"Node {node_id} {class_type}.{input_name} contains a workflow-provided URL",
                    )
                )
            if any(token in lowered_name for token in _PATHLIKE_INPUT_TOKENS):
                path_error = self._unmanaged_path_error(input_name, value)
                if path_error:
                    findings.append(
                        AdmissionFinding(
                            "UNMANAGED_WORKFLOW_PATH",
                            f"Node {node_id} {class_type}.{input_name} contains an unmanaged path: {path_error}",
                        )
                    )
        elif isinstance(value, list):
            for item in value:
                findings.extend(self._scan_input_value(node_id, class_type, input_name, item))
        elif isinstance(value, dict):
            for key, item in value.items():
                findings.extend(self._scan_input_value(node_id, class_type, f"{input_name}.{key}", item))
        return findings

    @staticmethod
    def _unmanaged_path_error(input_name: str, value: str) -> str | None:
        raw = value.strip()
        if not raw:
            return None
        lowered_name = input_name.lower()
        if "filename_prefix" in lowered_name:
            try:
                sanitize_comfy_output_prefix(raw)
                return None
            except UnsafePathError as exc:
                return str(exc)
        if "\\" in raw or ":" in raw:
            return "backslash and drive-like path components are not allowed"
        path = PurePosixPath(raw)
        if path.is_absolute():
            return "absolute paths are not allowed"
        if any(part in {".", ".."} for part in path.parts):
            return "relative traversal components are not allowed"
        return None
