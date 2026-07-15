"""Local file-backed Comfy job manifest store.

This is the local-only queue/spool boundary. It prepares output folders and
records intended jobs, but it never talks to ComfyUI or starts generation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError, not_found
from backend.app.schemas.local_jobs import LocalJobCreate, LocalJobManifest
from backend.app.services.local_archetypes import LocalArchetypeCatalogService
from backend.app.services.local_presets import LocalPresetCatalogService
from backend.app.services.local_runtime import (
    LTX23_SELECTED_FP8,
    SELECTED_FP8_SHA256,
    SELECTED_MODEL_KEY,
    prepare_project_output,
)
from backend.app.services.production_planner import validate_ltx_dimensions, validate_ltx_frame_count
from backend.app.services.workflows.template_service import WorkflowTemplateService
from backend.app.utils.path_safety import sanitize_output_prefix, sanitize_project_folder

_MANIFEST_ADAPTER = TypeAdapter(LocalJobManifest)


class LocalJobStore:
    def __init__(self, settings: Settings | None = None, root: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = root or (self.settings.storage_root / "local_jobs")
        self.audit_path = self.root / "events.jsonl"

    def create(self, request: LocalJobCreate) -> LocalJobManifest:
        preset = self._validate_request_contract(request)
        job_id = uuid4()
        project_folder = sanitize_project_folder(request.project_key)
        run_stem = sanitize_output_prefix(request.run_stem)
        output = prepare_project_output(self.settings, project_folder, run_stem)
        workflow_snapshot = self._snapshot_workflow_if_available(
            request,
            preset.default_archetype_id,
            output["filename_prefix"],
            job_id,
        )
        manifest_path = self.root / f"{job_id}.json"
        manifest = LocalJobManifest(
            job_id=job_id,
            state="blocked_offline" if preset.readiness == "blocked" else "prepared_offline",
            created_at=datetime.now(UTC),
            project_key=request.project_key,
            project_folder=project_folder,
            run_stem=run_stem,
            output_root=Path(output["output_root"]),
            project_output_dir=Path(output["project_output_dir"]),
            filename_prefix=output["filename_prefix"],
            manifest_path=manifest_path,
            preset_id=request.preset_id,
            preset_readiness=preset.readiness.value,
            archetype_id=preset.default_archetype_id,
            model_key=request.model_key,
            quality_profile=request.quality_profile,
            fp8_artifact_sha256=SELECTED_FP8_SHA256,
            workflow_template_id=workflow_snapshot.get("workflow_template_id"),
            workflow_template_version=workflow_snapshot.get("workflow_template_version"),
            workflow_snapshot_path=workflow_snapshot.get("workflow_snapshot_path"),
            runtime_patch_payload=workflow_snapshot.get("runtime_patch_payload"),
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            seed=request.seed,
            width=request.width,
            height=request.height,
            frames=request.frames,
            fps=request.fps,
            steps=request.steps,
        )
        self._write_manifest(manifest)
        self._append_event(
            {
                "event": "local_job_created",
                "job_id": str(job_id),
                "state": manifest.state,
                "filename_prefix": manifest.filename_prefix,
                "generation_submitted": False,
                "created_at": manifest.created_at.isoformat(),
            }
        )
        return manifest

    def _validate_request_contract(self, request: LocalJobCreate):
        preset = LocalPresetCatalogService(self.settings).get_preset(request.preset_id)
        if preset is None:
            raise ValidationError(f"Unknown local preset: {request.preset_id}")
        archetype = LocalArchetypeCatalogService(self.settings).get_archetype(preset.default_archetype_id)
        if archetype is None:
            raise ValidationError(f"Preset {preset.preset_id} references missing archetype {preset.default_archetype_id}")
        if request.model_key != SELECTED_MODEL_KEY:
            raise ValidationError(f"Only selected local model is allowed: {SELECTED_MODEL_KEY}")
        if preset.model_key != request.model_key:
            raise ValidationError(f"Preset {preset.preset_id} is bound to model {preset.model_key}")
        if request.quality_profile != preset.quality_profile:
            raise ValidationError(
                f"Preset {preset.preset_id} requires quality profile {preset.quality_profile.value}"
            )
        if archetype.archetype_id.startswith("CF-VID"):
            validate_ltx_dimensions(request.width or 512, request.height or 288)
            validate_ltx_frame_count(request.frames or 17)
        return preset

    def _snapshot_workflow_if_available(
        self,
        request: LocalJobCreate,
        archetype_id: str,
        filename_prefix: str,
        job_id: UUID,
    ) -> dict[str, object | None]:
        if archetype_id != "CF-VID-01":
            return {
                "workflow_template_id": None,
                "workflow_template_version": None,
                "workflow_snapshot_path": None,
                "runtime_patch_payload": None,
            }
        template_dir = self._workflow_template_dir("cf_vid_01_ltx23_single_stage")
        service = WorkflowTemplateService(snapshot_root=self.settings.workflow_snapshot_root)
        workflow, api_manifest = service.load_template(template_dir)
        patch_payload = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width or 512,
            "height": request.height or 288,
            "frames": request.frames or 17,
            "fps": request.fps or 24,
            "seed": request.seed or 0,
            "steps": request.steps or 4,
            "model_checkpoint": LTX23_SELECTED_FP8.name,
            "text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors",
            "output_prefix": filename_prefix,
        }
        result = service.apply_patch_and_snapshot(workflow, api_manifest, patch_payload, run_id=job_id)
        return {
            "workflow_template_id": api_manifest.template_id,
            "workflow_template_version": api_manifest.version,
            "workflow_snapshot_path": result.snapshot_path,
            "runtime_patch_payload": patch_payload,
        }

    def _workflow_template_dir(self, template_id: str) -> Path:
        return self.settings.workflow_template_root / template_id

    def get(self, job_id: UUID) -> LocalJobManifest:
        path = self.root / f"{job_id}.json"
        if not path.is_file():
            raise not_found("Local job not found.")
        return _MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8"))

    def list(self, limit: int = 25) -> list[LocalJobManifest]:
        if limit < 1:
            return []
        if not self.root.is_dir():
            return []
        manifests: list[LocalJobManifest] = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(manifests) >= limit:
                break
            manifests.append(_MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8")))
        return manifests

    def _write_manifest(self, manifest: LocalJobManifest) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json")
        temp_path = manifest.manifest_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(manifest.manifest_path)

    def _append_event(self, event: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
