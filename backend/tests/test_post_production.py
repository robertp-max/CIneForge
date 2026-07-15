from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.core.errors import UnsafePathError, ValidationError
from backend.app.schemas.post_production import (
    PostProductionPlanErrorRecord,
    PostProductionPlanSuccessRecord,
    PostProductionRecipeCommandErrorRecord,
    PostProductionRecipeCommandSuccessRecord,
)
from backend.app.schemas.production import AspectRatio, FFmpegAssemblyInput, GeometryProfile, OutputProfile
from backend.app.services.ffmpeg.service import FFmpegService, RecipeCommandBuildResult, sha256_file
from backend.app.services.post_production import PostProductionService
from backend.app.services.post_production_manifest import PostProductionPlanStore


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


def test_post_production_plan_store_persists_offline_manifest_without_execution(monkeypatch, tmp_path: Path):
    clip_path = tmp_path / "clip_a.mp4"
    clip_path.write_bytes(b"clip-a")
    service = PostProductionService(FFmpegService(storage_root=tmp_path))
    plan = service.build_assembly_plan(
        [_clip(Path("clip_a.mp4"), sha256="a" * 64)],
        target_duration_sec=1.0,
        geometry=_geometry(),
        fps=24,
        output_path=Path("delivery/final.mp4"),
    )

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("plan manifest creation must not execute FFmpeg")

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", forbidden_run)
    store = PostProductionPlanStore(root=tmp_path / "plans", service=service)

    manifest = store.create_from_plan(plan)

    assert manifest.state == "planned_offline"
    assert manifest.execution_submitted is False
    assert manifest.command_template_id == "assemble_exact_duration_h264_v1"
    assert manifest.command[0:2] == ["ffmpeg", "-y"]
    assert manifest.input_hashes == ["a" * 64]
    assert manifest.output_sha256 is None
    assert manifest.final_probe_json is None
    assert manifest.manifest_path.is_file()
    assert (tmp_path / "plans" / "events.jsonl").is_file()
    assert store.get(manifest.plan_id) == manifest
    assert store.list()[0].plan_id == manifest.plan_id


