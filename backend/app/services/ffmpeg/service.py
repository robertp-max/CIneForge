import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings
from backend.app.core.errors import UnsafePathError, ValidationError
from backend.app.schemas.ffmpeg_recipes import FFmpegCommandTemplateRecord
from backend.app.utils.path_safety import reject_path_traversal, resolve_inside


APPROVED_COMMAND_TEMPLATES = {
    "concat_stream_copy_v1": "concat demuxer with -c copy",
    "normalize_mezzanine_prores_v1": "high quality mezzanine normalization",
    "normalize_delivery_h264_v1": "delivery-compatible H.264 normalization",
    "assemble_exact_duration_h264_v1": "deterministic exact-duration H.264 assembly with trim/scale/pad",
    "conform_timing_h264_v1": "single-input timing conform to exact duration, frame rate, and delivery geometry",
    "captions_srt_mux_v1": "mux reviewed captions/subtitles into a delivery file",
    "audio_mux_v1": "mux reviewed audio/final mix into a delivery file",
    "audio_loudness_normalize_v1": "EBU R128-style audio loudness normalization",
    "delivery_package_mp4_faststart_v1": "package a reviewed asset as MP4 with faststart metadata",
    "transition_crossfade_h264_v1": "crossfade two reviewed video assets into H.264 delivery geometry",
    "decode_validate_v1": "full decode validation to null sink",
}

_COMMAND_TEMPLATE_METADATA = {
    "concat_stream_copy_v1": {
        "category": "assembly",
        "requires_probe_before_stream_copy": True,
        "notes": "Allowed only when stored probe signatures prove stream-copy compatibility.",
    },
    "normalize_mezzanine_prores_v1": {"category": "normalization"},
    "normalize_delivery_h264_v1": {"category": "normalization"},
    "assemble_exact_duration_h264_v1": {
        "category": "assembly",
        "notes": "Used by CF-POST-01 deterministic exact-duration assembly planning.",
    },
    "conform_timing_h264_v1": {"category": "timing_conform"},
    "captions_srt_mux_v1": {"category": "captions"},
    "audio_mux_v1": {"category": "audio"},
    "audio_loudness_normalize_v1": {"category": "audio"},
    "delivery_package_mp4_faststart_v1": {"category": "delivery_packaging"},
    "transition_crossfade_h264_v1": {
        "category": "transitions",
        "notes": "Canonical M5 transition recipe; builds argv only and never executes FFmpeg.",
    },
    "decode_validate_v1": {
        "category": "validation",
        "notes": "Validation recipe; still must use structured arguments, input hashes, and managed paths.",
    },
}


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    reason: str


@dataclass(frozen=True)
class ConcatManifestBuildResult:
    manifest: str
    input_paths: list[str]
    input_hashes: list[str]
    compatibility_reason: str


@dataclass(frozen=True)
class RecipeCommandBuildResult:
    command_template_id: str
    command: list[str]
    input_paths: list[str]
    input_hashes: list[str]
    output_path: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sha256_hex(value: str) -> str:
    cleaned = value.strip().lower()
    if len(cleaned) != 64 or any(ch not in "0123456789abcdef" for ch in cleaned):
        raise ValidationError("SHA256 must be a 64-character hexadecimal string")
    return cleaned


def _validate_positive_seconds(value: float, field_name: str) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a positive finite duration")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValidationError(f"{field_name} must be a positive finite duration")
    return f"{seconds:.6f}"


def _validate_positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field_name} must be a positive integer")
    return value


def _video_signature(probe: dict[str, Any]) -> tuple:
    streams = probe.get("streams", [])
    video = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not video:
        raise ValidationError("Probe contains no video stream")
    v0 = video[0]
    a0 = audio[0] if audio else {}
    return (
        len(video),
        len(audio),
        v0.get("codec_name"),
        v0.get("width"),
        v0.get("height"),
        v0.get("pix_fmt"),
        v0.get("r_frame_rate"),
        v0.get("time_base"),
        a0.get("codec_name"),
        a0.get("sample_rate"),
        a0.get("channel_layout"),
    )


