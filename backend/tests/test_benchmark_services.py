import json

import pytest

from backend.app.core.errors import UnsafePathError
from backend.app.services.benchmarks.logger import (
    BenchmarkEvent,
    BenchmarkJsonlLogger,
    BenchmarkMetrics,
    aggregate_benchmark_metrics,
)
from backend.app.services.benchmarks.promotion import (
    PromotionDecision,
    PromotionGateConfig,
    PromotionGateEvaluator,
)


def _complete_metrics(**overrides) -> BenchmarkMetrics:
    values = {
        "peak_vram_mib": 22000,
        "peak_ram_mib": 64000,
        "peak_temp_c": 78,
        "total_duration_sec": 420.5,
        "failure_count": 0,
        "failure_rate": 0.0,
        "completed_count": 3,
        "total_event_count": 3,
    }
    values.update(overrides)
    return BenchmarkMetrics(**values)


def test_benchmark_jsonl_writer_appends_event(tmp_path):
    logger = BenchmarkJsonlLogger(tmp_path)
    event = BenchmarkEvent(
        run_id="run-1",
        event="generation_completed",
        status="complete",
        model="Wan2.2-T2V-A14B",
        quant="fp8_scaled",
        workflow_template_id="wan22-a14b-fp8-v001",
        width=832,
        height=480,
        frames=81,
        fps=16,
        steps=20,
        seed=123456789,
        duration_sec=420.5,
        peak_vram_mib=22000,
        peak_ram_mib=64200,
        peak_temp_c=78,
    )

    path = logger.append_event("run-1", event)
    logger.append_event("run-1", {"run_id": "run-1", "event": "note", "status": "complete"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["run_id"] == "run-1"
    assert first["event"] == "generation_completed"
    assert first["ts"]
    assert first["peak_vram_mib"] == 22000


def test_benchmark_jsonl_writer_rejects_unsafe_path(tmp_path):
    logger = BenchmarkJsonlLogger(tmp_path)

    with pytest.raises(UnsafePathError):
        logger.append_event("../outside", {"run_id": "run-1", "event": "bad", "status": "failed"})


def test_benchmark_peak_metric_aggregation():
    metrics = aggregate_benchmark_metrics(
        [
            {"status": "complete", "duration_sec": 10, "peak_vram_mib": 100, "peak_ram_mib": 1000, "peak_temp_c": 60},
            {"status": "complete", "duration_sec": 12, "peak_vram_mib": 200, "peak_ram_mib": 900, "peak_temp_c": 62},
            {"status": "failed", "failure_message": "oom", "peak_vram_mib": 180, "peak_ram_mib": 1200, "peak_temp_c": 70},
        ]
    )

    assert metrics.peak_vram_mib == 200
    assert metrics.peak_ram_mib == 1200
    assert metrics.peak_temp_c == 70
    assert metrics.total_duration_sec == 22
    assert metrics.failure_count == 1
    assert metrics.failure_rate == pytest.approx(1 / 3)
    assert metrics.completed_count == 2
    assert metrics.total_event_count == 3


def test_promotion_gate_rejects_high_vram():
    result = PromotionGateEvaluator().evaluate(_complete_metrics(peak_vram_mib=23000))

    assert result.decision == PromotionDecision.reject
    assert any("peak_vram_mib" in reason for reason in result.reasons)


def test_promotion_gate_rejects_failure_rate():
    result = PromotionGateEvaluator(PromotionGateConfig(max_failure_rate=0.1)).evaluate(
        _complete_metrics(failure_count=1, failure_rate=0.25)
    )

    assert result.decision == PromotionDecision.reject
    assert any("failure_rate" in reason for reason in result.reasons)


def test_promotion_gate_retries_incomplete_metrics():
    result = PromotionGateEvaluator().evaluate(_complete_metrics(peak_temp_c=None))

    assert result.decision == PromotionDecision.retry
    assert result.reasons == ["benchmark metrics are incomplete"]


def test_promotion_gate_promotes_passing_metrics():
    result = PromotionGateEvaluator().evaluate(_complete_metrics())

    assert result.decision == PromotionDecision.promote
    assert result.reasons == ["benchmark metrics satisfy promotion gates"]
