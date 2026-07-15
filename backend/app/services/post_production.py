"""CF-POST-01 deterministic post-production planning and execution helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

from backend.app.core.errors import ValidationError
from backend.app.schemas.production import AspectRatio, FFmpegAssemblyInput, FFmpegAssemblyPlan, GeometryProfile
from backend.app.services.ffmpeg.service import FFmpegService, sha256_file


class PostProductionService:
    def __init__(self, ffmpeg: FFmpegService | None = None) -> None:
        self.ffmpeg = ffmpeg or FFmpegService()

    def build_assembly_plan(
        self,
        clips: Iterable[FFmpegAssemblyInput],
        *,
        target_duration_sec: float,
        geometry: GeometryProfile,
        fps: int,
        output_path: Path | None = None,
    ) -> FFmpegAssemblyPlan:
        clip_list = list(clips)
        if not clip_list:
            raise ValidationError("Assembly requires at least one clip")
        calculated = sum(clip.timeline_duration_sec for clip in clip_list)
        exact = abs(calculated - target_duration_sec) < 0.001
        if not exact:
            raise ValidationError(
                f"Timeline duration invalid: calculated {calculated:.3f}s, requested {target_duration_sec:.3f}s"
            )
        input_hashes = []
        for clip in clip_list:
            if clip.sha256:
                input_hashes.append(clip.sha256)
            elif clip.path.is_file():
                input_hashes.append(sha256_file(clip.path))
        return FFmpegAssemblyPlan(
            target_duration_sec=target_duration_sec,
            aspect_ratio=geometry.aspect_ratio,
            delivery_width=geometry.delivery_width,
            delivery_height=geometry.delivery_height,
            fps=fps,
            clips=clip_list,
            calculated_duration_sec=round(calculated, 6),
            exact_duration_preserved=True,
            output_path=output_path,
            input_hashes=input_hashes,
        )

    def build_command(self, plan: FFmpegAssemblyPlan) -> list[str]:
        self.ffmpeg.validate_command_template_id(plan.command_template_id)
        if plan.output_path is None:
            raise ValidationError("Assembly output_path is required to build a command")
        # Deterministic concat via normalized intermediate filter graph. This is
        # intentionally an argument array, never a user-authored command string.
        args = ["ffmpeg", "-y"]
        for clip in plan.clips:
            args.extend(["-i", str(clip.path)])
        filters = []
        concat_inputs = []
        for index, clip in enumerate(plan.clips):
            duration = f"{clip.timeline_duration_sec:.6f}"
            filters.append(
                f"[{index}:v]trim=0:{duration},setpts=PTS-STARTPTS,"
                f"fps={plan.fps},scale={plan.delivery_width}:{plan.delivery_height}:force_original_aspect_ratio=decrease,"
                f"pad={plan.delivery_width}:{plan.delivery_height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{index}]"
            )
            concat_inputs.append(f"[v{index}]")
        filters.append("".join(concat_inputs) + f"concat=n={len(plan.clips)}:v=1:a=0[vout]")
        args.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[vout]",
                "-t",
                f"{plan.target_duration_sec:.6f}",
                "-r",
                str(plan.fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(plan.output_path),
            ]
        )
        return args

    def execute_assembly(self, plan: FFmpegAssemblyPlan, *, timeout_sec: int = 600) -> dict:
        command = self.build_command(plan)
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_sec, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "ffmpeg assembly failed")
        if plan.output_path is None or not plan.output_path.is_file():
            raise FileNotFoundError(plan.output_path)
        final_probe = self.ffmpeg.ffprobe_asset(plan.output_path)
        return {
            "command_template_id": plan.command_template_id,
            "command": command,
            "output_path": str(plan.output_path),
            "output_sha256": sha256_file(plan.output_path),
            "probe_json": final_probe,
            "plan": json.loads(plan.model_dump_json()),
        }

    @staticmethod
    def aspect_ratio_label(aspect_ratio: AspectRatio) -> str:
        return aspect_ratio.value
