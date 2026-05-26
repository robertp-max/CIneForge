import pytest

from backend.app.queue.state_machine import InvalidTransition, JobState, transition


def test_queue_valid_transitions():
    result = transition(JobState.pending, JobState.reserved, "worker reservation")
    assert result.current == JobState.reserved
    assert result.audit_event["details"]["from"] == "pending"
    assert result.audit_event["details"]["to"] == "reserved"


def test_reserved_job_can_be_recovered_to_pending():
    result = transition(JobState.reserved, JobState.pending, "stale reservation retry")

    assert result.current == JobState.pending
    assert result.previous == JobState.reserved


def test_reserved_job_can_timeout():
    result = transition(JobState.reserved, JobState.timeout, "stale reservation exhausted")

    assert result.current == JobState.timeout
    assert result.previous == JobState.reserved


def test_queue_invalid_transition_rejected():
    with pytest.raises(InvalidTransition):
        transition(JobState.pending, JobState.complete, "cannot skip lifecycle")
