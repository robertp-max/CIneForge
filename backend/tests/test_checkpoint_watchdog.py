from __future__ import annotations

from pathlib import Path

from scripts.checkpoint_watchdog import build_watchdog_report, format_watchdog_report


def test_checkpoint_watchdog_report_contains_restart_reminder(monkeypatch, tmp_path: Path):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: example"
        if args == ["status", "--short", "--untracked-files=no"]:
            return ""
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    report = build_watchdog_report(tmp_path)
    rendered = format_watchdog_report(report)

    assert report.last_commit == "abc123 checkpoint: example"
    assert report.tracked_worktree_clean is True
    assert "checkpoint loop must restart now" in report.reminder
    assert "After each commit, immediately continue" in rendered
    assert "Record validation truthfully" in rendered
    assert "staged contents intentionally match" in rendered
    assert "No FFmpeg/ffprobe execution" in rendered
    assert "No ComfyUI/GPU/render/benchmark" in rendered


def test_checkpoint_watchdog_reports_dirty_tracked_worktree(monkeypatch, tmp_path: Path):
    def fake_run_git(_repo_root: Path, args: list[str]) -> str:
        if args == ["log", "--oneline", "-1"]:
            return "abc123 checkpoint: example"
        if args == ["status", "--short", "--untracked-files=no"]:
            return " M README.md"
        return "unexpected"

    monkeypatch.setattr("scripts.checkpoint_watchdog._run_git", fake_run_git)

    report = build_watchdog_report(tmp_path)

    assert report.tracked_worktree_clean is False
