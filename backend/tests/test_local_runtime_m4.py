import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.services.local_runtime_evidence import LocalRuntimeEvidenceService
from backend.app.services.local_runtime_m4 import M4HardwarePreflightService


def _smoke_evidence_payload() -> dict:
    return {
        "evidence_id": "cf_vid_01_t2v_smoke_test",
        "archetype_id": "CF-VID-01",
        "template_id": "cf_vid_01_ltx23_single_stage_t2v_smoke",
        "template_version": "0.2.0-api-t2v-smoke",
        "readiness_after_evidence": "benchmark_required",
        "model_key": "ltx2_3_22b_distilled_1_1_fp8",
        "checkpoint_filename": "ltx-2.3-22b-distilled-1.1-fp8.safetensors",
        "text_encoder_filename": "gemma_3_12B_it_fp4_mixed.safetensors",
        "workflow_api_sha256": "d040a311a80401dda3b7d2ecbbea0d8e24ca32b62a36e6d5801d0a7bda8865c1",
        "comfyui_version": "0.19.3",
        "ltxvideo_node_sha": "229437c6b65796d6a7a63ae34be2bd5ba31fa543",
        "runtime_args": ["--disable-api-nodes"],
        "object_info_path": "storage/runtime/object_info_test.json",
        "object_info_required_classes_missing": [],
        "smoke_parameters": {"width": 512, "height": 288, "frames": 17, "fps": 24, "steps": 4},
        "outputs": [
            {
                "prompt_id": "prompt-1",
                "path": "C:/AI/ComfyUI_windows_portable/ComfyUI/output/CineForge_runtime_validation/test.mp4",
                "sha256": "f" * 64,
                "size_bytes": 1234,
                "video_codec": "h264",
                "width": 512,
                "height": 288,
                "frames": 17,
                "fps": "24/1",
            }
        ],
        "queue_empty_after": True,
        "docs_path": "docs/CFVID01_RUNTIME_SMOKE.md",
        "remaining_gates": [
            "benchmark_ladder",
            "human_visual_audio_qa",
            "controlled_recovery_or_oom_exercise",
        ],
    }


def _write_smoke_evidence(tmp_path: Path) -> LocalRuntimeEvidenceService:
    path = tmp_path / "storage" / "runtime" / "cf_vid_01_smoke_evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_smoke_evidence_payload()), encoding="utf-8")
    return LocalRuntimeEvidenceService(Settings(storage_root=tmp_path / "storage"), evidence_path=path)


def test_m4_preflight_defaults_to_blocked_without_operator_gate_or_approval():
    report = M4HardwarePreflightService().report()

    assert report.hardware_operator_probe_allowed is False
    assert report.live_actions_executed is False
    assert report.public_generation_enabled is False
    assert report.public_prompt_enabled is False
    assert "hardware_operator_gate_enabled" in report.blocking_reasons
    assert "explicit_m4_probe_approval" in report.blocking_reasons
    assert "Do not run live ComfyUI" in report.next_allowed_action


def test_m4_preflight_blocks_when_smoke_evidence_is_missing(tmp_path: Path):
    settings = Settings(
        storage_root=tmp_path / "storage",
        hardware_operator_enabled=True,
        m4_hardware_probe_approved=True,
    )
    report = M4HardwarePreflightService(settings, LocalRuntimeEvidenceService(settings)).report()

    assert report.hardware_operator_probe_allowed is False
    assert "cf_vid01_smoke_evidence_present" in report.blocking_reasons


def test_m4_preflight_can_report_operator_probe_ready_without_running_live_work(tmp_path: Path):
    settings = Settings(
        storage_root=tmp_path / "storage",
        hardware_operator_enabled=True,
        queue_worker_enabled=False,
        m4_hardware_probe_approved=True,
    )
    service = M4HardwarePreflightService(settings, _write_smoke_evidence(tmp_path))

    report = service.report()

    assert report.hardware_operator_probe_allowed is True
    assert report.status == "operator_probe_ready"
    assert report.required_submission_mode == "hardware_operator"
    assert report.live_actions_executed is False
    assert report.public_generation_enabled is False
    assert report.public_prompt_enabled is False
    assert report.blocking_reasons == []


def test_m4_preflight_route_is_read_only_and_blocked_by_default():
    response = TestClient(app).get("/local-runtime/m4-preflight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == "M4"
    assert payload["hardware_operator_probe_allowed"] is False
    assert payload["live_actions_executed"] is False
    assert payload["public_generation_enabled"] is False
    assert payload["public_prompt_enabled"] is False
    assert "explicit_m4_probe_approval" in payload["blocking_reasons"]
