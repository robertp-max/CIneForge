"""Read-only local MVP readiness checkpoint service.

This service summarizes existing local-only safety metadata. It deliberately does
not run FFmpeg/ffprobe, contact ComfyUI, submit prompts, acquire GPU leases,
render media, benchmark, or create runtime state.
"""

from __future__ import annotations

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.local_mvp_readiness import (
    LocalMVPCheckpointStatus,
    LocalMVPReadinessCheck,
    LocalMVPReadinessReport,
    M4PreflightSummary,
    M5PostProductionReadinessSummary,
)
from backend.app.services.ffmpeg.service import ffmpeg_command_template_catalog
from backend.app.services.local_runtime import local_runtime_catalog
from backend.app.services.local_runtime_m4 import M4HardwarePreflightService


_REMAINING_LOCAL_OPERATOR_BLOCKERS = [
    "Explicit operator approval for the specific live run remains required; this endpoint cannot approve execution.",
    "Applicable production gates must pass for the exact request, workflow, preset, storyboard/continuity, and quality profile.",
    "A managed GPU lease/admission path is required before ComfyUI hardware work.",
    "Managed input/output paths, hashes, probes, and provenance records must be present before local operator runs.",
]


class LocalMVPReadinessService:
    def __init__(
        self,
        settings: Settings | None = None,
        m4_preflight_service: M4HardwarePreflightService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.m4_preflight_service = m4_preflight_service or M4HardwarePreflightService(self.settings)

    def report(self) -> LocalMVPReadinessReport:
        catalog = local_runtime_catalog(self.settings)
        m4 = self.m4_preflight_service.report()
        recipes = ffmpeg_command_template_catalog()

        public_generation_disabled = not catalog.public_generation_enabled
        generation_disabled = not catalog.generation_enabled
        autonomous_generation_disabled = not self.settings.queue_worker_enabled
        ffmpeg_recipes_read_only = all(
            recipe.read_only_catalog and not recipe.executes_from_catalog and not recipe.user_authored_command_allowed
            for recipe in recipes
        )
        ffmpeg_recipes_execute_from_catalog = any(recipe.executes_from_catalog for recipe in recipes)
        user_authored_ffmpeg_commands_allowed = any(recipe.user_authored_command_allowed for recipe in recipes)

        checks = [
            LocalMVPReadinessCheck(
                code="local_only_target",
                passed=True,
                severity="info",
                message="Checkpoint target is personal/local-only operation.",
                evidence={"local_only_target": True},
            ),
            LocalMVPReadinessCheck(
                code="public_generation_disabled",
                passed=public_generation_disabled and generation_disabled,
                severity="blocker" if not (public_generation_disabled and generation_disabled) else "info",
                message="Public/autonomous generation flags must remain disabled.",
                evidence={
                    "generation_enabled": catalog.generation_enabled,
                    "public_generation_enabled": catalog.public_generation_enabled,
                },
            ),
            LocalMVPReadinessCheck(
                code="autonomous_queue_execution_disabled",
                passed=autonomous_generation_disabled,
                severity="blocker" if not autonomous_generation_disabled else "info",
                message="General queue-worker execution must remain disabled unless a separate approved run path is active.",
                evidence={"queue_worker_enabled": self.settings.queue_worker_enabled},
            ),
            LocalMVPReadinessCheck(
                code="endpoint_does_not_execute_or_approve_live_work",
                passed=True,
                severity="info",
                message="This endpoint performs no live execution and grants no live-run approval.",
                evidence={
                    "live_execution_performed_by_endpoint": False,
                    "live_execution_approved_by_endpoint": False,
                },
            ),
            LocalMVPReadinessCheck(
                code="m5_ffmpeg_recipes_read_only",
                passed=ffmpeg_recipes_read_only,
                severity="blocker" if not ffmpeg_recipes_read_only else "info",
                message="FFmpeg recipe catalog is metadata-only and does not execute catalog entries.",
                evidence={
                    "recipe_catalog_count": len(recipes),
                    "executes_from_catalog": ffmpeg_recipes_execute_from_catalog,
                    "user_authored_commands_allowed": user_authored_ffmpeg_commands_allowed,
                },
            ),
            LocalMVPReadinessCheck(
                code="m4_preflight_summary_available",
                passed=True,
                severity="info",
                message="M4 preflight was summarized from the existing read-only gate service.",
                evidence={
                    "status": m4.status,
                    "hardware_operator_probe_allowed": m4.hardware_operator_probe_allowed,
                    "blocking_reasons": list(m4.blocking_reasons),
                },
            ),
        ]

        # This checkpoint intentionally never clears a live-run gate: it can only
        # report whether the surrounding local-only metadata is in a safer shape.
        # A concrete operator run still needs separate approval, gates, lease, and
        # provenance, so the overall checkpoint remains blocked for live execution.
        status = LocalMVPCheckpointStatus.blocked

        return LocalMVPReadinessReport(
            status=status,
            public_generation_disabled=public_generation_disabled and generation_disabled,
            autonomous_generation_disabled=autonomous_generation_disabled,
            generation_enabled=catalog.generation_enabled,
            public_generation_enabled=catalog.public_generation_enabled,
            queue_worker_enabled=self.settings.queue_worker_enabled,
            hardware_operator_enabled=self.settings.hardware_operator_enabled,
            m4_preflight=M4PreflightSummary(
                status=str(m4.status),
                hardware_operator_probe_allowed=m4.hardware_operator_probe_allowed,
                live_actions_executed=m4.live_actions_executed,
                public_generation_enabled=m4.public_generation_enabled,
                public_prompt_enabled=m4.public_prompt_enabled,
                check_count=len(m4.checks),
                passed_check_count=sum(1 for check in m4.checks if check.passed),
                blocking_reasons=list(m4.blocking_reasons),
                next_allowed_action=m4.next_allowed_action,
            ),
            m5_post_production=M5PostProductionReadinessSummary(
                recipe_catalog_count=len(recipes),
                recipe_template_ids=[recipe.template_id for recipe in recipes],
                ffmpeg_recipes_read_only=ffmpeg_recipes_read_only,
                ffmpeg_recipes_execute_from_catalog=ffmpeg_recipes_execute_from_catalog,
                user_authored_ffmpeg_commands_allowed=user_authored_ffmpeg_commands_allowed,
            ),
            checks=checks,
            remaining_blockers_before_local_operator_live_runs=list(_REMAINING_LOCAL_OPERATOR_BLOCKERS),
            safe_metadata_sources=[
                "backend.app.services.local_runtime.local_runtime_catalog",
                "backend.app.services.local_runtime_m4.M4HardwarePreflightService.report",
                "backend.app.services.ffmpeg.service.ffmpeg_command_template_catalog",
                "backend.app.api.routes.local_post_production read-only recipe-command route contract",
            ],
        )
