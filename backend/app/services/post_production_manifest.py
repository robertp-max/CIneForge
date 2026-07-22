"""File-backed offline post-production plan manifests.

This store records deterministic FFmpeg assembly intent and provenance before
any execution path is considered. It never runs FFmpeg.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError, not_found
from backend.app.schemas.post_production import (
    PostProductionAssemblyPlanCreate,
    PostProductionPlanErrorRecord,
    PostProductionPlanManifest,
    PostProductionPlanSuccessRecord,
    PostProductionRecipeCommandErrorRecord,
    PostProductionRecipeCommandManifest,
    PostProductionRecipeCommandSuccessRecord,
)
from backend.app.schemas.production import FFmpegAssemblyPlan
from backend.app.services.ffmpeg.service import RecipeCommandBuildResult, validate_sha256_hex
from backend.app.services.post_production import PostProductionService
from backend.app.utils.path_safety import resolve_inside

_MANIFEST_ADAPTER = TypeAdapter(PostProductionPlanManifest)
_RECIPE_COMMAND_MANIFEST_ADAPTER = TypeAdapter(PostProductionRecipeCommandManifest)


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
        self.recipe_command_root = self.root / "recipe_commands"
        self.recipe_command_audit_path = self.recipe_command_root / "events.jsonl"
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

    def create_from_recipe_command(
        self,
        result: RecipeCommandBuildResult,
        *,
        input_probe_jsons: list[dict[str, Any]] | None = None,
    ) -> PostProductionRecipeCommandManifest:
        self.service.ffmpeg.validate_command_template_id(result.command_template_id)
        if not result.command:
            raise ValidationError("Recipe command manifest requires a structured command array")
        if any(not isinstance(argument, str) or argument == "" for argument in result.command):
            raise ValidationError("Recipe command manifest command arguments must be non-empty strings")
        if not result.input_paths:
            raise ValidationError("Recipe command manifest requires at least one input path")
        if len(result.input_paths) != len(result.input_hashes):
            raise ValidationError("Recipe command manifest requires one input hash per input path")
        if input_probe_jsons is not None and len(input_probe_jsons) != len(result.input_paths):
            raise ValidationError(
                "Recipe command manifest requires one input probe per input path when probes are provided"
            )
        input_hashes = [validate_sha256_hex(value) for value in result.input_hashes]
        input_paths = [self._resolve_recipe_command_path(path) for path in result.input_paths]
        output_path = (
            self._resolve_recipe_command_path(result.output_path) if result.output_path is not None else None
        )
        persisted_input_probe_jsons = (
            [dict(probe) for probe in input_probe_jsons] if input_probe_jsons is not None else None
        )

        plan_id = uuid4()
        manifest_path = self.recipe_command_root / f"{plan_id}.json"
        manifest = PostProductionRecipeCommandManifest(
            plan_id=plan_id,
            created_at=datetime.now(UTC),
            manifest_path=manifest_path,
            command_template_id=result.command_template_id,
            command=list(result.command),
            input_paths=input_paths,
            input_hashes=input_hashes,
            input_probe_jsons=persisted_input_probe_jsons,
            input_probe_count=len(persisted_input_probe_jsons) if persisted_input_probe_jsons is not None else 0,
            output_path=output_path,
        )
        self._write_recipe_command_manifest(manifest)
        self._append_recipe_command_event(
            {
                "event": "post_production_recipe_command_plan_created",
                "plan_id": str(plan_id),
                "command_template_id": result.command_template_id,
                "execution_submitted": False,
                "created_at": manifest.created_at.isoformat(),
            }
        )
        return manifest

    def get_recipe_command(self, plan_id: UUID) -> PostProductionRecipeCommandManifest:
        path = self.recipe_command_root / f"{plan_id}.json"
        if not path.is_file():
            raise not_found("Post-production recipe command plan not found.")
        return _RECIPE_COMMAND_MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8"))

    def list_recipe_commands(self, limit: int = 25) -> list[PostProductionRecipeCommandManifest]:
        if limit < 1 or not self.recipe_command_root.is_dir():
            return []
        manifests: list[PostProductionRecipeCommandManifest] = []
        for path in sorted(self.recipe_command_root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(manifests) >= limit:
                break
            manifests.append(_RECIPE_COMMAND_MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8")))
        return manifests

    def record_recipe_command_success(
        self,
        plan_id: UUID,
        record: PostProductionRecipeCommandSuccessRecord,
    ) -> PostProductionRecipeCommandManifest:
        manifest = self.get_recipe_command(plan_id)
        now = datetime.now(UTC)
        updated_at = record.updated_at or now
        completed_at = record.completed_at or updated_at
        updated = manifest.model_copy(
            update={
                "state": "completed_offline_recorded",
                "updated_at": updated_at,
                "completed_at": completed_at,
                "execution_submitted": False,
                "output_sha256": validate_sha256_hex(record.output_sha256),
                "final_probe_json": record.final_probe_json,
                "error": None,
            }
        )
        self._write_recipe_command_manifest(updated)
        self._append_recipe_command_event(
            {
                "event": "post_production_recipe_command_plan_result_recorded",
                "plan_id": str(plan_id),
                "state": updated.state,
                "output_sha256": updated.output_sha256,
                "recorded_at": now.isoformat(),
            }
        )
        return updated

    def record_recipe_execution_started(
        self,
        plan_id: UUID,
        *,
        ffmpeg_job_id: UUID,
        requested_by: str,
    ) -> PostProductionRecipeCommandManifest:
        manifest = self.get_recipe_command(plan_id)
        if manifest.state != "planned_offline" or manifest.execution_submitted:
            raise ValidationError("Recipe command plan is not eligible for first execution")
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "running",
                "updated_at": now,
                "execution_submitted": True,
                "ffmpeg_job_id": ffmpeg_job_id,
                "error": None,
            }
        )
        self._write_recipe_command_manifest(updated)
        self._append_recipe_command_event(
            {
                "event": "post_production_recipe_command_execution_started",
                "plan_id": str(plan_id),
                "requested_by": requested_by,
                "ffmpeg_job_id": str(ffmpeg_job_id),
                "execution_submitted": True,
                "created_at": now.isoformat(),
            }
        )
        return updated

    def record_recipe_execution_success(
        self,
        plan_id: UUID,
        *,
        output_sha256: str,
        final_probe_json: dict[str, Any] | None,
    ) -> PostProductionRecipeCommandManifest:
        manifest = self.get_recipe_command(plan_id)
        if manifest.state != "running" or not manifest.execution_submitted:
            raise ValidationError("Recipe command execution is not running")
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "complete",
                "updated_at": now,
                "completed_at": now,
                "execution_submitted": True,
                "output_sha256": validate_sha256_hex(output_sha256),
                "final_probe_json": final_probe_json,
                "error": None,
            }
        )
        self._write_recipe_command_manifest(updated)
        self._append_recipe_command_event(
            {
                "event": "post_production_recipe_command_execution_completed",
                "plan_id": str(plan_id),
                "output_sha256": updated.output_sha256,
                "created_at": now.isoformat(),
            }
        )
        return updated

    def record_recipe_execution_error(
        self,
        plan_id: UUID,
        *,
        error: str,
    ) -> PostProductionRecipeCommandManifest:
        manifest = self.get_recipe_command(plan_id)
        message = error.strip()
        if not message:
            raise ValidationError("Recipe command execution error cannot be blank")
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "failed",
                "updated_at": now,
                "completed_at": now,
                "execution_submitted": True,
                "output_sha256": None,
                "final_probe_json": None,
                "error": message[:10_000],
            }
        )
        self._write_recipe_command_manifest(updated)
        self._append_recipe_command_event(
            {
                "event": "post_production_recipe_command_execution_failed",
                "plan_id": str(plan_id),
                "error": updated.error,
                "created_at": now.isoformat(),
            }
        )
        return updated

    def record_recipe_command_error(
        self,
        plan_id: UUID,
        record: PostProductionRecipeCommandErrorRecord,
    ) -> PostProductionRecipeCommandManifest:
        manifest = self.get_recipe_command(plan_id)
        error = (record.error_message if record.error_message is not None else record.error) or ""
        error = error.strip()
        if not error:
            raise ValidationError("Post-production recipe command error cannot be blank")
        now = datetime.now(UTC)
        updated_at = record.updated_at or now
        completed_at = record.completed_at or updated_at
        updated = manifest.model_copy(
            update={
                "state": "failed_offline_recorded",
                "updated_at": updated_at,
                "completed_at": completed_at,
                "execution_submitted": False,
                "output_sha256": None,
                "final_probe_json": None,
                "error": error,
            }
        )
        self._write_recipe_command_manifest(updated)
        self._append_recipe_command_event(
            {
                "event": "post_production_recipe_command_plan_error_recorded",
                "plan_id": str(plan_id),
                "state": updated.state,
                "recorded_at": now.isoformat(),
            }
        )
        return updated

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

    def record_execution_started(
        self,
        plan_id: UUID,
        *,
        ffmpeg_job_id: UUID,
        requested_by: str,
    ) -> PostProductionPlanManifest:
        manifest = self.get(plan_id)
        if manifest.state != "planned_offline" or manifest.execution_submitted:
            raise ValidationError("Post-production plan is not eligible for first execution")
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "running",
                "updated_at": now,
                "execution_submitted": True,
                "ffmpeg_job_id": ffmpeg_job_id,
                "error_message": None,
            }
        )
        self._write_manifest(updated)
        self._append_event(
            {
                "event": "post_production_execution_started",
                "plan_id": str(plan_id),
                "ffmpeg_job_id": str(ffmpeg_job_id),
                "requested_by": requested_by,
                "execution_submitted": True,
                "created_at": now.isoformat(),
            }
        )
        return updated

    def record_execution_success(
        self,
        plan_id: UUID,
        *,
        output_sha256: str,
        final_probe_json: dict[str, Any],
    ) -> PostProductionPlanManifest:
        manifest = self.get(plan_id)
        if manifest.state != "running" or not manifest.execution_submitted:
            raise ValidationError("Post-production execution is not running")
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "complete",
                "updated_at": now,
                "completed_at": now,
                "execution_submitted": True,
                "output_sha256": validate_sha256_hex(output_sha256),
                "final_probe_json": final_probe_json,
                "error_message": None,
            }
        )
        self._write_manifest(updated)
        self._append_event(
            {
                "event": "post_production_execution_completed",
                "plan_id": str(plan_id),
                "ffmpeg_job_id": str(updated.ffmpeg_job_id),
                "output_sha256": updated.output_sha256,
                "created_at": now.isoformat(),
            }
        )
        return updated

    def record_execution_error(self, plan_id: UUID, *, error_message: str) -> PostProductionPlanManifest:
        manifest = self.get(plan_id)
        message = error_message.strip()
        if not message:
            raise ValidationError("Post-production execution error cannot be blank")
        now = datetime.now(UTC)
        updated = manifest.model_copy(
            update={
                "state": "failed",
                "updated_at": now,
                "completed_at": now,
                "execution_submitted": True,
                "output_sha256": None,
                "final_probe_json": None,
                "error_message": message[:10_000],
            }
        )
        self._write_manifest(updated)
        self._append_event(
            {
                "event": "post_production_execution_failed",
                "plan_id": str(plan_id),
                "ffmpeg_job_id": str(updated.ffmpeg_job_id),
                "error_message": updated.error_message,
                "created_at": now.isoformat(),
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

    def _resolve_recipe_command_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        return resolve_inside(
            self.service.ffmpeg.storage_root,
            candidate,
            allow_absolute=self.service.ffmpeg.settings.allow_absolute_input_paths or candidate.is_absolute(),
        )

    def _write_manifest(self, manifest: PostProductionPlanManifest) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json")
        temp_path = manifest.manifest_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(manifest.manifest_path)

    def _write_recipe_command_manifest(self, manifest: PostProductionRecipeCommandManifest) -> None:
        self.recipe_command_root.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json")
        temp_path = manifest.manifest_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(manifest.manifest_path)

    def _append_event(self, event: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def _append_recipe_command_event(self, event: dict) -> None:
        self.recipe_command_root.mkdir(parents=True, exist_ok=True)
        with self.recipe_command_audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
