#!/usr/bin/env python
"""Print the CineForge checkpoint continuation watchdog banner.

This is a no-live, no-side-effect helper. It reads git metadata only and reminds
the operator/agent to restart the offline-safe continuation loop after each
checkpoint commit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckpointWatchdogReport:
    last_commit: str
    tracked_worktree_clean: bool
    reminder: str
    invariants: tuple[str, ...]


def _run_git(repo_root: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=repo_root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unavailable"


def build_watchdog_report(repo_root: Path) -> CheckpointWatchdogReport:
    repo_root = repo_root.resolve()
    last_commit = _run_git(repo_root, ["log", "--oneline", "-1"])
    status = _run_git(repo_root, ["status", "--short", "--untracked-files=no"])
    tracked_clean = status == ""
    return CheckpointWatchdogReport(
        last_commit=last_commit,
        tracked_worktree_clean=tracked_clean,
        reminder=(
            "WATCHDOG: checkpoint loop must restart now. Pick the next offline-safe hardening/documentation/test gap, "
            "implement it, run the curated offline-safe validation when appropriate, commit the checkpoint, then restart again. "
            "Do not stop for status chatter."
        ),
        invariants=(
            "No FFmpeg/ffprobe execution without explicit scoped live approval.",
            "No ComfyUI/GPU/render/benchmark/runtime-health probe without explicit scoped live approval.",
            "No prompt submission, queue execution, public generation, or public raw /prompt route.",
            "Keep local archetypes/presets disabled unless evidence gates and approval explicitly change that scope.",
            "Record validation truthfully in each checkpoint; if the full offline-safe suite was not run, say so.",
            "Before each checkpoint commit, verify staged contents intentionally match the checkpoint and no unrelated files are included.",
            "After each commit, immediately continue with the next offline-safe gap unless blocked by the live boundary.",
        ),
    )


def format_watchdog_report(report: CheckpointWatchdogReport) -> str:
    lines = [
        "",
        "================ CINEFORGE CHECKPOINT WATCHDOG ================",
        report.reminder,
        f"Last commit: {report.last_commit}",
        f"Tracked worktree clean: {report.tracked_worktree_clean}",
        "Invariants:",
    ]
    lines.extend(f"- {item}" for item in report.invariants)
    lines.append("================================================================")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    as_json = False
    if "--json" in argv:
        argv.remove("--json")
        as_json = True
    repo_root = Path(argv[0]) if argv else Path.cwd()
    report = build_watchdog_report(repo_root)
    if as_json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print(format_watchdog_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
