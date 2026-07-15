"""Managed ComfyUI output discovery for tracked CineForge jobs."""

from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.production import OutputDiscoveryRecord
from backend.app.services.ffmpeg.service import FFmpegService, sha256_file
from backend.app.utils.path_safety import sanitize_output_prefix, sanitize_project_folder


class OutputCollector:
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self, settings: Settings | None = None, ffmpeg: FFmpegService | None = None) -> None:
        self.settings = settings or get_settings()
        self.ffmpeg = ffmpeg or FFmpegService(storage_root=self.settings.comfyui_output_root)

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
