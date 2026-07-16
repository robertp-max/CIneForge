from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute

from backend.app.main import app


REQUIRED_DOCUMENTED_ENDPOINTS = {
    "/local-runtime/catalog",
    "/local-runtime/output-policy",
    "/local-runtime/evidence",
    "/local-runtime/evidence/cf-vid-01-smoke",
    "/local-runtime/m4-preflight",
    "/local-runtime/m4-ladder",
    "/local-runtime/local-mvp-readiness",
    "/local-runtime/public-readiness",
    "/local-runtime/safe-boundary",
    "/local-runtime/ffmpeg-recipes",
    "/local-archetypes/readiness",
    "/local-presets/readiness",
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


FORBIDDEN_ALLOWED_TABLE_ROWS = (
    "| `/local-operator/run` |",
    "| `/local-operator/execute` |",
    "| `/local-operator/submit` |",
    "| `/local-operator/approve` |",
    "| `/local-generation/execute` |",
    "| `/local-generation/submit` |",
    "| `/local-generation/approve` |",
    "| `/prompt` |",
)


def test_safe_local_endpoint_matrix_documents_current_safe_routes():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")
    route_paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    missing_from_docs = [endpoint for endpoint in sorted(REQUIRED_DOCUMENTED_ENDPOINTS) if f"`{endpoint}`" not in matrix]
    missing_from_app = [endpoint for endpoint in sorted(REQUIRED_DOCUMENTED_ENDPOINTS) if endpoint not in route_paths]

    assert missing_from_docs == []
    assert missing_from_app == []


def test_safe_local_endpoint_matrix_does_not_document_live_execution_as_allowed():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")

    assert "Executes live tools? | Records approval? | Starts generation/media work?" in matrix
    for forbidden in FORBIDDEN_ALLOWED_TABLE_ROWS:
        assert forbidden not in matrix
