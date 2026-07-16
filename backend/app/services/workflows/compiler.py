"""Semantic request compiler for admitted CineForge workflow templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.core.errors import ValidationError
from backend.app.schemas.production import CompiledWorkflow, GateCode, SemanticGenerationRequest
from backend.app.services.local_runtime import LTX23_SELECTED_FP8, SELECTED_MODEL_KEY
from backend.app.services.production_planner import validate_ltx_dimensions, validate_ltx_frame_count
from backend.app.services.workflows.registry import WorkflowRegistryService
from backend.app.services.workflows.template_service import WorkflowTemplateService


TEXT_ENCODER_DEFAULT = "gemma_3_12B_it_fp4_mixed.safetensors"


@dataclass(frozen=True)
class CompileFailure:
    code: GateCode
    message: str


class SemanticWorkflowCompiler:
    def __init__(
        self,
        registry: WorkflowRegistryService | None = None,
        template_service: WorkflowTemplateService | None = None,
    ) -> None:
        self.registry = registry or WorkflowRegistryService()
        self.template_service = template_service or WorkflowTemplateService()

    def compile(self, request: SemanticGenerationRequest) -> CompiledWorkflow:
        validate_ltx_dimensions(request.width, request.height)
        validate_ltx_frame_count(request.frame_count)
        record = self.registry.require(request.archetype_id)
        failures = self._technical_failures(request, record)
        if failures:
            joined = "; ".join(f"{failure.code.value}: {failure.message}" for failure in failures)
            raise ValidationError(joined)
        if record.template_dir is None:
            raise ValidationError(f"{GateCode.workflow_not_admitted.value}: archetype has no template directory")
        workflow, manifest = self.template_service.load_template(Path(record.template_dir))
        if request.production and self._is_smoke_template(manifest.template_id, manifest.version):
            raise ValidationError(f"{GateCode.smoke_workflow_forbidden.value}: smoke template cannot compile production work")
        if record.api_sha256 and manifest.original_workflow_sha256 != record.api_sha256:
            raise ValidationError("Workflow API hash differs from registry admission record")
        self._validate_semantic_bindings(record, manifest)
        patch_payload = self._patch_payload(request, manifest.nodes.keys())
        patched = self.template_service.apply_patch_and_snapshot(workflow, manifest, patch_payload)
        return CompiledWorkflow(
            archetype_id=request.archetype_id,
            template_id=manifest.template_id,
            template_version=manifest.version,
            workflow_api_sha256=manifest.original_workflow_sha256,
            patch_payload=patch_payload,
            patched_workflow=patched.patched_workflow,
            output_prefix=str(patch_payload["output_prefix"]),
            production=request.production,
            workflow_snapshot_path=patched.snapshot_path,
        )

    def _technical_failures(self, request: SemanticGenerationRequest, record) -> list[CompileFailure]:
        failures: list[CompileFailure] = []
        if request.production:
            if record.blocked_reasons:
                failures.append(CompileFailure(GateCode.workflow_not_admitted, "; ".join(record.blocked_reasons)))
            if not record.implemented or record.api_graph_path is None:
                failures.append(CompileFailure(GateCode.workflow_not_admitted, f"{record.archetype_id} has no executable API graph"))
            if not record.dependency_verified:
                failures.append(CompileFailure(GateCode.workflow_not_admitted, f"{record.archetype_id} dependencies are not verified"))
            if request.quality_profile not in record.supported_profiles:
                failures.append(CompileFailure(GateCode.workflow_not_admitted, f"profile {request.quality_profile} not supported by {record.archetype_id}"))
            if request.mode not in record.supported_modes:
                failures.append(CompileFailure(GateCode.workflow_not_admitted, f"mode {request.mode} not supported by {record.archetype_id}"))
            if request.quality_profile == "final_candidate" and request.upscale_factor < 2:
                failures.append(CompileFailure(GateCode.upscale_stage_missing, "final_candidate requires 2x upscale"))
        return failures

    def _validate_semantic_bindings(self, record, manifest) -> None:
        titles = [binding.semantic_title.strip() for binding in record.bindings]
        if any(not title for title in titles):
            raise ValidationError("Semantic binding title is required")
        duplicates = sorted({title for title in titles if titles.count(title) > 1})
        if duplicates:
            raise ValidationError(f"Duplicate semantic binding titles: {', '.join(duplicates)}")
        for binding in record.bindings:
            manifest_ref = None
            for ref in manifest.nodes.values():
                if ref.node_id == binding.node_id and ref.input_name == binding.input_name:
                    manifest_ref = ref
                    break
            if manifest_ref is None:
                raise ValidationError(f"Semantic binding {binding.semantic_key} does not map to manifest node/input")
            if manifest_ref.expected_class_type != binding.class_type:
                raise ValidationError(f"Semantic binding {binding.semantic_key} class drift")

    @staticmethod
    def _patch_payload(request: SemanticGenerationRequest, semantic_keys) -> dict[str, Any]:
        payload = {
            "prompt": request.prompt,
            "positive_prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "frames": request.frame_count,
            "frame_count": request.frame_count,
            "fps": request.fps,
            "seed": request.seed,
            "steps": 24 if request.output_profile in {"review", "final_candidate"} else 8,
            "model_checkpoint": LTX23_SELECTED_FP8.name if request.archetype_id.startswith("CF-VID") else SELECTED_MODEL_KEY,
            "text_encoder": TEXT_ENCODER_DEFAULT,
            "output_prefix": request.output_prefix,
            "upscale_factor": request.upscale_factor,
            "first_image": request.first_image_asset_id,
            "last_image": request.last_image_asset_id,
            "source_video": request.source_video_asset_id,
            "control_image": request.mask_or_control_asset_id,
        }
        # WorkflowTemplateService expects runtime parameter names, not semantic keys;
        # keep only non-None values. Missing required params are then caught by the manifest.
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _is_smoke_template(template_id: str, version: str) -> bool:
        text = f"{template_id} {version}".lower()
        return "smoke" in text
