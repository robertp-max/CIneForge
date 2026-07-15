"""Read-only benchmark ladder manifest loader.

This module validates planned benchmark ladders only. It never executes a stage,
contacts ComfyUI, acquires GPU leases, submits prompts, renders, or benchmarks.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.benchmark_ladder import BenchmarkLadderManifest


M4_ALLOWED_STAGES = [0, 1, 2, 3, 7]
M4_DEFERRED_STAGES = [4, 5, 6]
M4_ALLOWED_ARCHETYPES = {"CF-VID-01", "CF-IMG-01"}
M4_DEFERRED_ARCHETYPES = {"CF-VID-02", "CF-VID-03", "CF-VID-04"}


class BenchmarkLadderService:
    def __init__(self, settings: Settings | None = None, ladder_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.ladder_path = ladder_path or (self.settings.storage_root / "benchmark_ladders" / "m4_cf_vid01_ladder.json")

    def get_m4_ladder(self) -> BenchmarkLadderManifest:
        manifest = BenchmarkLadderManifest.model_validate_json(self.ladder_path.read_text(encoding="utf-8"))
        self._validate_m4_manifest(manifest)
        return manifest

    def _validate_m4_manifest(self, manifest: BenchmarkLadderManifest) -> None:
        if manifest.phase != "M4":
            raise ValidationError(f"Expected M4 ladder, got {manifest.phase}")
        if manifest.allowed_stage_numbers != M4_ALLOWED_STAGES:
            raise ValidationError(f"M4 ladder must allow exactly stages {M4_ALLOWED_STAGES}")
        if sorted(manifest.deferred_stage_numbers) != M4_DEFERRED_STAGES:
            raise ValidationError(f"M4 ladder must explicitly defer stages {M4_DEFERRED_STAGES}")
        stage_numbers = [stage.stage for stage in manifest.stages]
        if stage_numbers != M4_ALLOWED_STAGES:
            raise ValidationError(f"M4 ladder stages must be serialized as {M4_ALLOWED_STAGES}")
        if manifest.public_generation_enabled:
            raise ValidationError("M4 ladder must not enable public generation")
        if manifest.queue_worker_general_execution_enabled:
            raise ValidationError("M4 ladder must not enable general queue-worker execution")
        if not manifest.requires_serial_execution or not manifest.requires_hardware_operator_mode:
            raise ValidationError("M4 ladder requires serial hardware-operator execution")
        if not set(manifest.archetypes_in_scope).issubset(M4_ALLOWED_ARCHETYPES):
            raise ValidationError("M4 ladder scope may include only CF-VID-01 and CF-IMG-01")

        for stage in manifest.stages:
            if stage.public_generation_enabled:
                raise ValidationError(f"Stage {stage.stage} must not enable public generation")
            if not stage.requires_operator_approval:
                raise ValidationError(f"Stage {stage.stage} must require operator approval")
            if not stage.requires_hardware_operator_mode:
                raise ValidationError(f"Stage {stage.stage} must require hardware-operator mode")
            if not stage.requires_exclusive_gpu_lease:
                raise ValidationError(f"Stage {stage.stage} must require an exclusive GPU lease")
            if stage.live_action_approved:
                raise ValidationError(f"Stage {stage.stage} must not be pre-approved by the read-only manifest")
            if any(archetype in M4_DEFERRED_ARCHETYPES for archetype in stage.archetypes):
                raise ValidationError(f"Stage {stage.stage} references deferred archetype(s): {stage.archetypes}")
            if not set(stage.archetypes).issubset(M4_ALLOWED_ARCHETYPES):
                raise ValidationError(f"Stage {stage.stage} references out-of-scope archetype(s): {stage.archetypes}")
        stage_7 = next(stage for stage in manifest.stages if stage.stage == 7)
        if 1 not in stage_7.requires_stage_success:
            raise ValidationError("Stage 7 recovery sandbox must require Stage 1 success first")


def write_ladder_manifest(path: Path, manifest: BenchmarkLadderManifest | dict) -> Path:
    """Test/helper writer with deterministic JSON. Does not execute the ladder."""

    payload = manifest.model_dump(mode="json") if isinstance(manifest, BenchmarkLadderManifest) else manifest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
