import json
from pathlib import Path

import pytest

from backend.app.core.errors import ValidationError
from backend.app.schemas.production import OutputProfile, SemanticGenerationRequest
from backend.app.services.workflows.compiler import SemanticWorkflowCompiler
from backend.app.services.workflows.registry import CANONICAL_ARCHETYPE_IDS, WorkflowRegistryService
from backend.app.services.workflows.template_service import WorkflowTemplateService, sha256_json


def _request(**overrides) -> SemanticGenerationRequest:
    payload = {
        "preset_id": "CF-PRESET-001",
        "archetype_id": "CF-VID-01",
        "quality_profile": OutputProfile.draft,
        "mode": "t2v",
        "prompt": "A safe local compiler test prompt.",
        "negative_prompt": "bad quality",
        "seed": 42,
        "width": 512,
        "height": 288,
        "frame_count": 17,
        "fps": 24,
        "target_duration_sec": 1.0,
        "output_profile": OutputProfile.draft,
        "output_prefix": "Compiler Project/run 01",
        "production": False,
    }
    payload.update(overrides)
    return SemanticGenerationRequest(**payload)


def test_default_workflow_registry_loads_all_canonical_records():
    records = WorkflowRegistryService().load()
    ids = [record.archetype_id for record in records]

    assert ids == CANONICAL_ARCHETYPE_IDS
    cf_vid01 = WorkflowRegistryService().require("CF-VID-01")
    assert cf_vid01.implemented is True
    assert cf_vid01.publicly_enabled is False
    assert cf_vid01.api_graph_path is not None
    assert cf_vid01.api_graph_path.is_file()
    assert cf_vid01.api_sha256 == sha256_json(json.loads(cf_vid01.api_graph_path.read_text(encoding="utf-8")))
    assert cf_vid01.template_dir is not None
    assert cf_vid01.template_dir.is_dir()
    assert cf_vid01.bindings
    assert len({binding.semantic_title for binding in cf_vid01.bindings}) == len(cf_vid01.bindings)
    assert cf_vid01.readiness != "ready"
    assert cf_vid01.blocked_reasons
    assert WorkflowRegistryService().production_ready("CF-VID-01") is False


def test_workflow_registry_fails_closed_when_catalog_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        WorkflowRegistryService(registry_path=tmp_path / "missing" / "catalog.json").load()


def test_semantic_compiler_can_compile_non_production_cf_vid01_snapshot(tmp_path: Path):
    compiler = SemanticWorkflowCompiler(template_service=WorkflowTemplateService(snapshot_root=tmp_path))

    result = compiler.compile(_request())

    assert result.template_id == "cf_vid_01_ltx23_single_stage_t2v_smoke"
    assert result.production is False
    assert result.output_prefix == "Compiler Project/run 01"
    patched = result.patched_workflow
    assert patched["4823"]["inputs"]["filename_prefix"] == "Compiler_Project/run_01"
    assert patched["3059"]["inputs"]["width"] == 512
    assert patched["3059"]["inputs"]["height"] == 288
    assert patched["3059"]["inputs"]["length"] == 17
    assert list(tmp_path.glob("cf_vid_01_ltx23_single_stage_t2v_smoke_*.json"))


def test_semantic_compiler_rejects_invalid_ltx_geometry_and_frames(tmp_path: Path):
    compiler = SemanticWorkflowCompiler(template_service=WorkflowTemplateService(snapshot_root=tmp_path))

    with pytest.raises(ValidationError, match="divisible by 32"):
        compiler.compile(_request(width=513))
    with pytest.raises(ValidationError, match=r"8n\+1"):
        compiler.compile(_request(frame_count=10))

    assert list(tmp_path.iterdir()) == []


def test_semantic_compiler_rejects_production_smoke_candidate(tmp_path: Path):
    compiler = SemanticWorkflowCompiler(template_service=WorkflowTemplateService(snapshot_root=tmp_path))

    with pytest.raises(ValidationError) as exc:
        compiler.compile(_request(production=True, first_image_asset_id="asset-1"))

    message = str(exc.value)
    assert "WORKFLOW_NOT_ADMITTED" in message or "SMOKE_WORKFLOW_FORBIDDEN" in message
    assert list(tmp_path.iterdir()) == []
