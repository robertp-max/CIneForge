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
    LocalOperatorRunMode,
    LocalOperatorRunPacket,
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
