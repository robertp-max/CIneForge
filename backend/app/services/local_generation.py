"""File-backed offline semantic generation request manifest store.

This store is a safe handoff boundary. It evaluates production gates, records
request intent and evidence, and may snapshot an admitted workflow offline. It
never submits to ComfyUI, creates queue/database jobs, probes live runtimes, or
acquires GPU resources.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import not_found
from backend.app.db.base import Story, StoryboardVersion
from backend.app.schemas.local_generation import (
    SemanticCompiledWorkflowMetadata,
    SemanticGenerationRequestManifest,
    StoryboardHandoffManifestSummary,
    StoryboardHandoffReport,
    StoryboardHandoffRequest,
)
from backend.app.schemas.production import AspectRatio, SemanticGenerationRequest
from backend.app.services.production_planner import calculate_geometry, calculate_ltx_frame_plan
from backend.app.services.local_presets import LocalPresetCatalogService
from backend.app.services.production_gates import ProductionGateService
from backend.app.services.workflows.compiler import SemanticWorkflowCompiler
from backend.app.services.workflows.registry import WorkflowRegistryService
from backend.app.services.workflows.template_service import WorkflowTemplateService
from backend.app.utils.path_safety import (
    build_project_output_prefix,
    resolve_inside,
    sanitize_comfy_output_prefix,
    sanitize_output_prefix,
)

_MANIFEST_ADAPTER = TypeAdapter(SemanticGenerationRequestManifest)


class SemanticGenerationRequestManifestStore:
    def __init__(
        self,
        settings: Settings | None = None,
        root: Path | None = None,
        gate_service: ProductionGateService | None = None,
        compiler: SemanticWorkflowCompiler | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        expected_root = resolve_inside(self.settings.storage_root, Path("local_generation") / "semantic_requests")
        self.root = resolve_inside(expected_root, root, allow_absolute=True) if root is not None else expected_root
        self.audit_path = resolve_inside(self.root, "events.jsonl")
        registry = WorkflowRegistryService(self.settings)
        self.gate_service = gate_service or ProductionGateService(
            registry=registry,
            presets=LocalPresetCatalogService(self.settings),
        )
        self.compiler = compiler or SemanticWorkflowCompiler(
            registry=registry,
            template_service=WorkflowTemplateService(snapshot_root=self.settings.workflow_snapshot_root),
        )

    def create(self, request: SemanticGenerationRequest) -> SemanticGenerationRequestManifest:
        request = request.model_copy(update={"output_prefix": sanitize_comfy_output_prefix(request.output_prefix)})
        gate_report = self.gate_service.evaluate_generation_request(request)
        request_id = uuid4()
        manifest_path = resolve_inside(self.root, f"{request_id}.json")
        compiled_workflow_metadata = None
        workflow_snapshot_path = None
        state = "blocked_by_gates"

        if gate_report.allowed:
            compiled_workflow = self.compiler.compile(request)
            workflow_snapshot_path = compiled_workflow.workflow_snapshot_path
            compiled_workflow_metadata = SemanticCompiledWorkflowMetadata(
                archetype_id=compiled_workflow.archetype_id,
                template_id=compiled_workflow.template_id,
                template_version=compiled_workflow.template_version,
                workflow_api_sha256=compiled_workflow.workflow_api_sha256,
                patch_payload=compiled_workflow.patch_payload,
                output_prefix=compiled_workflow.output_prefix,
                production=compiled_workflow.production,
            )
            state = "prepared_offline"

        manifest = SemanticGenerationRequestManifest(
            request_id=request_id,
            state=state,
            created_at=datetime.now(UTC),
            manifest_path=manifest_path,
            request=request,
            gate_report=gate_report,
            generation_submitted=False,
            comfy_prompt_id=None,
            queue_job_id=None,
            workflow_snapshot_path=workflow_snapshot_path,
            compiled_workflow_metadata=compiled_workflow_metadata,
        )
        self._write_manifest(manifest)
        self._append_event(
            {
                "event": "semantic_generation_request_manifest_created",
                "request_id": str(request_id),
                "state": manifest.state,
                "gate_allowed": gate_report.allowed,
                "blocking_codes": [reason.code.value for reason in gate_report.blocking_reasons],
                "generation_submitted": False,
                "comfy_prompt_id": None,
                "queue_job_id": None,
                "created_at": manifest.created_at.isoformat(),
            }
        )
        return manifest

    def get(self, request_id: UUID) -> SemanticGenerationRequestManifest:
        path = resolve_inside(self.root, f"{request_id}.json")
        if not path.is_file():
            raise not_found("Semantic generation request manifest not found.")
        return _MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8"))

    def list(self, limit: int = 25) -> list[SemanticGenerationRequestManifest]:
        if limit < 1 or not self.root.is_dir():
            return []
        manifests: list[SemanticGenerationRequestManifest] = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(manifests) >= limit:
                break
            manifests.append(_MANIFEST_ADAPTER.validate_json(path.read_text(encoding="utf-8")))
        return manifests

    def _write_manifest(self, manifest: SemanticGenerationRequestManifest) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json")
        temp_path = manifest.manifest_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(manifest.manifest_path)

    def _append_event(self, event: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


class StoryboardSemanticHandoffService:
    """Create offline semantic request manifests from an approved storyboard snapshot.

    This bridge is explicit and non-executing: it reads the immutable approved
    storyboard version and persists semantic generation intent only.
    """

    def __init__(self, store: SemanticGenerationRequestManifestStore | None = None) -> None:
        self.store = store or SemanticGenerationRequestManifestStore()

    def create_handoff(self, db: Session, request: StoryboardHandoffRequest) -> StoryboardHandoffReport:
        story = db.get(Story, request.story_id)
        if story is None:
            return self._blocked(request.story_id, ["Story not found."])

        active_version_id = story.active_storyboard_version_id
        version = db.get(StoryboardVersion, active_version_id) if active_version_id is not None else None
        report = StoryboardHandoffReport(
            story_id=story.id,
            active_storyboard_version_id=active_version_id,
            active_storyboard_content_hash=version.content_hash if version is not None else None,
        )

        if story.approval_state != "approved":
            report.blocked_reasons.append("Storyboard handoff requires story.approval_state == approved.")
        if active_version_id is None:
            report.blocked_reasons.append("Storyboard handoff requires active_storyboard_version_id.")
        if version is None and active_version_id is not None:
            report.blocked_reasons.append("Active storyboard version was not found.")
        elif version is not None:
            if version.story_id != story.id:
                report.blocked_reasons.append("Active storyboard version does not belong to the story.")
            if version.status != "approved":
                report.blocked_reasons.append("Active storyboard version is not approved.")
            if not isinstance(version.snapshot_json, dict):
                report.blocked_reasons.append("Active storyboard version has no immutable snapshot.")
        if report.blocked_reasons:
            return report

        assert version is not None  # report guards above guarantee a version.
        snapshot = version.snapshot_json
        selected_shots = self._select_snapshot_shots(snapshot, request.shot_id)
        report.selected_shot_count = len(selected_shots)
        if request.shot_id is not None and not selected_shots:
            report.blocked_reasons.append("Requested shot_id is not present in the approved active storyboard snapshot.")
            return report
        if not selected_shots:
            report.blocked_reasons.append("Approved active storyboard snapshot contains no active shots to hand off.")
            return report

        story_fragment = snapshot.get("story", {}) if isinstance(snapshot.get("story", {}), dict) else {}
        for shot in selected_shots:
            semantic_request = self._build_semantic_request(
                request=request,
                story_fragment=story_fragment,
                shot=shot,
            )
            manifest = self.store.create(semantic_request)
            report.created_manifests.append(
                StoryboardHandoffManifestSummary(
                    shot_id=UUID(str(shot["id"])),
                    request_id=manifest.request_id,
                    state=manifest.state,
                    gate_allowed=manifest.gate_report.allowed,
                    blocking_codes=[reason.code.value for reason in manifest.gate_report.blocking_reasons],
                    generation_submitted=manifest.generation_submitted,
                )
            )
        return report

    @staticmethod
    def _blocked(story_id: UUID, reasons: list[str]) -> StoryboardHandoffReport:
        return StoryboardHandoffReport(story_id=story_id, blocked_reasons=reasons)

    @staticmethod
    def _select_snapshot_shots(snapshot: dict, shot_id: UUID | None) -> list[dict]:
        shots: list[dict] = []
        for chapter in snapshot.get("chapters", []):
            if not isinstance(chapter, dict):
                continue
            for scene in chapter.get("scenes", []):
                if not isinstance(scene, dict):
                    continue
                for shot in scene.get("shots", []):
                    if not isinstance(shot, dict) or "id" not in shot:
                        continue
                    if shot_id is None or str(shot_id) == str(shot["id"]):
                        shots.append(shot)
        return shots

    @staticmethod
    def _latest_prompt_package(shot: dict) -> dict | None:
        packages = [package for package in shot.get("prompt_packages", []) if isinstance(package, dict)]
        if not packages:
            return None
        return max(packages, key=lambda package: int(package.get("version") or 0))

    def _build_semantic_request(
        self,
        *,
        request: StoryboardHandoffRequest,
        story_fragment: dict,
        shot: dict,
    ) -> SemanticGenerationRequest:
        prompt_package = self._latest_prompt_package(shot)
        video_prompt = self._clean_text(prompt_package.get("video_prompt") if prompt_package else None)
        prompt = video_prompt or self._first_text(
            shot.get("visual_description"),
            shot.get("story_purpose"),
            shot.get("title"),
            story_fragment.get("title"),
            "Approved storyboard shot",
        )
        negative_prompt = self._clean_text(prompt_package.get("negative_prompt") if prompt_package else None) or ""
        duration_sec = float(shot.get("duration_sec") or 1.0)
        fps = 24
        frame_plan = calculate_ltx_frame_plan(duration_sec, fps)
        geometry = calculate_geometry(AspectRatio.widescreen_16_9, request.quality_profile)
        output_prefix = self._output_prefix(request, story_fragment, shot)

        return SemanticGenerationRequest(
            preset_id=request.preset_id,
            archetype_id=request.archetype_id,
            quality_profile=request.quality_profile,
            mode=request.mode,
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=0,
            width=geometry.generation_width,
            height=geometry.generation_height,
            frame_count=frame_plan.frame_count,
            fps=fps,
            target_duration_sec=duration_sec,
            upscale_factor=geometry.upscale_factor,
            output_profile=request.quality_profile,
            output_prefix=output_prefix,
            production=True,
        )

    @staticmethod
    def _clean_text(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    def _first_text(self, *values: object) -> str:
        for value in values:
            cleaned = self._clean_text(value)
            if cleaned:
                return cleaned
        return "Approved storyboard shot"

    def _output_prefix(self, request: StoryboardHandoffRequest, story_fragment: dict, shot: dict) -> str:
        project_key = request.output_project_key or self._first_text(
            story_fragment.get("title"),
            story_fragment.get("id"),
            "storyboard-handoff",
        )
        shot_label = self._first_text(shot.get("title"), shot.get("id"), "shot")
        shot_id = str(shot.get("id", ""))
        short_id = shot_id[:8] if shot_id else "shot"
        stem_base = request.run_stem or "storyboard_handoff"
        run_stem = sanitize_output_prefix(f"{stem_base}_{shot_label}_{short_id}")
        return build_project_output_prefix(project_key, run_stem)
