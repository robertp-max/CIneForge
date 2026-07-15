"""Local file-backed workflow archetype catalog loader."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.local_archetypes import LocalArchetype, LocalArchetypeCatalog


class LocalArchetypeCatalogService:
    def __init__(self, settings: Settings | None = None, catalog_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.catalog_path = catalog_path or (self.settings.storage_root / "archetypes" / "catalog.json")

    def load(self) -> LocalArchetypeCatalog:
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        for item in data.get("archetypes", []):
            source_path = item.get("source_path")
            item["source_exists"] = bool(source_path and Path(source_path).is_file())
        data["source_path"] = self.catalog_path
        return LocalArchetypeCatalog.model_validate(data)

    def list_archetypes(self, modality: str | None = None) -> list[LocalArchetype]:
        archetypes = self.load().archetypes
        if modality is None:
            return archetypes
        key = modality.strip().lower()
        return [archetype for archetype in archetypes if archetype.modality.lower() == key]

    def get_archetype(self, archetype_id: str) -> LocalArchetype | None:
        for archetype in self.load().archetypes:
            if archetype.archetype_id == archetype_id:
                return archetype
        return None
