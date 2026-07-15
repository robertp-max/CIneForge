from types import SimpleNamespace

from backend.app.schemas.production import OutputProfile, SemanticGenerationRequest
from backend.app.services.production_gates import ProductionGateService


class FakePresetCatalog:
    def __init__(self, preset) -> None:
        self.preset = preset

    def get_preset(self, preset_id: str):
        return self.preset if preset_id == self.preset.preset_id else None


class FakeRegistry:
    def __init__(self, record) -> None:
        self.record = record

    def get(self, archetype_id: str):
        return self.record if archetype_id == self.record.archetype_id else None


def _preset(*, readiness="ready", enabled=True):
    return SimpleNamespace(preset_id="CF-PRESET-001", readiness=readiness, enabled=enabled)


def _record(**overrides):
    values = {
        "archetype_id": "CF-VID-01",
        "api_graph_path": None,
        "blocked_reasons": [],
        "implemented": True,
        "dependency_verified": True,
        "locally_tested": True,
        "benchmark_passed": True,
        "human_approved": True,
        "readiness": "ready",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(**overrides) -> SemanticGenerationRequest:
    payload = {
        "preset_id": "CF-PRESET-001",
        "archetype_id": "CF-VID-01",
        "quality_profile": OutputProfile.draft,
        "mode": "t2v",
        "prompt": "safe production gate test",
        "negative_prompt": "bad quality",
        "width": 512,
        "height": 288,
        "frame_count": 17,
        "fps": 24,
        "target_duration_sec": 1.0,
        "output_profile": OutputProfile.draft,
        "output_prefix": "Gate Project/run 01",
        "production": True,
    }
    payload.update(overrides)
    return SemanticGenerationRequest(**payload)


def _service(record, preset=None) -> ProductionGateService:
    return ProductionGateService(registry=FakeRegistry(record), presets=FakePresetCatalog(preset or _preset()))


def test_generation_request_requires_benchmark_and_human_approval_even_when_locally_tested():
    service = _service(_record(benchmark_passed=False, human_approved=False, readiness="benchmark_required"))

    report = service.evaluate_generation_request(_request())

    assert report.allowed is False
    messages = [reason.message for reason in report.blocking_reasons]
    assert any("benchmark_passed" in message for message in messages)
    assert any("human_approved" in message for message in messages)
    assert any("readiness=benchmark_required" in message for message in messages)


def test_generation_request_allows_only_ready_preset_and_ready_archetype_for_t2v():
    service = _service(_record())

    report = service.evaluate_generation_request(_request())

    assert report.allowed is True
    assert report.blocking_reasons == []


def test_generation_request_blocks_disabled_ready_preset():
    service = _service(_record(), preset=_preset(readiness="ready", enabled=False))

    report = service.evaluate_generation_request(_request())

    assert report.allowed is False
    assert any(reason.code.value == "PRESET_BENCHMARK_REQUIRED" for reason in report.blocking_reasons)
