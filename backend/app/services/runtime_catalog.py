"""Factual, read-only runtime model/workflow catalog from registered DB evidence.

Hard rules:
- Never call ComfyUI, providers, GPU telemetry, FFmpeg, installers, downloads, or CLI.
- Unknown stays unknown.
- Never claim installed / validated / benchmarked without explicit database evidence.
- file_path present means path_recorded only — not proof of installation or validity.
"""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    BenchmarkRun,
    Lora,
    Model,
    ModelVariant,
    Quantization,
    WorkflowTemplate,
)
from backend.app.schemas.runtime_catalog import EvidenceStatus


def _path_status(file_path: str | None) -> EvidenceStatus:
    if file_path and str(file_path).strip():
        return EvidenceStatus.path_recorded
    return EvidenceStatus.unknown


def _checksum_status(sha256: str | None) -> EvidenceStatus:
    if sha256 and str(sha256).strip():
        return EvidenceStatus.checksum_recorded
    return EvidenceStatus.unknown


def _benchmark_status(count: int) -> EvidenceStatus:
    if count > 0:
        return EvidenceStatus.benchmark_recorded
    return EvidenceStatus.unknown


def _claims(
    *,
    path_recorded: bool = False,
    checksum_recorded: bool = False,
    benchmark_recorded: bool = False,
    extra: dict | None = None,
) -> dict:
    """Explicit non-claims. Presence of a path/hash is NOT installation proof."""
    payload = {
        "installed": False,
        "validated": False,
        "benchmarked": bool(benchmark_recorded),
        "downloaded": False,
        "path_recorded": bool(path_recorded),
        "checksum_recorded": bool(checksum_recorded),
    }
    if extra:
        payload.update(extra)
    return payload


def list_models(db: Session) -> list[dict]:
    rows = list(db.scalars(select(Model).order_by(Model.family, Model.name)))
    variant_counts = dict(
        db.execute(
            select(ModelVariant.model_id, func.count())
            .group_by(ModelVariant.model_id)
        ).all()
    )
    return [
        {
            "id": row.id,
            "family": row.family,
            "name": row.name,
            "source_url": row.source_url,
            "license": row.license,
            "evidence_level": row.evidence_level,
            "notes": row.notes,
            "registration_status": EvidenceStatus.registered.value,
            "variant_count": int(variant_counts.get(row.id, 0)),
        }
        for row in rows
    ]


def list_model_variants(db: Session, model_id: UUID | None = None) -> list[dict]:
    query = select(ModelVariant).order_by(ModelVariant.variant_name)
    if model_id is not None:
        query = query.where(ModelVariant.model_id == model_id)
    rows = list(db.scalars(query))

    bench_counts: Counter[UUID] = Counter()
    if rows:
        counts = db.execute(
            select(BenchmarkRun.model_variant_id, func.count())
            .where(BenchmarkRun.model_variant_id.is_not(None))
            .group_by(BenchmarkRun.model_variant_id)
        ).all()
        for variant_id, count in counts:
            if variant_id is not None:
                bench_counts[variant_id] = int(count)

    items: list[dict] = []
    for row in rows:
        path_recorded = bool(row.file_path and str(row.file_path).strip())
        checksum_recorded = bool(row.sha256 and str(row.sha256).strip())
        bench_count = bench_counts.get(row.id, 0)
        bench_recorded = bench_count > 0
        native = (row.native_voice_capability or "unknown").lower()
        if native not in {"supported", "unsupported", "unknown"}:
            native = "unknown"
        items.append(
            {
                "id": row.id,
                "model_id": row.model_id,
                "variant_name": row.variant_name,
                "params_b": float(row.params_b) if row.params_b is not None else None,
                "precision": row.precision,
                "quantization": row.quantization,
                "compatible_24gb_status": row.compatible_24gb_status,
                "notes": row.notes,
                "native_voice_capability": native,
                "native_voice_capability_source": row.native_voice_capability_source,
                "native_voice_capability_checked_at": row.native_voice_capability_checked_at,
                "path_status": _path_status(row.file_path).value,
                "checksum_status": _checksum_status(row.sha256).value,
                "has_file_path_recorded": path_recorded,
                "has_sha256_recorded": checksum_recorded,
                "has_file_size_recorded": row.file_size_bytes is not None,
                "file_size_bytes": row.file_size_bytes,
                "benchmark_status": _benchmark_status(bench_count).value,
                "benchmark_run_count": bench_count,
                "claims": _claims(
                    path_recorded=path_recorded,
                    checksum_recorded=checksum_recorded,
                    benchmark_recorded=bench_recorded,
                ),
            }
        )
    return items