def check_stream_copy_compatibility(probes: list[dict[str, Any]]) -> CompatibilityResult:
    if len(probes) < 2:
        return CompatibilityResult(True, "single input")
    first = _video_signature(probes[0])
    for index, probe in enumerate(probes[1:], start=1):
        if _video_signature(probe) != first:
            return CompatibilityResult(False, f"probe at index {index} differs from first stream signature")
    return CompatibilityResult(True, "all stream signatures match")


def select_normalization_plan(probes: list[dict[str, Any]]) -> str:
    return "concat_stream_copy_v1" if check_stream_copy_compatibility(probes).compatible else "normalize_delivery_h264_v1"


def generate_concat_manifest(paths: list[Path]) -> str:
    lines = []
    for path in paths:
        text = str(path).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{text}'")
    return "\n".join(lines) + "\n"


def ffmpeg_command_template_catalog() -> list[FFmpegCommandTemplateRecord]:
    records: list[FFmpegCommandTemplateRecord] = []
    for template_id, description in sorted(APPROVED_COMMAND_TEMPLATES.items()):
        metadata = _COMMAND_TEMPLATE_METADATA.get(template_id, {})
        records.append(
            FFmpegCommandTemplateRecord(
                template_id=template_id,
                description=description,
                category=str(metadata.get("category") or "other"),
                requires_input_hashes=bool(metadata.get("requires_input_hashes", True)),
                requires_probe_before_stream_copy=bool(metadata.get("requires_probe_before_stream_copy", False)),
                notes=metadata.get("notes"),
            )
        )
    return records


