from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from .controller import HeadlessController
from .context import build_context_prompt
from .models import TaskSpec, ToolProfile
from .policy import assert_task_preflight
from .runner import DEFAULT_GROK_EXE, verify_grok_executable


DEFAULT_STATE_ROOT = Path(
    os.environ.get("CINEFORGE_ORCH_STATE_ROOT", r"C:\AI\Git\_orchestration\CIneForge")
)


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
    )
    return result.stdout.strip()


def preflight(worktree: Path, expected_head: str, expected_branch: str) -> dict:
    verify_grok_executable()
    top_level = Path(_git("rev-parse", "--show-toplevel", cwd=worktree)).resolve()
    if top_level != worktree.resolve():
        raise RuntimeError(f"unexpected worktree top level: {top_level}")
    assert_task_preflight(top_level, expected_head, expected_branch)
    return {
        "status": "ready",
        "grok_executable": str(DEFAULT_GROK_EXE),
        "worktree": str(top_level),
        "branch": _git("branch", "--show-current", cwd=worktree),
        "head": _git("rev-parse", "HEAD", cwd=worktree),
        "dirty": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cineforge-headless-orch")
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--max-grok-workers", type=int, default=47)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--worktree", type=Path, required=True)
    preflight_parser.add_argument("--expected-head", required=True)
    preflight_parser.add_argument("--expected-branch", required=True)

    task_parser = subparsers.add_parser("run-task")
    task_parser.add_argument("--worktree", type=Path, required=True)
    task_parser.add_argument("--prompt-file", type=Path, required=True)
    task_parser.add_argument("--role", required=True)
    task_parser.add_argument("--task-id", default=None)
    task_parser.add_argument("--run-id", default=None)
    task_parser.add_argument("--owned-path", action="append", required=True)
    task_parser.add_argument("--expected-head", required=True)
    task_parser.add_argument("--expected-branch", required=True)
    task_parser.add_argument("--required-test", action="append", default=[])
    task_parser.add_argument("--tool-profile", choices=[item.value for item in ToolProfile], default="read_only")
    task_parser.add_argument("--max-turns", type=int, default=32)
    task_parser.add_argument("--timeout-sec", type=int, default=3600)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--run-id", default=None)

    invalidate_parser = subparsers.add_parser("invalidate-task")
    invalidate_parser.add_argument("--run-id", required=True)
    invalidate_parser.add_argument("--task-id", required=True)
    invalidate_parser.add_argument("--reason", required=True)

    context_parser = subparsers.add_parser("build-context")
    context_parser.add_argument("--worktree", type=Path, required=True)
    context_parser.add_argument("--template-file", type=Path, required=True)
    context_parser.add_argument("--context-path", action="append", required=True)
    context_parser.add_argument("--output-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preflight":
        print(json.dumps(preflight(args.worktree, args.expected_head, args.expected_branch), indent=2))
        return 0
    if args.command == "build-context":
        output = build_context_prompt(
            args.worktree,
            args.template_file,
            tuple(args.context_path),
            args.output_file,
            args.state_root,
        )
        print(json.dumps({"status": "created", "prompt": str(output)}, indent=2))
        return 0
    controller = HeadlessController(args.state_root, max_grok_workers=args.max_grok_workers)
    try:
        if args.command == "status":
            print(json.dumps(controller.ledger.list_tasks(args.run_id), indent=2))
            return 0
        if args.command == "invalidate-task":
            artifact = controller.invalidate_legacy_task(args.run_id, args.task_id, args.reason)
            print(json.dumps({"status": "invalidated", "artifact": str(artifact) if artifact else None}, indent=2))
            return 0
        spec = TaskSpec(
            run_id=args.run_id or str(uuid.uuid4()),
            task_id=args.task_id or str(uuid.uuid4()),
            role=args.role,
            prompt_file=args.prompt_file if args.prompt_file.is_absolute() else controller.state_root / args.prompt_file,
            worktree=args.worktree,
            owned_paths=tuple(args.owned_path),
            expected_head=args.expected_head,
            expected_branch=args.expected_branch,
            required_tests=tuple(args.required_test),
            tool_profile=ToolProfile(args.tool_profile),
            max_turns=args.max_turns,
            timeout_sec=args.timeout_sec,
        )
        artifact = controller.run_task(spec)
        print(json.dumps({"status": "passed", "artifact": str(artifact)}, indent=2))
        return 0
    finally:
        controller.close()


if __name__ == "__main__":
    sys.exit(main())
