from __future__ import annotations

import json
from pathlib import Path

from scripts.checkpoint_watchdog import CheckpointWatchdogReport
from scripts.run_offline_safe_validation import BACKEND_TESTS, run_validation


def test_offline_safe_validation_runner_includes_path_output_runtime_catalog_and_cf_vid01_contract_tests():
    assert "backend/tests/test_path_safety.py" in BACKEND_TESTS
    assert "backend/tests/test_output_collector.py" in BACKEND_TESTS
    assert "backend/tests/test_runtime_catalog.py" in BACKEND_TESTS
    assert "backend/tests/test_cf_vid01_api_workflow_template.py" in BACKEND_TESTS
    assert "backend/tests/test_object_info_cache.py" in BACKEND_TESTS
    assert "backend/tests/test_workflow_manifest_validation.py" in BACKEND_TESTS


def test_github_actions_uses_watchdog_json_output():
    workflow = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

    assert "python scripts/run_offline_safe_validation.py --watchdog-json artifacts/watchdog/ci.json --fail-on-dirty" in workflow


def test_github_actions_stays_on_offline_safe_runner_only():
    workflow = Path(".github/workflows/test.yml").read_text(encoding="utf-8")
    forbidden_live_fragments = [
        "/runtime/status",
        "/health/comfy",
        "/health/gpu",
        "/health/ffmpeg",
        "ffmpeg ",
        "ffprobe ",
        "comfyui",
        "/prompt",
        "benchmark",
        "render",
    ]

    assert "Run offline-safe validation" in workflow
    for fragment in forbidden_live_fragments:
        assert fragment not in workflow.lower()


def test_offline_safe_validation_runner_invokes_static_backend_frontend_and_diff(monkeypatch, tmp_path: Path):
    repo = tmp_path
    (repo / ".venv" / "Scripts").mkdir(parents=True)
    (repo / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    (repo / "frontend").mkdir()
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run(command, *, cwd, env=None, check=False):
        calls.append((tuple(command), Path(cwd)))
        assert check is True
        assert env is not None
        assert "CINEFORGE_TEST_POSTGRES_URL" not in env

    monkeypatch.setattr("scripts.run_offline_safe_validation.subprocess.run", fake_run)
    monkeypatch.setattr("scripts.run_offline_safe_validation._npm_executable", lambda: "npm-test")

    run_validation(repo)

    commands = [command for command, _cwd in calls]
    assert commands[0][1:] == ("-B", "scripts/validate_safe_local_boundary.py")
    assert commands[1][1:6] == ("-B", "-m", "pytest", "-q", "-p")
    assert all(test in commands[1] for test in BACKEND_TESTS)
    assert commands[2] == ("npm-test", "run", "lint")
    assert commands[3] == ("npm-test", "run", "build")
    assert commands[4] == ("git", "diff", "--check")
    assert commands[5][1:] == ("-B", "scripts/checkpoint_watchdog.py")
    assert calls[2][1] == repo / "frontend"
    assert calls[3][1] == repo / "frontend"


def test_offline_safe_validation_runner_can_forward_fail_on_dirty(monkeypatch, tmp_path: Path):
    repo = tmp_path
    (repo / "frontend").mkdir()
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, cwd, env=None, check=False):
        calls.append(tuple(command))

    monkeypatch.setattr("scripts.run_offline_safe_validation.subprocess.run", fake_run)

    run_validation(repo, skip_frontend=True, fail_on_dirty=True)

    assert calls[-2] == ("git", "diff", "--check")
    assert calls[-1][1:] == ("-B", "scripts/checkpoint_watchdog.py", "--fail-on-dirty")


def test_offline_safe_validation_runner_can_write_watchdog_json(monkeypatch, tmp_path: Path):
    repo = tmp_path
    (repo / "frontend").mkdir()
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, cwd, env=None, check=False):
        calls.append(tuple(command))

    def fake_build_watchdog_report(_repo_root: Path) -> CheckpointWatchdogReport:
        return CheckpointWatchdogReport(
            last_commit="abc123 checkpoint: json-artifact",
            tracked_worktree_clean=True,
            staged_files=("scripts/run_offline_safe_validation.py",),
            untracked_source_files=("docs/new.md",),
            reminder="WATCHDOG: checkpoint loop must restart now.",
            invariants=("No FFmpeg/ffprobe execution without explicit scoped live approval.",),
        )

    monkeypatch.setattr("scripts.run_offline_safe_validation.subprocess.run", fake_run)
    monkeypatch.setattr("scripts.run_offline_safe_validation.build_watchdog_report", fake_build_watchdog_report)

    run_validation(repo, skip_frontend=True, watchdog_json=Path("artifacts/watchdog/report.json"))

    payload = json.loads((repo / "artifacts" / "watchdog" / "report.json").read_text(encoding="utf-8"))
    assert payload["last_commit"] == "abc123 checkpoint: json-artifact"
    assert payload["tracked_worktree_clean"] is True
    assert payload["staged_files"] == ["scripts/run_offline_safe_validation.py"]
    assert payload["untracked_source_files"] == ["docs/new.md"]
    assert any("No FFmpeg/ffprobe" in item for item in payload["invariants"])
    assert calls[-2] == ("git", "diff", "--check")
    assert calls[-1][1:] == ("-B", "scripts/checkpoint_watchdog.py")


def test_offline_safe_validation_runner_can_skip_frontend(monkeypatch, tmp_path: Path):
    repo = tmp_path
    (repo / "frontend").mkdir()
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, cwd, env=None, check=False):
        calls.append(tuple(command))

    monkeypatch.setattr("scripts.run_offline_safe_validation.subprocess.run", fake_run)

    run_validation(repo, skip_frontend=True)

    assert all(command[0] != "npm" for command in calls)
    assert calls[-2] == ("git", "diff", "--check")
    assert calls[-1][1:] == ("-B", "scripts/checkpoint_watchdog.py")
