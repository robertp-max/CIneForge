"""Planning media asset helpers for Storyboard Phase 1.

Stores managed asset IDs / URIs only. Never accepts or persists audio bytes,
base64 payloads, or raw provider responses.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import PlanningMediaAsset
from backend.app.schemas.voice import PlanningAssetRegisterRequest

FORBIDDEN_META_KEYS = frozenset(
    {
        "audio",
        "audio_base64",
        "base64",
        "data",
        "bytes",
        "raw_response",
        "wav_bytes",
        "mp3_bytes",
    }
)


class PlanningAssetError(Exception):
    """Domain error for planning media assets."""


def _sanitize_metadata(metadata: dict | None) -> dict:
    data = dict(metadata or {})
    bad = FORBIDDEN_META_KEYS.intersection({str(k).lower() for k in data})
    if bad:
        raise PlanningAssetError(f"Planning assets must not embed payload fields: {sorted(bad)}")
    return data


def register_planning_asset(
    db: Session,
    payload: PlanningAssetRegisterRequest,
) -> PlanningMediaAsset:
    if payload.managed_uri.strip().lower().startswith("data:"):
        raise PlanningAssetError("Planning assets must not use data: URIs (no embedded base64).")

    meta = _sanitize_metadata(payload.metadata)

    # Deduplicate by project + sha256 when hash is provided.
    if payload.sha256:
        existing = db.scalars(
            select(PlanningMediaAsset).where(
                PlanningMediaAsset.project_id == payload.project_id,
                PlanningMediaAsset.sha256 == payload.sha256,
            )
        ).first()
        if existing is not None:
            return existing

    asset = PlanningMediaAsset(
        project_id=payload.project_id,
        kind=payload.kind,
        source_type=payload.source_type,
        managed_uri=payload.managed_uri,
        sha256=payload.sha256,
        mime_type=payload.mime_type,
        width=payload.width,
        height=payload.height,
        duration_sec=payload.duration_sec,
        approval_state="draft",
        metadata_json=meta,
        original_filename=payload.original_filename,
        size_bytes=payload.size_bytes,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def get_planning_asset(db: Session, asset_id: UUID) -> PlanningMediaAsset:
    asset = db.get(PlanningMediaAsset, asset_id)
    if asset is None:
        raise PlanningAssetError(f"Planning media asset {asset_id} not found.")
    return asset


def register_voice_preview_asset(
    db: Session,
    *,
    project_id: UUID,
    managed_uri: str,
    sha256: str | None = None,
    mime_type: str | None = None,
    duration_sec: float | None = None,
    size_bytes: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    extra_metadata: dict | None = None,
) -> PlanningMediaAsset:
    """Register a managed voice preview artifact (URI/hash only)."""
    meta = {
        "kind_detail": "voice_preview",
        "provider": provider,
        "model": model,
    }
    if extra_metadata:
        meta.update(_sanitize_metadata(extra_metadata))

    return register_planning_asset(
        db,
        PlanningAssetRegisterRequest(
            project_id=project_id,
            kind="voice_preview",
            source_type="voice_preview_job",
            managed_uri=managed_uri,
            sha256=sha256,
            mime_type=mime_type,
            duration_sec=duration_sec,
            size_bytes=size_bytes,
            metadata=meta,
        ),
    )
