from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProgressEventKind(StrEnum):
    execution_start = "execution_start"
    executing = "executing"
    progress = "progress"
    executed = "executed"
    execution_error = "execution_error"
    unknown = "unknown"


@dataclass(frozen=True)
class ProgressEvent:
    kind: ProgressEventKind
    raw_type: str
    prompt_id: str | None
    node_id: str | None
    raw: dict[str, Any]
    value: int | float | None = None
    max_value: int | float | None = None
    is_completion_signal: bool = False
    is_runtime_failure_candidate: bool = False
    error: str | None = None


class ProgressEventParser:
    def parse(self, payload: dict[str, Any]) -> ProgressEvent:
        raw_type = str(payload.get("type") or "unknown")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        prompt_id = self._optional_text(data.get("prompt_id"))
        node_id = self._optional_text(data.get("node"))

        if raw_type == ProgressEventKind.execution_start.value:
            return ProgressEvent(
                kind=ProgressEventKind.execution_start,
                raw_type=raw_type,
                prompt_id=prompt_id,
                node_id=node_id,
                raw=payload,
            )
        if raw_type == ProgressEventKind.executing.value:
            return ProgressEvent(
                kind=ProgressEventKind.executing,
                raw_type=raw_type,
                prompt_id=prompt_id,
                node_id=node_id,
                raw=payload,
                is_completion_signal=data.get("node") is None,
            )
        if raw_type == ProgressEventKind.progress.value:
            return ProgressEvent(
                kind=ProgressEventKind.progress,
                raw_type=raw_type,
                prompt_id=prompt_id,
                node_id=node_id,
                raw=payload,
                value=self._optional_number(data.get("value")),
                max_value=self._optional_number(data.get("max")),
            )
        if raw_type == ProgressEventKind.executed.value:
            return ProgressEvent(
                kind=ProgressEventKind.executed,
                raw_type=raw_type,
                prompt_id=prompt_id,
                node_id=node_id,
                raw=payload,
            )
        if raw_type == ProgressEventKind.execution_error.value:
            return ProgressEvent(
                kind=ProgressEventKind.execution_error,
                raw_type=raw_type,
                prompt_id=prompt_id,
                node_id=node_id,
                raw=payload,
                is_runtime_failure_candidate=True,
                error=self._error_text(data),
            )
        return ProgressEvent(
            kind=ProgressEventKind.unknown,
            raw_type=raw_type,
            prompt_id=prompt_id,
            node_id=node_id,
            raw=payload,
        )

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _optional_number(value: Any) -> int | float | None:
        if isinstance(value, int | float):
            return value
        return None

    @staticmethod
    def _error_text(data: dict[str, Any]) -> str | None:
        exception_message = data.get("exception_message")
        if exception_message is not None:
            return str(exception_message)
        exception_type = data.get("exception_type")
        if exception_type is not None:
            return str(exception_type)
        return None


@dataclass(frozen=True)
class HistoryFallbackResult:
    prompt_id: str
    history: dict[str, Any]


class ProgressMonitor:
    def __init__(self, parser: ProgressEventParser | None = None) -> None:
        self.parser = parser or ProgressEventParser()

    def parse_event(self, payload: dict[str, Any]) -> ProgressEvent:
        return self.parser.parse(payload)

    async def connect(self, client: Any, client_id: str) -> Any:
        return await client.connect_progress_websocket(client_id)

    async def history_fallback(self, client: Any, prompt_id: str) -> HistoryFallbackResult:
        history = await client.get_history(prompt_id)
        return HistoryFallbackResult(prompt_id=prompt_id, history=history)
