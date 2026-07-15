"""Canonical workflow registry for the local CineForge production lane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.production import CanonicalWorkflowRecord
from backend.app.services.workflows.template_service import sha256_json


_RECORDS = TypeAdapter(list[CanonicalWorkflowRecord])

CANONICAL_ARCHETYPE_IDS = [
    "CF-IMG-01",
    "CF-IMG-02",
    "CF-IMG-03",
    "CF-IMG-04",
    "CF-IMG-05",
    "CF-VID-01",
    "CF-VID-02",
    "CF-VID-03",
    "CF-VID-04",
    "CF-VID-05",
    "CF-UTIL-01",
    "CF-POST-01",
]


class WorkflowRegistryService:
    def __init__(self, settings: Settings | None = None, registry_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.registry_path = registry_path or (self.settings.storage_root / "workflow_registry" / "catalog.json")

    def load(self) -> list[CanonicalWorkflowRecord]:
        if not self.registry_path.is_file():
            raise FileNotFoundError(self.registry_path)
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        records = _RECORDS.validate_python(payload.get("workflows", payload))
        seen = {record.archetype_id for record in records}
        missing = [item for item in CANONICAL_ARCHETYPE_IDS if item not in seen]
        if missing:
            raise ValidationError(f"Canonical workflow registry missing archetypes: {', '.join(missing)}")
        return [self._with_live_evidence(record) for record in records]

    def get(self, archetype_id: str) -> CanonicalWorkflowRecord | None:
        for record in self.load():
            if record.archetype_id == archetype_id:
                return record
        return None

    def require(self, archetype_id: str) -> CanonicalWorkflowRecord:
        record = self.get(archetype_id)
        if record is None:
            raise ValidationError(f"Unknown archetype: {archetype_id}")
        return record

    def production_ready(self, archetype_id: str) -> bool:
        record = self.require(archetype_id)
        return bool(record.implemented and record.dependency_verified and record.locally_tested and record.benchmark_passed)

    def _with_live_evidence(self, record: CanonicalWorkflowRecord) -> CanonicalWorkflowRecord:
        data = record.model_dump()
        blocked = list(record.blocked_reasons)
        hard_blocked = False
        if record.ui_graph_path:
            ui_path = Path(record.ui_graph_path)
            data["ui_graph_path"] = ui_path
            if ui_path.is_file():
                try:
                    ui_hash = sha256_json(json.loads(ui_path.read_text(encoding="utf-8")))
                    data["ui_sha256"] = data.get("ui_sha256") or ui_hash
                    if record.ui_sha256 and ui_hash != record.ui_sha256:
                        hard_blocked = True
                        blocked.append(f"UI graph hash mismatch: expected {record.ui_sha256}, found {ui_hash}")
                except Exception as exc:
                    hard_blocked = True
                    blocked.append(f"UI graph unreadable: {exc}")
            else:
                hard_blocked = True
                blocked.append(f"UI graph missing: {ui_path}")
        if record.api_graph_path:
            api_path = Path(record.api_graph_path)
            data["api_graph_path"] = api_path
            if api_path.is_file():
                try:
                    api_hash = sha256_json(json.loads(api_path.read_text(encoding="utf-8")))
                    data["api_sha256"] = data.get("api_sha256") or api_hash
                    if record.api_sha256 and api_hash != record.api_sha256:
                        hard_blocked = True
                        blocked.append(f"API graph hash mismatch: expected {record.api_sha256}, found {api_hash}")
                except Exception as exc:
                    hard_blocked = True
                    blocked.append(f"API graph unreadable: {exc}")
            else:
                hard_blocked = True
                blocked.append(f"API graph missing: {api_path}")
        deps = []
        dependency_verified = record.dependency_verified
        for dep in record.dependencies:
            dep_data = dep.model_dump()
            path = dep.path
            if path:
                exists = Path(path).is_file()
                dep_data["present"] = exists
                if dep.required and not exists:
                    hard_blocked = True
                    dependency_verified = False
                    blocked.append(f"Required dependency missing: {dep.key} ({path})")
            deps.append(dep_data)
        data["dependencies"] = deps
        data["dependency_verified"] = dependency_verified
        data["blocked_reasons"] = list(dict.fromkeys(blocked))
        if hard_blocked or (data["blocked_reasons"] and data.get("readiness") == "ready"):
            data["readiness"] = "blocked"
        return CanonicalWorkflowRecord.model_validate(data)


def registry_summary(records: list[CanonicalWorkflowRecord]) -> dict[str, Any]:
    return {
        "total": len(records),
        "implemented": sum(1 for record in records if record.implemented),
        "dependency_verified": sum(1 for record in records if record.dependency_verified),
        "locally_tested": sum(1 for record in records if record.locally_tested),
        "benchmark_passed": sum(1 for record in records if record.benchmark_passed),
        "publicly_enabled": sum(1 for record in records if record.publicly_enabled),
        "blocked": [record.archetype_id for record in records if record.blocked_reasons],
    }
