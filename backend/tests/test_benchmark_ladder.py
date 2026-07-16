from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.core.errors import ValidationError
from backend.app.services.benchmarks.ladder import BenchmarkLadderService, write_ladder_manifest


def _manifest() -> dict:
    return json.loads(Path("storage/benchmark_ladders/m4_cf_vid01_ladder.json").read_text(encoding="utf-8"))


def test_m4_ladder_manifest_loads_as_read_only_pending_plan():
    manifest = BenchmarkLadderService().get_m4_ladder()

    assert manifest.phase == "M4"
    assert manifest.allowed_stage_numbers == [0, 1, 2, 3, 7]
    assert manifest.deferred_stage_numbers == [4, 5, 6]
    assert [stage.stage for stage in manifest.stages] == [0, 1, 2, 3, 7]
    assert manifest.public_generation_enabled is False
    assert manifest.queue_worker_general_execution_enabled is False
    assert manifest.requires_serial_execution is True
    assert manifest.requires_hardware_operator_mode is True
    assert all(stage.live_action_approved is False for stage in manifest.stages)
    assert all(stage.requires_operator_approval for stage in manifest.stages)
    assert all(stage.requires_exclusive_gpu_lease for stage in manifest.stages)
    assert "does not run ComfyUI" in manifest.evidence_note


def test_m4_ladder_rejects_deferred_stage_numbers(tmp_path: Path):
    payload = _manifest()
    stage_4 = copy.deepcopy(payload["stages"][3])
    stage_4["stage"] = 4
    stage_4["stage_id"] = "m4_stage_4_forbidden"
    payload["allowed_stage_numbers"] = [0, 1, 2, 3, 4, 7]
    payload["stages"] = payload["stages"][:4] + [stage_4] + payload["stages"][4:]
    path = write_ladder_manifest(tmp_path / "bad_ladder.json", payload)

    with pytest.raises(ValidationError, match="allow exactly stages"):
        BenchmarkLadderService(Settings(storage_root=tmp_path), ladder_path=path).get_m4_ladder()


def test_m4_ladder_rejects_public_generation_or_preapproval(tmp_path: Path):
    payload = _manifest()
    payload["public_generation_enabled"] = True
    path = write_ladder_manifest(tmp_path / "public_ladder.json", payload)
    with pytest.raises(ValidationError, match="must not enable public generation"):
        BenchmarkLadderService(Settings(storage_root=tmp_path), ladder_path=path).get_m4_ladder()

    payload = _manifest()
    payload["stages"][0]["live_action_approved"] = True
    path = write_ladder_manifest(tmp_path / "preapproved_ladder.json", payload)
    with pytest.raises(ValidationError, match="must not be pre-approved"):
        BenchmarkLadderService(Settings(storage_root=tmp_path), ladder_path=path).get_m4_ladder()


def test_m4_ladder_rejects_deferred_or_out_of_scope_archetypes(tmp_path: Path):
    payload = _manifest()
    payload["stages"][0]["archetypes"] = ["CF-VID-02"]
    path = write_ladder_manifest(tmp_path / "deferred_archetype_ladder.json", payload)

    with pytest.raises(ValidationError, match="deferred archetype"):
        BenchmarkLadderService(Settings(storage_root=tmp_path), ladder_path=path).get_m4_ladder()


def test_m4_ladder_route_returns_read_only_manifest():
    client = TestClient(app)
    assert client.post("/local-runtime/m4-ladder", json={}).status_code == 405

    response = client.get("/local-runtime/m4-ladder")

    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == "M4"
    assert payload["allowed_stage_numbers"] == [0, 1, 2, 3, 7]
    assert payload["deferred_stage_numbers"] == [4, 5, 6]
    assert payload["public_generation_enabled"] is False
    assert payload["requires_serial_execution"] is True
    assert all(stage["live_action_approved"] is False for stage in payload["stages"])
    assert "does not run ComfyUI" in payload["evidence_note"]


def test_m4_ladder_requires_stage_7_after_stage_1_success(tmp_path: Path):
    payload = _manifest()
    payload["stages"][-1]["requires_stage_success"] = []
    path = write_ladder_manifest(tmp_path / "bad_stage7_ladder.json", payload)

    with pytest.raises(ValidationError, match="Stage 1 success"):
        BenchmarkLadderService(Settings(storage_root=tmp_path), ladder_path=path).get_m4_ladder()
