#!/usr/bin/env python
"""Validate CineForge's safe/local-only boundary without live probes.

This script is intentionally static/file-only. It does not import the FastAPI app,
contact ComfyUI, probe GPU/runtime health, run FFmpeg/ffprobe, submit prompts,
create jobs, render, benchmark, or execute media tools.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LIVE_FRONTEND_CALL_RE = re.compile(r"api\.(runtimeStatus|comfyHealth|gpuHealth|ffmpegHealth)\(")
RAW_PROMPT_ROUTE_RE = re.compile(
    r"@(router|app)\.(post|get|put|patch|delete)\(\s*['\"]/(prompt|api/prompt)['\"]"
)
FORBIDDEN_LOCAL_CHILD_RE = re.compile(
    r"local-(generation|operator)/.+(execute|submit|approve|prompt)|"
    r"local-(generation|operator)/(execute|submit|approve|prompt)|"
    r"local-runtime/checkpoint-watchdog(?:/[^'\"\s)]*)?/(execute|submit|approve|prompt|run)|"
    r"/local-operator/run(?=$|[^A-Za-z0-9_-])"
)
SAFE_ENDPOINT_ROW_RE = re.compile(r"^\| `(?P<path>/local-[^`]+)` \| (?P<methods>[A-Z/]+) \|")
ALLOWED_MUTATING_SAFE_ENDPOINTS = {
    "/local-jobs",
    "/local-generation/semantic-requests",
    "/local-generation/storyboard-handoffs",
    "/local-operator/packets",
    "/local-post-production/plans",
}


@dataclass(frozen=True)
class BoundaryFinding:
    code: str
    path: str
    detail: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_endpoint_methods(repo_root: Path) -> dict[str, set[str]]:
    matrix_path = repo_root / "docs" / "SAFE_LOCAL_ENDPOINTS.md"
    if not matrix_path.is_file():
        return {}
    methods: dict[str, set[str]] = {}
    for line in matrix_path.read_text(encoding="utf-8").splitlines():
        match = SAFE_ENDPOINT_ROW_RE.match(line)
        if match:
            methods[match.group("path")] = set(match.group("methods").split("/"))
    return methods


def _scan_text_files(root: Path, pattern: str, *, skip: set[Path] | None = None) -> list[Path]:
    if not root.exists():
        return []
    skip = skip or set()
    return [path for path in root.rglob(pattern) if path.is_file() and path not in skip]


def validate_boundary(repo_root: Path) -> list[BoundaryFinding]:
    repo_root = repo_root.resolve()
    findings: list[BoundaryFinding] = []

    archetype_path = repo_root / "storage" / "archetypes" / "catalog.json"
    preset_path = repo_root / "storage" / "presets" / "catalog.json"

    for endpoint, methods in _safe_endpoint_methods(repo_root).items():
        mutating_methods = methods - {"GET"}
        if mutating_methods and endpoint not in ALLOWED_MUTATING_SAFE_ENDPOINTS:
            findings.append(
                BoundaryFinding(
                    "unexpected_mutating_safe_endpoint_method",
                    "docs/SAFE_LOCAL_ENDPOINTS.md",
                    f"{endpoint} documents mutating method(s): {', '.join(sorted(mutating_methods))}",
                )
            )

    try:
        archetypes = _load_json(archetype_path).get("archetypes", [])
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        findings.append(BoundaryFinding("archetype_catalog_unreadable", str(archetype_path), str(exc)))
        archetypes = []
    for item in archetypes:
        if item.get("enabled") or item.get("readiness") == "ready":
            findings.append(
                BoundaryFinding(
                    "archetype_enabled_or_ready",
                    str(archetype_path),
                    f"{item.get('archetype_id')} enabled={item.get('enabled')} readiness={item.get('readiness')}",
                )
            )

    try:
        presets = _load_json(preset_path).get("presets", [])
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        findings.append(BoundaryFinding("preset_catalog_unreadable", str(preset_path), str(exc)))
        presets = []
    for item in presets:
        if item.get("enabled") or item.get("readiness") == "ready":
            findings.append(
                BoundaryFinding(
                    "preset_enabled_or_ready",
                    str(preset_path),
                    f"{item.get('preset_id')} enabled={item.get('enabled')} readiness={item.get('readiness')}",
                )
            )

    api_client = (repo_root / "frontend" / "src" / "api" / "client.ts").resolve()
    for path in _scan_text_files(repo_root / "frontend" / "src", "*.ts*"):
        if path.resolve() == api_client:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in LIVE_FRONTEND_CALL_RE.finditer(text):
            findings.append(BoundaryFinding("frontend_live_probe_callsite", str(path), match.group(0)))
        for match in FORBIDDEN_LOCAL_CHILD_RE.finditer(text):
            findings.append(BoundaryFinding("frontend_forbidden_local_child_route", str(path), match.group(0)))

    for path in _scan_text_files(repo_root / "backend" / "app", "*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in RAW_PROMPT_ROUTE_RE.finditer(text):
            findings.append(BoundaryFinding("raw_prompt_route", str(path), match.group(0)))
        for match in FORBIDDEN_LOCAL_CHILD_RE.finditer(text):
            findings.append(BoundaryFinding("backend_forbidden_local_child_route", str(path), match.group(0)))

    return findings


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    repo_root = Path(argv[0]) if argv else Path.cwd()
    findings = validate_boundary(repo_root)
    if findings:
        print("Safe/local boundary validation failed:")
        for finding in findings:
            print(f"- {finding.code}: {finding.path}: {finding.detail}")
        return 1
    print("Safe/local boundary validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
