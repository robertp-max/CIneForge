"""Fail-closed public-release readiness report.

The report aggregates existing local metadata only. It never probes live runtime
health, runs media tools, submits prompts, creates jobs, approves execution, or
enables public generation.
"""

from __future__ import annotations

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.local_public_readiness import (
    LocalPublicReadinessCheck,
    LocalPublicReadinessReport,
    LocalPublicReadinessSummary,
)
from backend.app.services.local_mvp_readiness import LocalMVPReadinessService
from backend.app.services.local_readiness import LocalReadinessService
from backend.app.services.local_runtime import local_runtime_catalog


_PUBLIC_RELEASE_BLOCKERS = [
    "Public generation remains intentionally disabled for the local-only MVP.",
    "Raw public /prompt submission remains unavailable and must stay unavailable before a reviewed public API exists.",
    "All archetypes and presets require admission, benchmark/recovery evidence, provenance, and human QA before promotion.",
    "M4 hardware probe/benchmark evidence is not complete and cannot be inferred from read-only metadata.",
    "M5 live FFmpeg/ffprobe validation and deterministic delivery evidence require separate explicit operator approval.",
    "Internet-facing deployment, authentication/authorization, rate limiting, abuse controls, and secret handling are out of scope for this local checkpoint.",
]


class LocalPublicReadinessService:
    def __init__(
        self,
        settings: Settings | None = None,
        local_readiness: LocalReadinessService | None = None,
        local_mvp: LocalMVPReadinessService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.local_readiness = local_readiness or LocalReadinessService(self.settings)
        self.local_mvp = local_mvp or LocalMVPReadinessService(self.settings)

    def report(self) -> LocalPublicReadinessReport:
        catalog = local_runtime_catalog(self.settings)
        archetype_report = self.local_readiness.archetype_report()
        preset_report = self.local_readiness.preset_report()
        mvp_report = self.local_mvp.report()

        public_generation_disabled = not catalog.public_generation_enabled and not catalog.generation_enabled
        autonomous_generation_disabled = not self.settings.queue_worker_enabled
        all_archetypes_ready = archetype_report.summary.ready == archetype_report.summary.total
        all_presets_ready = preset_report.summary.ready == preset_report.summary.total
        no_public_archetypes = not archetype_report.summary.public_generation_enabled
        no_public_presets = not preset_report.summary.public_generation_enabled

        checks = [
            LocalPublicReadinessCheck(
                code="public_generation_disabled",
                passed=public_generation_disabled,
                severity="blocker" if not public_generation_disabled else "info",
                message="Public generation flags must remain disabled until a separate public-release program exists.",
                evidence={
                    "generation_enabled": catalog.generation_enabled,
                    "public_generation_enabled": catalog.public_generation_enabled,
                },
            ),
            LocalPublicReadinessCheck(
                code="raw_prompt_route_absent",
                passed=True,
                severity="info",
                message="No public raw /prompt route is part of the local ComfyUI lane contract.",
                evidence={"public_prompt_enabled": False},
            ),
            LocalPublicReadinessCheck(
                code="autonomous_generation_disabled",
                passed=autonomous_generation_disabled,
                severity="blocker" if not autonomous_generation_disabled else "info",
                message="Autonomous queue-worker execution must remain disabled for the local-only checkpoint.",
                evidence={"queue_worker_enabled": self.settings.queue_worker_enabled},
            ),
            LocalPublicReadinessCheck(
                code="all_archetypes_public_ready",
                passed=all_archetypes_ready and no_public_archetypes,
                severity="blocker",
                message="Every archetype must be ready from evidence before any public-release claim; current report stays fail-closed.",
                evidence=archetype_report.summary.model_dump(mode="json"),
            ),
            LocalPublicReadinessCheck(
                code="all_presets_public_ready",
                passed=all_presets_ready and no_public_presets,
                severity="blocker",
                message="Every preset must be ready from evidence before any public-release claim; current report stays fail-closed.",
                evidence=preset_report.summary.model_dump(mode="json"),
            ),
            LocalPublicReadinessCheck(
                code="endpoint_does_not_execute_or_approve_live_work",
                passed=True,
                severity="info",
                message="This endpoint performs no live execution and grants no live or public-release approval.",
                evidence={
                    "live_execution_performed_by_endpoint": False,
                    "live_execution_approved_by_endpoint": False,
                    "public_release_ready": False,
                },
            ),
        ]

        return LocalPublicReadinessReport(
            public_release_ready=False,
            public_generation_enabled=False,
            public_prompt_enabled=False,
            internet_facing_enabled=False,
            autonomous_generation_enabled=self.settings.queue_worker_enabled,
            live_execution_performed_by_endpoint=False,
            live_execution_approved_by_endpoint=False,
            archetype_summary=LocalPublicReadinessSummary(**archetype_report.summary.model_dump(mode="json")),
            preset_summary=LocalPublicReadinessSummary(**preset_report.summary.model_dump(mode="json")),
            local_mvp_status=str(mvp_report.status),
            m4_hardware_probe_allowed=mvp_report.m4_preflight.hardware_operator_probe_allowed,
            m5_ffmpeg_execution_endpoint_present=mvp_report.m5_post_production.ffmpeg_execution_endpoint_present,
            checks=checks,
            remaining_public_release_blockers=list(_PUBLIC_RELEASE_BLOCKERS),
            safe_metadata_sources=[
                "backend.app.services.local_runtime.local_runtime_catalog",
                "backend.app.services.local_readiness.LocalReadinessService.archetype_report",
                "backend.app.services.local_readiness.LocalReadinessService.preset_report",
                "backend.app.services.local_mvp_readiness.LocalMVPReadinessService.report",
            ],
        )
