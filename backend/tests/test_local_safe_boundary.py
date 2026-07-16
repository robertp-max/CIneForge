from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.local_safe_boundary import LocalSafeBoundaryService


def test_local_safe_boundary_service_passes_current_repository():
    report = LocalSafeBoundaryService(Path.cwd()).report()

    assert report.checkpoint_id == "local_safe_boundary"
    assert report.passed is True
    assert report.finding_count == 0
    assert report.findings == []
    assert report.live_execution_performed_by_endpoint is False
    assert report.live_execution_approved_by_endpoint is False
    assert report.public_generation_enabled is False


def test_local_safe_boundary_service_returns_relative_findings(tmp_path: Path):
    (tmp_path / "storage" / "archetypes").mkdir(parents=True)
    (tmp_path / "storage" / "presets").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "api").mkdir(parents=True)
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "storage" / "archetypes" / "catalog.json").write_text(
        '{"archetypes":[{"archetype_id":"CF-X","enabled":true,"readiness":"blocked"}]}',
        encoding="utf-8",
    )
    (tmp_path / "storage" / "presets" / "catalog.json").write_text('{"presets":[]}', encoding="utf-8")
    (tmp_path / "frontend" / "src" / "api" / "client.ts").write_text("", encoding="utf-8")

    report = LocalSafeBoundaryService(tmp_path).report()

    assert report.passed is False
    assert report.finding_count == 1
    assert report.findings[0].code == "archetype_enabled_or_ready"
    assert report.findings[0].path == "storage/archetypes/catalog.json"


def test_local_safe_boundary_route_is_get_only_and_non_executing():
    client = TestClient(app)

    response = client.get("/local-runtime/safe-boundary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint_id"] == "local_safe_boundary"
    assert payload["passed"] is True
    assert payload["finding_count"] == 0
    assert payload["live_execution_performed_by_endpoint"] is False
    assert payload["live_execution_approved_by_endpoint"] is False
    assert payload["public_generation_enabled"] is False

    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert {method for method, path in method_paths if path == "/local-runtime/safe-boundary"} == {"GET"}
    assert ("POST", "/local-runtime/safe-boundary") not in method_paths
    assert not any(
        path.startswith("/local-runtime/safe-boundary/")
        and any(child in path for child in ("execute", "submit", "approve", "prompt", "run"))
        for _method, path in method_paths
    )
