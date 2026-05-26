import json

import pytest

from backend.app.core.errors import ValidationError
from backend.app.services.comfy.object_info_cache import ObjectInfoCacheService
from backend.app.services.workflows.template_service import WorkflowManifest, sha256_json


def _workflow():
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old positive"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 8}},
        "99": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "old"}},
    }


def _manifest(workflow):
    return WorkflowManifest.model_validate(
        {
            "template_id": "object-info-smoke",
            "version": "0.1.0",
            "original_workflow_sha256": sha256_json(workflow),
            "comfyui_snapshot_ref": "fixture",
            "nodes": {
                "positive_prompt": {
                    "node_id": "6",
                    "class_type": "CLIPTextEncode",
                    "input": "text",
                    "runtime_parameter": "positive_prompt",
                    "value_schema": {"type": "string"},
                    "required": True,
                },
                "seed": {
                    "node_id": "3",
                    "class_type": "KSampler",
                    "input": "seed",
                    "runtime_parameter": "seed",
                    "value_schema": {"type": "integer"},
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
    )


def _object_info():
    return {
        "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}}},
        "KSampler": {"input": {"required": {"seed": ["INT", {}], "steps": ["INT", {}]}}},
        "SaveVideo": {"input": {"optional": {"filename_prefix": ["STRING", {}]}}},
    }


def test_object_info_cache_loads_fixture(tmp_path):
    fixture_path = tmp_path / "object_info.json"
    fixture_path.write_text(json.dumps(_object_info()), encoding="utf-8")

    service = ObjectInfoCacheService()
    loaded = service.load_fixture(fixture_path)

    assert loaded == _object_info()
    assert service.object_info == _object_info()
    assert service.loaded_at is not None


@pytest.mark.asyncio
async def test_object_info_cache_offline_refresh_graceful():
    class OfflineClient:
        async def get_object_info(self):
            raise RuntimeError("ComfyUI offline")

    service = ObjectInfoCacheService(_object_info())

    result = await service.refresh(OfflineClient())

    assert not result.refreshed
    assert result.error == "ComfyUI offline"
    assert service.object_info == _object_info()


def test_manifest_object_info_missing_class_fails():
    workflow = _workflow()
    object_info = _object_info()
    object_info.pop("KSampler")
    service = ObjectInfoCacheService(object_info)

    with pytest.raises(ValidationError, match="Object info missing class KSampler"):
        service.validate_manifest_compatibility(_manifest(workflow))


def test_manifest_object_info_missing_input_fails():
    workflow = _workflow()
    object_info = _object_info()
    object_info["CLIPTextEncode"]["input"]["required"].pop("text")
    service = ObjectInfoCacheService(object_info)

    with pytest.raises(ValidationError, match="missing input text"):
        service.validate_manifest_compatibility(_manifest(workflow))


def test_manifest_object_info_valid_case_passes():
    workflow = _workflow()
    service = ObjectInfoCacheService(_object_info())

    service.validate_manifest_compatibility(_manifest(workflow))
    service.validate_workflow_manifest(workflow, _manifest(workflow))