class FFmpegService:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.settings = get_settings()
        self.storage_root = storage_root or self.settings.storage_root
        self.probes_root = self.storage_root / "probes"

    def health(self) -> dict[str, Any]:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        return {
            "status": "ok" if ffmpeg and ffprobe else "unavailable",
            "ffmpeg_available": bool(ffmpeg),
            "ffprobe_available": bool(ffprobe),
        }

    def ffprobe_asset(self, asset_path: str | Path) -> dict[str, Any]:
        path = resolve_inside(self.storage_root, asset_path, allow_absolute=self.settings.allow_absolute_input_paths)
        if not path.exists():
            raise FileNotFoundError(path)
        if shutil.which("ffprobe") is None:
            raise RuntimeError("ffprobe not found")
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        probe = json.loads(result.stdout)
        self.save_probe_json(path, probe)
        return probe

    def save_probe_json(self, asset_path: Path, probe: dict[str, Any]) -> Path:
        self.probes_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(str(asset_path.resolve()).encode("utf-8")).hexdigest()[:16]
        output = self.probes_root / f"{asset_path.stem}.{digest}.probe.json"
        if output.exists():
            raise FileExistsError(f"Probe JSON already exists: {output}")
        output.write_text(json.dumps(probe, indent=2, sort_keys=True), encoding="utf-8")
        return output

    def build_stream_copy_concat_manifest(
        self,
        paths: list[str | Path],
        probes: list[dict[str, Any]],
        input_hashes: list[str],
    ) -> ConcatManifestBuildResult:
        if not paths:
            raise ValidationError("Concat manifest requires at least one input path")
        if len(paths) != len(probes):
            raise ValidationError("Concat manifest requires one probe per input path")
        if len(paths) != len(input_hashes):
            raise ValidationError("Concat manifest requires one input hash per input path")
        validated_hashes = [validate_sha256_hex(str(value)) for value in input_hashes]

        compatibility = check_stream_copy_compatibility(probes)
        if not compatibility.compatible:
            raise ValidationError(f"Stream-copy concat rejected: {compatibility.reason}")

        safe_paths = [
            resolve_inside(self.storage_root, path, allow_absolute=self.settings.allow_absolute_input_paths)
            for path in paths
        ]
        return ConcatManifestBuildResult(
            manifest=generate_concat_manifest(safe_paths),
            input_paths=[str(path) for path in safe_paths],
            input_hashes=validated_hashes,
            compatibility_reason=compatibility.reason,
        )

    def build_decode_validate_command(self, input_path: str | Path, input_sha256: str) -> RecipeCommandBuildResult:
        self.validate_command_template_id("decode_validate_v1")
        safe_input = resolve_inside(
            self.storage_root,
            input_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        validated_hash = validate_sha256_hex(input_sha256)
        return RecipeCommandBuildResult(
            command_template_id="decode_validate_v1",
            command=["ffmpeg", "-v", "error", "-i", str(safe_input), "-f", "null", "NUL"],
            input_paths=[str(safe_input)],
            input_hashes=[validated_hash],
        )

    def build_audio_mux_command(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
        *,
        video_sha256: str,
        audio_sha256: str,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("audio_mux_v1")
        safe_video = resolve_inside(
            self.storage_root,
            video_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_audio = resolve_inside(
            self.storage_root,
            audio_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        video_hash = validate_sha256_hex(video_sha256)
        audio_hash = validate_sha256_hex(audio_sha256)
        return RecipeCommandBuildResult(
            command_template_id="audio_mux_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_video),
                "-i",
                str(safe_audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(safe_output),
            ],
            input_paths=[str(safe_video), str(safe_audio)],
            input_hashes=[video_hash, audio_hash],
            output_path=str(safe_output),
        )

    def build_normalize_delivery_h264_command(
        self,
        input_path: str | Path,
        output_path: str | Path,
        input_sha256: str,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("normalize_delivery_h264_v1")
        safe_input = resolve_inside(
            self.storage_root,
            input_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        validated_hash = validate_sha256_hex(input_sha256)
        return RecipeCommandBuildResult(
            command_template_id="normalize_delivery_h264_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_input),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(safe_output),
            ],
            input_paths=[str(safe_input)],
            input_hashes=[validated_hash],
            output_path=str(safe_output),
        )

    def build_normalize_mezzanine_prores_command(
        self,
        input_path: str | Path,
        output_path: str | Path,
        input_sha256: str,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("normalize_mezzanine_prores_v1")
        safe_input = resolve_inside(
            self.storage_root,
            input_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        validated_hash = validate_sha256_hex(input_sha256)
        return RecipeCommandBuildResult(
            command_template_id="normalize_mezzanine_prores_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_input),
                "-c:v",
                "prores_ks",
                "-profile:v",
                "3",
                "-pix_fmt",
                "yuv422p10le",
                "-c:a",
                "pcm_s16le",
                str(safe_output),
            ],
            input_paths=[str(safe_input)],
            input_hashes=[validated_hash],
            output_path=str(safe_output),
        )

    def build_conform_timing_h264_command(
        self,
        input_path: str | Path,
        output_path: str | Path,
        input_sha256: str,
        *,
        target_duration_sec: float,
        fps: int,
        width: int,
        height: int,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("conform_timing_h264_v1")
        safe_input = resolve_inside(
            self.storage_root,
            input_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        validated_hash = validate_sha256_hex(input_sha256)
        duration = _validate_positive_seconds(target_duration_sec, "target_duration_sec")
        safe_fps = _validate_positive_int(fps, "fps")
        safe_width = _validate_positive_int(width, "width")
        safe_height = _validate_positive_int(height, "height")
        video_filter = (
            f"trim=0:{duration},setpts=PTS-STARTPTS,"
            f"fps={safe_fps},"
            f"scale={safe_width}:{safe_height}:force_original_aspect_ratio=decrease,"
            f"pad={safe_width}:{safe_height}:(ow-iw)/2:(oh-ih)/2,"
            "setsar=1,format=yuv420p"
        )
        return RecipeCommandBuildResult(
            command_template_id="conform_timing_h264_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_input),
                "-vf",
                video_filter,
                "-t",
                duration,
                "-r",
                str(safe_fps),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(safe_output),
            ],
            input_paths=[str(safe_input)],
            input_hashes=[validated_hash],
            output_path=str(safe_output),
        )

    def build_transition_crossfade_h264_command(
        self,
        first_video_path: str | Path,
        second_video_path: str | Path,
        output_path: str | Path,
        *,
        first_video_sha256: str,
        second_video_sha256: str,
        transition_duration_sec: float,
        transition_offset_sec: float,
        fps: int,
        width: int,
        height: int,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("transition_crossfade_h264_v1")
        safe_first_video = resolve_inside(
            self.storage_root,
            first_video_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_second_video = resolve_inside(
            self.storage_root,
            second_video_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        first_hash = validate_sha256_hex(first_video_sha256)
        second_hash = validate_sha256_hex(second_video_sha256)
        transition_duration = _validate_positive_seconds(transition_duration_sec, "transition_duration_sec")
        transition_offset = _validate_positive_seconds(transition_offset_sec, "transition_offset_sec")
        safe_fps = _validate_positive_int(fps, "fps")
        safe_width = _validate_positive_int(width, "width")
        safe_height = _validate_positive_int(height, "height")
        geometry_filter = (
            f"fps={safe_fps},"
            f"scale={safe_width}:{safe_height}:force_original_aspect_ratio=decrease,"
            f"pad={safe_width}:{safe_height}:(ow-iw)/2:(oh-ih)/2,"
            "setsar=1,format=yuv420p"
        )
        filter_complex = (
            f"[0:v]{geometry_filter}[v0];"
            f"[1:v]{geometry_filter}[v1];"
            f"[v0][v1]xfade=transition=fade:duration={transition_duration}:offset={transition_offset},"
            "format=yuv420p[v]"
        )
        return RecipeCommandBuildResult(
            command_template_id="transition_crossfade_h264_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_first_video),
                "-i",
                str(safe_second_video),
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-an",
                "-r",
                str(safe_fps),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-movflags",
                "+faststart",
                str(safe_output),
            ],
            input_paths=[str(safe_first_video), str(safe_second_video)],
            input_hashes=[first_hash, second_hash],
            output_path=str(safe_output),
        )

    def build_captions_srt_mux_command(
        self,
        video_path: str | Path,
        captions_path: str | Path,
        output_path: str | Path,
        *,
        video_sha256: str,
        captions_sha256: str,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("captions_srt_mux_v1")
        safe_video = resolve_inside(
            self.storage_root,
            video_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_captions = resolve_inside(
            self.storage_root,
            captions_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        if safe_captions.suffix.lower() != ".srt":
            raise ValidationError("Captions mux requires a reviewed .srt captions file")
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        video_hash = validate_sha256_hex(video_sha256)
        captions_hash = validate_sha256_hex(captions_sha256)
        return RecipeCommandBuildResult(
            command_template_id="captions_srt_mux_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_video),
                "-i",
                str(safe_captions),
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-c:s",
                "mov_text",
                str(safe_output),
            ],
            input_paths=[str(safe_video), str(safe_captions)],
            input_hashes=[video_hash, captions_hash],
            output_path=str(safe_output),
        )

    def build_audio_loudness_normalize_command(
        self,
        input_path: str | Path,
        output_path: str | Path,
        input_sha256: str,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("audio_loudness_normalize_v1")
        safe_input = resolve_inside(
            self.storage_root,
            input_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        validated_hash = validate_sha256_hex(input_sha256)
        return RecipeCommandBuildResult(
            command_template_id="audio_loudness_normalize_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_input),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(safe_output),
            ],
            input_paths=[str(safe_input)],
            input_hashes=[validated_hash],
            output_path=str(safe_output),
        )

    def build_delivery_package_mp4_faststart_command(
        self,
        input_path: str | Path,
        output_path: str | Path,
        input_sha256: str,
    ) -> RecipeCommandBuildResult:
        self.validate_command_template_id("delivery_package_mp4_faststart_v1")
        safe_input = resolve_inside(
            self.storage_root,
            input_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        safe_output = resolve_inside(
            self.storage_root,
            output_path,
            allow_absolute=self.settings.allow_absolute_input_paths,
        )
        if safe_output.suffix.lower() != ".mp4":
            raise ValidationError("Delivery packaging output must be an .mp4 file")
        validated_hash = validate_sha256_hex(input_sha256)
        return RecipeCommandBuildResult(
            command_template_id="delivery_package_mp4_faststart_v1",
            command=[
                "ffmpeg",
                "-y",
                "-i",
                str(safe_input),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(safe_output),
            ],
            input_paths=[str(safe_input)],
            input_hashes=[validated_hash],
            output_path=str(safe_output),
        )

    def validate_command_template_id(self, template_id: str) -> None:
        reject_path_traversal(template_id)
        if template_id not in APPROVED_COMMAND_TEMPLATES:
            raise UnsafePathError(f"Unapproved FFmpeg command template: {template_id}")

