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


SOURCE_SCOPED_UNTRACKED_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".jsonl",
    ".lock",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
IGNORED_UNTRACKED_PREFIXES = ("artifacts/watchdog/",)


@dataclass(frozen=True)
class CheckpointWatchdogReport:
    last_commit: str
    tracked_worktree_clean: bool
    staged_files: tuple[str, ...]
    reminder: str
    invariants: tuple[str, ...]
    untracked_source_files: tuple[str, ...] = ()


def _run_git(repo_root: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=repo_root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unavailable"


def _source_scoped_untracked_files(repo_root: Path) -> tuple[str, ...]:
    status = _run_git(repo_root, ["status", "--short", "--untracked-files=all"])
    files: list[str] = []
    for line in status.splitlines():
        if not line.startswith("?? "):
            continue
        rel_path = line[3:].replace("\\", "/")
        if rel_path.startswith(IGNORED_UNTRACKED_PREFIXES):
            continue
        if Path(rel_path).suffix.lower() in SOURCE_SCOPED_UNTRACKED_SUFFIXES:
            files.append(rel_path)
    return tuple(sorted(files))


def build_watchdog_report(repo_root: Path) -> CheckpointWatchdogReport:
    repo_root = repo_root.resolve()
    last_commit = _run_git(repo_root, ["log", "--oneline", "-1"])
    status = _run_git(repo_root, ["status", "--short", "--untracked-files=no"])
    staged = _run_git(repo_root, ["diff", "--cached", "--name-only"])
    tracked_clean = status == ""
    staged_files = tuple(line for line in staged.splitlines() if line)
    untracked_source_files = _source_scoped_untracked_files(repo_root)
    return CheckpointWatchdogReport(
        last_commit=last_commit,
        tracked_worktree_clean=tracked_clean,
        staged_files=staged_files,
        reminder=(
            "WATCHDOG: checkpoint loop must restart now. Pick the next offline-safe hardening/documentation/test gap, "
            "implement it, run the curated offline-safe validation when appropriate, commit the checkpoint, then restart again. "
            "Do not stop for status chatter."
        ),
        invariants=(
            "No FFmpeg/ffprobe execution without explicit scoped live approval.",
            "No ComfyUI/GPU/render/benchmark/runtime-health probe without explicit scoped live approval.",
            "No prompt submission, queue execution, public generation, or public raw /prompt or /api/prompt route.",
            "Keep local archetypes/presets disabled unless evidence gates and approval explicitly change that scope.",
            "Record validation truthfully in each checkpoint; if the full offline-safe suite was not run, say so.",
            "Before each checkpoint commit, verify staged contents intentionally match the checkpoint and no unrelated files are included.",
            "After each commit, immediately continue with the next offline-safe gap unless blocked by the live boundary.",
            "A watchdog/status answer is not a stopping point; continue the next offline-safe gap immediately after reporting it.",
        ),
        untracked_source_files=untracked_source_files,
    )


def format_watchdog_report(report: CheckpointWatchdogReport) -> str:
    lines = [
        "",
        "================ CINEFORGE CHECKPOINT WATCHDOG ================",
        report.reminder,
        f"Last commit: {report.last_commit}",
        f"Tracked worktree clean: {report.tracked_worktree_clean}",
        f"Staged files: {len(report.staged_files)}",
        f"Source-scoped untracked files: {len(report.untracked_source_files)}",
        "Invariants:",
    ]
    if report.staged_files:
        lines.append("Staged file list:")
        lines.extend(f"- {path}" for path in report.staged_files)
    if report.untracked_source_files:
        lines.append("Source-scoped untracked file list:")
        lines.extend(f"- {path}" for path in report.untracked_source_files)
    lines.extend(f"- {item}" for item in report.invariants)
    lines.append("================================================================")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    as_json = False
    fail_on_dirty = False
    if "--json" in argv:
        argv.remove("--json")
        as_json = True
    if "--fail-on-dirty" in argv:
        argv.remove("--fail-on-dirty")
        fail_on_dirty = True
    repo_root = Path(argv[0]) if argv else Path.cwd()
    report = build_watchdog_report(repo_root)
    if as_json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print(format_watchdog_report(report))
    if fail_on_dirty and (not report.tracked_worktree_clean or report.untracked_source_files):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