def test_post_production_plan_store_persists_generic_recipe_command_manifest_without_execution(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "mix.wav"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")
    ffmpeg = FFmpegService(storage_root=tmp_path)
    command_result = ffmpeg.build_audio_mux_command(
        "video.mp4",
        "mix.wav",
        "delivery/final.mp4",
        video_sha256="b" * 64,
        audio_sha256="c" * 64,
    )

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("recipe command manifest creation must not execute FFmpeg")

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", forbidden_run)
    store = PostProductionPlanStore(root=tmp_path / "plans", service=PostProductionService(ffmpeg))

    manifest = store.create_from_recipe_command(command_result)

    assert manifest.state == "planned_offline"
    assert manifest.execution_submitted is False
    assert manifest.command_template_id == "audio_mux_v1"
    assert manifest.command == command_result.command
    assert [str(path) for path in manifest.input_paths] == command_result.input_paths
    assert manifest.input_hashes == ["b" * 64, "c" * 64]
    assert str(manifest.output_path) == command_result.output_path
    assert manifest.output_sha256 is None
    assert manifest.final_probe_json is None
    assert manifest.error is None
    assert manifest.manifest_path == tmp_path / "plans" / "recipe_commands" / f"{manifest.plan_id}.json"
    assert manifest.manifest_path.is_file()
    assert (tmp_path / "plans" / "recipe_commands" / "events.jsonl").is_file()
    assert store.get_recipe_command(manifest.plan_id) == manifest
    assert store.list_recipe_commands()[0].plan_id == manifest.plan_id
    assert store.list() == []


def test_post_production_plan_store_records_generic_recipe_command_success_without_execution(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "mix.wav"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")
    ffmpeg = FFmpegService(storage_root=tmp_path)
    command_result = ffmpeg.build_audio_mux_command(
        "video.mp4",
        "mix.wav",
        "delivery/final.mp4",
        video_sha256="b" * 64,
        audio_sha256="c" * 64,
    )

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("recipe command result recording must not execute FFmpeg")

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", forbidden_run)
    store = PostProductionPlanStore(root=tmp_path / "plans", service=PostProductionService(ffmpeg))
    manifest = store.create_from_recipe_command(command_result)

    recorded_updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    recorded_completed_at = datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC)
    completed = store.record_recipe_command_success(
        manifest.plan_id,
        PostProductionRecipeCommandSuccessRecord(
            output_sha256="D" * 64,
            final_probe_json={"streams": [{"codec_type": "video", "width": 1280, "height": 720}]},
            updated_at=recorded_updated_at,
            completed_at=recorded_completed_at,
        ),
    )

    assert completed.state == "completed_offline_recorded"
    assert completed.execution_submitted is False
    assert completed.output_sha256 == "d" * 64
    assert completed.final_probe_json["streams"][0]["codec_type"] == "video"
    assert completed.error is None
    assert completed.updated_at == recorded_updated_at
    assert completed.completed_at == recorded_completed_at
    assert store.get_recipe_command(manifest.plan_id) == completed
    assert store.list_recipe_commands()[0] == completed
    assert (tmp_path / "plans" / "recipe_commands" / "events.jsonl").read_text(encoding="utf-8").count(
        "post_production_recipe_command_plan_"
    ) == 2


def test_post_production_plan_store_records_generic_recipe_command_error_clears_stale_output(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "video.mp4"
    audio_path = tmp_path / "mix.wav"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")
    ffmpeg = FFmpegService(storage_root=tmp_path)
    command_result = ffmpeg.build_audio_mux_command(
        "video.mp4",
        "mix.wav",
        "delivery/final.mp4",
        video_sha256="b" * 64,
        audio_sha256="c" * 64,
    )

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("recipe command error recording must not execute FFmpeg")

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", forbidden_run)
    store = PostProductionPlanStore(root=tmp_path / "plans", service=PostProductionService(ffmpeg))
    manifest = store.create_from_recipe_command(command_result)
    store.record_recipe_command_success(
        manifest.plan_id,
        PostProductionRecipeCommandSuccessRecord(output_sha256="d" * 64, final_probe_json={"streams": []}),
    )

    failed = store.record_recipe_command_error(
        manifest.plan_id,
        PostProductionRecipeCommandErrorRecord(error="  mux validation failed  "),
    )

    assert failed.state == "failed_offline_recorded"
    assert failed.execution_submitted is False
    assert failed.output_sha256 is None
    assert failed.final_probe_json is None
    assert failed.error == "mux validation failed"
    assert failed.completed_at is not None
    assert store.get_recipe_command(manifest.plan_id).error == "mux validation failed"
    assert store.list_recipe_commands()[0].output_sha256 is None


def test_post_production_plan_store_rejects_invalid_generic_recipe_command_success_hash(tmp_path: Path):
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"clip")
    ffmpeg = FFmpegService(storage_root=tmp_path)
    command_result = ffmpeg.build_decode_validate_command("clip.mp4", "a" * 64)
    store = PostProductionPlanStore(root=tmp_path / "plans", service=PostProductionService(ffmpeg))
    manifest = store.create_from_recipe_command(command_result)

    with pytest.raises(ValidationError, match="SHA256"):
        store.record_recipe_command_success(
            manifest.plan_id,
            PostProductionRecipeCommandSuccessRecord(output_sha256="bad", final_probe_json={"streams": []}),
        )

    stored = store.get_recipe_command(manifest.plan_id)
    assert stored.state == "planned_offline"
    assert stored.output_sha256 is None
    assert stored.final_probe_json is None



def test_post_production_plan_store_rejects_invalid_generic_recipe_manifest(tmp_path: Path):
    store = PostProductionPlanStore(root=tmp_path / "plans")

    with pytest.raises(ValidationError, match="one input hash per input path"):
        store.create_from_recipe_command(
            RecipeCommandBuildResult(
                command_template_id="decode_validate_v1",
                command=["ffmpeg", "-v", "error"],
                input_paths=[str(tmp_path / "clip_a.mp4")],
                input_hashes=[],
            )
        )

    with pytest.raises(ValidationError, match="structured command array"):
        store.create_from_recipe_command(
            RecipeCommandBuildResult(
                command_template_id="decode_validate_v1",
                command=[],
                input_paths=[str(tmp_path / "clip_a.mp4")],
                input_hashes=["a" * 64],
            )
        )


def test_post_production_plan_store_rejects_unsafe_recipe_command_paths(tmp_path: Path):
    storage_root = tmp_path / "storage"
    service = PostProductionService(FFmpegService(storage_root=storage_root))
    store = PostProductionPlanStore(root=storage_root / "plans", service=service)

    with pytest.raises(UnsafePathError):
        store.create_from_recipe_command(
            RecipeCommandBuildResult(
                command_template_id="decode_validate_v1",
                command=["ffmpeg", "-v", "error"],
                input_paths=["../outside.mp4"],
                input_hashes=["a" * 64],
            )
        )

    with pytest.raises(UnsafePathError):
        store.create_from_recipe_command(
            RecipeCommandBuildResult(
                command_template_id="audio_mux_v1",
                command=["ffmpeg", "-y"],
                input_paths=["inside.mp4"],
                input_hashes=["b" * 64],
                output_path="../outside/final.mp4",
            )
        )


def test_post_production_plan_store_records_success_and_error_without_execution(monkeypatch, tmp_path: Path):
    service = PostProductionService(FFmpegService(storage_root=tmp_path))
    plan = service.build_assembly_plan(
        [_clip(Path("clip_a.mp4"), sha256="a" * 64)],
        target_duration_sec=1.0,
        geometry=_geometry(),
        fps=24,
        output_path=Path("delivery/final.mp4"),
    )

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("recording plan metadata must not execute FFmpeg")

    monkeypatch.setattr("backend.app.services.post_production.subprocess.run", forbidden_run)
    store = PostProductionPlanStore(root=tmp_path / "plans", service=service)
    manifest = store.create_from_plan(plan)

    completed = store.record_success(
        manifest.plan_id,
        PostProductionPlanSuccessRecord(
            output_sha256="B" * 64,
            final_probe_json={"streams": [{"codec_type": "video", "width": 1280, "height": 720}]},
        ),
    )

    assert completed.state == "completed_offline_recorded"
    assert completed.output_sha256 == "b" * 64
    assert completed.final_probe_json["streams"][0]["codec_type"] == "video"
    assert completed.error_message is None
    assert completed.completed_at is not None
    assert store.get(manifest.plan_id).output_sha256 == "b" * 64

    failed = store.record_error(
        manifest.plan_id,
        PostProductionPlanErrorRecord(error_message="  probe mismatch  "),
    )

    assert failed.state == "failed_offline_recorded"
    assert failed.output_sha256 is None
    assert failed.final_probe_json is None
    assert failed.error_message == "probe mismatch"
    assert (tmp_path / "plans" / "events.jsonl").read_text(encoding="utf-8").count("post_production_plan_") == 3


def test_post_production_plan_store_rejects_invalid_recorded_success_hash(tmp_path: Path):
    service = PostProductionService(FFmpegService(storage_root=tmp_path))
    plan = service.build_assembly_plan(
        [_clip(Path("clip_a.mp4"), sha256="a" * 64)],
        target_duration_sec=1.0,
        geometry=_geometry(),
        fps=24,
        output_path=Path("delivery/final.mp4"),
    )
    store = PostProductionPlanStore(root=tmp_path / "plans", service=service)
    manifest = store.create_from_plan(plan)

    with pytest.raises(ValidationError, match="SHA256"):
        store.record_success(
            manifest.plan_id,
            PostProductionPlanSuccessRecord(output_sha256="bad", final_probe_json={"streams": []}),
        )

    assert store.get(manifest.plan_id).state == "planned_offline"
    assert store.get(manifest.plan_id).output_sha256 is None


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
