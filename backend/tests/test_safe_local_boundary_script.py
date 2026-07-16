from __future__ import annotations

from pathlib import Path

from scripts.validate_safe_local_boundary import BoundaryFinding, validate_boundary


def test_safe_local_boundary_validator_passes_current_repository():
    findings = validate_boundary(Path.cwd())

    assert findings == []


def test_safe_local_boundary_validator_detects_assistant_analysis_leak(tmp_path: Path):
    repo = tmp_path
    (repo / "docs").mkdir(parents=True)
    (repo / "artifacts").mkdir(parents=True)
    (repo / "storage" / "archetypes").mkdir(parents=True)
    (repo / "storage" / "presets").mkdir(parents=True)
    (repo / "frontend" / "src" / "api").mkdir(parents=True)
    (repo / "backend" / "app").mkdir(parents=True)
    (repo / "storage" / "archetypes" / "catalog.json").write_text('{"archetypes":[]}', encoding="utf-8")
    (repo / "storage" / "presets" / "catalog.json").write_text('{"presets":[]}', encoding="utf-8")
    leak_phrase = "Wait " + "JSON malformed"
    (repo / "docs" / "LEAK.md").write_text(f"{leak_phrase} should never be committed.", encoding="utf-8")
    (repo / "artifacts" / "LEAK.md").write_text(f"{leak_phrase} should never be committed as an artifact.", encoding="utf-8")
    (repo / "frontend" / "src" / "api" / "client.ts").write_text("", encoding="utf-8")

    findings = validate_boundary(repo)

    assert any(finding.code == "assistant_analysis_leak" and leak_phrase in finding.detail for finding in findings)
    assert any(finding.code == "assistant_analysis_leak" and "artifacts" in finding.path for finding in findings)


def test_safe_local_boundary_validator_detects_unexpected_mutating_safe_endpoint_method(tmp_path: Path):
    repo = tmp_path
    (repo / "docs").mkdir(parents=True)
    (repo / "storage" / "archetypes").mkdir(parents=True)
    (repo / "storage" / "presets").mkdir(parents=True)
    (repo / "frontend" / "src" / "api").mkdir(parents=True)
    (repo / "backend" / "app").mkdir(parents=True)
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "frontend" / "package.json").write_text(
        '{"scripts":{"bad":"ffmpeg -version"}}',
        encoding="utf-8",
    )
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
    assert any(finding.code == "package_script_live_fragment" and "ffmpeg" in finding.detail for finding in findings)


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
        "export const api = { runtimeStatus: () => null, rawPrompt: () => fetch('/prompt') }",
        encoding="utf-8",
    )
    (repo / "frontend" / "src" / "pages" / "Runtime.tsx").write_text(
        "api.runtimeStatus(); fetch(`/health/gpu`); fetch(`/api/prompt`); fetch('/local-operator/run'); fetch('/local-runtime/checkpoint-watchdog/execute'); fetch('/local-post-production/plans/abc/execute'); fetch('/local-runtime/ffmpeg-recipes/execute')",
        encoding="utf-8",
    )
    (repo / "backend" / "app" / "routes.py").write_text(
        '@router.post("/prompt")\ndef prompt(): pass\n@router.post("/local-post-production/plans/{plan_id}/execute")\ndef execute_plan(): pass',
        encoding="utf-8",
    )

    findings = validate_boundary(repo)
    codes = {finding.code for finding in findings}

    assert "archetype_enabled_or_ready" in codes
    assert "frontend_live_probe_callsite" in codes
    assert "frontend_live_probe_fetch" in codes
    assert "frontend_forbidden_local_child_route" in codes
    assert "frontend_raw_prompt_reference" in codes
    assert any(
        finding.code == "frontend_forbidden_local_child_route"
        and "checkpoint-watchdog/execute" in finding.detail
        for finding in findings
    )
    assert any(
        finding.code == "frontend_forbidden_local_child_route"
        and "local-post-production/plans/abc/execute" in finding.detail
        for finding in findings
    )
    assert any(
        finding.code == "frontend_forbidden_local_child_route"
        and "local-runtime/ffmpeg-recipes/execute" in finding.detail
        for finding in findings
    )
    assert any(finding.code == "frontend_live_probe_fetch" and "/health/gpu" in finding.detail for finding in findings)
    assert any(finding.code == "frontend_raw_prompt_reference" and "/api/prompt" in finding.detail for finding in findings)
    assert any(
        finding.code == "frontend_raw_prompt_reference"
        and "client.ts" in finding.path
        and "/prompt" in finding.detail
        for finding in findings
    )
    assert "raw_prompt_route" in codes
    assert any(
        finding.code == "backend_forbidden_local_child_route"
        and "local-post-production/plans/{plan_id}/execute" in finding.detail
        for finding in findings
    )
    assert all(isinstance(finding, BoundaryFinding) for finding in findings)
