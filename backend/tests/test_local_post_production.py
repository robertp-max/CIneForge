from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.services.ffmpeg.service import FFmpegService
from backend.app.services.post_production import PostProductionService
from backend.app.services.post_production_manifest import PostProductionPlanStore


_GEOMETRY = {
    "aspect_ratio": "16:9",
    "quality_profile": "draft",
    "generation_width": 512,
    "generation_height": 288,
    "preview_width": 512,
    "preview_height": 288,
    "delivery_width": 1280,
    "delivery_height": 720,
}


def _store(tmp_path: Path) -> PostProductionPlanStore:
    service = PostProductionService(FFmpegService(storage_root=tmp_path / "storage"))
    return PostProductionPlanStore(root=tmp_path / "storage" / "post_production_plans", service=service)


def _payload() -> dict:
    return {
        "clips": [
            {
                "path": "clips/shot-a.mp4",
                "duration_sec": 2.0,
                "start_sec": 0.0,
                "timeline_duration_sec": 2.0,
                "sha256": "a" * 64,
                "probe_json": {"streams": [{"codec_type": "video", "codec_name": "h264"}]},
            }
        ],
        "target_duration_sec": 2.0,
        "geometry": _GEOMETRY,
        "fps": 24,
        "output_path": "delivery/final.mp4",
    }


def _recipe_command_manifest(store: PostProductionPlanStore):
    result = store.service.ffmpeg.build_audio_mux_command(
        "video.mp4",
        "mix.wav",
        "delivery/final.mp4",
        video_sha256="b" * 64,
        audio_sha256="c" * 64,
    )
    return store.create_from_recipe_command(result)


def test_local_post_production_plan_route_creates_lists_and_gets_offline_manifest(monkeypatch, tmp_path: Path):
    store = _store(tmp_path)
    monkeypatch.setattr("backend.app.api.routes.local_post_production._store", lambda: store)

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("offline post-production planning must not execute FFmpeg")

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", forbidden_run)
    client = TestClient(app)

    response = client.post("/local-post-production/plans", json=_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "planned_offline"
    assert payload["execution_submitted"] is False
    assert payload["ffmpeg_job_id"] is None
    assert payload["output_sha256"] is None
    assert payload["final_probe_json"] is None
    assert payload["error_message"] is None
    assert payload["command_template_id"] == "assemble_exact_duration_h264_v1"
    assert payload["input_hashes"] == ["a" * 64]
    assert payload["probe_count"] == 1
    assert Path(payload["manifest_path"]).is_file()

    list_response = client.get("/local-post-production/plans")
    assert list_response.status_code == 200
    assert list_response.json()[0]["plan_id"] == payload["plan_id"]

    get_response = client.get(f"/local-post-production/plans/{payload['plan_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["plan_id"] == payload["plan_id"]


def test_local_post_production_plan_route_rejects_invalid_hash_and_unsafe_path(monkeypatch, tmp_path: Path):
    store = _store(tmp_path)
    monkeypatch.setattr("backend.app.api.routes.local_post_production._store", lambda: store)
    client = TestClient(app)

    bad_hash = _payload()
    bad_hash["clips"][0]["sha256"] = "not-a-hash"
    response = client.post("/local-post-production/plans", json=bad_hash)
    assert response.status_code == 422
    assert "SHA256" in response.json()["detail"]

    unsafe_path = _payload()
    unsafe_path["clips"][0]["path"] = "../escape.mp4"
    response = client.post("/local-post-production/plans", json=unsafe_path)
    assert response.status_code == 422
    assert "escapes configured root" in response.json()["detail"]

    assert store.list() == []


def test_local_post_production_recipe_command_routes_list_and_get_persisted_manifests(monkeypatch, tmp_path: Path):
    store = _store(tmp_path)
    monkeypatch.setattr("backend.app.api.routes.local_post_production._store", lambda: store)

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("recipe command read routes must not execute FFmpeg")

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", forbidden_run)
    manifest = _recipe_command_manifest(store)
    client = TestClient(app)

    list_response = client.get("/local-post-production/recipe-commands")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert [item["plan_id"] for item in listed] == [str(manifest.plan_id)]
    assert listed[0]["state"] == "planned_offline"
    assert listed[0]["execution_submitted"] is False
    assert listed[0]["command_template_id"] == "audio_mux_v1"
    assert listed[0]["command"] == manifest.command
    assert listed[0]["input_hashes"] == ["b" * 64, "c" * 64]

    get_response = client.get(f"/local-post-production/recipe-commands/{manifest.plan_id}")
    assert get_response.status_code == 200
    assert get_response.json() == listed[0]


def test_local_post_production_recipe_command_routes_handle_invalid_and_missing_ids_consistently(
    monkeypatch,
    tmp_path: Path,
):
    store = _store(tmp_path)
    monkeypatch.setattr("backend.app.api.routes.local_post_production._store", lambda: store)
    client = TestClient(app)

    invalid = client.get("/local-post-production/recipe-commands/not-a-uuid")
    assert invalid.status_code == 422

    missing = client.get(f"/local-post-production/recipe-commands/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Post-production recipe command plan not found."


def test_local_post_production_routes_do_not_expose_execution_endpoint():
    paths = {route.path for route in app.routes}
    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    recipe_command_methods = {
        method
        for method, path in method_paths
        if path.startswith("/local-post-production/recipe-commands")
    }

    assert "/local-post-production/execute" not in paths
    assert "/local-post-production/plans/{plan_id}/execute" not in paths
    assert not any(
        path.startswith("/local-post-production/recipe-commands") and "execute" in path
        for path in paths
    )
    assert recipe_command_methods == {"GET"}
    assert ("POST", "/local-post-production/recipe-commands") not in method_paths
