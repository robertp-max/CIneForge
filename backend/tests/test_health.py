from fastapi.testclient import TestClient
import pytest

from backend.app.main import app


client = TestClient(app)


def test_root_returns_ok():
    response = client.get("/")

    assert response.status_code == 200


def test_root_returns_useful_cineforge_status_json():
    response = client.get("/")

    assert response.json() == {
        "app": "CineForge",
        "status": "ok",
        "message": "CineForge backend is running.",
        "docs_url": "/docs",
        "frontend_dev_url": "http://localhost:5173",
        "generation_enabled": False,
        "prompt_submission_publicly_accessible": False,
        "current_phase": "Phase 2 controlled ComfyUI submission backend capability",
    }


def test_favicon_does_not_return_404():
    response = client.get("/favicon.ico")

    assert response.status_code == 204


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database_required"] is False
    assert payload["hardware_operator_enabled"] is False
    assert payload["local_state_mode"] == "file_backed"
    assert payload["comfyui_output_root"].replace("\\", "/").endswith("ComfyUI/output")


def test_local_vite_origin_is_allowed_by_cors():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_phase1_mutation_methods_are_allowed_by_cors(method):
    response = client.options(
        "/projects/00000000-0000-0000-0000-000000000000/storyboard-settings",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": method,
        },
    )
    assert response.status_code == 200
    allowed = {item.strip() for item in response.headers["access-control-allow-methods"].split(",")}
    assert method in allowed


def test_comfy_offline_health_handled_gracefully():
    response = client.get("/health/comfy")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded", "unavailable"}


def test_gpu_unavailable_handled_gracefully(monkeypatch):
    monkeypatch.setattr("backend.app.services.telemetry.gpu.shutil.which", lambda _name: None)
    response = client.get("/health/gpu")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_ffmpeg_unavailable_handled_gracefully(monkeypatch):
    monkeypatch.setattr("backend.app.services.ffmpeg.service.shutil.which", lambda _name: None)
    response = client.get("/health/ffmpeg")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_runtime_status_is_read_only_and_reports_disabled_actions(monkeypatch):
    async def fake_health(self):
        return {"status": "unavailable", "reachable": False, "error": "offline"}

    async def fake_object_info(self):
        raise RuntimeError("object_info unavailable")

    monkeypatch.setattr("backend.app.services.comfy.client.ComfyUIClient.health", fake_health)
    monkeypatch.setattr("backend.app.services.comfy.client.ComfyUIClient.get_object_info", fake_object_info)
    monkeypatch.setattr("backend.app.services.telemetry.gpu.shutil.which", lambda _name: None)
    monkeypatch.setattr("backend.app.services.ffmpeg.service.shutil.which", lambda _name: None)

    response = client.get("/runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["queue"]["submission_enabled"] is False
    assert payload["queue"]["hardware_operator_enabled"] is False
    assert payload["queue"]["controlled_submission_enabled"] is False
    assert payload["queue"]["public_submission_enabled"] is False
    assert payload["queue"]["database_required"] is False
    assert payload["queue"]["local_state_mode"] == "file_backed"
    assert payload["output_policy"]["filename_prefix_shape"] == "<project-folder>/<run-stem>"
    assert payload["output_policy"]["one_folder_per_project"] is True
    assert payload["disabled_actions"]["public_submit_prompt"] == "disabled"
    assert payload["disabled_actions"]["hardware_operator_submit"] == "disabled"

