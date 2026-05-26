import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.utils.path_safety import resolve_inside, sanitize_output_prefix


@dataclass(frozen=True)
class BenchmarkEvent:
    run_id: str
    event: str
    status: str
    timestamp: str | None = None
    model: str | None = None
    quant: str | None = None
    workflow_template_id: str | None = None
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    fps: float | None = None
    steps: int | None = None
    seed: int | None = None
    duration_sec: float | None = None
    peak_vram_mib: int | None = None
    peak_ram_mib: int | None = None
    peak_temp_c: int | None = None
    failure_message: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        data = {key: value for key, value in asdict(self).items() if value is not None}
        data["ts"] = data.pop("timestamp", None) or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return data


@dataclass(frozen=True)
class BenchmarkMetrics:
    peak_vram_mib: int | None
    peak_ram_mib: int | None
    peak_temp_c: int | None
    total_duration_sec: float | None
    failure_count: int
    failure_rate: float | None
    completed_count: int
    total_event_count: int

    @property
    def complete(self) -> bool:
        return (
            self.total_event_count > 0
            and self.peak_vram_mib is not None
            and self.peak_ram_mib is not None
            and self.peak_temp_c is not None
            and self.total_duration_sec is not None
            and self.completed_count > 0
            and self.failure_rate is not None
        )


class BenchmarkJsonlLogger:
    def __init__(self, root: Path) -> None:
        self.root = root

    def append_event(self, filename: str, event: BenchmarkEvent | dict[str, Any]) -> Path:
        path = self._safe_jsonl_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.to_json_dict() if isinstance(event, BenchmarkEvent) else self._normalize_event(event)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        return path

    def _safe_jsonl_path(self, filename: str) -> Path:
        safe_stem = sanitize_output_prefix(filename.removesuffix(".jsonl"))
        return resolve_inside(self.root, f"{safe_stem}.jsonl")

    @staticmethod
    def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in event.items() if value is not None}
        payload.setdefault("ts", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        return payload


def aggregate_benchmark_metrics(events: list[BenchmarkEvent | dict[str, Any]]) -> BenchmarkMetrics:
    payloads = [event.to_json_dict() if isinstance(event, BenchmarkEvent) else event for event in events]
    total_count = len(payloads)
    completed_count = sum(1 for event in payloads if event.get("status") == "complete")
    failure_count = sum(1 for event in payloads if _is_failure(event))

    durations = [float(event["duration_sec"]) for event in payloads if event.get("duration_sec") is not None]
    return BenchmarkMetrics(
        peak_vram_mib=_max_int(payloads, "peak_vram_mib"),
        peak_ram_mib=_max_int(payloads, "peak_ram_mib"),
        peak_temp_c=_max_int(payloads, "peak_temp_c"),
        total_duration_sec=sum(durations) if durations else None,
        failure_count=failure_count,
        failure_rate=(failure_count / total_count) if total_count else None,
        completed_count=completed_count,
        total_event_count=total_count,
    )


def _max_int(events: list[dict[str, Any]], key: str) -> int | None:
    values = [int(event[key]) for event in events if event.get(key) is not None]
    return max(values) if values else None


def _is_failure(event: dict[str, Any]) -> bool:
    status = str(event.get("status") or "").lower()
    return status in {"failed", "failure", "error", "timeout", "oom"} or event.get("failure_message") is not None
