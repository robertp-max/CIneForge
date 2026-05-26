from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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

