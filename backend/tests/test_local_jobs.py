import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import Settings
from backend.app.core.errors import ValidationError
from backend.app.main import app
from backend.app.schemas.local_jobs import LocalJobCreate
from backend.app.services.local_jobs import LocalJobStore


def _temp_settings(tmp_path: Path, *, include_workflow: bool = True) -> Settings:
    settings = Settings(storage_root=tmp_path / "storage", comfyui_output_root=tmp_path / "comfy-output")
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree("storage/presets", settings.storage_root / "presets")
    shutil.copytree("storage/archetypes", settings.storage_root / "archetypes")
    if include_workflow:
        workflow_root = settings.storage_root / "workflow_templates"
        workflow_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            "storage/workflow_templates/cf_vid_01_ltx23_single_stage",
            workflow_root / "cf_vid_01_ltx23_single_stage",
        )
    return settings


def test_local_job_store_creates_manifest_and_project_output_folder(tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = LocalJobStore(settings)

    manifest = store.create(
        LocalJobCreate(
            project_key="Project A",
            run_stem="shot 001",
            prompt="test prompt",
            width=704,
            height=384,
            frames=49,
            fps=24,
        )
    )

    assert manifest.state == "prepared_offline"
    assert manifest.generation_submitted is False
    assert manifest.comfy_prompt_id is None
    assert manifest.project_folder == "Project_A"
    assert manifest.filename_prefix == "Project_A/shot_001"
    assert manifest.project_output_dir == tmp_path / "comfy-output" / "Project_A"
    assert manifest.project_output_dir.is_dir()
    assert manifest.workflow_template_id == "cf_vid_01_ltx23_single_stage_t2v_smoke"
    assert manifest.workflow_snapshot_path is not None
    assert manifest.workflow_snapshot_path.is_file()
    snapshot = json.loads(manifest.workflow_snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["4823"]["inputs"]["filename_prefix"] == "Project_A/shot_001"
    assert snapshot["3940"]["inputs"]["ckpt_name"] == "ltx-2.3-22b-distilled-1.1-fp8.safetensors"
    assert snapshot["4010"]["inputs"]["ckpt_name"] == "ltx-2.3-22b-distilled-1.1-fp8.safetensors"
    assert snapshot["4960"]["inputs"]["text_encoder"] == "gemma_3_12B_it_fp4_mixed.safetensors"
    assert "4922" not in snapshot
    assert "4968" not in snapshot
    assert manifest.manifest_path.is_file()
    assert (settings.storage_root / "local_jobs" / "events.jsonl").is_file()

    loaded = store.get(manifest.job_id)
    assert loaded == manifest
    assert store.list()[0].job_id == manifest.job_id


def test_local_job_route_can_be_bound_to_temp_store(monkeypatch, tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = LocalJobStore(settings)

    monkeypatch.setattr("backend.app.api.routes.local_jobs._store", lambda: store)
    client = TestClient(app)

    response = client.post(
        "/local-jobs",
        json={
            "project_key": "Route Project",
            "run_stem": "run 01",
            "prompt": "route prompt",
            "frames": 49,
            "fps": 24,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generation_submitted"] is False
    assert payload["filename_prefix"] == "Route_Project/run_01"
    assert Path(payload["project_output_dir"]).is_dir()
    assert payload["workflow_template_id"] == "cf_vid_01_ltx23_single_stage_t2v_smoke"
    assert Path(payload["workflow_snapshot_path"]).is_file()

    list_response = client.get("/local-jobs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["job_id"] == payload["job_id"]

    get_response = client.get(f"/local-jobs/{payload['job_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["filename_prefix"] == "Route_Project/run_01"


def test_local_job_store_fails_closed_when_configured_workflow_template_missing(tmp_path: Path):
    settings = _temp_settings(tmp_path, include_workflow=False)
    store = LocalJobStore(settings)

    with pytest.raises(FileNotFoundError):
        store.create(LocalJobCreate(project_key="Project A", run_stem="shot 001"))


def test_local_job_store_rejects_non_selected_model(tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = LocalJobStore(settings)

    with pytest.raises(ValidationError, match="Only selected local model"):
        store.create(
            LocalJobCreate(
                project_key="Project A",
                run_stem="shot 001",
                model_key="wrong_model",
            )
        )


def test_local_job_store_rejects_invalid_ltx_dimensions_and_frame_count(tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = LocalJobStore(settings)

    with pytest.raises(ValidationError, match="divisible by 32"):
        store.create(
            LocalJobCreate(
                project_key="Project A",
                run_stem="bad dimensions",
                width=513,
                height=288,
                frames=17,
            )
        )
    with pytest.raises(ValidationError, match=r"8n\+1"):
        store.create(
            LocalJobCreate(
                project_key="Project A",
                run_stem="bad frames",
                width=512,
                height=288,
                frames=10,
            )
        )

    assert store.list() == []
    assert not (settings.storage_root / "local_jobs" / "events.jsonl").exists()


def test_local_job_route_rejects_invalid_ltx_contract(monkeypatch, tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = LocalJobStore(settings)
    monkeypatch.setattr("backend.app.api.routes.local_jobs._store", lambda: store)

    response = TestClient(app).post(
        "/local-jobs",
        json={"project_key": "Bad", "run_stem": "bad", "prompt": "bad", "width": 512, "height": 288, "frames": 10},
    )

    assert response.status_code == 422
    assert "8n+1" in response.json()["detail"]
    assert store.list() == []


def test_local_job_route_does_not_submit_to_comfyui(monkeypatch, tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = LocalJobStore(settings)
    monkeypatch.setattr("backend.app.api.routes.local_jobs._store", lambda: store)

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("local job manifest creation must not submit prompts")

    monkeypatch.setattr("backend.app.services.comfy.client.ComfyUIClient.submit_prompt", fail_if_called)

    response = TestClient(app).post(
        "/local-jobs",
        json={"project_key": "Safe", "run_stem": "run", "prompt": "no submit"},
    )

    assert response.status_code == 200
    assert response.json()["generation_submitted"] is False
