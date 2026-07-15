"""Read-only M4 hardware-operator preflight gate.

The report in this module is deliberately non-executing: it does not contact
ComfyUI, acquire a GPU lease, submit a prompt, render media, benchmark, install,
or download anything. It only summarizes whether the explicit operator-only M4
probe path is administratively allowed.
"""

from __future__ import annotations

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.local_runtime_m4 import M4HardwarePreflightReport, M4PreflightCheck, M4PreflightStatus
from backend.app.services.benchmarks.ladder import BenchmarkLadderService
from backend.app.services.local_runtime import local_runtime_catalog
from backend.app.services.local_runtime_evidence import LocalRuntimeEvidenceService


class M4HardwarePreflightService:
    def __init__(
        self,
        settings: Settings | None = None,
        evidence_service: LocalRuntimeEvidenceService | None = None,
        ladder_service: BenchmarkLadderService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.evidence_service = evidence_service or LocalRuntimeEvidenceService(self.settings)
        self.ladder_service = ladder_service or BenchmarkLadderService(self.settings)

    def report(self) -> M4HardwarePreflightReport:
        checks: list[M4PreflightCheck] = []
        catalog = local_runtime_catalog(self.settings)

        checks.append(
            M4PreflightCheck(
                code="public_generation_disabled",
                passed=not catalog.public_generation_enabled and not catalog.generation_enabled,
                message="Public/autonomous generation remains disabled.",
                evidence={
                    "generation_enabled": catalog.generation_enabled,
                    "public_generation_enabled": catalog.public_generation_enabled,
                },
            )
        )
        checks.append(
            M4PreflightCheck(
                code="queue_worker_general_execution_disabled",
                passed=not self.settings.queue_worker_enabled,
                message="General durable queue-worker execution must remain disabled for the M4 hardware probe.",
                evidence={"queue_worker_enabled": self.settings.queue_worker_enabled},
            )
        )
        checks.append(
            M4PreflightCheck(
                code="hardware_operator_gate_enabled",
                passed=self.settings.hardware_operator_enabled,
                message="CINEFORGE_HARDWARE_OPERATOR_ENABLED must be true for the operator-only M4 probe path.",
                evidence={"hardware_operator_enabled": self.settings.hardware_operator_enabled},
            )
        )
        checks.append(
            M4PreflightCheck(
                code="explicit_m4_probe_approval",
                passed=self.settings.m4_hardware_probe_approved,
                message="CINEFORGE_M4_HARDWARE_PROBE_APPROVED must be true before any live M4 probe is allowed.",
                evidence={"m4_hardware_probe_approved": self.settings.m4_hardware_probe_approved},
            )
        )

        try:
            ladder = self.ladder_service.get_m4_ladder()
        except FileNotFoundError as exc:
            checks.append(
                M4PreflightCheck(
                    code="m4_ladder_manifest_valid",
                    passed=False,
                    message="M4 serialized ladder manifest is missing.",
                    evidence={"missing_path": exc.filename},
                )
            )
        except ValidationError as exc:
            checks.append(
                M4PreflightCheck(
                    code="m4_ladder_manifest_valid",
                    passed=False,
                    message="M4 serialized ladder manifest is invalid.",
                    evidence={"error": str(exc)},
                )
            )
        else:
            checks.append(
                M4PreflightCheck(
                    code="m4_ladder_manifest_valid",
                    passed=True,
                    message="M4 serialized ladder manifest is present and valid.",
                    evidence={
                        "ladder_id": ladder.ladder_id,
                        "allowed_stage_numbers": ladder.allowed_stage_numbers,
                        "deferred_stage_numbers": ladder.deferred_stage_numbers,
                        "stage_count": len(ladder.stages),
                    },
                )
            )

        try:
            evidence = self.evidence_service.get_cf_vid01_smoke()
        except FileNotFoundError as exc:
            checks.append(
                M4PreflightCheck(
                    code="cf_vid01_smoke_evidence_present",
                    passed=False,
                    message="CF-VID-01 local smoke evidence is missing.",
                    evidence={"missing_path": exc.filename},
                )
            )
        else:
            checks.append(
                M4PreflightCheck(
                    code="cf_vid01_smoke_evidence_present",
                    passed=True,
                    message="CF-VID-01 local smoke evidence is recorded.",
                    evidence={
                        "evidence_id": evidence.evidence_id,
                        "template_id": evidence.template_id,
                        "output_count": len(evidence.outputs),
                    },
                )
            )
            checks.append(
                M4PreflightCheck(
                    code="cf_vid01_remains_benchmark_required",
                    passed=evidence.readiness_after_evidence == "benchmark_required",
                    message="CF-VID-01 must remain benchmark_required before the serialized M4 ladder.",
                    evidence={
                        "readiness_after_evidence": evidence.readiness_after_evidence,
                        "remaining_gates": list(evidence.remaining_gates),
                    },
                )
            )
            checks.append(
                M4PreflightCheck(
                    code="smoke_queue_empty_after",
                    passed=evidence.queue_empty_after,
                    message="Previous smoke evidence must show Comfy queue cleanup before M4.",
                    evidence={"queue_empty_after": evidence.queue_empty_after},
                )
            )

        blocking_reasons = [check.code for check in checks if not check.passed]
        allowed = not blocking_reasons
        return M4HardwarePreflightReport(
            status=M4PreflightStatus.operator_probe_ready if allowed else M4PreflightStatus.blocked,
            hardware_operator_probe_allowed=allowed,
            queue_worker_enabled=self.settings.queue_worker_enabled,
            hardware_operator_enabled=self.settings.hardware_operator_enabled,
            m4_hardware_probe_approved=self.settings.m4_hardware_probe_approved,
            checks=checks,
            blocking_reasons=blocking_reasons,
            next_allowed_action=(
                "Operator may run the serialized M4 hardware probe outside this report."
                if allowed
                else "Do not run live ComfyUI/GPU/render/benchmark work; resolve blocking reasons first."
            ),
        )
