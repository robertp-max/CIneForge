import json
import hashlib
from pathlib import Path

import pytest

from scripts.headless_orchestrator.ledger import Ledger
from scripts.headless_orchestrator.models import TaskSpec, TaskStatus, ToolProfile
from scripts.headless_orchestrator.patches import apply_file_patches
from scripts.headless_orchestrator.policy import (
    WorktreeSnapshot,
    assert_owned_paths,
    build_child_environment,
    path_is_owned,
    verify_worktree_changes,
)
from scripts.headless_orchestrator.runner import build_worker_args, validate_json_output
from scripts.headless_orchestrator.schemas import parse_implementation_result
from scripts.headless_orchestrator.schemas import FilePatch


def _spec(tmp_path: Path, task_id: str = "task-1") -> TaskSpec:
    worktree = tmp_path / "worktree"
    worktree.mkdir(exist_ok=True)
    (worktree / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    prompt = worktree / "prompt.md"
    prompt.write_text("review", encoding="utf-8")
    return TaskSpec(
        run_id="run-1",
        task_id=task_id,
        role="qa",
        prompt_file=prompt,
        worktree=worktree,
        owned_paths=("backend/tests/**",),
        expected_head="0" * 40,
        expected_branch="codex/test-lane",
        tool_profile=ToolProfile.read_only,
        max_turns=8,
        timeout_sec=60,
    )


def test_worker_args_pin_model_effort_and_disable_uncontrolled_tools(tmp_path):
    args = build_worker_args(_spec(tmp_path), "session-1", Path("grok.exe"))
    assert args[0] == "grok.exe"
    assert args[args.index("--model") + 1] == "grok-4.5"
    assert args[args.index("--reasoning-effort") + 1] == "high"
    assert "--no-subagents" in args
    assert "--no-memory" in args
    assert args[args.index("--tools") + 1] == "todo_write"
    disallowed = args[args.index("--disallowed-tools") + 1]
    assert "run_terminal_cmd" in disallowed
    assert "read_file" in disallowed
    assert "search_replace" in disallowed
    assert "task" in disallowed
    assert "todo_write" in disallowed
    assert "--json-schema" in args
    assert "--always-approve" not in args


def test_child_environment_drops_secret_values():
    result = build_child_environment(
        {
            "PATH": "safe",
            "USERPROFILE": r"C:\Users\worker",
            "XAI_API_KEY": "secret",
            "DATABASE_URL": "secret",
        }
    )
    assert result["PATH"] == "safe"
    assert "XAI_API_KEY" not in result
    assert "DATABASE_URL" not in result


def test_ownership_is_case_insensitive_and_blocks_unexpected_paths():
    assert path_is_owned("Backend/Tests/test_example.py", ("backend/tests/**",))
    with pytest.raises(ValueError, match="outside task ownership"):
        assert_owned_paths(["backend/app/main.py"], ("backend/tests/**",))
    with pytest.raises(ValueError, match="forbidden path"):
        path_is_owned(".git/config", ("**",))
    with pytest.raises(ValueError, match="absolute paths"):
        path_is_owned(r"C:\secrets.txt", ("**",))
    with pytest.raises(ValueError, match="absolute paths"):
        path_is_owned(r"\\server\share\secrets.txt", ("**",))
    with pytest.raises(ValueError, match="absolute paths"):
        path_is_owned("/etc/passwd", ("**",))


def test_ledger_validates_transitions_and_worker_limit(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    try:
        first = _spec(tmp_path, "task-1")
        second = _spec(tmp_path, "task-2")
        ledger.create_run(first.run_id)
        ledger.add_task(first)
        ledger.add_task(second)
        ledger.transition(first.run_id, first.task_id, TaskStatus.preparing)
        ledger.reserve_slot(first.task_id, "lease-1", max_active=1)
        with pytest.raises(RuntimeError, match="worker limit reached"):
            ledger.reserve_slot(second.task_id, "lease-2", max_active=1)
        with pytest.raises(ValueError, match="between 1 and 64"):
            ledger.reserve_slot(second.task_id, "lease-3", max_active=65)
        with pytest.raises(ValueError, match="invalid task transition"):
            ledger.transition(first.run_id, first.task_id, TaskStatus.passed)
        ledger.release_slot(first.task_id)
        assert json.loads(ledger.list_tasks(first.run_id)[0]["owned_paths_json"])
    finally:
        ledger.close()


def test_worker_output_strips_private_reasoning_fields():
    parsed = validate_json_output(
        json.dumps(
            {
                "text": "final answer",
                "thought": "private",
                "nested": {"reasoning_content": "private", "status": "ok"},
            }
        )
    )
    assert parsed == {"text": "final answer", "nested": {"status": "ok"}}


def test_worktree_verification_enforces_read_only_and_owned_paths():
    before = WorktreeSnapshot("branch", "head", {"backend/app/a.py": "one"})
    after = WorktreeSnapshot("branch", "head", {"backend/app/a.py": "two"})
    with pytest.raises(RuntimeError, match="read-only worker changed files"):
        verify_worktree_changes(before, after, ("backend/app/**",), read_only=True)
    assert verify_worktree_changes(before, after, ("backend/app/**",), read_only=False) == ["backend/app/a.py"]
    with pytest.raises(ValueError, match="outside task ownership"):
        verify_worktree_changes(before, after, ("frontend/**",), read_only=False)


def test_strict_grok_envelope_and_inner_result_validation():
    session_id = "00000000-0000-4000-8000-000000000001"
    request_id = "00000000-0000-4000-8000-000000000002"
    payload = {
        "status": "completed",
        "summary": "done",
        "patches": [],
        "findings": [],
        "tests": [],
        "blockers": [],
    }
    parsed = parse_implementation_result(
        {
            "text": json.dumps(payload),
            "stopReason": "EndTurn",
            "sessionId": session_id,
            "requestId": request_id,
            "structuredOutput": payload,
        },
        session_id,
    )
    assert parsed.status == "completed"
    with pytest.raises(ValueError, match="session ID mismatch"):
        parse_implementation_result(
            {
                "text": json.dumps(payload),
                "stopReason": "EndTurn",
                "sessionId": request_id,
                "requestId": request_id,
                "structuredOutput": payload,
            },
            session_id,
        )
    with pytest.raises(ValueError, match="must be an object"):
        parse_implementation_result(
            {
                "text": "schema-constrained result",
                "stopReason": "EndTurn",
                "sessionId": session_id,
                "requestId": request_id,
                "structuredOutput": "not-an-object",
            },
            session_id,
        )
    with pytest.raises(ValueError, match="missing or unknown"):
        parse_implementation_result(
            {
                "text": json.dumps({**payload, "unexpected": True}),
                "stopReason": "EndTurn",
                "sessionId": session_id,
                "requestId": request_id,
                "structuredOutput": {**payload, "unexpected": True},
            },
            session_id,
        )


def test_controller_applies_only_owned_non_stale_full_file_patches(tmp_path):
    worktree = tmp_path / "worktree"
    target = worktree / "backend" / "owned.py"
    target.parent.mkdir(parents=True)
    target.write_text("before\n", encoding="utf-8")
    expected = hashlib.sha256(target.read_bytes()).hexdigest()
    changed = apply_file_patches(
        worktree,
        (FilePatch("backend/owned.py", "replace", expected, "after\n"),),
        ("backend/**",),
    )
    assert changed == ["backend/owned.py"]
    assert target.read_text(encoding="utf-8") == "after\n"
    with pytest.raises(ValueError, match="stale"):
        apply_file_patches(
            worktree,
            (FilePatch("backend/owned.py", "replace", expected, "again\n"),),
            ("backend/**",),
        )
    with pytest.raises(ValueError, match="outside task ownership"):
        apply_file_patches(
            worktree,
            (FilePatch("frontend/unowned.py", "create", None, "no\n"),),
            ("backend/**",),
        )
