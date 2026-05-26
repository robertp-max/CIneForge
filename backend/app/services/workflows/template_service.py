import copy
import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.utils.path_safety import sanitize_output_prefix


class ValueSchema(BaseModel):
    type: Literal["string", "integer", "number", "boolean", "array", "object"]
    min: float | None = None
    max: float | None = None


class ManifestNodeRef(BaseModel):
    node_id: str
    expected_class_type: str = Field(alias="class_type")
    input_name: str = Field(alias="input")
    runtime_parameter: str
    value_schema: ValueSchema
    required: bool = True


class WorkflowManifest(BaseModel):
    template_id: str
    version: str
    original_workflow_sha256: str
    comfyui_snapshot_ref: str
    nodes: dict[str, ManifestNodeRef]

    @field_validator("nodes")
    @classmethod
    def nodes_not_empty(cls, value: dict[str, ManifestNodeRef]) -> dict[str, ManifestNodeRef]:
        if not value:
            raise ValueError("Manifest requires at least one semantic node ref")
        return value


@dataclass(frozen=True)
class PatchPlanItem:
    semantic_key: str
    node_id: str
    input_name: str
    value: Any


@dataclass(frozen=True)
class PatchResult:
    patched_workflow: dict[str, Any]
    snapshot_path: Path
    patch_plan: list[PatchPlanItem]


def sha256_json(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_value(value: Any, schema: ValueSchema, semantic_key: str) -> None:
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    if not isinstance(value, type_map[schema.type]):
        raise ValidationError(f"{semantic_key} must be {schema.type}")
    if schema.type in {"integer", "number"}:
        numeric = float(value)
        if schema.min is not None and numeric < schema.min:
            raise ValidationError(f"{semantic_key} below minimum")
        if schema.max is not None and numeric > schema.max:
            raise ValidationError(f"{semantic_key} above maximum")


class WorkflowTemplateService:
    def __init__(self, template_root: Path | None = None, snapshot_root: Path | None = None) -> None:
        settings = get_settings()
        self.template_root = template_root or settings.workflow_template_root
        self.snapshot_root = snapshot_root or settings.workflow_snapshot_root

    def load_template(self, template_dir: Path) -> tuple[dict[str, Any], WorkflowManifest]:
        workflow = json.loads((template_dir / "workflow_api.json").read_text(encoding="utf-8"))
        manifest_data = json.loads((template_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
        manifest = WorkflowManifest.model_validate(manifest_data)
        self.validate_manifest(workflow, manifest)
        return workflow, manifest

    def validate_manifest(self, workflow: dict[str, Any], manifest: WorkflowManifest, object_info: dict[str, Any] | None = None) -> None:
        actual_sha = sha256_json(workflow)
        if actual_sha != manifest.original_workflow_sha256:
            raise ValidationError("Workflow SHA256 does not match manifest")
        for semantic_key, ref in manifest.nodes.items():
            node = workflow.get(ref.node_id)
            if node is None:
                raise ValidationError(f"Missing workflow node for {semantic_key}: {ref.node_id}")
            if node.get("class_type") != ref.expected_class_type:
                raise ValidationError(f"Class type mismatch for {semantic_key}")
            inputs = node.get("inputs") or {}
            if ref.input_name not in inputs:
                raise ValidationError(f"Missing input {ref.input_name} for {semantic_key}")
            if object_info is not None:
                self.validate_object_info_ref(ref, object_info)

    def validate_object_info_ref(self, ref: ManifestNodeRef, object_info: dict[str, Any]) -> None:
        class_info = object_info.get(ref.expected_class_type)
        if class_info is None:
            raise ValidationError(f"Object info missing class {ref.expected_class_type}")
        required = ((class_info.get("input") or {}).get("required") or {})
        optional = ((class_info.get("input") or {}).get("optional") or {})
        if ref.input_name not in required and ref.input_name not in optional:
            raise ValidationError(f"Object info class {ref.expected_class_type} missing input {ref.input_name}")

    def build_patch_plan(self, manifest: WorkflowManifest, patch_payload: dict[str, Any]) -> list[PatchPlanItem]:
        plan: list[PatchPlanItem] = []
        for semantic_key, ref in manifest.nodes.items():
            if ref.runtime_parameter not in patch_payload:
                if ref.required:
                    raise ValidationError(f"Missing required runtime parameter {ref.runtime_parameter}")
                continue
            value = patch_payload[ref.runtime_parameter]
            if ref.runtime_parameter == "output_prefix":
                value = sanitize_output_prefix(str(value))
            _validate_value(value, ref.value_schema, semantic_key)
            plan.append(PatchPlanItem(semantic_key, ref.node_id, ref.input_name, value))
        return plan

    def apply_patch_and_snapshot(
        self,
        workflow: dict[str, Any],
        manifest: WorkflowManifest,
        patch_payload: dict[str, Any],
        *,
        run_id: uuid.UUID | None = None,
    ) -> PatchResult:
        self.validate_manifest(workflow, manifest)
        run_id = run_id or uuid.uuid4()
        patched = copy.deepcopy(workflow)
        plan = self.build_patch_plan(manifest, patch_payload)
        for item in plan:
            patched[item.node_id]["inputs"][item.input_name] = item.value
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.snapshot_root / f"{manifest.template_id}_{manifest.version}_{run_id}.json"
        if snapshot_path.exists():
            raise FileExistsError(snapshot_path)
        snapshot_path.write_text(json.dumps(patched, indent=2, sort_keys=True), encoding="utf-8")
        return PatchResult(patched, snapshot_path, plan)

