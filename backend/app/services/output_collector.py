"""Managed ComfyUI output discovery for tracked CineForge jobs."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.db.base import ComfyJob, FileOutput, GeneratedAsset, QueueStatus, WorkflowRun
from backend.app.queue.state_machine import JobState
from backend.app.schemas.production import OutputDiscoveryRecord
from backend.app.services.ffmpeg.service import FFmpegService, sha256_file
from backend.app.services.queue.service import QueueService
from backend.app.utils.path_safety import sanitize_output_prefix, sanitize_project_folder


class OutputCollector:
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(
        self,
        settings: Settings | None = None,
        ffmpeg: FFmpegService | None = None,
        queue_service: QueueService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.ffmpeg = ffmpeg or FFmpegService(storage_root=self.settings.comfyui_output_root)
        self.queue_service = queue_service or QueueService()

    def discover(self, project_key: str, run_stem: str, *, probe: bool = True) -> list[OutputDiscoveryRecord]:
        project_folder = sanitize_project_folder(project_key)
        safe_stem = sanitize_output_prefix(run_stem)
        project_dir = (self.settings.comfyui_output_root / project_folder).resolve()
        output_root = self.settings.comfyui_output_root.resolve()
        if output_root != project_dir and output_root not in project_dir.parents:
            raise ValueError("Project output directory escapes output root")
        if not project_dir.is_dir():
            return []
        records: list[OutputDiscoveryRecord] = []
        for path in sorted(project_dir.iterdir()):
            if not path.is_file():
                continue
            if not path.name.startswith(safe_stem):
                continue
            if path.suffix.lower() not in self.VIDEO_EXTENSIONS | self.IMAGE_EXTENSIONS:
                continue
            probe_json = None
            if probe and path.suffix.lower() in self.VIDEO_EXTENSIONS:
                try:
                    probe_json = self.ffmpeg.ffprobe_asset(Path(project_folder) / path.name)
                except Exception as exc:
                    probe_json = {"probe_error": str(exc)}
            records.append(
                OutputDiscoveryRecord(
                    path=path,
                    filename=path.name,
                    subfolder=project_folder,
                    sha256=sha256_file(path),
                    size_bytes=path.stat().st_size,
                    probe_json=probe_json,
                )
            )
        return records

    def collect_for_job(
        self,
        db: Session,
        job_id: UUID,
        project_key: str,
        run_stem: str,
        *,
        worker_id: str | None = None,
        probe: bool = True,
    ) -> list[OutputDiscoveryRecord]:
        """Persist managed outputs for a job in collecting_outputs state.

        No files are moved or copied here; ComfyUI is already configured to save
        under the managed project folder. This method records hash/probe data,
        advances terminal queue state, and releases the bound GPU lease.
        """

        job = db.get(ComfyJob, job_id)
        if job is None:
            raise ValidationError(f"ComfyJob not found: {job_id}")
        if job.status != QueueStatus.collecting_outputs:
            raise ValidationError(f"Job must be collecting_outputs, got {job.status.value}")
        workflow_run = db.get(WorkflowRun, job.workflow_run_id)
        if workflow_run is None:
            raise ValidationError(f"WorkflowRun not found: {job.workflow_run_id}")

        records = self.discover(project_key, run_stem, probe=probe)
        if not records:
            self.queue_service.mark_terminal_job(
                db,
                job_id,
                JobState.postprocess_failed,
                "No managed ComfyUI outputs found for expected prefix",
                actor="worker",
                worker_id=worker_id,
                error_message="No managed ComfyUI outputs found for expected prefix",
            )
            return []

        filename_prefix = f"{sanitize_project_folder(project_key)}/{sanitize_output_prefix(run_stem)}"
        for record in records:
            kind = self._kind_for_path(record.path)
            asset = GeneratedAsset(
                clip_iteration_id=None,
                kind=kind,
                path=str(record.path),
                sha256=record.sha256,
                width=self._probe_int(record.probe_json, "width"),
                height=self._probe_int(record.probe_json, "height"),
                frame_count=self._probe_int(record.probe_json, "nb_frames"),
                fps=None,
                duration_sec=self._probe_float(record.probe_json, "duration"),
                probe_json=record.probe_json,
            )
            db.add(asset)
            db.flush()
            db.add(
                FileOutput(
                    workflow_run_id=workflow_run.id,
                    generated_asset_id=asset.id,
                    filename_prefix=filename_prefix,
                    filename=record.filename,
                    subfolder=record.subfolder,
                    type=kind,
                    path=str(record.path),
                    sha256=record.sha256,
                )
            )
        db.commit()

        self.queue_service.mark_terminal_job(
            db,
            job_id,
            JobState.complete,
            "Managed ComfyUI outputs collected",
            actor="worker",
            worker_id=worker_id,
        )
        return records

    def _kind_for_path(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in self.VIDEO_EXTENSIONS:
            return "video"
        if suffix in self.IMAGE_EXTENSIONS:
            return "image"
        return "file"

    @staticmethod
    def _first_video_stream(probe_json: dict | None) -> dict | None:
        if not isinstance(probe_json, dict):
            return None
        streams = probe_json.get("streams")
        if not isinstance(streams, list):
            return None
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == "video":
                return stream
        return None

    @classmethod
    def _probe_int(cls, probe_json: dict | None, key: str) -> int | None:
        stream = cls._first_video_stream(probe_json)
        if stream is None or stream.get(key) is None:
            return None
        try:
            return int(stream[key])
        except (TypeError, ValueError):
            return None

    @classmethod
    def _probe_float(cls, probe_json: dict | None, key: str) -> float | None:
        stream = cls._first_video_stream(probe_json)
        if stream is None or stream.get(key) is None:
            return None
        try:
            return float(stream[key])
        except (TypeError, ValueError):
            return None
