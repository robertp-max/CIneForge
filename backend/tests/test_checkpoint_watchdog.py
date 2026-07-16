from __future__ import annotations

import json
from pathlib import Path

from scripts.checkpoint_watchdog import build_watchdog_report, format_watchdog_report, main


def test_runtime_ui_does_not_truncate_watchdog_invariants():
    runtime_page = Path("frontend/src/pages/Runtime.tsx").read_text(encoding="utf-8")

    assert "localCheckpointWatchdog?.invariants ?? []" in runtime_page
    assert "localCheckpointWatchdog.untracked_source_files" in runtime_page
    assert ".slice(0, 5).map((invariant)" not in runtime_page
    assert ".slice(0, 4).map((invariant)" not in runtime_page
    assert "A watchdog/status answer is not a stopping point" not in runtime_page  # UI must use API data, not hard-coded text.


def test_checkpoint_watchdog_docs_include_script_invariants():
    report = build_watchdog_report(Path.cwd())
    docs = Path("docs/CHECKPOINT_WATCHDOG.md").read_text(encoding="utf-8")

    for invariant in report.invariants:
        assert invariant in docs


def test_checkpoint_watchdog_report_contains_restart_reminder(monkeypatch, tmp_path: Path):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: example"
        if args == ["status", "--short", "--untracked-files=no"]:
            return ""
        if args == ["diff", "--cached", "--name-only"]:
            return ""
        if args == ["status", "--short", "--untracked-files=all"]:
            return ""
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    report = build_watchdog_report(tmp_path)
    rendered = format_watchdog_report(report)

    assert report.last_commit == "abc123 checkpoint: example"
    assert report.tracked_worktree_clean is True
    assert report.staged_files == ()
    assert report.untracked_source_files == ()
    assert "Staged files: 0" in rendered
    assert "Source-scoped untracked files: 0" in rendered
    assert "checkpoint loop must restart now" in report.reminder
    assert "After each commit, immediately continue" in rendered
    assert "A watchdog/status answer is not a stopping point" in rendered
    assert "Record validation truthfully" in rendered
    assert "staged contents intentionally match" in rendered
    assert "No FFmpeg/ffprobe execution" in rendered
    assert "public raw /prompt or /api/prompt" in rendered
    assert "No ComfyUI/GPU/render/benchmark" in rendered


def test_checkpoint_watchdog_text_mode_lists_staged_files(monkeypatch, tmp_path: Path):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: staged"
        if args == ["status", "--short", "--untracked-files=no"]:
            return "M  README.md"
        if args == ["diff", "--cached", "--name-only"]:
            return "README.md\nbackend/tests/test_checkpoint_watchdog.py\n"
        if args == ["status", "--short", "--untracked-files=all"]:
            return "M  README.md"
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    rendered = format_watchdog_report(build_watchdog_report(tmp_path))

    assert "Staged files: 2" in rendered
    assert "Staged file list:" in rendered
    assert "- README.md" in rendered
    assert "- backend/tests/test_checkpoint_watchdog.py" in rendered


def test_checkpoint_watchdog_reports_source_scoped_untracked_files(monkeypatch, tmp_path: Path):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: untracked"
        if args == ["status", "--short", "--untracked-files=no"]:
            return ""
        if args == ["diff", "--cached", "--name-only"]:
            return ""
        if args == ["status", "--short", "--untracked-files=all"]:
            return "?? docs/new.md\n?? requirements.txt\n?? config/local.ini\n?? artifacts/watchdog/latest.json\n?? scratch.tmp\n"
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    report = build_watchdog_report(tmp_path)
    rendered = format_watchdog_report(report)

    assert report.tracked_worktree_clean is True
    assert report.untracked_source_files == ("config/local.ini", "docs/new.md", "requirements.txt")
    assert "Source-scoped untracked files: 3" in rendered
    assert "Source-scoped untracked file list:" in rendered
    assert "- config/local.ini" in rendered
    assert "- docs/new.md" in rendered
    assert "- requirements.txt" in rendered
    assert "artifacts/watchdog/latest.json" not in rendered
    assert "scratch.tmp" not in rendered


def test_checkpoint_watchdog_json_mode(monkeypatch, tmp_path: Path, capsys):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: json"
        if args == ["status", "--short", "--untracked-files=no"]:
            return ""
        if args == ["diff", "--cached", "--name-only"]:
            return "backend/tests/test_checkpoint_watchdog.py\n"
        if args == ["status", "--short", "--untracked-files=all"]:
            return ""
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    assert main([str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["last_commit"] == "abc123 checkpoint: json"
    assert payload["tracked_worktree_clean"] is True
    assert payload["staged_files"] == ["backend/tests/test_checkpoint_watchdog.py"]
    assert payload["untracked_source_files"] == []
    assert any("No FFmpeg/ffprobe" in item for item in payload["invariants"])


def test_checkpoint_watchdog_json_fail_on_dirty_returns_nonzero(monkeypatch, tmp_path: Path, capsys):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: dirty-json"
        if args == ["status", "--short", "--untracked-files=no"]:
            return " M README.md"
        if args == ["diff", "--cached", "--name-only"]:
            return "README.md\n"
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    assert main([str(tmp_path), "--json", "--fail-on-dirty"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["tracked_worktree_clean"] is False
    assert payload["staged_files"] == ["README.md"]


def test_checkpoint_watchdog_fail_on_dirty_returns_nonzero_for_untracked_source(monkeypatch, tmp_path: Path, capsys):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: untracked-dirty"
        if args == ["status", "--short", "--untracked-files=no"]:
            return ""
        if args == ["diff", "--cached", "--name-only"]:
            return ""
        if args == ["status", "--short", "--untracked-files=all"]:
            return "?? docs/new.md\n"
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    assert main([str(tmp_path), "--fail-on-dirty"]) == 2
    output = capsys.readouterr().out
    assert "Tracked worktree clean: True" in output
    assert "Source-scoped untracked files: 1" in output


def test_checkpoint_watchdog_fail_on_dirty_returns_nonzero(monkeypatch, tmp_path: Path, capsys):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: dirty"
        if args == ["status", "--short", "--untracked-files=no"]:
            return " M README.md"
        if args == ["diff", "--cached", "--name-only"]:
            return ""
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    assert main([str(tmp_path), "--fail-on-dirty"]) == 2
    assert "Tracked worktree clean: False" in capsys.readouterr().out


def test_checkpoint_watchdog_reports_dirty_tracked_worktree(monkeypatch, tmp_path: Path):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: example"
        if args == ["status", "--short", "--untracked-files=no"]:
            return " M README.md"
        if args == ["diff", "--cached", "--name-only"]:
            return "README.md\n"
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    report = build_watchdog_report(tmp_path)

    assert report.tracked_worktree_clean is False
    assert report.staged_files == ("README.md",)
