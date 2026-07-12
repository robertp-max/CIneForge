"""Persisted state transitions for orchestration runs and steps."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.app.schemas.orchestration import RunStatus, StepStatus
from backend.app.services.planning.errors import PlanningError, PlanningErrorCode


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Allowed run transitions: from -> to
RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.pending: frozenset({RunStatus.running, RunStatus.canceled, RunStatus.failed}),
    RunStatus.running: frozenset({RunStatus.completed, RunStatus.failed, RunStatus.canceled}),
    RunStatus.completed: frozenset(),
    RunStatus.failed: frozenset(),
    RunStatus.canceled: frozenset(),
}

STEP_TRANSITIONS: dict[StepStatus, frozenset[StepStatus]] = {
    StepStatus.pending: frozenset(
        {StepStatus.running, StepStatus.skipped, StepStatus.canceled, StepStatus.failed}
    ),
    StepStatus.running: frozenset(
        {StepStatus.completed, StepStatus.failed, StepStatus.canceled}
    ),
    StepStatus.completed: frozenset(),
    StepStatus.failed: frozenset(),
    StepStatus.skipped: frozenset(),
    StepStatus.canceled: frozenset(),
}

TERMINAL_RUN_STATUSES = frozenset({RunStatus.completed, RunStatus.failed, RunStatus.canceled})
TERMINAL_STEP_STATUSES = frozenset(
    {StepStatus.completed, StepStatus.failed, StepStatus.skipped, StepStatus.canceled}
)
ACTIVE_RUN_STATUSES = frozenset({RunStatus.pending, RunStatus.running})


def parse_run_status(value: str) -> RunStatus:
    try:
        return RunStatus(value)
    except ValueError as exc:
        raise PlanningError(
            PlanningErrorCode.INVALID_TRANSITION,
            f"Unknown run status: {value}",
        ) from exc


def parse_step_status(value: str) -> StepStatus:
    try:
        return StepStatus(value)
    except ValueError as exc:
        raise PlanningError(
            PlanningErrorCode.INVALID_TRANSITION,
            f"Unknown step status: {value}",
        ) from exc


def assert_run_transition(current: str | RunStatus, target: RunStatus) -> RunStatus:
    cur = current if isinstance(current, RunStatus) else parse_run_status(current)
    if cur == target:
        return cur
    allowed = RUN_TRANSITIONS.get(cur, frozenset())
    if target not in allowed:
        raise PlanningError(
            PlanningErrorCode.INVALID_TRANSITION,
            f"Invalid run transition {cur.value} → {target.value}",
            details={"from": cur.value, "to": target.value},
        )
    return cur


def assert_step_transition(current: str | StepStatus, target: StepStatus) -> StepStatus:
    cur = current if isinstance(current, StepStatus) else parse_step_status(current)
    if cur == target:
        return cur
    allowed = STEP_TRANSITIONS.get(cur, frozenset())
    if target not in allowed:
        raise PlanningError(
            PlanningErrorCode.INVALID_TRANSITION,
            f"Invalid step transition {cur.value} → {target.value}",
            details={"from": cur.value, "to": target.value},
        )
    return cur


def is_run_terminal(status: str | RunStatus) -> bool:
    cur = status if isinstance(status, RunStatus) else parse_run_status(status)
    return cur in TERMINAL_RUN_STATUSES


def is_step_terminal(status: str | StepStatus) -> bool:
    cur = status if isinstance(status, StepStatus) else parse_step_status(status)
    return cur in TERMINAL_STEP_STATUSES


def is_run_active(status: str | RunStatus) -> bool:
    cur = status if isinstance(status, RunStatus) else parse_run_status(status)
    return cur in ACTIVE_RUN_STATUSES
