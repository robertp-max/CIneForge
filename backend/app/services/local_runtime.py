"""DB-free local runtime catalog and output policy.

This module is deliberately read-only except for explicit project output-folder
creation helpers. It never launches ComfyUI, loads models, submits prompts,
installs packages, downloads files, or hashes large artifacts on demand.
"""

from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.local_runtime import (
    ArtifactRole,
    LocalArtifactRecord,
    LocalReadiness,
    LocalRuntimeCatalog,
    OutputPolicy,
)
from backend.app.utils.path_safety import (
    build_project_output_prefix,
    ensure_project_output_dir,
)

_MODEL_ROOT = Path("C:/AI/ComfyUI_windows_portable/ComfyUI/models/checkpoints")

LTX23_SOURCE = _MODEL_ROOT / "ltx-2.3-22b-distilled-1.1.safetensors"
LTX23_SELECTED_FP8 = _MODEL_ROOT / "ltx-2.3-22b-distilled-1.1-fp8.safetensors"
LTX23_TRANSFORMER_FP8 = _MODEL_ROOT / "ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors"
LTX23_TRANSFORMER_MXFP8 = _MODEL_ROOT / "ltx-2.3-22b-distilled-1.1_transformer_only_mxfp8_block32.safetensors"

SELECTED_MODEL_KEY = "ltx2_3_22b_distilled_1_1_fp8"
SOURCE_SHA256 = "b33b7fe4bbfe084f484be4aaf90b0f1d95dca20d403ac4c0e037eb8c4f0af7cc"
SELECTED_FP8_SHA256 = "c5dd96a75c4b588171b9807a8a25fea91e71a3cc7386d8bc245f50a21756cfbb"
TRANSFORMER_FP8_SHA256 = "0a1d7aac2b338e8ec7e832149f1dcf11c9323272482b1cca0673d229702370f0"
TRANSFORMER_MXFP8_SHA256 = "b7a945ff24d65ad22c6977787c2e594e74df226e35f1f9dedb64be8fdbd6ffd8"


def _size_if_present(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _artifact(
    *,
    key: str,
    role: ArtifactRole,
    path: Path,
    expected_size_bytes: int,
    sha256: str,
    precision: str,
    readiness: LocalReadiness,
    fp8_method: str | None = None,
    header_identity: str | None = None,
    notes: str | None = None,
) -> LocalArtifactRecord:
    return LocalArtifactRecord(
        key=key,
        role=role,
        path=path,
        path_exists=path.is_file(),
        size_bytes=_size_if_present(path),
        expected_size_bytes=expected_size_bytes,
        sha256=sha256,
        precision=precision,
        fp8_method=fp8_method,
        header_identity=header_identity,
        readiness=readiness,
        notes=notes,
    )


def output_policy(settings: Settings | None = None) -> OutputPolicy:
    settings = settings or get_settings()
    return OutputPolicy(output_root=settings.comfyui_output_root)


def local_runtime_catalog(settings: Settings | None = None) -> LocalRuntimeCatalog:
    settings = settings or get_settings()
    selected_exists = LTX23_SELECTED_FP8.is_file()
    readiness = LocalReadiness.benchmark_required if selected_exists else LocalReadiness.blocked
    return LocalRuntimeCatalog(
        queue_worker_enabled=settings.queue_worker_enabled,
        readiness=readiness,
        artifacts=[
            _artifact(
                key="ltx2_3_22b_distilled_1_1_source_bf16",
                role=ArtifactRole.source,
                path=LTX23_SOURCE,
                expected_size_bytes=46_149_345_334,
                sha256=SOURCE_SHA256,
                precision="bf16/f32",
                readiness=LocalReadiness.candidate,
                header_identity="full checkpoint: model + vae + audio_vae + vocoder",
                notes="Verified M0 source identity; not an FP8 artifact.",
            ),
            _artifact(
                key=SELECTED_MODEL_KEY,
                role=ArtifactRole.selected_fp8,
                path=LTX23_SELECTED_FP8,
                expected_size_bytes=25_134_891_534,
                sha256=SELECTED_FP8_SHA256,
                precision="fp8_e4m3/bf16",
                fp8_method="converted_derivative",
                readiness=readiness,
                header_identity=(
                    "same 5,947 tensor names/shapes and same model_version/config as "
                    "verified BF16 source; 4,444 tensors F8_E4M3"
                ),
                notes=(
                    "Operator-selected local full-checkpoint FP8 artifact. "
                    "Conversion provenance is pending; graph and hardware admission required."
                ),
            ),
            _artifact(
                key="ltx2_3_22b_distilled_1_1_transformer_only_fp8_scaled",
                role=ArtifactRole.secondary_candidate,
                path=LTX23_TRANSFORMER_FP8,
                expected_size_bytes=25_226_571_988,
                sha256=TRANSFORMER_FP8_SHA256,
                precision="fp8_e4m3/u8/bf16/f32",
                fp8_method="converted_derivative_candidate",
                readiness=LocalReadiness.blocked,
                header_identity="transformer/model tensors only; not selected product artifact",
                notes="Retained as secondary evidence only.",
            ),
            _artifact(
                key="ltx2_3_22b_distilled_1_1_transformer_only_mxfp8_block32",
                role=ArtifactRole.secondary_candidate,
                path=LTX23_TRANSFORMER_MXFP8,
                expected_size_bytes=24_052_755_552,
                sha256=TRANSFORMER_MXFP8_SHA256,
                precision="mxfp8/fp8_e4m3/u8/bf16/f32",
                fp8_method="converted_derivative_candidate",
                readiness=LocalReadiness.blocked,
                header_identity="transformer/model tensors only; not selected product artifact",
                notes="Retained as secondary evidence only.",
            ),
        ],
        output_policy=output_policy(settings),
    )


def prepare_project_output(settings: Settings | None, project_key: str, run_stem: str) -> dict[str, str]:
    """Create a safe project output folder and return ComfyUI prefix data."""

    settings = settings or get_settings()
    project_dir = ensure_project_output_dir(settings.comfyui_output_root, project_key)
    prefix = build_project_output_prefix(project_key, run_stem)
    return {
        "output_root": str(settings.comfyui_output_root),
        "project_output_dir": str(project_dir),
        "filename_prefix": prefix,
    }
