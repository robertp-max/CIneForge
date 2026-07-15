from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.core.errors import UnsafePathError, ValidationError
from backend.app.schemas.production import AspectRatio, FFmpegAssemblyInput, GeometryProfile, OutputProfile
from backend.app.services.ffmpeg.service import FFmpegService, sha256_file
from backend.app.services.post_production import PostProductionService


def _geometry() -> GeometryProfile:
    return GeometryProfile(
        aspect_ratio=AspectRatio.widescreen_16_9,
        quality_profile=OutputProfile.draft,
        generation_width=640,
        generation_height=360,
        preview_width=640,
        preview_height=360,
        delivery_width=1280,
        delivery_height=720,
    )


def _clip(path: Path, *, duration: float = 1.0, sha256: str | None = None) -> FFmpegAssemblyInput:
    return FFmpegAssemblyInput(
        path=path,
        duration_sec=duration,
        start_sec=0,
        timeline_duration_sec=duration,
        sha256=sha256,
    )


def test_post_production_builds_structured_command_with_safe_paths_and_input_hashes(tmp_path: Path):
    clip_path = tmp_path / "clip_a.mp4"
    clip_path.write_bytes(b"clip-a")
    service = PostProductionService(FFmpegService(storage_root=tmp_path))

    plan = service.build_assembly_plan(
        [_clip(Path("clip_a.mp4"))],
        target_duration_sec=1.0,
        geometry=_geometry(),
        fps=24,
        output_path=Path("delivery/final.mp4"),
    )
    command = service.build_command(plan)

    assert plan.input_hashes == [sha256_file(clip_path)]
    assert isinstance(command, list)
    assert command[0:2] == ["ffmpeg", "-y"]
    assert str((tmp_path / "clip_a.mp4").resolve()) in command
    assert str((tmp_path / "delivery" / "final.mp4").resolve()) in command
    assert not any(";" in item and item.startswith("ffmpeg") for item in command)


def test_post_production_requires_input_hash_or_existing_file(tmp_path: Path):
    service = PostProductionService(FFmpegService(storage_root=tmp_path))

    with pytest.raises(ValidationError, match="Assembly input hash is required"):
        service.build_assembly_plan(
            [_clip(Path("missing.mp4"))],
            target_duration_sec=1.0,
            geometry=_geometry(),
            fps=24,
            output_path=Path("delivery/final.mp4"),
        )


def test_post_production_rejects_invalid_supplied_hash(tmp_path: Path):
    service = PostProductionService(FFmpegService(storage_root=tmp_path))

    with pytest.raises(ValidationError, match="SHA256"):
        service.build_assembly_plan(
            [_clip(Path("missing.mp4"), sha256="not-a-sha")],
            target_duration_sec=1.0,
            geometry=_geometry(),
            fps=24,
            output_path=Path("delivery/final.mp4"),
        )


def test_post_production_rejects_unsafe_input_or_output_paths(tmp_path: Path):
    (tmp_path / "clip_a.mp4").write_bytes(b"clip-a")
    service = PostProductionService(FFmpegService(storage_root=tmp_path))

    with pytest.raises(UnsafePathError):
        service.build_assembly_plan(
            [_clip(Path("../escape.mp4"), sha256="f" * 64)],
            target_duration_sec=1.0,
            geometry=_geometry(),
            fps=24,
            output_path=Path("delivery/final.mp4"),
        )

    plan = service.build_assembly_plan(
        [_clip(Path("clip_a.mp4"))],
        target_duration_sec=1.0,
        geometry=_geometry(),
        fps=24,
        output_path=Path("../outside.mp4"),
    )
    with pytest.raises(UnsafePathError):
        service.build_command(plan)


def test_execute_assembly_uses_resolved_output_path_without_real_ffmpeg(monkeypatch, tmp_path: Path):
    clip_path = tmp_path / "clip_a.mp4"
    clip_path.write_bytes(b"clip-a")
    ffmpeg = FFmpegService(storage_root=tmp_path)
    service = PostProductionService(ffmpeg)
    plan = service.build_assembly_plan(
        [_clip(Path("clip_a.mp4"))],
        target_duration_sec=1.0,
        geometry=_geometry(),
        fps=24,
        output_path=Path("delivery/final.mp4"),
    )
    output_path = (tmp_path / "delivery" / "final.mp4").resolve()

    def fake_run(command, **_kwargs):
        assert str(output_path) in command
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"final")
        return SimpleNamespace(returncode=0, stderr="")

    def fake_probe(asset_path):
        assert asset_path == Path("delivery/final.mp4")
        return {"streams": [{"codec_type": "video", "width": 1280, "height": 720}]}

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", fake_run)
    monkeypatch.setattr(ffmpeg, "ffprobe_asset", fake_probe)

    result = service.execute_assembly(plan)

    assert result["output_path"] == str(output_path)
    assert result["output_sha256"] == sha256_file(output_path)
    assert result["probe_json"]["streams"][0]["codec_type"] == "video"


def test_post_production_rejects_command_build_without_hashes(tmp_path: Path):
    clip_path = tmp_path / "clip_a.mp4"
    clip_path.write_bytes(b"clip-a")
    service = PostProductionService(FFmpegService(storage_root=tmp_path))
    plan = service.build_assembly_plan(
        [_clip(Path("clip_a.mp4"))],
        target_duration_sec=1.0,
        geometry=_geometry(),
        fps=24,
        output_path=Path("delivery/final.mp4"),
    )
    plan.input_hashes.clear()

    with pytest.raises(ValidationError, match="one input hash per clip"):
        service.build_command(plan)
