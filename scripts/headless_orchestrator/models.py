from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class TaskStatus(StrEnum):
    queued = "queued"
    preparing = "preparing"
    leased = "leased"
    running = "running"
    result_received = "result_received"
    verifying = "verifying"
    passed = "passed"
    retry_wait = "retry_wait"
    blocked = "blocked"
    failed = "failed"
    cancel_requested = "cancel_requested"
    canceled = "canceled"
    invalidated = "invalidated"


class ToolProfile(StrEnum):
    read_only = "read_only"
    edit_owned = "edit_owned"


TERMINAL_STATUSES = {
    TaskStatus.passed,
    TaskStatus.blocked,
    TaskStatus.failed,
    TaskStatus.canceled,
    TaskStatus.invalidated,
}

VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.queued: {TaskStatus.preparing, TaskStatus.cancel_requested},
    TaskStatus.preparing: {TaskStatus.leased, TaskStatus.blocked, TaskStatus.failed, TaskStatus.cancel_requested},
    TaskStatus.leased: {TaskStatus.running, TaskStatus.failed, TaskStatus.cancel_requested},
    TaskStatus.running: {
        TaskStatus.result_received,
        TaskStatus.retry_wait,
        TaskStatus.blocked,
        TaskStatus.failed,
        TaskStatus.cancel_requested,
    },
    TaskStatus.result_received: {TaskStatus.verifying, TaskStatus.blocked, TaskStatus.failed},
    TaskStatus.verifying: {TaskStatus.passed, TaskStatus.retry_wait, TaskStatus.blocked, TaskStatus.failed},
    TaskStatus.retry_wait: {TaskStatus.queued, TaskStatus.cancel_requested},
    TaskStatus.cancel_requested: {TaskStatus.canceled},
    TaskStatus.passed: {TaskStatus.invalidated},
    TaskStatus.blocked: set(),
    TaskStatus.failed: set(),
    TaskStatus.canceled: set(),
    TaskStatus.invalidated: set(),
}


@dataclass(frozen=True, slots=True)
class TaskSpec:
    run_id: str
    task_id: str
    role: str
    prompt_file: Path
    worktree: Path
    owned_paths: tuple[str, ...]
    expected_head: str
    expected_branch: str
    required_tests: tuple[str, ...] = ()
    tool_profile: ToolProfile = ToolProfile.read_only
    max_turns: int = 32
    timeout_sec: int = 3600

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.task_id.strip() or not self.role.strip():
            raise ValueError("run_id, task_id, and role are required")
        if not 1 <= self.max_turns <= 256:
            raise ValueError("max_turns must be between 1 and 256")
        if not 30 <= self.timeout_sec <= 14400:
            raise ValueError("timeout_sec must be between 30 and 14400")
        if not self.owned_paths:
            raise ValueError("at least one owned path is required")
        if len(self.expected_head) != 40 or not self.expected_branch.strip():
            raise ValueError("expected_head and expected_branch are required")
