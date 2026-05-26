import pytest

from backend.app.services.comfy.progress_monitor import ProgressEventKind, ProgressEventParser, ProgressMonitor


def test_progress_parser_execution_start():
    event = ProgressEventParser().parse(
        {"type": "execution_start", "data": {"prompt_id": "prompt-1"}}
    )

    assert event.kind == ProgressEventKind.execution_start
    assert event.prompt_id == "prompt-1"
    assert event.node_id is None
    assert not event.is_completion_signal


def test_progress_parser_progress_update():
    event = ProgressEventParser().parse(
        {"type": "progress", "data": {"prompt_id": "prompt-1", "node": "3", "value": 4, "max": 10}}
    )

    assert event.kind == ProgressEventKind.progress
    assert event.prompt_id == "prompt-1"
    assert event.node_id == "3"
    assert event.value == 4
    assert event.max_value == 10


def test_progress_parser_executing_complete_signal():
    event = ProgressEventParser().parse(
        {"type": "executing", "data": {"prompt_id": "prompt-1", "node": None}}
    )

    assert event.kind == ProgressEventKind.executing
    assert event.prompt_id == "prompt-1"
    assert event.node_id is None
    assert event.is_completion_signal


def test_progress_parser_error_event():
    event = ProgressEventParser().parse(
        {
            "type": "execution_error",
            "data": {
                "prompt_id": "prompt-1",
                "node": "8",
                "exception_type": "RuntimeError",
                "exception_message": "CUDA out of memory",
            },
        }
    )

    assert event.kind == ProgressEventKind.execution_error
    assert event.prompt_id == "prompt-1"
    assert event.node_id == "8"
    assert event.is_runtime_failure_candidate
    assert event.error == "CUDA out of memory"


def test_progress_parser_preserves_unknown_event():
    payload = {"type": "custom_node_metric", "data": {"prompt_id": "prompt-1", "value": "kept"}}

    event = ProgressEventParser().parse(payload)

    assert event.kind == ProgressEventKind.unknown
    assert event.raw_type == "custom_node_metric"
    assert event.raw == payload
    assert event.prompt_id == "prompt-1"


@pytest.mark.asyncio
async def test_monitor_interface_uses_history_fallback_boundary():
    class FakeClient:
        async def get_history(self, prompt_id: str):
            return {prompt_id: {"outputs": {"9": {"videos": []}}}}

    result = await ProgressMonitor().history_fallback(FakeClient(), "prompt-1")

    assert result.prompt_id == "prompt-1"
    assert result.history == {"prompt-1": {"outputs": {"9": {"videos": []}}}}
