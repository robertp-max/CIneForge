#!/usr/bin/env python
"""Run CineForge's offline-safe validation suite.

This runner intentionally executes only static checks, unit tests, and frontend
lint/build. It does not run FFmpeg/ffprobe, contact ComfyUI, probe GPU/runtime
health, submit prompts, create jobs, render media, benchmark, or enable public
generation.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_TESTS = [
    "backend/tests/test_safe_local_boundary_script.py",
    "backend/tests/test_offline_safe_validation_runner.py",
    "backend/tests/test_local_safe_boundary.py",
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
    "backend/tests/test_benchmark_ladder.py",
    "backend/tests/test_ffmpeg_service.py",
    "backend/tests/test_post_production.py",
    "backend/tests/test_local_post_production.py",
    "backend/tests/test_phase1_app_routing.py",
    "backend/tests/test_production_gates.py",
    "backend/tests/test_workflow_admission.py",
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


def run_validation(repo_root: Path, *, skip_frontend: bool = False) -> None:
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
    print("\nOffline-safe validation passed.", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CineForge offline-safe validation.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--skip-frontend", action="store_true", help="Skip npm lint/build.")
    args = parser.parse_args(argv)
    run_validation(args.repo_root, skip_frontend=args.skip_frontend)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
