"""File-backed local operator run packets.

The store prepares review packets for future operator-approved live M4/M5 work.
It deliberately does not approve or execute anything: no FFmpeg/ffprobe,
ComfyUI, GPU telemetry, queue worker, render, benchmark, prompt submission, or
runtime health call is made here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import not_found
from backend.app.schemas.local_operator import (
    LocalOperatorLocalMVPSummary,
    LocalOperatorM4PreflightSummary,
    LocalOperatorM5RecipeSummary,
    LocalOperatorApprovalTemplate,
    LocalOperatorEvidenceField,
    LocalOperatorRunMode,
    LocalOperatorRunPacket,
    LocalOperatorRunbook,
    LocalOperatorRunbookStep,
    LocalOperatorRunPacketCreate,
)
from backend.app.services.ffmpeg.service import ffmpeg_command_template_catalog
from backend.app.services.local_mvp_readiness import LocalMVPReadinessService
from backend.app.services.local_runtime_m4 import M4HardwarePreflightService
from backend.app.utils.path_safety import resolve_inside

_PACKET_ADAPTER = TypeAdapter(LocalOperatorRunPacket)

_SAFE_METADATA_SOURCES = [
    "backend.app.services.local_mvp_readiness.LocalMVPReadinessService.report",
    "backend.app.services.local_runtime_m4.M4HardwarePreflightService.report",
    "backend.app.services.ffmpeg.service.ffmpeg_command_template_catalog",
]

_COMMON_CHECKLIST = [
    "Record explicit operator approval outside this packet before any live action.",
    "Confirm public/autonomous generation remains disabled.",
    "Confirm the exact mode/run scope; do not reuse approval for another mode.",
    "Confirm managed input/output paths and provenance locations before live work.",
    "Return gates to default-off posture after the approved run or if approval is unused.",
]

_M4_CHECKLIST = [
    "Confirm CINEFORGE_HARDWARE_OPERATOR_ENABLED and CINEFORGE_M4_HARDWARE_PROBE_APPROVED only for the approved run window.",
    "Confirm queue-empty evidence and exclusive GPU lease requirements before Comfy/GPU work.",
    "Run only the serialized M4 ladder stage(s) approved by the operator; stop on any unapproved deviation.",
]

_M5_CHECKLIST = [
    "Confirm allowlisted recipe identity, input hashes, probe metadata, and output workspace before FFmpeg/ffprobe work.",
    "Do not accept raw FFmpeg command strings; use structured allowlisted recipes only.",
    "Capture output hashes/final probe/error records after any separately approved live media-tool run.",
]

_FORBIDDEN_RUNBOOK_ACTIONS = [
    "No public raw /prompt route or direct ComfyUI prompt submission.",
    "No ComfyUI, GPU, render, benchmark, FFmpeg, or ffprobe action without separate explicit operator approval.",
    "No raw FFmpeg command strings; use allowlisted structured recipe builders only.",
    "No model/node installs, downloads, ComfyUI updates, or workflow-provided URL execution.",
    "No public/autonomous generation enablement from a runbook or packet endpoint.",
]


def _evidence(field: str, description: str, source: str, *, required: bool = True) -> LocalOperatorEvidenceField:
    return LocalOperatorEvidenceField(field=field, description=description, source=source, required=required)


def _step(step_id: str, title: str, description: str) -> LocalOperatorRunbookStep:
    return LocalOperatorRunbookStep(step_id=step_id, title=title, description=description)


def _m4_runbook() -> LocalOperatorRunbook:
    return LocalOperatorRunbook(
        mode=LocalOperatorRunMode.m4_hardware_ladder_probe,
        title="M4 hardware ladder probe reference",
        purpose="Prepare the operator to run only approved CF-VID-01 ladder stages after explicit approval; this endpoint never runs them.",
        prerequisites=[
            "A pending operator packet exists for mode m4_hardware_ladder_probe.",
            "Operator has explicitly approved the exact stage range and run window outside this runbook.",
            "CINEFORGE_HARDWARE_OPERATOR_ENABLED and CINEFORGE_M4_HARDWARE_PROBE_APPROVED are enabled only for the approved run window.",
            "Public/autonomous generation remains disabled and general queue-worker execution remains disabled.",
            "CF-VID-01 workflow/model pins, smoke evidence, serialized M4 ladder manifest, and queue-empty evidence are available.",
            "A controlled worker path, active GPU lease, managed output path, and recovery/stop rules are in force before Comfy/GPU work.",
        ],
        steps=[
            _step("m4-review-preflight", "Review read-only preflight", "Inspect /local-runtime/m4-preflight and /local-runtime/m4-ladder before any separate live action."),
            _step("m4-confirm-scope", "Confirm approved ladder scope", "Confirm only stages 0, 1, 2, 3, and 7 are in M4 scope; stages 4-6 remain deferred."),
            _step("m4-run-one-stage", "Run one approved stage at a time", "A future approved runner must serialize stages and stop after each stage for evidence capture."),
            _step("m4-capture-evidence", "Capture evidence", "Record duration, queue state, lease state, memory/thermal telemetry when available, output hashes/probes, and recovery outcome."),
            _step("m4-restore-gates", "Restore default-off gates", "Return operator-only flags to default-off posture after the approved run or any stop condition."),
        ],
        stop_rules=[
            "Stop immediately on unapproved graph/model/profile/stage deviation.",
            "Stop if Stage 0 or Stage 1 fails twice after approved recovery adjustments.",
            "Stop on OOM, process crash, stale GPU lease, non-empty queue after cleanup, missing output hash, or unmanaged output path.",
            "Stop if public/autonomous generation or general queue-worker execution is observed enabled outside the approved run window.",
        ],
        expected_evidence_fields=[
            _evidence("approval_id", "Identifier or note for the separate explicit operator approval.", "operator_audit"),
            _evidence("stage_number", "One of the serialized M4 ladder stages approved for the run.", "storage/benchmark_ladders/m4_cf_vid01_ladder.json"),
            _evidence("workflow_api_sha256", "Pinned workflow API hash used for the stage.", "workflow_manifest"),
            _evidence("model_artifact_sha256", "Pinned selected FP8 model artifact hash.", "local_runtime_catalog"),
            _evidence("gpu_lease_id", "Exclusive GPU lease bound to the worker-owned run.", "runtime_gpu_leases"),
            _evidence("queue_empty_before_after", "Queue-empty evidence before and after the stage.", "comfy_queue_control"),
            _evidence("output_sha256", "Hash of each managed output collected by CineForge.", "output_collector", required=False),
            _evidence("final_probe_json", "Bounded media probe summary for collected output when media exists.", "output_collector", required=False),
            _evidence("recovery_outcome", "Recovery/restart/next-job-health result for failures or Stage 7.", "runtime_recovery", required=False),
        ],
        forbidden_actions=list(_FORBIDDEN_RUNBOOK_ACTIONS),
        safe_metadata_sources=[*_SAFE_METADATA_SOURCES, "backend.app.services.benchmarks.ladder.BenchmarkLadderService.get_m4_ladder"],
    )


def _m5_runbook(mode: LocalOperatorRunMode) -> LocalOperatorRunbook:
    if mode == LocalOperatorRunMode.m5_ffmpeg_probe_validation:
        title = "M5 FFmpeg/ffprobe probe validation reference"
        purpose = "Prepare evidence expectations for a separately approved media probe validation run; this endpoint never runs ffprobe or FFmpeg."
        recipe_scope = "decode_validate_v1 and probe-dependent recipe validation records"
    else:
        title = "M5 FFmpeg assembly validation reference"
        purpose = "Prepare evidence expectations for a separately approved deterministic assembly validation run; this endpoint never runs FFmpeg."
        recipe_scope = "allowlisted concat, normalize, mux, captions, timing, transition, and delivery recipe IDs"
    return LocalOperatorRunbook(
        mode=mode,
        title=title,
        purpose=purpose,
        prerequisites=[
            "A pending operator packet exists for the exact M5 mode.",
            "Operator has explicitly approved the exact local media-tool run outside this runbook.",
            "All inputs are inside managed storage or otherwise admitted by path-safety policy.",
            "Every input has a validated SHA256 and, where required, existing probe provenance.",
            f"The recipe scope is limited to {recipe_scope}; raw command strings are not accepted.",
            "Output paths are resolved inside managed storage before any future approved media-tool execution.",
        ],
        steps=[
            _step("m5-review-recipe", "Review allowlisted recipe identity", "Inspect read-only FFmpeg recipe metadata and persisted command manifests before any separate live action."),
            _step("m5-confirm-inputs", "Confirm inputs and hashes", "Verify one hash per input plus probe compatibility where the selected recipe requires it."),
            _step("m5-run-approved-recipe", "Run only the approved structured recipe", "A future approved runner must build argv from the allowlisted recipe builder, never from user-authored command strings."),
            _step("m5-capture-outcome", "Capture outcome evidence", "Record output hash, final probe, timestamps, structured error text, and provenance after the approved run."),
            _step("m5-restore-boundary", "Restore default-off boundary", "Leave recipe-command APIs read-only and avoid adding generic execute endpoints."),
        ],
        stop_rules=[
            "Stop on unsafe path, missing/invalid hash, probe incompatibility, unsupported template ID, or user-authored command text.",
            "Stop if an output would overwrite untracked or unmanaged files.",
            "Stop on FFmpeg/ffprobe error and record structured error provenance without retry loops.",
            "Stop if any endpoint attempts to expose raw command submission or public execution.",
        ],
        expected_evidence_fields=[
            _evidence("approval_id", "Identifier or note for the separate explicit operator approval.", "operator_audit"),
            _evidence("command_template_id", "Allowlisted recipe template ID.", "ffmpeg_recipe_catalog"),
            _evidence("structured_argument_array", "Structured argv generated by CineForge builder, not user-authored command text.", "ffmpeg_service"),
            _evidence("input_paths", "Managed input paths accepted by path-safety policy.", "post_production_manifest"),
            _evidence("input_hashes", "Validated SHA256 for each input.", "post_production_manifest"),
            _evidence("input_probe_jsons", "Stored probe provenance used for compatibility decisions.", "recipe_command_manifest", required=False),
            _evidence("output_sha256", "Hash of produced output after the separately approved run.", "recipe_command_manifest", required=False),
            _evidence("final_probe_json", "Bounded final probe summary after the separately approved run.", "recipe_command_manifest", required=False),
            _evidence("error", "Structured error record for failed approved runs.", "recipe_command_manifest", required=False),
        ],
        forbidden_actions=list(_FORBIDDEN_RUNBOOK_ACTIONS),
        safe_metadata_sources=[*_SAFE_METADATA_SOURCES, "backend.app.services.ffmpeg.service.ffmpeg_command_template_catalog"],
    )


_REQUIRED_APPROVAL_SHAPE = [
    "Action family: M4 ComfyUI/GPU ladder, M5 FFmpeg/ffprobe probe validation, or M5 FFmpeg assembly validation.",
    "Target: exact archetype, recipe/template ID, packet ID, plan ID, stage number(s), or input/output manifest IDs.",
    "Scope: one stage/run/recipe at a time unless a bounded serial range is explicitly listed.",
    "Local-only constraint: public/autonomous generation stays disabled and no internet-facing exposure is enabled.",
    "Live-tool acknowledgement: explicitly states that ComfyUI/GPU/render/benchmark or FFmpeg/ffprobe work may run.",
]

_NON_APPROVAL_EXAMPLES = ["k", "ok", "continue", "go on", "what's next", "approve storyboard", "create packet"]


def local_operator_approval_templates() -> list[LocalOperatorApprovalTemplate]:
    return [
        LocalOperatorApprovalTemplate(
            mode=LocalOperatorRunMode.m4_hardware_ladder_probe,
            title="M4 local ComfyUI/GPU approval template",
            required_approval_shape=list(_REQUIRED_APPROVAL_SHAPE),
            example_approval=(
                "I approve a local M4 ComfyUI/GPU hardware probe for CF-VID-01, Stage 0 only, "
                "using the current M4 ladder and operator packet <packet-id>. Keep public/autonomous generation disabled."
            ),
            non_approval_examples=list(_NON_APPROVAL_EXAMPLES),
        ),
        LocalOperatorApprovalTemplate(
            mode=LocalOperatorRunMode.m5_ffmpeg_probe_validation,
            title="M5 local FFmpeg/ffprobe probe approval template",
            required_approval_shape=list(_REQUIRED_APPROVAL_SHAPE),
            example_approval=(
                "I approve a local M5 FFmpeg/ffprobe validation run for recipe <template-id> using plan <plan-id> only. "
                "Use allowlisted structured arguments, no raw command strings, and keep public/autonomous generation disabled."
            ),
            non_approval_examples=list(_NON_APPROVAL_EXAMPLES),
        ),
        LocalOperatorApprovalTemplate(
            mode=LocalOperatorRunMode.m5_ffmpeg_assembly_validation,
            title="M5 local FFmpeg assembly approval template",
            required_approval_shape=list(_REQUIRED_APPROVAL_SHAPE),
            example_approval=(
                "I approve a local M5 FFmpeg assembly validation run for recipe <template-id> using plan <plan-id> only. "
                "Use allowlisted structured arguments, no raw command strings, and keep public/autonomous generation disabled."
            ),
            non_approval_examples=list(_NON_APPROVAL_EXAMPLES),
        ),
    ]


def get_local_operator_approval_template(mode: LocalOperatorRunMode) -> LocalOperatorApprovalTemplate | None:
    return next((template for template in local_operator_approval_templates() if template.mode == mode), None)


def local_operator_runbooks() -> list[LocalOperatorRunbook]:
    return [
        _m4_runbook(),
        _m5_runbook(LocalOperatorRunMode.m5_ffmpeg_probe_validation),
        _m5_runbook(LocalOperatorRunMode.m5_ffmpeg_assembly_validation),
    ]


def get_local_operator_runbook(mode: LocalOperatorRunMode) -> LocalOperatorRunbook | None:
    return next((runbook for runbook in local_operator_runbooks() if runbook.mode == mode), None)


class LocalOperatorRunPacketStore:
    def __init__(self, settings: Settings | None = None, root: Path | None = None) -> None:
        self.settings = settings or get_settings()
        expected_root = resolve_inside(self.settings.storage_root, "local_operator_run_packets")
        self.root = resolve_inside(expected_root, root, allow_absolute=True) if root is not None else expected_root
        self.audit_path = resolve_inside(self.root, "events.jsonl")

    def create(self, request: LocalOperatorRunPacketCreate) -> LocalOperatorRunPacket:
        local_mvp_report = LocalMVPReadinessService(self.settings).report()
        m4_summary = self._m4_summary() if request.mode == LocalOperatorRunMode.m4_hardware_ladder_probe else None
        m5_summary = self._m5_summary() if request.mode in {
            LocalOperatorRunMode.m5_ffmpeg_probe_validation,
            LocalOperatorRunMode.m5_ffmpeg_assembly_validation,
        } else None
        packet_id = uuid4()
        manifest_path = resolve_inside(self.root, f"{packet_id}.json")
        blocking_reasons = self._blocking_reasons(request, m4_summary, m5_summary)
        packet = LocalOperatorRunPacket(
            packet_id=packet_id,
            created_at=datetime.now(UTC),
            manifest_path=manifest_path,
            request=request,
            local_mvp=LocalOperatorLocalMVPSummary(
                status=str(local_mvp_report.status),
                local_only_target=local_mvp_report.local_only_target,
                public_generation_disabled=local_mvp_report.public_generation_disabled,
                autonomous_generation_disabled=local_mvp_report.autonomous_generation_disabled,
                live_execution_approved_by_endpoint=local_mvp_report.live_execution_approved_by_endpoint,
                local_operator_live_runs_allowed_by_endpoint=local_mvp_report.local_operator_live_runs_allowed_by_endpoint,
            ),
            m4_preflight=m4_summary,
            m5_recipes=m5_summary,
            blocking_reasons=blocking_reasons,
            operator_checklist=self._checklist(request.mode),
            safe_metadata_sources=list(_SAFE_METADATA_SOURCES),
        )
        self._write_packet(packet)
        self._append_event(
            {
                "event": "local_operator_run_packet_created",
                "packet_id": str(packet_id),
                "mode": request.mode.value,
                "state": packet.state,
                "approval_recorded": False,
                "live_execution_started": False,
                "generation_submitted": False,
                "ffmpeg_submitted": False,
                "created_at": packet.created_at.isoformat(),
            }
        )
        return packet

    def get(self, packet_id: UUID) -> LocalOperatorRunPacket:
        path = resolve_inside(self.root, f"{packet_id}.json")
        if not path.is_file():
            raise not_found("Local operator run packet not found.")
        return _PACKET_ADAPTER.validate_json(path.read_text(encoding="utf-8"))

    def list(self, limit: int = 25) -> list[LocalOperatorRunPacket]:
        if limit < 1 or not self.root.is_dir():
            return []
        packets: list[LocalOperatorRunPacket] = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(packets) >= limit:
                break
            packets.append(_PACKET_ADAPTER.validate_json(path.read_text(encoding="utf-8")))
        return packets

    def _m4_summary(self) -> LocalOperatorM4PreflightSummary:
        report = M4HardwarePreflightService(self.settings).report()
        return LocalOperatorM4PreflightSummary(
            status=str(report.status),
            hardware_operator_probe_allowed=report.hardware_operator_probe_allowed,
            live_actions_executed=report.live_actions_executed,
            check_count=len(report.checks),
            passed_check_count=sum(1 for check in report.checks if check.passed),
            blocking_reasons=list(report.blocking_reasons),
            next_allowed_action=report.next_allowed_action,
        )

    @staticmethod
    def _m5_summary() -> LocalOperatorM5RecipeSummary:
        recipes = ffmpeg_command_template_catalog()
        return LocalOperatorM5RecipeSummary(
            recipe_catalog_count=len(recipes),
            ffmpeg_recipes_read_only=all(
                recipe.read_only_catalog and not recipe.executes_from_catalog and not recipe.user_authored_command_allowed
                for recipe in recipes
            ),
            ffmpeg_execution_endpoint_present=False,
            live_ffmpeg_probe_or_execute_performed=False,
            user_authored_ffmpeg_commands_allowed=any(recipe.user_authored_command_allowed for recipe in recipes),
        )

    @staticmethod
    def _blocking_reasons(
        request: LocalOperatorRunPacketCreate,
        m4_summary: LocalOperatorM4PreflightSummary | None,
        m5_summary: LocalOperatorM5RecipeSummary | None,
    ) -> list[str]:
        reasons = [
            "explicit_operator_approval_required",
            "packet_does_not_authorize_live_execution",
        ]
        if request.mode == LocalOperatorRunMode.m4_hardware_ladder_probe:
            reasons.append("m4_live_hardware_probe_requires_separate_operator_run")
            if m4_summary and not m4_summary.hardware_operator_probe_allowed:
                reasons.extend(f"m4_preflight:{reason}" for reason in m4_summary.blocking_reasons)
        if request.mode in {
            LocalOperatorRunMode.m5_ffmpeg_probe_validation,
            LocalOperatorRunMode.m5_ffmpeg_assembly_validation,
        }:
            reasons.append("m5_live_ffmpeg_or_ffprobe_requires_separate_operator_run")
            if m5_summary and not m5_summary.ffmpeg_recipes_read_only:
                reasons.append("m5_recipe_catalog_not_read_only")
            if m5_summary and m5_summary.ffmpeg_execution_endpoint_present:
                reasons.append("m5_execution_endpoint_present")
        return list(dict.fromkeys(reasons))

    @staticmethod
    def _checklist(mode: LocalOperatorRunMode) -> list[str]:
        if mode == LocalOperatorRunMode.m4_hardware_ladder_probe:
            return [*_COMMON_CHECKLIST, *_M4_CHECKLIST]
        return [*_COMMON_CHECKLIST, *_M5_CHECKLIST]

    def _write_packet(self, packet: LocalOperatorRunPacket) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = packet.model_dump(mode="json")
        temp_path = packet.manifest_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(packet.manifest_path)

    def _append_event(self, event: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
