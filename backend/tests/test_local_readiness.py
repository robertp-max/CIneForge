from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.local_archetypes import CANONICAL_REGISTRY_ARCHETYPE_IDS
from backend.app.services.local_readiness import LocalReadinessService


def test_local_archetype_readiness_merges_catalog_registry_and_gates_without_enablement():
    report = LocalReadinessService().archetype_report()

    assert report.public_generation_enabled is False
    assert report.live_execution_performed_by_endpoint is False
    assert report.summary.total >= len(CANONICAL_REGISTRY_ARCHETYPE_IDS)
    assert report.summary.ready == 0
    assert report.summary.benchmark_required >= 1
    records_by_id = {record.archetype_id: record for record in report.records}
    assert CANONICAL_REGISTRY_ARCHETYPE_IDS <= set(records_by_id)
    assert all(records_by_id[archetype_id].catalog_present is True for archetype_id in CANONICAL_REGISTRY_ARCHETYPE_IDS)
    assert all(records_by_id[archetype_id].public_generation_enabled is False for archetype_id in CANONICAL_REGISTRY_ARCHETYPE_IDS)
    assert all(records_by_id[archetype_id].production_ready is False for archetype_id in CANONICAL_REGISTRY_ARCHETYPE_IDS)
    assert all(records_by_id[archetype_id].status != "ready" for archetype_id in CANONICAL_REGISTRY_ARCHETYPE_IDS)

    cf_vid01 = next(record for record in report.records if record.archetype_id == "CF-VID-01")
    assert cf_vid01.status == "benchmark_required"
    assert cf_vid01.public_generation_enabled is False
    assert cf_vid01.live_execution_required_for_promotion is True
    assert cf_vid01.workflow_registry.implemented is True
    assert cf_vid01.workflow_registry.dependency_verified is True
    assert cf_vid01.workflow_registry.benchmark_passed is False
    assert cf_vid01.workflow_registry.human_approved is False
    assert cf_vid01.production_ready is False
    assert cf_vid01.production_gates.production_ready is False
    assert "benchmark_passed" in cf_vid01.production_gates.missing_gates
    assert "human_approved" in cf_vid01.production_gates.missing_gates
    reason_codes = {reason.code for reason in cf_vid01.reasons}
    assert "missing_benchmark" in reason_codes
    assert "missing_human_approval" in reason_codes

    cf_vid02 = next(record for record in report.records if record.archetype_id == "CF-VID-02")
    assert cf_vid02.status == "blocked"
    blocked_codes = {reason.code for reason in cf_vid02.reasons if reason.severity == "blocker"}
    assert "catalog_blocked" in blocked_codes
    assert "missing_implementation" in blocked_codes

    cf_vid05 = next(record for record in report.records if record.archetype_id == "CF-VID-05")
    assert cf_vid05.catalog_present is True
    assert cf_vid05.status == "blocked"
    cf_vid05_reason_codes = {reason.code for reason in cf_vid05.reasons}
    assert "catalog_blocked" in cf_vid05_reason_codes
    assert "catalog_record_missing" not in cf_vid05_reason_codes


def test_local_preset_readiness_merges_default_archetype_rollup():
    report = LocalReadinessService().preset_report()

    assert report.public_generation_enabled is False
    assert report.live_execution_performed_by_endpoint is False
    assert report.summary.total == 64
    assert report.summary.ready == 0

    draft = next(record for record in report.records if record.preset_id == "CF-PRESET-001")
    assert draft.status == "benchmark_required"
    assert draft.default_archetype_id == "CF-VID-01"
    assert draft.default_archetype_status == "benchmark_required"
    assert draft.live_execution_required_for_promotion is True
    assert draft.public_generation_enabled is False
    assert draft.production_ready is False
    assert "benchmark_passed" in draft.production_gates.missing_gates
    assert {reason.code for reason in draft.reasons} >= {
        "preset_benchmark_required",
        "default_archetype_benchmark_required",
        "default_archetype_missing_benchmark",
        "default_archetype_missing_human_approval",
    }

    final_candidate = next(record for record in report.records if record.preset_id == "CF-PRESET-003")
    assert final_candidate.status == "blocked"
    assert final_candidate.default_archetype_id == "CF-VID-02"
    assert final_candidate.default_archetype_status == "blocked"
    assert "default_archetype_blocked" in {reason.code for reason in final_candidate.reasons}


def test_local_readiness_routes_are_read_only_get_contracts():
    client = TestClient(app)

    archetype_response = client.get("/local-archetypes/readiness")
    assert archetype_response.status_code == 200
    archetype_payload = archetype_response.json()
    assert archetype_payload["public_generation_enabled"] is False
    assert archetype_payload["live_execution_performed_by_endpoint"] is False
    assert archetype_payload["summary"]["ready"] == 0
    assert any(record["archetype_id"] == "CF-VID-01" for record in archetype_payload["records"])

    single_archetype_response = client.get("/local-archetypes/CF-VID-01/readiness")
    assert single_archetype_response.status_code == 200
    single_archetype = single_archetype_response.json()
    assert single_archetype["archetype_id"] == "CF-VID-01"
    assert single_archetype["status"] == "benchmark_required"
    assert single_archetype["public_generation_enabled"] is False

    expanded_archetype_response = client.get("/local-archetypes/CF-VID-05/readiness")
    assert expanded_archetype_response.status_code == 200
    expanded_archetype = expanded_archetype_response.json()
    assert expanded_archetype["catalog_present"] is True
    assert expanded_archetype["catalog_enabled"] is False
    assert expanded_archetype["public_generation_enabled"] is False
    assert expanded_archetype["status"] == "blocked"

    missing_archetype_response = client.get("/local-archetypes/CF-VID-99/readiness")
    assert missing_archetype_response.status_code == 404

    preset_response = client.get("/local-presets/readiness")
    assert preset_response.status_code == 200
    preset_payload = preset_response.json()
    assert preset_payload["public_generation_enabled"] is False
    assert preset_payload["live_execution_performed_by_endpoint"] is False
    assert preset_payload["summary"]["total"] == 64
    assert preset_payload["summary"]["ready"] == 0

    single_preset_response = client.get("/local-presets/CF-PRESET-001/readiness")
    assert single_preset_response.status_code == 200
    single_preset = single_preset_response.json()
    assert single_preset["preset_id"] == "CF-PRESET-001"
    assert single_preset["status"] == "benchmark_required"
    assert single_preset["public_generation_enabled"] is False

    missing_preset_response = client.get("/local-presets/CF-PRESET-999/readiness")
    assert missing_preset_response.status_code == 404

    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    expected_readiness_paths = {
        "/local-archetypes/readiness",
        "/local-archetypes/{archetype_id}/readiness",
        "/local-presets/readiness",
        "/local-presets/{preset_id}/readiness",
    }
    local_readiness_paths = {
        path
        for _method, path in method_paths
        if path in expected_readiness_paths
        or (path.startswith(("/local-archetypes", "/local-presets")) and "/readiness/" in path)
    }

    assert local_readiness_paths == expected_readiness_paths
    for readiness_path in expected_readiness_paths:
        assert {method for method, path in method_paths if path == readiness_path} == {"GET"}
        assert ("POST", readiness_path) not in method_paths

    forbidden_readiness_children = ("/execute", "/submit", "/run", "/prompt")
    assert not any(
        path.startswith(("/local-archetypes", "/local-presets"))
        and "/readiness/" in path
        and any(child in path.split("/readiness", 1)[1] for child in forbidden_readiness_children)
        for _method, path in method_paths
    )
    assert "/prompt" not in {path for _method, path in method_paths}
