import pytest

from backend.app.queue.state_machine import InvalidTransition, JobState, transition


def test_queue_valid_transitions():
    result = transition(JobState.pending, JobState.reserved, "worker reservation")
    assert result.current == JobState.reserved
    assert result.audit_event["details"]["from"] == "pending"
    assert result.audit_event["details"]["to"] == "reserved"


def test_queue_invalid_transition_rejected():
    with pytest.raises(InvalidTransition):
        transition(JobState.pending, JobState.complete, "cannot skip lifecycle")

