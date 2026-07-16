from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.schemas.local_runtime import ArtifactRole, LocalReadiness
from backend.app.services.local_runtime import local_runtime_catalog, prepare_project_output


def test_local_runtime_catalog_is_db_free_and_records_selected_fp8():
    catalog = local_runtime_catalog(Settings())

    assert catalog.database_required is False
    assert catalog.generation_enabled is False
    assert catalog.public_generation_enabled is False
    assert catalog.model_key == "ltx2_3_22b_distilled_1_1_fp8"
    assert catalog.fp8_method == "converted_derivative"

    selected = next(item for item in catalog.artifacts if item.role == ArtifactRole.selected_fp8)
    assert selected.key == "ltx2_3_22b_distilled_1_1_fp8"
    assert selected.sha256 == "c5dd96a75c4b588171b9807a8a25fea91e71a3cc7386d8bc245f50a21756cfbb"
    assert selected.expected_size_bytes == 25_134_891_534
    assert selected.fp8_method == "converted_derivative"
    assert "same 5,947 tensor" in (selected.header_identity or "")
    assert selected.readiness in {LocalReadiness.benchmark_required, LocalReadiness.blocked}

    assert catalog.output_policy.one_folder_per_project is True
    assert catalog.output_policy.user_supplied_output_paths_allowed is False


def test_prepare_project_output_creates_project_folder(tmp_path: Path):
    settings = Settings(comfyui_output_root=tmp_path)

    prepared = prepare_project_output(settings, "Project A", "run 01")

    assert prepared["output_root"] == str(tmp_path)
    assert prepared["filename_prefix"] == "Project_A/run_01"
    assert Path(prepared["project_output_dir"]).is_dir()
    assert Path(prepared["project_output_dir"]) == tmp_path / "Project_A"


def test_local_runtime_routes_are_read_only():
    client = TestClient(app)

    assert client.post("/local-runtime/catalog", json={}).status_code == 405
    assert client.post("/local-runtime/output-policy", json={}).status_code == 405

    catalog_response = client.get("/local-runtime/catalog")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert catalog["database_required"] is False
    assert catalog["generation_enabled"] is False
    assert catalog["model_key"] == "ltx2_3_22b_distilled_1_1_fp8"
    assert any(item["role"] == "selected_fp8" for item in catalog["artifacts"])

    policy_response = client.get("/local-runtime/output-policy")
    assert policy_response.status_code == 200
    policy = policy_response.json()
    assert policy["one_folder_per_project"] is True
    assert policy["filename_prefix_shape"] == "<project-folder>/<run-stem>"
    assert policy["user_supplied_output_paths_allowed"] is False
