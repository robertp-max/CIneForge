"""File-backed offline post-production plan manifests.

This store records deterministic FFmpeg assembly intent and provenance before
any execution path is considered. It never runs FFmpeg.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError, not_found
from backend.app.schemas.post_production import (
    PostProductionAssemblyPlanCreate,
    PostProductionPlanErrorRecord,
    PostProductionPlanManifest,
    PostProductionPlanSuccessRecord,
)
from backend.app.schemas.production import FFmpegAssemblyPlan
from backend.app.services.ffmpeg.service import validate_sha256_hex
from backend.app.services.post_production import PostProductionService

_MANIFEST_ADAPTER = TypeAdapter(PostProductionPlanManifest)


class PostProductionPlanStore:
    def __init__(
        self,
        settings: Settings | None = None,
        root: Path | None = None,
        service: PostProductionService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.root = root or (self.settings.storage_root / "post_production_plans")
        self.audit_path = self.root / "events.jsonl"
        self.service = service or PostProductionService()

    def create_from_request(self, request: PostProductionAssemblyPlanCreate) -> PostProductionPlanManifest:
        plan = self.service.build_assembly_plan(
            request.clips,
            target_duration_sec=request.target_duration_sec,
            geometry=request.geometry,
            fps=request.fps,
            output_path=request.output_path,
        )
        return self.create_from_plan(plan)

    def create_from_plan(self, plan: FFmpegAssemblyPlan) -> PostProductionPlanManifest:
        command = self.service.build_command(plan)
        if plan.output_path is None:
            # build_command already guards this, keep type narrowing explicit.
            raise ValueError("Assembly output_path is required")
        plan_id = uuid4()
        manifest_path = self.root / f"{plan_id}.json"
        manifest = PostProductionPlanManifest(
            plan_id=plan_id,
            created_at=datetime.now(UTC),
            manifest_path=manifest_path,
            command_template_id=plan.command_template_id,
            command=command,
            input_paths=[clip.path for clip in plan.clips],
            input_hashes=list(plan.input_hashes),
            probe_count=sum(1 for clip in plan.clips if clip.probe_json is not None),
            output_path=plan.output_path,
            target_duration_sec=plan.target_duration_sec,
            calculated_duration_sec=plan.calculated_duration_sec,
            exact_duration_preserved=plan.exact_duration_preserved,
            plan=plan,
        )
        self._write_manifest(manifest)
        self._append_event(
            {
                "event": "post_production_plan_created",
                "plan_id": str(plan_id),
                "command_template_id": plan.command_template_id,
                "execution_submitted": False,
                "created_at": manifest.created_at.isoformat(),
            }
        )
        return manifest

    def get(self, plan_id: UUID) -> PostProductionPlanManifest:
        path = self.root / f"{plan_id}.json"
        if not path.is_file():
            raise not_found("Post-production plan not found.")
        return _MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8"))

    def list(self, limit: int = 25) -> list[PostProductionPlanManifest]:
        if limit < 1 or not self.root.is_dir():
            return []
        manifests: list[PostProductionPlanManifest] = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(manifests) >= limit:
                break
            manifests.append(_MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8")))
        return manifests

    def record_success(
        self,
        plan_id: UUID,
        record: PostProductionPlanSuccessRecord,
    ) -> PostProductionPlanManifest:
        manifest = self.get(plan_id)
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "completed_offline_recorded",
                "updated_at": now,
                "completed_at": now,
                "ffmpeg_job_id": record.ffmpeg_job_id,
                "output_sha256": validate_sha256_hex(record.output_sha256),
                "final_probe_json": record.final_probe_json,
                "error_message": None,
            }
        )
        self._write_manifest(updated)
        self._append_event(
            {
                "event": "post_production_plan_result_recorded",
                "plan_id": str(plan_id),
                "state": updated.state,
                "output_sha256": updated.output_sha256,
                "recorded_at": now.isoformat(),
            }
        )
        return updated

    def record_error(
        self,
        plan_id: UUID,
        record: PostProductionPlanErrorRecord,
    ) -> PostProductionPlanManifest:
        manifest = self.get(plan_id)
        error_message = record.error_message.strip()
        if not error_message:
            raise ValidationError("Post-production error_message cannot be blank")
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "failed_offline_recorded",
                "updated_at": now,
                "completed_at": now,
                "ffmpeg_job_id": record.ffmpeg_job_id,
                "output_sha256": None,
                "final_probe_json": None,
                "error_message": error_message,
            }
        )
        self._write_manifest(updated)
        self._append_event(
            {
                "event": "post_production_plan_error_recorded",
                "plan_id": str(plan_id),
                "state": updated.state,
                "recorded_at": now.isoformat(),
            }
        )
        return updated

    def _write_manifest(self, manifest: PostProductionPlanManifest) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json")
        temp_path = manifest.manifest_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(manifest.manifest_path)

    def _append_event(self, event: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
