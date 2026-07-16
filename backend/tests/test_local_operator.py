from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import UUID

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.schemas.local_operator import LocalOperatorRunMode, LocalOperatorRunPacketCreate
from backend.app.services.local_operator import LocalOperatorRunPacketStore


def _settings(tmp_path: Path) -> Settings:
    return Settings(storage_root=tmp_path / "storage", queue_worker_enabled=False)


def _payload(mode: str = "m4_hardware_ladder_probe") -> dict:
    return {
        "mode": mode,
        "requested_by": "local-operator",
        "target_ref": "CF-VID-01",
        "notes": "prepare offline packet only",
        "acknowledge_no_execution": True,
    }


def test_local_operator_run_packet_store_creates_m4_packet_without_live_work(monkeypatch, tmp_path: Path):
    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("operator run packet creation must not execute subprocesses")

    monkeypatch.setattr(subprocess, "run", forbidden_run)
    store = LocalOperatorRunPacketStore(_settings(tmp_path))

    packet = store.create(LocalOperatorRunPacketCreate(**_payload()))

    assert packet.state == "pending_explicit_operator_approval"
    assert packet.approval_recorded is False
    assert packet.live_execution_started is False
    assert packet.generation_submitted is False
    assert packet.ffmpeg_submitted is False
    assert packet.comfy_prompt_id is None
    assert packet.queue_job_id is None
    assert packet.local_mvp.live_execution_approved_by_endpoint is False
    assert packet.local_mvp.local_operator_live_runs_allowed_by_endpoint is False
    assert packet.m4_preflight is not None
    assert packet.m4_preflight.live_actions_executed is False
    assert packet.m5_recipes is None
    assert "explicit_operator_approval_required" in packet.blocking_reasons
    assert "packet_does_not_authorize_live_execution" in packet.blocking_reasons
    assert packet.manifest_path.is_file()
    assert (packet.manifest_path.parent / "events.jsonl").is_file()
    assert store.get(packet.packet_id).packet_id == packet.packet_id


def test_local_operator_run_packet_store_creates_m5_packet_with_read_only_recipe_summary(tmp_path: Path):
    store = LocalOperatorRunPacketStore(_settings(tmp_path))

    packet = store.create(
        LocalOperatorRunPacketCreate(**_payload(mode=LocalOperatorRunMode.m5_ffmpeg_probe_validation.value))
    )

    assert packet.m4_preflight is None
    assert packet.m5_recipes is not None
    assert packet.m5_recipes.recipe_catalog_count >= 1
    assert packet.m5_recipes.ffmpeg_recipes_read_only is True
    assert packet.m5_recipes.ffmpeg_execution_endpoint_present is False
    assert packet.m5_recipes.live_ffmpeg_probe_or_execute_performed is False
    assert packet.m5_recipes.user_authored_ffmpeg_commands_allowed is False
    assert packet.approval_recorded is False
    assert packet.live_execution_started is False
    assert packet.ffmpeg_submitted is False
    assert "m5_live_ffmpeg_or_ffprobe_requires_separate_operator_run" in packet.blocking_reasons


def test_local_operator_run_packet_rejects_missing_no_execution_acknowledgement(tmp_path: Path):
    store = LocalOperatorRunPacketStore(_settings(tmp_path))
    payload = _payload()
    payload["acknowledge_no_execution"] = False

    with pytest.raises(ValueError, match="acknowledge_no_execution"):
        store.create(LocalOperatorRunPacketCreate(**payload))

    assert not (tmp_path / "storage" / "local_operator_run_packets").exists()


def test_local_operator_run_packet_routes_create_list_and_get(monkeypatch, tmp_path: Path):
    store = LocalOperatorRunPacketStore(_settings(tmp_path))
    monkeypatch.setattr("backend.app.api.routes.local_operator._store", lambda: store)
    client = TestClient(app)

    create_response = client.post("/local-operator/packets", json=_payload())

    assert create_response.status_code == 200
    created = create_response.json()
    UUID(created["packet_id"])
    assert created["state"] == "pending_explicit_operator_approval"
    assert created["approval_recorded"] is False
    assert created["live_execution_started"] is False
    assert created["generation_submitted"] is False
    assert created["ffmpeg_submitted"] is False
    assert created["comfy_prompt_id"] is None
    assert created["queue_job_id"] is None
    assert created["m4_preflight"]["live_actions_executed"] is False

    list_response = client.get("/local-operator/packets")
    assert list_response.status_code == 200
    assert list_response.json()[0]["packet_id"] == created["packet_id"]

    get_response = client.get(f"/local-operator/packets/{created['packet_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["packet_id"] == created["packet_id"]


def test_local_operator_run_packet_route_requires_no_execution_ack(monkeypatch, tmp_path: Path):
    store = LocalOperatorRunPacketStore(_settings(tmp_path))
    monkeypatch.setattr("backend.app.api.routes.local_operator._store", lambda: store)
    client = TestClient(app)
    payload = _payload()
    payload["acknowledge_no_execution"] = False

    response = client.post("/local-operator/packets", json=payload)

    assert response.status_code == 422
    assert not (tmp_path / "storage" / "local_operator_run_packets").exists()


def test_local_operator_route_contract_has_no_live_child_routes_or_prompt():
    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert {method for method, path in method_paths if path == "/local-operator/packets"} == {"GET", "POST"}
    assert {method for method, path in method_paths if path == "/local-operator/packets/{packet_id}"} == {"GET"}
    assert "/prompt" not in {path for _method, path in method_paths}
    assert not any(
        path.startswith("/local-operator") and any(child in path for child in ("/execute", "/submit", "/run", "/approve", "/prompt"))
        for _method, path in method_paths
    )
