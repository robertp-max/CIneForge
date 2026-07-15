"""Production hard gates for local CineForge generation requests."""

from __future__ import annotations

from backend.app.schemas.production import (
    BlockingReason,
    GateCode,
    OutputProfile,
    ProductionGateReport,
    ProductionPlan,
    SemanticGenerationRequest,
)
from backend.app.services.local_presets import LocalPresetCatalogService
from backend.app.services.production_planner import validate_ltx_dimensions, validate_ltx_frame_count
from backend.app.services.workflows.registry import WorkflowRegistryService


class ProductionGateService:
    def __init__(
        self,
        registry: WorkflowRegistryService | None = None,
        presets: LocalPresetCatalogService | None = None,
    ) -> None:
        self.registry = registry or WorkflowRegistryService()
        self.presets = presets or LocalPresetCatalogService()

    def evaluate_plan(self, plan: ProductionPlan) -> ProductionGateReport:
        reasons: list[BlockingReason] = []
        if not plan.timeline.exact_duration_preserved:
            reasons.append(self._reason(GateCode.timeline_duration_invalid, "Timeline does not preserve requested final duration"))
        if not plan.narration_required and not (plan.no_narration_reason or "").strip():
            reasons.append(self._reason(GateCode.narration_decision_missing, "Narration or explicit no-narration decision is required"))
        for character in plan.characters:
            if not character.ready_for_character_video:
                reasons.append(
                    self._reason(
                        GateCode.character_references_missing,
                        f"Character package for {character.name} lacks approved primary identity assets",
                        subject=character.character_id,
                    )
                )
        for scene in plan.scenes:
            for shot in scene.shots:
                try:
                    validate_ltx_frame_count(shot.frame_plan.frame_count)
                except Exception as exc:
                    reasons.append(self._reason(GateCode.invalid_model_frame_count, str(exc), subject=shot.shot_id))
                try:
                    validate_ltx_dimensions(shot.geometry.generation_width, shot.geometry.generation_height)
                except Exception as exc:
                    reasons.append(self._reason(GateCode.invalid_aspect_ratio_profile, str(exc), subject=shot.shot_id))
                if shot.generation_mode in {"i2v", "control", "continuation", "lipdub"}:
                    if shot.storyboard.approval_state != "approved" or not shot.storyboard.first_frame_asset_id:
                        reasons.append(
                            self._reason(GateCode.start_frame_missing, "I2V/control production requires an approved connected first-frame asset", subject=shot.shot_id)
                        )
                if not shot.continuity.resolved:
                    reasons.append(
                        self._reason(GateCode.continuity_conditioning_missing, "Continuity dependency is unresolved", subject=shot.shot_id)
                    )
                record = self.registry.get(shot.video_archetype_id)
                if record is None or not record.implemented:
                    reasons.append(self._reason(GateCode.workflow_not_admitted, f"{shot.video_archetype_id} is not implemented", subject=shot.shot_id))
                elif not self._record_ready_for_production(record):
                    reasons.append(
                        self._reason(
                            GateCode.workflow_not_admitted,
                            f"{shot.video_archetype_id} is not ready for local production: {self._record_block_message(record)}",
                            subject=shot.shot_id,
                        )
                    )
                if plan.quality_profile == OutputProfile.final_candidate and shot.geometry.upscale_factor < 2:
                    reasons.append(self._reason(GateCode.upscale_stage_missing, "Final candidate profile requires 2x upscale", subject=shot.shot_id))
        return ProductionGateReport(allowed=not reasons, blocking_reasons=reasons)

    def evaluate_generation_request(self, request: SemanticGenerationRequest) -> ProductionGateReport:
        reasons: list[BlockingReason] = []
        if request.production:
            preset = self.presets.get_preset(request.preset_id)
            if preset is None:
                reasons.append(self._reason(GateCode.workflow_not_admitted, f"Unknown preset {request.preset_id}"))
            elif preset.readiness != "ready" or not preset.enabled:
                reasons.append(
                    self._reason(
                        GateCode.preset_benchmark_required,
                        f"Preset {request.preset_id} is {preset.readiness} and enabled={preset.enabled}",
                        evidence={"preset_id": request.preset_id},
                    )
                )
            record = self.registry.get(request.archetype_id)
            if record is None:
                reasons.append(self._reason(GateCode.workflow_not_admitted, f"Unknown archetype {request.archetype_id}"))
            else:
                if record.api_graph_path and "smoke" in str(record.api_graph_path).lower():
                    reasons.append(self._reason(GateCode.smoke_workflow_forbidden, "Production request cannot use a smoke workflow"))
                if not self._record_ready_for_production(record):
                    reasons.append(
                        self._reason(
                            GateCode.workflow_not_admitted,
                            f"{record.archetype_id} is not production-ready: {self._record_block_message(record)}",
                        )
                    )
            try:
                validate_ltx_frame_count(request.frame_count)
            except Exception as exc:
                reasons.append(self._reason(GateCode.invalid_model_frame_count, str(exc)))
            try:
                validate_ltx_dimensions(request.width, request.height)
            except Exception as exc:
                reasons.append(self._reason(GateCode.invalid_aspect_ratio_profile, str(exc)))
            if request.mode in {"i2v", "control", "continuation", "lipdub"} and not request.first_image_asset_id:
                reasons.append(self._reason(GateCode.start_frame_missing, "Requested mode requires a connected first image asset"))
            if request.output_profile == OutputProfile.final_candidate and request.upscale_factor < 2:
                reasons.append(self._reason(GateCode.upscale_stage_missing, "Final profile cannot bypass required 2x upscale"))
        return ProductionGateReport(allowed=not reasons, blocking_reasons=reasons)

    @staticmethod
    def _record_ready_for_production(record) -> bool:
        return bool(
            record.implemented
            and record.dependency_verified
            and record.locally_tested
            and record.benchmark_passed
            and record.human_approved
            and record.readiness == "ready"
            and not record.blocked_reasons
        )

    @staticmethod
    def _record_block_message(record) -> str:
        if record.blocked_reasons:
            return "; ".join(record.blocked_reasons)
        missing = []
        for field in ("implemented", "dependency_verified", "locally_tested", "benchmark_passed", "human_approved"):
            if not getattr(record, field, False):
                missing.append(field)
        if getattr(record, "readiness", None) != "ready":
            missing.append(f"readiness={getattr(record, 'readiness', None)}")
        return ", ".join(missing) or "unknown readiness block"

    @staticmethod
    def direct_comfy_submission_blocked(reason: str = "Only tracked backend worker submissions are allowed") -> ProductionGateReport:
        return ProductionGateReport(
            allowed=False,
            blocking_reasons=[BlockingReason(code=GateCode.untracked_direct_comfy_submission, message=reason)],
        )

    @staticmethod
    def _reason(code: GateCode, message: str, *, subject: str | None = None, evidence: dict | None = None) -> BlockingReason:
        return BlockingReason(code=code, message=message, subject=subject, evidence=evidence or {})
