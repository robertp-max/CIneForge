from pathlib import Path
from uuid import UUID

import pytest

from backend.app.core.errors import ValidationError
from backend.app.services.workflows.template_service import WorkflowTemplateService


TEMPLATE_DIR = Path("storage/workflow_templates/cf_vid_01_ltx23_single_stage")
MODEL_CHECKPOINT = "ltx-2.3-22b-distilled-1.1-fp8.safetensors"
TEXT_ENCODER = "gemma_3_12B_it_fp4_mixed.safetensors"


def _payload() -> dict:
    return {
        "prompt": "A safe local smoke prompt.",
        "negative_prompt": "bad quality",
        "width": 512,
        "height": 288,
        "frames": 17,
        "fps": 24,
        "seed": 20260713,
        "steps": 4,
        "model_checkpoint": MODEL_CHECKPOINT,
        "text_encoder": TEXT_ENCODER,
        "output_prefix": "Project A/run 01",
    }


def _object_info_for_manifest(manifest) -> dict:
    object_info: dict[str, dict] = {}
    for ref in manifest.nodes.values():
        class_info = object_info.setdefault(ref.expected_class_type, {"input": {"required": {}}})
        class_info["input"]["required"][ref.input_name] = ["ANY"]
    return object_info


def test_cf_vid01_api_manifest_loads_and_validates_against_object_info():
    workflow, manifest = WorkflowTemplateService().load_template(TEMPLATE_DIR)

    assert manifest.template_id == "cf_vid_01_ltx23_single_stage_t2v_smoke"
    assert manifest.version == "0.2.0-api-t2v-smoke"
    assert workflow["3940"]["inputs"]["ckpt_name"] == MODEL_CHECKPOINT
    assert workflow["4960"]["inputs"]["text_encoder"] == TEXT_ENCODER
    assert "4922" not in workflow  # no missing/non-1.1 LoRA substitution
    assert "4968" not in workflow

    WorkflowTemplateService().validate_manifest(workflow, manifest, _object_info_for_manifest(manifest))


def test_cf_vid01_api_patch_snapshots_safe_prefix_and_runtime_values(tmp_path: Path):
    service = WorkflowTemplateService(snapshot_root=tmp_path)
    workflow, manifest = service.load_template(TEMPLATE_DIR)

    result = service.apply_patch_and_snapshot(
        workflow,
        manifest,
        _payload(),
        run_id=UUID("00000000-0000-0000-0000-000000000002"),
    )

    assert result.snapshot_path.is_file()
    patched = result.patched_workflow
    assert patched["4823"]["inputs"]["filename_prefix"] == "Project_A/run_01"
    assert patched["3940"]["inputs"]["ckpt_name"] == MODEL_CHECKPOINT
    assert patched["4010"]["inputs"]["ckpt_name"] == MODEL_CHECKPOINT
    assert patched["4960"]["inputs"]["ckpt_name"] == MODEL_CHECKPOINT
    assert patched["4960"]["inputs"]["text_encoder"] == TEXT_ENCODER
    assert patched["3059"]["inputs"]["width"] == 512
    assert patched["3059"]["inputs"]["height"] == 288
    assert patched["3059"]["inputs"]["length"] == 17
    assert patched["3980"]["inputs"]["frames_number"] == 17
    assert patched["4814"]["inputs"]["noise_seed"] == 20260713
    assert patched["4966"]["inputs"]["steps"] == 4


def test_cf_vid01_api_patch_rejects_unsafe_prefix(tmp_path: Path):
    service = WorkflowTemplateService(snapshot_root=tmp_path)
    workflow, manifest = service.load_template(TEMPLATE_DIR)
    payload = _payload()
    payload["output_prefix"] = "../escape"

    with pytest.raises(ValidationError):
        service.apply_patch_and_snapshot(workflow, manifest, payload)
