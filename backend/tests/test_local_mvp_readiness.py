from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.services.ffmpeg.service import ffmpeg_command_template_catalog
from backend.app.services.local_mvp_readiness import LocalMVPReadinessService


def test_local_mvp_readiness_report_is_read_only_checkpoint(monkeypatch):
    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("local MVP readiness report must not execute subprocesses")

    monkeypatch.setattr("backend.app.services.ffmpeg.service.subprocess.run", forbidden_run)

    report = LocalMVPReadinessService(Settings(queue_worker_enabled=False)).report()
    recipe_count = len(ffmpeg_command_template_catalog())

    assert report.local_only_target is True
    assert report.public_generation_disabled is True
    assert report.autonomous_generation_disabled is True
    assert report.generation_enabled is False
    assert report.public_generation_enabled is False
    assert report.live_execution_performed_by_endpoint is False
    assert report.live_execution_approved_by_endpoint is False
    assert report.local_operator_live_runs_allowed_by_endpoint is False
    assert report.m4_preflight.live_actions_executed is False
    assert report.m4_preflight.public_generation_enabled is False
    assert report.m5_post_production.recipe_catalog_count == recipe_count
    assert report.m5_post_production.ffmpeg_recipes_read_only is True
    assert report.m5_post_production.ffmpeg_recipes_execute_from_catalog is False
    assert report.m5_post_production.user_authored_ffmpeg_commands_allowed is False
    assert report.m5_post_production.ffmpeg_execution_endpoint_present is False
    assert report.m5_post_production.live_ffmpeg_probe_or_execute_performed is False
    assert any("Explicit operator approval" in blocker for blocker in report.remaining_blockers_before_local_operator_live_runs)
    assert any("GPU lease" in blocker for blocker in report.remaining_blockers_before_local_operator_live_runs)
    assert any(check.code == "endpoint_does_not_execute_or_approve_live_work" for check in report.checks)


def test_local_mvp_readiness_reports_autonomous_queue_blocker_when_worker_enabled():
    report = LocalMVPReadinessService(Settings(queue_worker_enabled=True)).report()

    assert report.status == "blocked"
    assert report.autonomous_generation_disabled is False
    blocker = next(check for check in report.checks if check.code == "autonomous_queue_execution_disabled")
    assert blocker.passed is False
    assert blocker.severity == "blocker"


def test_local_mvp_readiness_route_contract_is_get_only():
    client = TestClient(app)

    assert client.post("/local-runtime/local-mvp-readiness", json={}).status_code == 405

    response = client.get("/local-runtime/local-mvp-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint_id"] == "local_mvp_readiness"
    assert payload["local_only_target"] is True
    assert payload["public_generation_disabled"] is True
    assert payload["live_execution_performed_by_endpoint"] is False
    assert payload["live_execution_approved_by_endpoint"] is False
    assert payload["local_operator_live_runs_allowed_by_endpoint"] is False
    assert payload["m5_post_production"]["ffmpeg_execution_endpoint_present"] is False
    assert payload["m5_post_production"]["recipe_command_routes_read_only"] is True

    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    readiness_methods = {
        method for method, path in method_paths if path == "/local-runtime/local-mvp-readiness"
    }

    assert readiness_methods == {"GET"}
    assert ("POST", "/local-runtime/local-mvp-readiness") not in method_paths
    assert not any(
        path.startswith("/local-runtime/local-mvp-readiness") and any(token in path for token in ("execute", "submit", "create"))
        for _method, path in method_paths
    )
