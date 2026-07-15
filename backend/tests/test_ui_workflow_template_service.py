from pathlib import Path
from uuid import UUID

import pytest

from backend.app.core.errors import ValidationError
from backend.app.services.workflows.ui_template_service import UIWorkflowTemplateService


TEMPLATE_DIR = Path("storage/workflow_templates/cf_vid_01_ltx23_single_stage")
MODEL_CHECKPOINT = "ltx-2.3-22b-distilled-1.1-fp8.safetensors"


def _payload() -> dict:
    return {
        "prompt": "A safe local smoke prompt.",
        "negative_prompt": "bad quality",
        "width": 704,
        "height": 384,
        "frames": 49,
        "fps": 24,
        "seed": 1234,
        "model_checkpoint": MODEL_CHECKPOINT,
        "output_prefix": "Project A/run 01",
        "bypass_i2v": True,
        "lora_stage_1_strength": 0,
        "lora_stage_2_strength": 0,
    }


def _node(workflow: dict, node_id: int) -> dict:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def test_cf_vid01_ui_manifest_loads_and_records_blockers():
    workflow, manifest = UIWorkflowTemplateService().load_template(TEMPLATE_DIR)

    assert workflow["nodes"]
    assert manifest.template_id == "cf_vid_01_ltx23_single_stage"
    assert manifest.archetype_id == "CF-VID-01"
    assert manifest.selected_model_key == "ltx2_3_22b_distilled_1_1_fp8"
    assert manifest.readiness == "candidate_only_no_generation"
    assert manifest.blockers
    assert "save_video_stage_f_prefix" in manifest.nodes
    assert "save_video_stage_d_prefix" in manifest.nodes


def test_cf_vid01_ui_patch_snapshots_safe_prefix_and_selected_checkpoint(tmp_path: Path):
    service = UIWorkflowTemplateService(snapshot_root=tmp_path)
    workflow, manifest = service.load_template(TEMPLATE_DIR)

    result = service.apply_patch_and_snapshot(
        workflow,
        manifest,
        _payload(),
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    assert result.snapshot_path.is_file()
    assert _node(result.patched_workflow, 4823)["widgets_values"][0] == "Project_A/run_01"
    assert _node(result.patched_workflow, 4852)["widgets_values"][0] == "Project_A/run_01"
    assert _node(result.patched_workflow, 3940)["widgets_values"][0] == MODEL_CHECKPOINT
    assert _node(result.patched_workflow, 4010)["widgets_values"][0] == MODEL_CHECKPOINT
    assert _node(result.patched_workflow, 4923)["widgets_values"][2] == MODEL_CHECKPOINT
    assert _node(result.patched_workflow, 4961)["widgets_values"][3] == MODEL_CHECKPOINT
    assert _node(result.patched_workflow, 4922)["widgets_values"][1] == 0
    assert _node(result.patched_workflow, 4968)["widgets_values"][1] == 0


def test_cf_vid01_ui_patch_rejects_unsafe_output_prefix(tmp_path: Path):
    service = UIWorkflowTemplateService(snapshot_root=tmp_path)
    workflow, manifest = service.load_template(TEMPLATE_DIR)
    payload = _payload()
    payload["output_prefix"] = "C:/escape"

    with pytest.raises(ValidationError, match="unsafe path component"):
        service.apply_patch_and_snapshot(workflow, manifest, payload)


def test_cf_vid01_ui_patch_requires_runtime_parameters(tmp_path: Path):
    service = UIWorkflowTemplateService(snapshot_root=tmp_path)
    workflow, manifest = service.load_template(TEMPLATE_DIR)
    payload = _payload()
    del payload["model_checkpoint"]

    with pytest.raises(ValidationError, match="Missing required runtime parameter model_checkpoint"):
        service.apply_patch_and_snapshot(workflow, manifest, payload)
