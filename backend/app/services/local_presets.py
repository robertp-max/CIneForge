"""Local file-backed preset catalog loader."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.local_presets import LocalPreset, LocalPresetCatalog, QualityProfile


class LocalPresetCatalogService:
    def __init__(self, settings: Settings | None = None, catalog_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.catalog_path = catalog_path or (self.settings.storage_root / "presets" / "catalog.json")

    def load(self) -> LocalPresetCatalog:
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        data["source_path"] = self.catalog_path
        return LocalPresetCatalog.model_validate(data)

    def list_presets(self, quality_profile: QualityProfile | None = None) -> list[LocalPreset]:
        catalog = self.load()
        if quality_profile is None:
            return catalog.presets
        return [preset for preset in catalog.presets if preset.quality_profile == quality_profile]

    def get_preset(self, preset_id: str) -> LocalPreset | None:
        for preset in self.load().presets:
            if preset.preset_id == preset_id:
                return preset
        return None
