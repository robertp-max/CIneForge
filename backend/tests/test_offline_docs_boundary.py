from __future__ import annotations

import re
from pathlib import Path

APPROVAL_REQUIRED_PHRASES = {
    "docs/API_CONTRACT.md": [
        "GET /health/comfy` is a live ComfyUI reachability probe",
        "GET /health/gpu` is a live GPU telemetry probe",
        "GET /health/ffmpeg` is a live FFmpeg/ffprobe availability probe",
    ],
    "docs/UI_MVP_STATUS.md": [
        "ComfyUI/GPU/FFmpeg live probes are not auto-called by the UI",
        "Automatic live calls to `/runtime/status`, `/health/comfy`, `/health/gpu`, or `/health/ffmpeg` from the UI.",
    ],
    "docs/LOCAL_SMOKE_TEST_PLAN.md": [
        "Live probes are not part of the default smoke path",
        "must not be run from the default smoke path",
    ],
}

CURRENT_VALIDATION_RESULT = "195 passed"
STALE_VALIDATION_WARNING_RESULT_RE = r"(?:15[0-9]|16[0-9]|17[0-9]|18[0-9]|19[0-4]) passed(?:, \d+ warnings)?|195 passed, \d+ warnings"

NON_APPROVAL_PHRASES = ["`k`", "`ok`", "`continue`", "`f`", "abusive", "threat"]

FORBIDDEN_STALE_PHRASES = [
    "ComfyUI mock connection",
    "validated against this machine",
    "The visible MVP exposes current live backend capability",
    "Check `GET /health/comfy`",
    "Confirm `/health/ffmpeg`",
    "Confirm `/health/gpu`",
]


def test_offline_boundary_docs_mark_live_probes_as_approval_required():
    for path, phrases in APPROVAL_REQUIRED_PHRASES.items():
        text = Path(path).read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase in text, f"{path} missing approval-required phrase: {phrase}"


def test_offline_validation_count_is_consistent_across_current_docs():
    docs = [
        Path("CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md"),
        Path("docs/OFFLINE_SAFE_VALIDATION.md"),
        Path("docs/LOCAL_SMOKE_TEST_PLAN.md"),
        Path("docs/UI_MVP_STATUS.md"),
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert CURRENT_VALIDATION_RESULT in text, f"{path} has stale validation count"
        assert not re.search(STALE_VALIDATION_WARNING_RESULT_RE, text), f"{path} has stale warning-bearing validation count"


def test_live_boundary_docs_include_current_non_approval_phrases():
    docs = [Path("docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md"), Path("docs/CHECKPOINT_WATCHDOG.md"), Path("docs/SAFE_LOCAL_ENDPOINTS.md")]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    for phrase in NON_APPROVAL_PHRASES:
        assert phrase in combined


def test_live_boundary_current_status_mentions_safe_endpoint_matrix_paths():
    matrix = Path("docs/SAFE_LOCAL_ENDPOINTS.md").read_text(encoding="utf-8")
    live_boundary = Path("docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md").read_text(encoding="utf-8")
    matrix_paths = re.findall(r"^\| `(?P<path>/local-[^`]+)` \|", matrix, flags=re.MULTILINE)

    missing = [path for path in matrix_paths if path not in live_boundary]

    assert missing == []


def test_offline_boundary_docs_do_not_use_stale_live_probe_language():
    docs = [Path("docs/API_CONTRACT.md"), Path("docs/UI_MVP_STATUS.md"), Path("docs/LOCAL_SMOKE_TEST_PLAN.md")]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    for phrase in FORBIDDEN_STALE_PHRASES:
        assert phrase not in combined
