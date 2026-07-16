from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.schemas.local_archetypes import CANONICAL_REGISTRY_ARCHETYPE_IDS, LocalArchetypeCatalog
from backend.app.services.local_archetypes import LocalArchetypeCatalogService
from backend.app.services.workflows.registry import WorkflowRegistryService


def test_local_archetype_catalog_contains_required_ids():
    catalog = LocalArchetypeCatalogService().load()

    ids = {archetype.archetype_id for archetype in catalog.archetypes}
    registry_ids = {record.archetype_id for record in WorkflowRegistryService().load()}
    assert registry_ids == CANONICAL_REGISTRY_ARCHETYPE_IDS
    assert registry_ids <= ids

    vid01 = next(archetype for archetype in catalog.archetypes if archetype.archetype_id == "CF-VID-01")
    assert vid01.default_model_key == "ltx2_3_22b_distilled_1_1_fp8"
    assert vid01.readiness == "benchmark_required"
    assert vid01.enabled is False
    assert "draft" in vid01.quality_profiles
    assert "review" in vid01.quality_profiles

    assert all(archetype.enabled is False for archetype in catalog.archetypes)
    assert all(archetype.readiness != "ready" for archetype in catalog.archetypes)
    assert all(
        archetype.readiness == "blocked"
        for archetype in catalog.archetypes
        if archetype.archetype_id in CANONICAL_REGISTRY_ARCHETYPE_IDS - {"CF-VID-01"}
    )


def test_local_archetype_catalog_fails_closed_when_configured_catalog_missing(tmp_path):
    settings = Settings(storage_root=tmp_path / "missing-storage")

    with pytest.raises(FileNotFoundError):
        LocalArchetypeCatalogService(settings).load()


def test_local_archetype_catalog_requires_core_ids():
    with pytest.raises(ValueError, match="Missing required"):
        LocalArchetypeCatalog.model_validate({"catalog_version": "bad", "archetypes": []})


def test_local_archetype_service_filter_and_get():
    service = LocalArchetypeCatalogService()

    video = service.list_archetypes("video")
    assert video
    assert all(archetype.modality == "video" for archetype in video)
    assert service.get_archetype("CF-VID-01") is not None
    assert service.get_archetype("CF-VID-99") is None


def test_local_archetype_routes():
    client = TestClient(app)

    assert client.post("/local-archetypes/catalog", json={}).status_code == 405
    assert client.post("/local-archetypes", json={}).status_code == 405
    assert client.post("/local-archetypes/CF-VID-01", json={}).status_code == 405

    catalog_response = client.get("/local-archetypes/catalog")
    assert catalog_response.status_code == 200
    assert len(catalog_response.json()["archetypes"]) >= len(CANONICAL_REGISTRY_ARCHETYPE_IDS)

    list_response = client.get("/local-archetypes", params={"modality": "video"})
    assert list_response.status_code == 200
    assert list_response.json()
    assert all(item["modality"] == "video" for item in list_response.json())

    get_response = client.get("/local-archetypes/CF-VID-01")
    assert get_response.status_code == 200
    assert get_response.json()["archetype_id"] == "CF-VID-01"
    assert get_response.json()["enabled"] is False
    assert get_response.json()["readiness"] != "ready"

    missing_response = client.get("/local-archetypes/CF-VID-99")
    assert missing_response.status_code == 404
