from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .policy import build_child_environment


@dataclass(frozen=True, slots=True)
class TestResult:
    test_id: str
    exit_code: int
    stdout: str
    stderr: str


TEST_CATALOG: dict[str, tuple[str, ...]] = {
    "orchestrator": ("-m", "pytest", "backend/tests/test_headless_orchestrator.py", "-q"),
    "storyboard-targeted": (
        "-m",
        "pytest",
        "backend/tests/test_storyboard_routes.py",
        "backend/tests/test_ai_proposal_validator.py",
        "backend/tests/test_db_schema.py",
        "-q",
    ),
    "schema-lane": (
        "-m",
        "pytest",
        "backend/tests/test_db_schema.py",
        "backend/tests/test_storyboard_phase1_schema.py",
        "backend/tests/test_storyboard_phase1_migration.py",
        "-q",
    ),
}


def run_fixed_tests(worktree: Path, test_ids: tuple[str, ...]) -> list[TestResult]:
    results: list[TestResult] = []
    environment = build_child_environment()
    environment.pop("CINEFORGE_TEST_POSTGRES_URL", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for test_id in test_ids:
        command = TEST_CATALOG.get(test_id)
        if command is None:
            raise ValueError(f"unknown controller test ID: {test_id}")
        completed = subprocess.run(
            [sys.executable, *command],
            cwd=worktree,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        result = TestResult(test_id, completed.returncode, completed.stdout, completed.stderr)
        results.append(result)
    return results
