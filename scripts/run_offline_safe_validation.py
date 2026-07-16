#!/usr/bin/env python
"""Run CineForge's offline-safe validation suite.

This runner intentionally executes only static checks, unit tests, and frontend
lint/build. It does not run FFmpeg/ffprobe, contact ComfyUI, probe GPU/runtime
health, submit prompts, create jobs, render media, benchmark, or enable public
generation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.checkpoint_watchdog import build_watchdog_report

BACKEND_TESTS = [
    "backend/tests/test_safe_local_boundary_script.py",
    "backend/tests/test_checkpoint_watchdog.py",
    "backend/tests/test_offline_safe_validation_runner.py",
    "backend/tests/test_local_safe_boundary.py",
    "backend/tests/test_local_checkpoint_watchdog.py",
    "backend/tests/test_safe_local_endpoint_docs.py",
    "backend/tests/test_offline_docs_boundary.py",
    "backend/tests/test_local_archetypes.py",
    "backend/tests/test_local_presets.py",
    "backend/tests/test_local_jobs.py",
    "backend/tests/test_local_generation.py",
    "backend/tests/test_local_readiness.py",
    "backend/tests/test_local_mvp_readiness.py",
    "backend/tests/test_local_public_readiness.py",
    "backend/tests/test_local_operator.py",
    "backend/tests/test_local_runtime.py",
    "backend/tests/test_local_runtime_m4.py",
    "backend/tests/test_local_runtime_evidence.py",
    "backend/tests/test_gpu_telemetry_parser.py",
    "backend/tests/test_path_safety.py",
    "backend/tests/test_output_collector.py",
    "backend/tests/test_runtime_catalog.py",
    "backend/tests/test_benchmark_ladder.py",
    "backend/tests/test_cf_vid01_api_workflow_template.py",
    "backend/tests/test_object_info_cache.py",
    "backend/tests/test_ffmpeg_service.py",
    "backend/tests/test_post_production.py",
    "backend/tests/test_local_post_production.py",
    "backend/tests/test_phase1_app_routing.py",
    "backend/tests/test_queue_state_machine.py",
    "backend/tests/test_production_gates.py",
    "backend/tests/test_workflow_admission.py",
    "backend/tests/test_storyboard_approval.py",
    "backend/tests/test_workflow_manifest_validation.py",
    "backend/tests/test_workflow_registry_and_compiler.py",
]


def _python_executable(repo_root: Path) -> str:
    windows_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if windows_python.is_file():
        return str(windows_python)
    posix_python = repo_root / ".venv" / "bin" / "python"
    if posix_python.is_file():
        return str(posix_python)
    return sys.executable


def _npm_executable() -> str:
    return shutil.which("npm") or shutil.which("npm.cmd") or "npm.cmd"


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("\n$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def run_validation(
    repo_root: Path,
    *,
    skip_frontend: bool = False,
    watchdog_json: Path | None = None,
    fail_on_dirty: bool = False,
) -> None:
    repo_root = repo_root.resolve()
    python = _python_executable(repo_root)
    env = os.environ.copy()
    env.pop("CINEFORGE_TEST_POSTGRES_URL", None)

    _run([python, "-B", "scripts/validate_safe_local_boundary.py"], cwd=repo_root, env=env)
    _run([python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *BACKEND_TESTS], cwd=repo_root, env=env)

    if not skip_frontend:
        npm = _npm_executable()
        _run([npm, "run", "lint"], cwd=repo_root / "frontend", env=env)
        _run([npm, "run", "build"], cwd=repo_root / "frontend", env=env)

    _run(["git", "diff", "--check"], cwd=repo_root, env=env)
    watchdog_command = [python, "-B", "scripts/checkpoint_watchdog.py"]
    if fail_on_dirty:
        watchdog_command.append("--fail-on-dirty")
    _run(watchdog_command, cwd=repo_root, env=env)
    if watchdog_json is not None:
        watchdog_json_path = watchdog_json if watchdog_json.is_absolute() else repo_root / watchdog_json
        watchdog_json_path.parent.mkdir(parents=True, exist_ok=True)
        watchdog_json_path.write_text(
            json.dumps(asdict(build_watchdog_report(repo_root)), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote checkpoint watchdog JSON: {watchdog_json_path}", flush=True)
    print("\nOffline-safe validation passed.", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CineForge offline-safe validation.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--skip-frontend", action="store_true", help="Skip npm lint/build.")
    parser.add_argument("--watchdog-json", type=Path, default=None, help="Optional path for machine-readable watchdog output.")
    parser.add_argument("--fail-on-dirty", action="store_true", help="Exit nonzero if tracked files are dirty after validation.")
    args = parser.parse_args(argv)
    run_validation(
        args.repo_root,
        skip_frontend=args.skip_frontend,
        watchdog_json=args.watchdog_json,
        fail_on_dirty=args.fail_on_dirty,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
