from __future__ import annotations

import subprocess

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.services.local_public_readiness import LocalPublicReadinessService


def test_local_public_readiness_report_is_fail_closed_and_read_only(monkeypatch):
    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("public readiness report must not execute subprocesses")

    monkeypatch.setattr(subprocess, "run", forbidden_run)
    report = LocalPublicReadinessService(Settings(queue_worker_enabled=False)).report()

    assert report.checkpoint_id == "local_public_release_readiness"
    assert report.status == "blocked"
    assert report.public_release_ready is False
    assert report.public_generation_enabled is False
    assert report.public_prompt_enabled is False
    assert report.internet_facing_enabled is False
    assert report.autonomous_generation_enabled is False
    assert report.live_execution_performed_by_endpoint is False
    assert report.live_execution_approved_by_endpoint is False
    assert report.archetype_summary.ready == 0
    assert report.preset_summary.ready == 0
    assert report.archetype_summary.public_generation_enabled is False
    assert report.preset_summary.public_generation_enabled is False
    assert report.m5_ffmpeg_execution_endpoint_present is False
    assert any("Public generation" in blocker for blocker in report.remaining_public_release_blockers)
    assert any(check.code == "raw_prompt_route_absent" and check.passed for check in report.checks)
    assert any(check.code == "endpoint_does_not_execute_or_approve_live_work" for check in report.checks)


def test_local_public_readiness_reports_queue_blocker_when_worker_enabled():
    report = LocalPublicReadinessService(Settings(queue_worker_enabled=True)).report()

    assert report.public_release_ready is False
    assert report.autonomous_generation_enabled is True
    blocker = next(check for check in report.checks if check.code == "autonomous_generation_disabled")
    assert blocker.passed is False
    assert blocker.severity == "blocker"


def test_local_public_readiness_route_contract_is_get_only():
    client = TestClient(app)

    assert client.post("/local-runtime/public-readiness", json={}).status_code == 405

    response = client.get("/local-runtime/public-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint_id"] == "local_public_release_readiness"
    assert payload["status"] == "blocked"
    assert payload["public_release_ready"] is False
    assert payload["public_generation_enabled"] is False
    assert payload["public_prompt_enabled"] is False
    assert payload["live_execution_performed_by_endpoint"] is False
    assert payload["live_execution_approved_by_endpoint"] is False
    assert payload["archetype_summary"]["ready"] == 0
    assert payload["preset_summary"]["ready"] == 0

    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert {method for method, path in method_paths if path == "/local-runtime/public-readiness"} == {"GET"}
    assert ("POST", "/local-runtime/public-readiness") not in method_paths
    assert not any(
        path.startswith("/local-runtime/public-readiness/")
        and any(child in path.split("/public-readiness", 1)[1] for child in ("execute", "submit", "approve", "prompt", "run"))
        for _method, path in method_paths
    )
    assert "/prompt" not in {path for _method, path in method_paths}
