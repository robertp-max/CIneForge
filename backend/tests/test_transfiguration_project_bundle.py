from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import json
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE = REPO_ROOT / "examples" / "projects" / "transfiguration_5m"


def _read_bundle_bytes(path: Path) -> bytes:
    if path.is_file():
        return path.read_bytes()
    parts = sorted(path.parent.glob(path.name + ".b64.part*"))
    assert parts, f"Missing bundle data for {path}"
    return base64.b64decode("".join(part.read_text(encoding="ascii") for part in parts))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_transfiguration_bundle_is_complete_and_fail_closed() -> None:
    payload = json.loads(gzip.decompress(_read_bundle_bytes(BUNDLE / "project_payload.json.gz")).decode("utf-8"))
    assets = json.loads((BUNDLE / "asset_manifest.json").read_text(encoding="utf-8"))

    chapters = payload["story"]["chapters"]
    scenes = [scene for chapter in chapters for scene in chapter["scenes"]]
    shots = [shot for scene in scenes for shot in scene["shots"]]

    assert len(chapters) == 4
    assert len(scenes) == 8
    assert len(shots) == 40
    assert sum(float(shot["duration_sec"]) for shot in shots) == 300.0
    assert {float(shot["duration_sec"]) for shot in shots} <= {7.0, 8.0}
    assert len(payload["story"]["characters"]) == 6
    assert payload["settings"]["allow_rendering"] is False
    assert payload["settings"]["allow_model_download"] is False
    assert payload["settings"]["final_width"] == payload["settings"]["preview_width"] * 2
    assert payload["settings"]["final_height"] == payload["settings"]["preview_height"] * 2

    for shot in shots:
        metadata = shot["production_metadata"]
        assert int(metadata["ltx_latent_frames"]) in {169, 193}
        assert (int(metadata["ltx_latent_frames"]) - 1) % 8 == 0
        assert shot["starting_image_required"] is True
        combined = (
            shot["prompt_package"]["image_prompt"]
            + shot["prompt_package"]["video_prompt"]
            + shot["prompt_package"]["negative_prompt"]
        ).lower()
        assert "transfiguration, not the ascension" in combined
        assert "ascending into heaven" in combined
        assert metadata["final_workflow"] == "CF-VID-02"
        assert "required_2x" in metadata["required_2x_upscale"]

    manifest_items = assets["assets"]
    assert len(manifest_items) == 14
    assert sum(item["role"] == "identity_reference_sheet" for item in manifest_items) == 6
    assert sum(item["role"] == "scene_storyboard_reference_board" for item in manifest_items) == 8
    assert {
        item["kind"]
        for item in manifest_items
        if item["role"] == "scene_storyboard_reference_board"
    } == {"art_direction_reference"}
    preview_zip = BUNDLE / assets["bundled_preview_archive"]["path"]
    assert preview_zip.is_file()
    with zipfile.ZipFile(preview_zip) as archive:
        for item in manifest_items:
            data = archive.read(item["bundle_zip_entry"])
            assert hashlib.sha256(data).hexdigest() == item["bundle_sha256"]
            assert item["approval_state"] == "draft"


def test_transfiguration_csv_matches_json_timeline() -> None:
    payload = json.loads(gzip.decompress(_read_bundle_bytes(BUNDLE / "project_payload.json.gz")).decode("utf-8"))
    with gzip.open(
        BUNDLE / "timeline" / "shot_manifest.csv.gz", "rt", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    shots = [
        shot
        for chapter in payload["story"]["chapters"]
        for scene in chapter["scenes"]
        for shot in scene["shots"]
    ]
    assert [row["shot_id"].lower() for row in rows] == [shot["client_id"] for shot in shots]
    assert [float(row["target_duration_sec"]) for row in rows] == [
        float(shot["duration_sec"]) for shot in shots
    ]
