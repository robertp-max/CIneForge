import pytest

from backend.app.services import generation_model_contract
from backend.app.services.phase_six_images import (
    DEFAULT_FLUX_IMAGE_MODEL,
    DEFAULT_GUIDANCE,
    DEFAULT_STEPS,
    FALLBACK_FLUX_IMAGE_MODEL,
    _image_archetype,
    _workflow,
)


def _inputs_for(workflow: dict, class_type: str, input_name: str) -> list:
    values = []
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") != class_type:
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, dict) and input_name in inputs:
            values.append(inputs[input_name])
    return values


def test_generation_model_allowlist_is_exact() -> None:
    assert generation_model_contract.APPROVED_BASE_MODELS == {
        "flux2_dev_fp8mixed.safetensors",
        "flux2_dev.safetensors",
        "ltx-2.3-22b-distilled-1.1-fp8.safetensors",
    }


def test_phase_six_workflow_uses_flux_family_base_model_and_runtime_settings() -> None:
    workflow = _workflow("period-correct test", "unused", 42, "cineforge/test")

    assert _inputs_for(workflow, "UNETLoader", "unet_name") == [DEFAULT_FLUX_IMAGE_MODEL]
    assert _inputs_for(workflow, "SaveImage", "filename_prefix") == ["cineforge/test"]
    assert _inputs_for(workflow, "RandomNoise", "noise_seed") == [42]
    assert all(value == DEFAULT_GUIDANCE for value in _inputs_for(workflow, "FluxGuidance", "guidance"))
    assert (
        DEFAULT_STEPS in _inputs_for(workflow, "Flux2Scheduler", "steps")
        or DEFAULT_STEPS in _inputs_for(workflow, "PrimitiveInt", "value")
    )
    assert all(
        node.get("inputs", {}).get("ckpt_name") is None for node in workflow.values()
    )


def test_phase_six_routes_semantic_image_archetypes() -> None:
    assert _image_archetype("Estate — Establishing Geography 1")["id"] == "CF-IMG-01-WIDE"
    assert _image_archetype("Estate — Principal Action 2")["id"] == "CF-IMG-02-ACTION"
    assert _image_archetype("Estate — Restrained Reaction 3")["id"] == "CF-IMG-02-REACTION"
    detail = _image_archetype("Estate — Tactile Detail 4")
    assert detail["id"] == "CF-IMG-04-DETAIL"
    assert detail["lora_name"] == "Detailed_Hands-000001.safetensors"


def test_phase_six_reference_arguments_do_not_replace_the_flux_base_model() -> None:
    workflow = _workflow(
        "period-correct test",
        "unused",
        42,
        "cineforge/test",
        "cineforge_prodigal_estate_style.png",
        0.15,
    )
    assert _inputs_for(workflow, "UNETLoader", "unet_name") == [DEFAULT_FLUX_IMAGE_MODEL]
    assert all(
        node.get("inputs", {}).get("ckpt_name") is None for node in workflow.values()
    )


def test_wrong_base_models_fail_closed() -> None:
    generation_model_contract.require_approved_planning_image_model(DEFAULT_FLUX_IMAGE_MODEL)
    generation_model_contract.require_approved_planning_image_model(FALLBACK_FLUX_IMAGE_MODEL)
    generation_model_contract.require_approved_planning_image_model("flux1-dev-Q8_0.gguf")
    with pytest.raises(ValueError, match="Flux-family local model"):
        generation_model_contract.require_approved_planning_image_model(
            "cyberrealisticXL_v100.safetensors"
        )
    with pytest.raises(ValueError, match="Video generation requires ltx-2.3"):
        generation_model_contract.require_approved_video_model(
            "ltx-2.3-22b-dev.safetensors"
        )
