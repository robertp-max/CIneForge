from dataclasses import dataclass
from enum import StrEnum


class JobState(StrEnum):
    pending = "pending"
    reserved = "reserved"
    validating = "validating"
    submitted = "submitted"
    running = "running"
    collecting_outputs = "collecting_outputs"
    complete = "complete"
    validation_failed = "validation_failed"
    comfy_rejected = "comfy_rejected"
    runtime_failed = "runtime_failed"
    timeout = "timeout"
    interrupted = "interrupted"
    oom = "oom"
    postprocess_failed = "postprocess_failed"
    canceled = "canceled"


ACTIVE_FLOW = [
    JobState.pending,
    JobState.reserved,
    JobState.validating,
    JobState.submitted,
    JobState.running,
    JobState.collecting_outputs,
    JobState.complete,
]

FAILURE_STATES = {
    JobState.validation_failed,
    JobState.comfy_rejected,
    JobState.runtime_failed,
    JobState.timeout,
    JobState.interrupted,
    JobState.oom,
    JobState.postprocess_failed,
}

VALID_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.pending: {JobState.reserved, JobState.canceled},
    JobState.reserved: {
        JobState.pending,
        JobState.validating,
        JobState.timeout,
        JobState.canceled,
        JobState.interrupted,
    },
    JobState.validating: {JobState.submitted, JobState.validation_failed, JobState.canceled, JobState.interrupted},
    JobState.submitted: {JobState.running, JobState.comfy_rejected, JobState.timeout, JobState.interrupted},
    JobState.running: {
        JobState.collecting_outputs,
        JobState.runtime_failed,
        JobState.timeout,
        JobState.interrupted,
        JobState.oom,
    },
    JobState.collecting_outputs: {JobState.complete, JobState.postprocess_failed, JobState.runtime_failed},
    JobState.complete: set(),
    JobState.validation_failed: set(),
    JobState.comfy_rejected: set(),
    JobState.runtime_failed: set(),
    JobState.timeout: set(),
    JobState.interrupted: set(),
    JobState.oom: set(),
    JobState.postprocess_failed: set(),
    JobState.canceled: set(),
}


class InvalidTransition(ValueError):
    pass


@dataclass(frozen=True)
class TransitionResult:
    previous: JobState
    current: JobState
    reason: str
    audit_event: dict


def transition(current: JobState | str, target: JobState | str, reason: str) -> TransitionResult:
    current_state = JobState(current)
    target_state = JobState(target)
    if target_state not in VALID_TRANSITIONS[current_state]:
        raise InvalidTransition(f"Invalid queue transition: {current_state.value} -> {target_state.value}")
    return TransitionResult(
        previous=current_state,
        current=target_state,
        reason=reason,
        audit_event={
            "entity_type": "comfy_job",
            "action": "queue_transition",
            "details": {
                "from": current_state.value,
                "to": target_state.value,
                "reason": reason,
            },
        },
    )
