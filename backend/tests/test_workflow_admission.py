import copy
import json
from pathlib import Path

import pytest

from backend.app.core.errors import ValidationError
from backend.app.schemas.production import OutputProfile, SemanticGenerationRequest
from backend.app.services.workflows.admission import WorkflowAdmissionService
from backend.app.services.workflows.compiler import SemanticWorkflowCompiler
from backend.app.services.workflows.registry import WorkflowRegistryService
from backend.app.services.workflows.template_service import WorkflowTemplateService


def _catalog() -> dict:
    return json.loads(Path("storage/workflow_registry/catalog.json").read_text(encoding="utf-8"))


def _write_catalog(tmp_path: Path, catalog: dict) -> Path:
    path = tmp_path / "workflow_registry" / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    return path


def _cf_vid01(catalog: dict) -> dict:
    return next(record for record in catalog["workflows"] if record["archetype_id"] == "CF-VID-01")


def _request() -> SemanticGenerationRequest:
    return SemanticGenerationRequest(
        preset_id="CF-PRESET-001",
        archetype_id="CF-VID-01",
        quality_profile=OutputProfile.draft,
        mode="t2v",
        prompt="A safe local compiler test prompt.",
        negative_prompt="bad quality",
        width=512,
        height=288,
        frame_count=17,
        fps=24,
        target_duration_sec=1.0,
        output_profile=OutputProfile.draft,
        output_prefix="Admission Project/run 01",
        production=False,
    )


def test_admission_reports_default_cf_vid01_blockers_without_public_enablement():
    result = WorkflowAdmissionService().evaluate("CF-VID-01")

    codes = [finding.code for finding in result.findings]
    assert result.admitted_for_local_execution is False
    assert "PUBLIC_ENABLEMENT_FORBIDDEN" not in codes
    assert "BLOCKED" in codes


def test_admission_reports_missing_object_info_classes():
    result = WorkflowAdmissionService().evaluate("CF-VID-01", object_info={})

    assert result.admitted_for_local_execution is False
    assert "OBJECT_INFO_CLASS_MISSING" in [finding.code for finding in result.findings]


def test_admission_reports_duplicate_semantic_titles(tmp_path: Path):
    catalog = _catalog()
    cf_vid01 = _cf_vid01(catalog)
    mutated = copy.deepcopy(cf_vid01["bindings"][0]["semantic_title"])
    cf_vid01["bindings"][1]["semantic_title"] = mutated
    registry = WorkflowRegistryService(registry_path=_write_catalog(tmp_path, catalog))

    result = WorkflowAdmissionService(registry).evaluate("CF-VID-01")

    assert "DUPLICATE_SEMANTIC_TITLE" in [finding.code for finding in result.findings]


def test_admission_reports_public_enablement_forbidden(tmp_path: Path):
    catalog = _catalog()
    _cf_vid01(catalog)["publicly_enabled"] = True
    registry = WorkflowRegistryService(registry_path=_write_catalog(tmp_path, catalog))

    result = WorkflowAdmissionService(registry).evaluate("CF-VID-01")

    assert "PUBLIC_ENABLEMENT_FORBIDDEN" in [finding.code for finding in result.findings]


def test_registry_blocks_api_hash_mismatch(tmp_path: Path):
    catalog = _catalog()
    _cf_vid01(catalog)["api_sha256"] = "0" * 64
    registry = WorkflowRegistryService(registry_path=_write_catalog(tmp_path, catalog))

    record = registry.require("CF-VID-01")

    assert any("API graph hash mismatch" in reason for reason in record.blocked_reasons)
    assert record.readiness == "blocked"


def test_semantic_compiler_rejects_binding_class_drift(tmp_path: Path):
    catalog = _catalog()
    _cf_vid01(catalog)["bindings"][0]["class_type"] = "WrongNode"
    registry = WorkflowRegistryService(registry_path=_write_catalog(tmp_path, catalog))
    compiler = SemanticWorkflowCompiler(
        registry=registry,
        template_service=WorkflowTemplateService(snapshot_root=tmp_path / "snapshots"),
    )

    with pytest.raises(ValidationError, match="class drift"):
        compiler.compile(_request())

    assert not (tmp_path / "snapshots").exists()
