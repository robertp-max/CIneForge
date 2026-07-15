from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.services.local_runtime_evidence import LocalRuntimeEvidenceService


def test_cf_vid01_smoke_evidence_loads_from_storage():
    evidence = LocalRuntimeEvidenceService().get_cf_vid01_smoke()

    assert evidence.evidence_id == "cf_vid_01_t2v_smoke_20260713"
    assert evidence.archetype_id == "CF-VID-01"
    assert evidence.template_id == "cf_vid_01_ltx23_single_stage_t2v_smoke"
    assert evidence.readiness_after_evidence == "benchmark_required"
    assert evidence.object_info_required_classes_missing == []
    assert len(evidence.outputs) == 2
    assert evidence.outputs[0].width == 512
    assert evidence.outputs[0].height == 288
    assert evidence.outputs[0].frames == 17
    assert evidence.queue_empty_after is True
    assert "benchmark_ladder" in evidence.remaining_gates


def test_local_runtime_evidence_missing_returns_empty_list(tmp_path: Path):
    settings = Settings(storage_root=tmp_path / "storage")
    assert LocalRuntimeEvidenceService(settings).list_evidence() == []


def test_local_runtime_evidence_routes():
    client = TestClient(app)

    list_response = client.get("/local-runtime/evidence")
    assert list_response.status_code == 200
    assert list_response.json()[0]["evidence_id"] == "cf_vid_01_t2v_smoke_20260713"

    get_response = client.get("/local-runtime/evidence/cf-vid-01-smoke")
    assert get_response.status_code == 200
    assert get_response.json()["template_id"] == "cf_vid_01_ltx23_single_stage_t2v_smoke"
