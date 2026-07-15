import pytest
from fastapi.testclient import TestClient

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

