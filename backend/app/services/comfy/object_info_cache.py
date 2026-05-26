import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.errors import ValidationError
from backend.app.services.workflows.template_service import WorkflowManifest, WorkflowTemplateService


@dataclass(frozen=True)
class ObjectInfoRefreshResult:
    refreshed: bool
    error: str | None = None


class ObjectInfoCacheService:
    def __init__(self, object_info: dict[str, Any] | None = None) -> None:
        self.object_info: dict[str, Any] | None = object_info
        self.loaded_at: datetime | None = datetime.now(UTC) if object_info is not None else None
        self.last_refresh_error: str | None = None

    def load_fixture(self, path: Path) -> dict[str, Any]:
        return self.load_dict(json.loads(path.read_text(encoding="utf-8")))

    def load_dict(self, object_info: dict[str, Any]) -> dict[str, Any]:
        self.object_info = object_info
        self.loaded_at = datetime.now(UTC)
        self.last_refresh_error = None
        return object_info

    async def refresh(self, client: Any) -> ObjectInfoRefreshResult:
        try:
            self.load_dict(await client.get_object_info())
        except Exception as exc:
            self.last_refresh_error = str(exc)
            return ObjectInfoRefreshResult(refreshed=False, error=self.last_refresh_error)
        return ObjectInfoRefreshResult(refreshed=True)

    def validate_manifest_compatibility(self, manifest: WorkflowManifest) -> None:
        object_info = self._require_object_info()
        for semantic_key, ref in manifest.nodes.items():
            self.validate_class(ref.expected_class_type, semantic_key=semantic_key)
            self.validate_input(
                ref.expected_class_type,
                ref.input_name,
                semantic_key=semantic_key,
                object_info=object_info,
            )

    def validate_workflow_manifest(self, workflow: dict[str, Any], manifest: WorkflowManifest) -> None:
        WorkflowTemplateService().validate_manifest(workflow, manifest, self._require_object_info())

    def validate_class(self, class_type: str, *, semantic_key: str | None = None) -> None:
        object_info = self._require_object_info()
        if class_type not in object_info:
            suffix = f" for {semantic_key}" if semantic_key else ""
            raise ValidationError(f"Object info missing class {class_type}{suffix}")

    def validate_input(
        self,
        class_type: str,
        input_name: str,
        *,
        semantic_key: str | None = None,
        object_info: dict[str, Any] | None = None,
    ) -> None:
        snapshot = object_info or self._require_object_info()
        class_info = snapshot.get(class_type)
        if class_info is None:
            suffix = f" for {semantic_key}" if semantic_key else ""
            raise ValidationError(f"Object info missing class {class_type}{suffix}")

        input_info = class_info.get("input") or {}
        required = input_info.get("required") or {}
        optional = input_info.get("optional") or {}
        if input_name not in required and input_name not in optional:
            suffix = f" for {semantic_key}" if semantic_key else ""
            raise ValidationError(f"Object info class {class_type} missing input {input_name}{suffix}")

    def _require_object_info(self) -> dict[str, Any]:
        if self.object_info is None:
            raise ValidationError("Object info cache is empty")
        return self.object_info
