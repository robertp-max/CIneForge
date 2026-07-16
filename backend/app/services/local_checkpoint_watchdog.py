"""Read-only checkpoint watchdog report service."""

from __future__ import annotations

from pathlib import Path

from backend.app.schemas.local_checkpoint_watchdog import LocalCheckpointWatchdogReport
from scripts.checkpoint_watchdog import build_watchdog_report


class LocalCheckpointWatchdogService:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[3]).resolve()

    def report(self) -> LocalCheckpointWatchdogReport:
        report = build_watchdog_report(self.repo_root)
        return LocalCheckpointWatchdogReport(
            last_commit=report.last_commit,
            tracked_worktree_clean=report.tracked_worktree_clean,
            reminder=report.reminder,
            invariants=list(report.invariants),
        )
