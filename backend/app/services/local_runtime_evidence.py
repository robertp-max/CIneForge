"""DB-free read-only runtime evidence loader."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.local_runtime_evidence import LocalRuntimeEvidence


class LocalRuntimeEvidenceService:
    def __init__(self, settings: Settings | None = None, evidence_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.evidence_path = evidence_path or (self.settings.storage_root / "runtime" / "cf_vid_01_smoke_evidence.json")

    def get_cf_vid01_smoke(self) -> LocalRuntimeEvidence:
        return LocalRuntimeEvidence.model_validate_json(self.evidence_path.read_text(encoding="utf-8"))

    def list_evidence(self) -> list[LocalRuntimeEvidence]:
        if not self.evidence_path.is_file():
            return []
        return [self.get_cf_vid01_smoke()]
