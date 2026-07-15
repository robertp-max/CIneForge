import pytest
from fastapi.testclient import TestClient

from backend.app.core.errors import UnsafePathError, ValidationError
from backend.app.main import app
from backend.app.services.ffmpeg.service import (
    APPROVED_COMMAND_TEMPLATES,
    FFmpegService,
    check_stream_copy_compatibility,
    ffmpeg_command_template_catalog,
    select_normalization_plan,
)


def _probe(width=1920, height=1080, pix_fmt="yuv420p", fps="30/1"):
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": width,
                "height": height,
                "pix_fmt": pix_fmt,
                "r_frame_rate": fps,
                "time_base": "1/15360",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channel_layout": "stereo",
            },
        ]
    }


def test_ffprobe_unavailable_handled(monkeypatch, tmp_path):
    service = FFmpegService(storage_root=tmp_path)
    asset = tmp_path / "clip.mp4"
    asset.write_bytes(b"not real video")
    monkeypatch.setattr("backend.app.services.ffmpeg.service.shutil.which", lambda _name: None)
    with pytest.raises(RuntimeError, match="ffprobe not found"):
        service.ffprobe_asset("clip.mp4")


def test_ffprobe_compatibility_matching_clips():
    result = check_stream_copy_compatibility([_probe(), _probe()])
    assert result.compatible is True
    assert select_normalization_plan([_probe(), _probe()]) == "concat_stream_copy_v1"


def test_ffprobe_compatibility_mismatch_rejects_stream_copy():
    result = check_stream_copy_compatibility([_probe(), _probe(width=1280)])
    assert result.compatible is False
    assert select_normalization_plan([_probe(), _probe(width=1280)]) == "normalize_delivery_h264_v1"


def test_stream_copy_concat_manifest_requires_hashes_and_compatible_probes(tmp_path):
    first = tmp_path / "clip_001.mp4"
    second = tmp_path / "clip_002.mp4"
    first.write_bytes(b"clip-1")
    second.write_bytes(b"clip-2")
    result = FFmpegService(storage_root=tmp_path).build_stream_copy_concat_manifest(
        ["clip_001.mp4", "clip_002.mp4"],
        [_probe(), _probe()],
        ["a" * 64, "b" * 64],
    )

    assert result.compatibility_reason == "all stream signatures match"
    assert result.input_hashes == ["a" * 64, "b" * 64]
    assert str(first.resolve()).replace("\\", "/") in result.manifest
    assert str(second.resolve()).replace("\\", "/") in result.manifest


def test_stream_copy_concat_manifest_rejects_missing_hashes_bad_probes_and_unsafe_paths(tmp_path):
    first = tmp_path / "clip_001.mp4"
    first.write_bytes(b"clip-1")
    service = FFmpegService(storage_root=tmp_path)

    with pytest.raises(ValidationError, match="one input hash"):
        service.build_stream_copy_concat_manifest(["clip_001.mp4"], [_probe()], [])
    with pytest.raises(ValidationError, match="SHA256"):
        service.build_stream_copy_concat_manifest(["clip_001.mp4"], [_probe()], ["not-a-sha"])
    with pytest.raises(ValidationError, match="Stream-copy concat rejected"):
        service.build_stream_copy_concat_manifest(
            ["clip_001.mp4", "clip_002.mp4"],
            [_probe(), _probe(width=1280)],
            ["a" * 64, "b" * 64],
        )
    with pytest.raises(UnsafePathError):
        service.build_stream_copy_concat_manifest(["../escape.mp4"], [_probe()], ["a" * 64])


def test_decode_validate_command_builder_is_structured_and_hash_gated(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    result = FFmpegService(storage_root=tmp_path).build_decode_validate_command("clip.mp4", "A" * 64)

    assert result.command_template_id == "decode_validate_v1"
    assert result.command == ["ffmpeg", "-v", "error", "-i", str(clip.resolve()), "-f", "null", "NUL"]
    assert result.input_hashes == ["a" * 64]
    assert result.output_path is None


def test_audio_mux_command_builder_is_structured_hash_gated_and_path_safe(tmp_path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "mix.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    service = FFmpegService(storage_root=tmp_path)

    result = service.build_audio_mux_command(
        "video.mp4",
        "mix.wav",
        "out/final.mp4",
        video_sha256="b" * 64,
        audio_sha256="c" * 64,
    )

    assert result.command_template_id == "audio_mux_v1"
    assert result.command[0:2] == ["ffmpeg", "-y"]
    assert str(video.resolve()) in result.command
    assert str(audio.resolve()) in result.command
    assert str((tmp_path / "out" / "final.mp4").resolve()) in result.command
    assert result.input_hashes == ["b" * 64, "c" * 64]

    with pytest.raises(ValidationError, match="SHA256"):
        service.build_audio_mux_command("video.mp4", "mix.wav", "out/final.mp4", video_sha256="bad", audio_sha256="c" * 64)
    with pytest.raises(UnsafePathError):
        service.build_audio_mux_command("../video.mp4", "mix.wav", "out/final.mp4", video_sha256="b" * 64, audio_sha256="c" * 64)


def test_ffmpeg_recipe_catalog_is_read_only_and_matches_allowlist():
    catalog = ffmpeg_command_template_catalog()

    assert {record.template_id for record in catalog} == set(APPROVED_COMMAND_TEMPLATES)
    assert all(record.command_shape == "structured_argument_array" for record in catalog)
    assert all(record.read_only_catalog for record in catalog)
    assert all(record.executes_from_catalog is False for record in catalog)
    assert all(record.user_authored_command_allowed is False for record in catalog)
    concat = next(record for record in catalog if record.template_id == "concat_stream_copy_v1")
    assert concat.requires_probe_before_stream_copy is True


def test_ffmpeg_recipe_catalog_route_is_read_only():
    response = TestClient(app).get("/local-runtime/ffmpeg-recipes")

    assert response.status_code == 200
    payload = response.json()
    assert {record["template_id"] for record in payload} == set(APPROVED_COMMAND_TEMPLATES)
    assert all(record["executes_from_catalog"] is False for record in payload)
    assert all(record["user_authored_command_allowed"] is False for record in payload)

