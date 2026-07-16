from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.local_checkpoint_watchdog import LocalCheckpointWatchdogService
from scripts.checkpoint_watchdog import CheckpointWatchdogReport


def test_local_checkpoint_watchdog_service_is_read_only(monkeypatch, tmp_path: Path):
    def fake_build(_repo_root: Path) -> CheckpointWatchdogReport:
        return CheckpointWatchdogReport(
            last_commit="abc123 checkpoint: example",
            tracked_worktree_clean=True,
            staged_files=("backend/app/services/local_checkpoint_watchdog.py",),
            reminder="WATCHDOG: checkpoint loop must restart now.",
            invariants=("No FFmpeg/ffprobe execution without explicit scoped live approval.",),
        )

    monkeypatch.setattr("backend.app.services.local_checkpoint_watchdog.build_watchdog_report", fake_build)

    report = LocalCheckpointWatchdogService(tmp_path).report()

    assert report.checkpoint_id == "local_checkpoint_watchdog"
    assert report.last_commit == "abc123 checkpoint: example"
    assert report.tracked_worktree_clean is True
    assert report.staged_files == ["backend/app/services/local_checkpoint_watchdog.py"]
    assert "restart now" in report.reminder
    assert report.live_execution_performed_by_endpoint is False
    assert report.live_execution_approved_by_endpoint is False
    assert report.public_generation_enabled is False
    assert report.invariants == ["No FFmpeg/ffprobe execution without explicit scoped live approval."]


def test_local_checkpoint_watchdog_route_is_get_only_and_non_executing():
    client = TestClient(app)

    assert client.post("/local-runtime/checkpoint-watchdog", json={}).status_code == 405

    response = client.get("/local-runtime/checkpoint-watchdog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint_id"] == "local_checkpoint_watchdog"
    assert "checkpoint loop must restart now" in payload["reminder"]
    assert isinstance(payload["staged_files"], list)
    assert payload["live_execution_performed_by_endpoint"] is False
    assert payload["live_execution_approved_by_endpoint"] is False
    assert payload["public_generation_enabled"] is False
    assert any("No FFmpeg/ffprobe" in item for item in payload["invariants"])

    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert {method for method, path in method_paths if path == "/local-runtime/checkpoint-watchdog"} == {"GET"}
    assert not any(
        path.startswith("/local-runtime/checkpoint-watchdog/")
        and any(child in path for child in ("execute", "submit", "approve", "prompt", "run"))
        for _method, path in method_paths
    )
