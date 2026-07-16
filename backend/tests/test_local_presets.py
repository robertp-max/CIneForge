import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.schemas.local_presets import LocalPresetCatalog, QualityProfile
from backend.app.services.local_presets import LocalPresetCatalogService


def test_local_preset_catalog_has_exactly_64_disabled_presets():
    catalog = LocalPresetCatalogService().load()

    assert catalog.catalog_version == "2026-07-local-m1"
    assert len(catalog.presets) == 64
    assert [preset.preset_id for preset in catalog.presets] == [
        f"CF-PRESET-{index:03d}" for index in range(1, 65)
    ]
    assert {preset.model_key for preset in catalog.presets} == {"ltx2_3_22b_distilled_1_1_fp8"}
    assert all(preset.enabled is False for preset in catalog.presets)
    assert {preset.quality_profile for preset in catalog.presets} == set(QualityProfile)
    assert all(preset.readiness in {"benchmark_required", "blocked"} for preset in catalog.presets)


def test_local_preset_catalog_fails_closed_when_configured_catalog_missing(tmp_path: Path):
    settings = Settings(storage_root=tmp_path / "missing-storage")

    with pytest.raises(FileNotFoundError):
        LocalPresetCatalogService(settings).load()


def test_local_preset_catalog_rejects_wrong_count(tmp_path: Path):
    bad = {
        "catalog_version": "bad",
        "presets": [],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly 64"):
        LocalPresetCatalog.model_validate({**bad, "source_path": path})


def test_local_preset_service_filter_and_get():
    service = LocalPresetCatalogService()

    draft = service.list_presets(QualityProfile.draft)
    assert draft
    assert all(preset.quality_profile == QualityProfile.draft for preset in draft)
    assert service.get_preset("CF-PRESET-001") is not None
    assert service.get_preset("CF-PRESET-999") is None


def test_local_preset_routes():
    client = TestClient(app)

    assert client.post("/local-presets/catalog", json={}).status_code == 405
    assert client.post("/local-presets", json={}).status_code == 405
    assert client.post("/local-presets/CF-PRESET-001", json={}).status_code == 405

    catalog_response = client.get("/local-presets/catalog")
    assert catalog_response.status_code == 200
    assert len(catalog_response.json()["presets"]) == 64

    list_response = client.get("/local-presets", params={"quality_profile": "draft"})
    assert list_response.status_code == 200
    assert list_response.json()
    assert all(item["quality_profile"] == "draft" for item in list_response.json())

    get_response = client.get("/local-presets/CF-PRESET-001")
    assert get_response.status_code == 200
    assert get_response.json()["preset_id"] == "CF-PRESET-001"
    assert get_response.json()["enabled"] is False
    assert get_response.json()["readiness"] != "ready"

    missing_response = client.get("/local-presets/CF-PRESET-999")
    assert missing_response.status_code == 404
