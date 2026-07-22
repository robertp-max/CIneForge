from __future__ import annotations

from pathlib import Path
import re

from fastapi.routing import APIRoute

from backend.app.main import app


REQUIRED_DOCUMENTED_ENDPOINTS = {
    "/local-runtime/catalog",
    "/local-runtime/live-status",
    "/local-runtime/output-policy",
    "/local-runtime/evidence",
    "/local-runtime/evidence/cf-vid-01-smoke",
    "/local-runtime/m4-preflight",
    "/local-runtime/m4-ladder",
    "/local-runtime/local-mvp-readiness",
    "/local-runtime/public-readiness",
    "/local-runtime/safe-boundary",
    "/local-runtime/checkpoint-watchdog",
    "/local-runtime/ffmpeg-recipes",
    "/local-archetypes/catalog",
    "/local-archetypes",
    "/local-archetypes/{archetype_id}",
    "/local-archetypes/readiness",
    "/local-archetypes/{archetype_id}/readiness",
    "/local-presets/catalog",
    "/local-presets",
    "/local-presets/{preset_id}",
    "/local-presets/readiness",
    "/local-presets/{preset_id}/readiness",
    "/local-jobs",
    "/local-jobs/{job_id}",
    "/local-generation/semantic-requests",
    "/local-generation/semantic-requests/{request_id}",
    "/local-generation/storyboard-handoffs",
    "/local-operator/approval-templates",
    "/local-operator/approval-templates/{mode}",
    "/local-operator/runbooks",
    "/local-operator/runbooks/{mode}",
    "/local-operator/packets",
    "/local-operator/packets/{packet_id}",
    "/local-post-production/plans",
    "/local-post-production/plans/{plan_id}",
    "/local-post-production/recipe-commands",
    "/local-post-production/recipe-commands/{plan_id}",
}


MATRIX_ROW_RE = re.compile(r"^\| `(?P<path>/local-[^`]+)` \| (?P<methods>[A-Z/]+) \|")
SAFE_MATRIX_ROW_RE = re.compile(
    r"^\| `(?P<path>/local-[^`]+)` \| (?P<methods>[A-Z/]+) \| (?P<purpose>[^|]+) \| (?P<executes>Yes|No) \| (?P<approves>Yes|No) \| (?P<starts>Yes|No) \|"
)


FORBIDDEN_LOCAL_EXECUTION_SEGMENTS = {"execute", "submit", "approve", "prompt", "run"}


FORBIDDEN_ALLOWED_TABLE_ROWS = (
    "| `/local-operator/run` |",
    "| `/local-operator/execute` |",
    "| `/local-operator/submit` |",
    "| `/local-operator/approve` |",
    "| `/local-generation/execute` |",
    "| `/local-generation/submit` |",
    "| `/local-generation/approve` |",
    "| `/local-post-production/execute` |",
    "| `/local-post-production/plans/{plan_id}/execute` |",
    "| `/local-runtime/ffmpeg-recipes/execute` |",
    "| `/local-runtime/checkpoint-watchdog/execute` |",
    "| `/prompt` |",
    "| `/api/prompt` |",
)


def _matrix_methods(matrix: str) -> dict[str, set[str]]:
    rows: dict[str, set[str]] = {}
    for line in matrix.splitlines():
        match = MATRIX_ROW_RE.match(line)
        if not match:
            continue
        rows[match.group("path")] = set(match.group("methods").split("/"))
    return rows


def _app_methods() -> dict[str, set[str]]:
    methods: dict[str, set[str]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods.setdefault(route.path, set()).update(set(route.methods or set()) - {"HEAD", "OPTIONS"})
    return methods


def test_safe_local_endpoint_matrix_documents_current_safe_routes():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")
    route_paths = set(_app_methods())
    documented_paths = set(_matrix_methods(matrix))

    missing_from_docs = [endpoint for endpoint in sorted(REQUIRED_DOCUMENTED_ENDPOINTS) if endpoint not in documented_paths]
    missing_from_app = [endpoint for endpoint in sorted(REQUIRED_DOCUMENTED_ENDPOINTS) if endpoint not in route_paths]

    assert missing_from_docs == []
    assert missing_from_app == []


def test_safe_local_endpoint_matrix_has_no_extra_documented_local_routes():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")
    route_paths = set(_app_methods())
    documented_paths = set(_matrix_methods(matrix))

    extra_documented_paths = [path for path in sorted(documented_paths) if path not in route_paths]

    assert extra_documented_paths == []


def test_safe_local_endpoint_matrix_methods_match_app_routes():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")
    documented_methods = _matrix_methods(matrix)
    app_methods = _app_methods()

    mismatches = {
        path: {"docs": sorted(documented_methods[path]), "app": sorted(app_methods[path])}
        for path in sorted(REQUIRED_DOCUMENTED_ENDPOINTS)
        if documented_methods[path] != app_methods[path]
    }

    assert mismatches == {}


def test_safe_local_endpoint_matrix_does_not_document_live_execution_as_allowed():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")

    assert "Executes live tools? | Records approval? | Starts generation/media work?" in matrix
    assert "any `/local-*` route with an exact `/execute`, `/submit`, `/run`, `/approve`, or `/prompt` child segment" in matrix
    assert "/local-operator/runbooks` remains allowed reference metadata" in matrix
    for forbidden in FORBIDDEN_ALLOWED_TABLE_ROWS:
        assert forbidden not in matrix


def test_safe_local_endpoint_matrix_rows_remain_non_executing_non_approving():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")
    rows = [match.groupdict() for line in matrix.splitlines() if (match := SAFE_MATRIX_ROW_RE.match(line))]

    assert rows
    assert all(row["executes"] == "No" for row in rows)
    assert all(row["approves"] == "No" for row in rows)
    assert all(row["starts"] == "No" for row in rows)


def test_app_has_no_local_execution_child_routes():
    offenders = []
    for path in _app_methods():
        if not path.startswith("/local-"):
            continue
        segments = {segment for segment in path.split("/") if segment}
        if segments & FORBIDDEN_LOCAL_EXECUTION_SEGMENTS:
            offenders.append(path)

    assert offenders == []
