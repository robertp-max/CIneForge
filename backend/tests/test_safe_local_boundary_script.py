from __future__ import annotations

from pathlib import Path

from scripts.validate_safe_local_boundary import BoundaryFinding, validate_boundary


def test_safe_local_boundary_validator_passes_current_repository():
    findings = validate_boundary(Path.cwd())

    assert findings == []


def test_safe_local_boundary_validator_detects_unexpected_mutating_safe_endpoint_method(tmp_path: Path):
    repo = tmp_path
    (repo / "docs").mkdir(parents=True)
    (repo / "storage" / "archetypes").mkdir(parents=True)
    (repo / "storage" / "presets").mkdir(parents=True)
    (repo / "frontend" / "src" / "api").mkdir(parents=True)
    (repo / "backend" / "app").mkdir(parents=True)
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "storage" / "archetypes" / "catalog.json").write_text('{"archetypes":[]}', encoding="utf-8")
    (repo / "storage" / "presets" / "catalog.json").write_text('{"presets":[]}', encoding="utf-8")
    (repo / "docs" / "SAFE_LOCAL_ENDPOINTS.md").write_text(
        "| Endpoint | Method(s) | Purpose | Executes live tools? | Records approval? | Starts generation/media work? |\n"
        "|---|---:|---|---:|---:|---:|\n"
        "| `/local-runtime/catalog` | GET/POST | bad | No | No | No |\n",
        encoding="utf-8",
    )
    (repo / ".github" / "workflows" / "test.yml").write_text(
        "steps:\n  - run: curl http://127.0.0.1:8000/health/gpu\n",
        encoding="utf-8",
    )

    findings = validate_boundary(repo)

    assert any(finding.code == "unexpected_mutating_safe_endpoint_method" for finding in findings)
    assert any(finding.code == "github_workflow_live_fragment" and "/health/gpu" in finding.detail for finding in findings)


def test_safe_local_boundary_validator_detects_enabled_catalog_and_live_call(tmp_path: Path):
    repo = tmp_path
    (repo / "storage" / "archetypes").mkdir(parents=True)
    (repo / "storage" / "presets").mkdir(parents=True)
    (repo / "frontend" / "src" / "pages").mkdir(parents=True)
    (repo / "frontend" / "src" / "api").mkdir(parents=True)
    (repo / "backend" / "app" / "api").mkdir(parents=True)

    (repo / "storage" / "archetypes" / "catalog.json").write_text(
        '{"archetypes":[{"archetype_id":"CF-VID-X","enabled":true,"readiness":"ready"}]}',
        encoding="utf-8",
    )
    (repo / "storage" / "presets" / "catalog.json").write_text(
        '{"presets":[{"preset_id":"CF-PRESET-X","enabled":false,"readiness":"blocked"}]}',
        encoding="utf-8",
    )
    (repo / "frontend" / "src" / "api" / "client.ts").write_text(
        "export const api = { runtimeStatus: () => null }",
        encoding="utf-8",
    )
    (repo / "frontend" / "src" / "pages" / "Runtime.tsx").write_text(
        "api.runtimeStatus(); fetch('/api/prompt'); fetch('/local-operator/run'); fetch('/local-runtime/checkpoint-watchdog/execute')",
        encoding="utf-8",
    )
    (repo / "backend" / "app" / "routes.py").write_text(
        '@router.post("/prompt")\ndef prompt(): pass',
        encoding="utf-8",
    )

    findings = validate_boundary(repo)
    codes = {finding.code for finding in findings}

    assert "archetype_enabled_or_ready" in codes
    assert "frontend_live_probe_callsite" in codes
    assert "frontend_forbidden_local_child_route" in codes
    assert "frontend_raw_prompt_reference" in codes
    assert any(
        finding.code == "frontend_forbidden_local_child_route"
        and "checkpoint-watchdog/execute" in finding.detail
        for finding in findings
    )
    assert any(finding.code == "frontend_raw_prompt_reference" and "/api/prompt" in finding.detail for finding in findings)
    assert "raw_prompt_route" in codes
    assert all(isinstance(finding, BoundaryFinding) for finding in findings)
