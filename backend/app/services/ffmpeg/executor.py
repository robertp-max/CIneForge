"""Explicit, default-off execution of persisted CF-POST-01 plans."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.db.base import FFmpegJob
from backend.app.schemas.post_production import (
    PostProductionPlanManifest,
    PostProductionRecipeCommandManifest,
)
from backend.app.services.ffmpeg.service import FFmpegService, sha256_file
from backend.app.services.post_production import PostProductionService
from backend.app.services.post_production_manifest import PostProductionPlanStore
from backend.app.utils.path_safety import resolve_inside


class FFmpegExecutionBlocked(RuntimeError):
    pass


class GatedFFmpegExecutor:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        store: PostProductionPlanStore | None = None,
        ffmpeg: FFmpegService | None = None,
        runner: Any = subprocess.run,
    ) -> None:
        self.settings = settings or get_settings()
        self.ffmpeg = ffmpeg or FFmpegService(storage_root=self.settings.storage_root)
        self.post = PostProductionService(self.ffmpeg)
        self.store = store or PostProductionPlanStore(self.settings, service=self.post)
        self.runner = runner

    def execute_plan(self, db: Session, plan_id: UUID, *, requested_by: str) -> PostProductionPlanManifest:
        self._require_gate()
        manifest = self.store.get(plan_id)
        expected = self.post.build_command(manifest.plan)
        if manifest.command != expected:
            raise ValidationError("Persisted post-production command differs from its deterministic plan")
        self._validate_inputs(manifest.input_paths, manifest.input_hashes)
        output = self._validate_output(manifest.output_path)

        job = FFmpegJob(
            campaign_id=None,
            kind="cf_post_01_assembly",
            command_template_id=manifest.command_template_id,
            input_manifest={
                "plan_id": str(plan_id),
                "requested_by": requested_by,
                "input_paths": [str(path) for path in manifest.input_paths],
                "input_hashes": manifest.input_hashes,
                "command": manifest.command,
            },
            output_path=str(output),
            status="pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        try:
            self.store.record_execution_started(plan_id, ffmpeg_job_id=job.id, requested_by=requested_by)
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:10_000]
            db.commit()
            raise
        job.status = "running"
        db.commit()
        try:
            self._run(manifest.command)
            if not output.is_file():
                raise FileNotFoundError(output)
            probe = self._probe(output)
            digest = sha256_file(output)
            job.status = "complete"
            job.probe_json = probe
            job.error_message = None
            db.commit()
            return self.store.record_execution_success(
                plan_id,
                output_sha256=digest,
                final_probe_json=probe,
            )
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:10_000]
            db.commit()
            self.store.record_execution_error(plan_id, error_message=str(exc))
            raise

    def execute_recipe(
        self,
        db: Session,
        plan_id: UUID,
        *,
        requested_by: str,
    ) -> PostProductionRecipeCommandManifest:
        self._require_gate()
        manifest = self.store.get_recipe_command(plan_id)
        self._validate_recipe_command(manifest)
        self._validate_inputs(manifest.input_paths, manifest.input_hashes)
        output = self._validate_output(manifest.output_path) if manifest.output_path is not None else None
        job = FFmpegJob(
            campaign_id=None,
            kind="cf_post_01_recipe",
            command_template_id=manifest.command_template_id,
            input_manifest={
                "plan_id": str(plan_id),
                "requested_by": requested_by,
                "input_paths": [str(path) for path in manifest.input_paths],
                "input_hashes": manifest.input_hashes,
                "command": manifest.command,
            },
            output_path=str(output) if output is not None else None,
            status="pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        try:
            self.store.record_recipe_execution_started(
                plan_id,
                ffmpeg_job_id=job.id,
                requested_by=requested_by,
            )
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:10_000]
            db.commit()
            raise
        job.status = "running"
        db.commit()
        try:
            self._run(manifest.command)
            evidence_path = output or resolve_inside(
                self.ffmpeg.storage_root,
                manifest.input_paths[0],
                allow_absolute=True,
            )
            if not evidence_path.is_file():
                raise FileNotFoundError(evidence_path)
            digest = sha256_file(evidence_path)
            probe = self._probe(evidence_path)
            job.status = "complete"
            job.probe_json = probe
            job.error_message = None
            db.commit()
            return self.store.record_recipe_execution_success(
                plan_id,
                output_sha256=digest,
                final_probe_json=probe,
            )
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:10_000]
            db.commit()
            self.store.record_recipe_execution_error(plan_id, error=str(exc))
            raise

    def _require_gate(self) -> None:
        if not self.settings.ffmpeg_operator_enabled:
            raise FFmpegExecutionBlocked(
                "Local FFmpeg execution requires CINEFORGE_FFMPEG_OPERATOR_ENABLED=true"
            )

    def _validate_inputs(self, paths: list[Path], hashes: list[str]) -> None:
        if len(paths) != len(hashes) or not paths:
            raise ValidationError("Persisted execution requires one hash per input path")
        for path, expected in zip(paths, hashes, strict=True):
            safe = resolve_inside(self.ffmpeg.storage_root, path, allow_absolute=True)
            if not safe.is_file():
                raise FileNotFoundError(safe)
            actual = sha256_file(safe)
            if actual.lower() != expected.lower():
                raise ValidationError(f"Input hash changed after plan creation: {safe.name}")

    def _validate_output(self, path: Path) -> Path:
        safe = resolve_inside(self.ffmpeg.storage_root, path, allow_absolute=True)
        if safe.exists():
            raise ValidationError("FFmpeg output already exists; overwrite is refused")
        safe.parent.mkdir(parents=True, exist_ok=True)
        return safe

    def _validate_recipe_command(self, manifest: PostProductionRecipeCommandManifest) -> None:
        self.ffmpeg.validate_command_template_id(manifest.command_template_id)
        command = manifest.command
        if not command or command[0].strip().lower() not in {"ffmpeg", "ffmpeg.exe"}:
            raise ValidationError("Persisted recipe must invoke the pinned ffmpeg executable by name")
        forbidden_flags = {"-filter_script", "-filter_complex_script", "-protocol_whitelist", "-safe"}
        forbidden_prefixes = ("http:", "https:", "ftp:", "pipe:", "crypto:", "concat:", "subfile:")
        forbidden_filters = ("movie=", "amovie=", "subtitles=", "ass=")
        for argument in command[1:]:
            lowered = argument.strip().lower()
            if "\x00" in argument or "\n" in argument or "\r" in argument:
                raise ValidationError("Persisted recipe contains an unsafe argument")
            if lowered in forbidden_flags or lowered.startswith(forbidden_prefixes):
                raise ValidationError(f"Persisted recipe contains forbidden FFmpeg input or flag: {argument}")
            if any(fragment in lowered for fragment in forbidden_filters):
                raise ValidationError("Persisted recipe contains a file-reading filter")
        command_text = set(command)
        declared_inputs = {str(path) for path in manifest.input_paths}
        for index, argument in enumerate(command[:-1]):
            if argument == "-i" and command[index + 1] not in declared_inputs:
                raise ValidationError("Persisted recipe contains an undeclared FFmpeg input")
        for input_path in manifest.input_paths:
            if str(input_path) not in command_text:
                raise ValidationError("Persisted recipe command does not reference every declared input")
        if manifest.output_path is not None and command[-1] != str(manifest.output_path):
            raise ValidationError("Persisted recipe output does not match the final command argument")

    def _run(self, command: list[str]) -> None:
        result = self.runner(
            command,
            cwd=self.ffmpeg.storage_root,
            capture_output=True,
            text=True,
            timeout=self.settings.ffmpeg_timeout_sec,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "FFmpeg execution failed").strip())

    def _probe(self, path: Path) -> dict[str, Any]:
        relative = path.relative_to(self.ffmpeg.storage_root.resolve())
        return self.ffmpeg.ffprobe_asset(relative)
