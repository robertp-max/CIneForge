import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings
from backend.app.core.errors import UnsafePathError, ValidationError
from backend.app.utils.path_safety import reject_path_traversal, resolve_inside


APPROVED_COMMAND_TEMPLATES = {
    "concat_stream_copy_v1": "concat demuxer with -c copy",
    "normalize_mezzanine_prores_v1": "high quality mezzanine normalization",
    "normalize_delivery_h264_v1": "delivery-compatible H.264 normalization",
    "decode_validate_v1": "full decode validation to null sink",
}


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    reason: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    def validate_command_template_id(self, template_id: str) -> None:
        reject_path_traversal(template_id)
        if template_id not in APPROVED_COMMAND_TEMPLATES:
            raise UnsafePathError(f"Unapproved FFmpeg command template: {template_id}")

