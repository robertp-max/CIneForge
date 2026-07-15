"""Offline UI-format ComfyUI workflow template admission.

ComfyUI example workflows are often exported in UI format, not API prompt
format. This service validates and snapshots safe widget-level mutations for
local admission candidates without launching ComfyUI or submitting prompts.
"""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.services.workflows.template_service import ValueSchema, _validate_value, sha256_json
from backend.app.utils.path_safety import sanitize_comfy_output_prefix


class UIManifestNodeRef(BaseModel):
    node_id: int
    expected_class_type: str = Field(alias="class_type")
    widget_index: int = Field(ge=0)
    runtime_parameter: str
    value_schema: ValueSchema
    required: bool = True
    notes: str = ""


class UIWorkflowManifest(BaseModel):
    template_id: str
    archetype_id: str
    version: str
    source_format: Literal["comfyui_ui"] = "comfyui_ui"
    original_workflow_sha256: str
    comfyui_snapshot_ref: str
    selected_model_key: str
    readiness: str
    blockers: list[str] = Field(default_factory=list)
    nodes: dict[str, UIManifestNodeRef]

    @field_validator("nodes")
    @classmethod
    def nodes_not_empty(cls, value: dict[str, UIManifestNodeRef]) -> dict[str, UIManifestNodeRef]:
        if not value:
            raise ValueError("UI manifest requires at least one semantic node ref")
        return value


@dataclass(frozen=True)
class UIWorkflowPatchPlanItem:
    semantic_key: str
    node_id: int
    widget_index: int
    value: Any


@dataclass(frozen=True)
class UIWorkflowPatchResult:
    patched_workflow: dict[str, Any]
    snapshot_path: Path
    patch_plan: list[UIWorkflowPatchPlanItem]


class UIWorkflowTemplateService:
    def __init__(self, template_root: Path | None = None, snapshot_root: Path | None = None) -> None:
        settings = get_settings()
        self.template_root = template_root or settings.workflow_template_root
        self.snapshot_root = snapshot_root or settings.workflow_snapshot_root

    def load_template(self, template_dir: Path) -> tuple[dict[str, Any], UIWorkflowManifest]:
        workflow = json.loads((template_dir / "workflow_ui.json").read_text(encoding="utf-8"))
        manifest_data = json.loads((template_dir / "workflow_ui_manifest.json").read_text(encoding="utf-8"))
        manifest = UIWorkflowManifest.model_validate(manifest_data)
        self.validate_manifest(workflow, manifest)
        return workflow, manifest

    def validate_manifest(self, workflow: dict[str, Any], manifest: UIWorkflowManifest) -> None:
        actual_sha = sha256_json(workflow)
        if actual_sha != manifest.original_workflow_sha256:
            raise ValidationError("UI workflow SHA256 does not match manifest")
        node_map = {int(node["id"]): node for node in workflow.get("nodes", [])}
        for semantic_key, ref in manifest.nodes.items():
            node = node_map.get(ref.node_id)
            if node is None:
                raise ValidationError(f"Missing UI workflow node for {semantic_key}: {ref.node_id}")
            if node.get("type") != ref.expected_class_type:
                raise ValidationError(f"Class type mismatch for {semantic_key}")
            widgets = node.get("widgets_values") or []
            if ref.widget_index >= len(widgets):
                raise ValidationError(f"Missing widget index {ref.widget_index} for {semantic_key}")

    def build_patch_plan(self, manifest: UIWorkflowManifest, patch_payload: dict[str, Any]) -> list[UIWorkflowPatchPlanItem]:
        plan: list[UIWorkflowPatchPlanItem] = []
        for semantic_key, ref in manifest.nodes.items():
            if ref.runtime_parameter not in patch_payload:
                if ref.required:
                    raise ValidationError(f"Missing required runtime parameter {ref.runtime_parameter}")
                continue
            value = patch_payload[ref.runtime_parameter]
            if ref.runtime_parameter == "output_prefix":
                value = sanitize_comfy_output_prefix(str(value))
            _validate_value(value, ref.value_schema, semantic_key)
            plan.append(UIWorkflowPatchPlanItem(semantic_key, ref.node_id, ref.widget_index, value))
        return plan

    def apply_patch_and_snapshot(
        self,
        workflow: dict[str, Any],
        manifest: UIWorkflowManifest,
        patch_payload: dict[str, Any],
        *,
        run_id: uuid.UUID | None = None,
    ) -> UIWorkflowPatchResult:
        self.validate_manifest(workflow, manifest)
        run_id = run_id or uuid.uuid4()
        patched = copy.deepcopy(workflow)
        plan = self.build_patch_plan(manifest, patch_payload)
        node_map = {int(node["id"]): node for node in patched.get("nodes", [])}
        for item in plan:
            node_map[item.node_id]["widgets_values"][item.widget_index] = item.value
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.snapshot_root / f"{manifest.template_id}_{manifest.version}_{run_id}.ui.json"
        if snapshot_path.exists():
            raise FileExistsError(snapshot_path)
        snapshot_path.write_text(json.dumps(patched, indent=2, sort_keys=True), encoding="utf-8")
        return UIWorkflowPatchResult(patched, snapshot_path, plan)
