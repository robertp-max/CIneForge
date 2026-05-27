import json
from pathlib import Path

import pytest

from backend.app.core.errors import ValidationError
from backend.app.services.workflows.template_service import WorkflowManifest, WorkflowTemplateService, sha256_json


def _workflow():
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old positive"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "old negative"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 8}},
        "99": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "old"}},
    }


def _manifest(workflow):
    return {
        "template_id": "example-smoke",
        "version": "0.1.0",
        "original_workflow_sha256": sha256_json(workflow),
        "comfyui_snapshot_ref": "scaffold-only",
        "nodes": {
            "positive_prompt": {
                "node_id": "6",
                "class_type": "CLIPTextEncode",
                "input": "text",
                "runtime_parameter": "positive_prompt",
                "value_schema": {"type": "string"},
                "required": True,
            },
            "output_prefix": {
                "node_id": "99",
                "class_type": "SaveVideo",
                "input": "filename_prefix",
                "runtime_parameter": "output_prefix",
                "value_schema": {"type": "string"},
                "required": True,
            },
        },
    }


def test_workflow_manifest_valid_case(tmp_path):
    workflow = _workflow()
    manifest = WorkflowManifest.model_validate(_manifest(workflow))
    service = WorkflowTemplateService(snapshot_root=tmp_path)
    result = service.apply_patch_and_snapshot(
        workflow,
        manifest,
        {"positive_prompt": "new prompt", "output_prefix": "run 01"},
    )
    assert result.patched_workflow["6"]["inputs"]["text"] == "new prompt"
    assert result.patched_workflow["99"]["inputs"]["filename_prefix"] == "run_01"
    assert result.snapshot_path.exists()


def test_manifest_missing_node_fails():
    workflow = _workflow()
    manifest_data = _manifest(workflow)
    manifest_data["nodes"]["positive_prompt"]["node_id"] = "missing"
    manifest = WorkflowManifest.model_validate(manifest_data)
    with pytest.raises(ValidationError):
        WorkflowTemplateService().validate_manifest(workflow, manifest)


def test_manifest_class_type_mismatch_fails():
    workflow = _workflow()
    manifest_data = _manifest(workflow)
    manifest_data["nodes"]["positive_prompt"]["class_type"] = "WrongNode"
    manifest = WorkflowManifest.model_validate(manifest_data)
    with pytest.raises(ValidationError):
        WorkflowTemplateService().validate_manifest(workflow, manifest)


def test_manifest_missing_input_fails():
    workflow = _workflow()
    manifest_data = _manifest(workflow)
    manifest_data["nodes"]["positive_prompt"]["input"] = "missing_input"
    manifest = WorkflowManifest.model_validate(manifest_data)
    with pytest.raises(ValidationError):
        WorkflowTemplateService().validate_manifest(workflow, manifest)


def test_template_integrity_validation_still_rejects_original_sha_mismatch():
    workflow = _workflow()
    manifest_data = _manifest(workflow)
    manifest_data["original_workflow_sha256"] = "not-the-workflow-sha"
    manifest = WorkflowManifest.model_validate(manifest_data)

    with pytest.raises(ValidationError, match="Workflow SHA256 does not match manifest"):
        WorkflowTemplateService().validate_manifest(workflow, manifest)


def test_example_template_loads():
    template_dir = Path("storage/workflow_templates/example_smoke")
    workflow = json.loads((template_dir / "workflow_api.json").read_text())
    manifest = json.loads((template_dir / "workflow_manifest.json").read_text())
    assert manifest["original_workflow_sha256"] == sha256_json(workflow)
    WorkflowTemplateService().load_template(template_dir)