def get_model_variant(db: Session, variant_id: UUID) -> dict | None:
    for item in list_model_variants(db):
        if item["id"] == variant_id:
            return item
    return None


def list_workflow_templates(db: Session) -> list[dict]:
    rows = list(
        db.scalars(select(WorkflowTemplate).order_by(WorkflowTemplate.name, WorkflowTemplate.version))
    )
    bench_counts: Counter[UUID] = Counter()
    if rows:
        counts = db.execute(
            select(BenchmarkRun.workflow_template_id, func.count())
            .where(BenchmarkRun.workflow_template_id.is_not(None))
            .group_by(BenchmarkRun.workflow_template_id)
        ).all()
        for template_id, count in counts:
            if template_id is not None:
                bench_counts[template_id] = int(count)

    items: list[dict] = []
    for row in rows:
        bench_count = bench_counts.get(row.id, 0)
        has_manifest = isinstance(row.manifest_json, dict) and bool(row.manifest_json)
        has_workflow = isinstance(row.workflow_api_json, dict) and bool(row.workflow_api_json)
        items.append(
            {
                "id": row.id,
                "name": row.name,
                "version": row.version,
                "sha256": row.sha256,
                "comfyui_commit": row.comfyui_commit,
                "created_at": row.created_at,
                "registration_status": EvidenceStatus.registered.value,
                "has_manifest": has_manifest,
                "has_workflow_api": has_workflow,
                "benchmark_status": _benchmark_status(bench_count).value,
                "benchmark_run_count": bench_count,
                "claims": _claims(
                    path_recorded=False,
                    checksum_recorded=bool(row.sha256),
                    benchmark_recorded=bench_count > 0,
                    extra={"comfy_reachable": False},
                ),
            }
        )
    return items


def get_workflow_template(db: Session, template_id: UUID) -> dict | None:
    for item in list_workflow_templates(db):
        if item["id"] == template_id:
            return item
    return None


def list_quantizations(db: Session) -> list[dict]:
    rows = list(db.scalars(select(Quantization).order_by(Quantization.name)))
    return [
        {
            "id": row.id,
            "name": row.name,
            "applies_to": row.applies_to,
            "loader_node": row.loader_node,
            "evidence_level": row.evidence_level,
            "recommended_24gb": bool(row.recommended_24gb),
            "notes": row.notes,
            "registration_status": EvidenceStatus.registered.value,
        }
        for row in rows
    ]


def list_loras(db: Session) -> list[dict]:
    rows = list(db.scalars(select(Lora).order_by(Lora.name)))
    items: list[dict] = []
    for row in rows:
        path_recorded = bool(row.file_path and str(row.file_path).strip())
        checksum_recorded = bool(row.sha256 and str(row.sha256).strip())
        items.append(
            {
                "id": row.id,
                "name": row.name,
                "purpose": row.purpose,
                "evidence_level": row.evidence_level,
                "quantized_base_status": row.quantized_base_status or "unknown",
                "license": row.license,
                "notes": row.notes,
                "path_status": _path_status(row.file_path).value,
                "has_file_path_recorded": path_recorded,
                "has_sha256_recorded": checksum_recorded,
                "claims": _claims(
                    path_recorded=path_recorded,
                    checksum_recorded=checksum_recorded,
                    benchmark_recorded=False,
                ),
            }
        )
    return items


def catalog_summary(db: Session) -> dict:
    return {
        "models": int(db.scalar(select(func.count()).select_from(Model)) or 0),
        "model_variants": int(db.scalar(select(func.count()).select_from(ModelVariant)) or 0),
        "workflow_templates": int(
            db.scalar(select(func.count()).select_from(WorkflowTemplate)) or 0
        ),
        "quantizations": int(db.scalar(select(func.count()).select_from(Quantization)) or 0),
        "loras": int(db.scalar(select(func.count()).select_from(Lora)) or 0),
        "benchmark_runs": int(db.scalar(select(func.count()).select_from(BenchmarkRun)) or 0),
        "evidence_note": (
            "Statuses reflect registered database evidence only. "
            "Unknown remains unknown. This endpoint never probes ComfyUI, GPUs, "
            "installers, downloads, or external providers."
        ),
    }


def full_catalog(db: Session) -> dict:
    return {
        "summary": catalog_summary(db),
        "models": list_models(db),
        "model_variants": list_model_variants(db),
        "workflow_templates": list_workflow_templates(db),
        "quantizations": list_quantizations(db),
        "loras": list_loras(db),
    }
