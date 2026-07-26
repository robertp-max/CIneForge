"""Query helpers for local_runtime_assets catalog."""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.db.base import LocalRuntimeAsset


def _row_dict(row: LocalRuntimeAsset) -> dict:
    return {
        "id": row.id,
        "asset_type": row.asset_type,
        "name": row.name,
        "file_path": row.file_path,
        "relative_path": row.relative_path,
        "model_category": row.model_category,
        "file_extension": row.file_extension,
        "file_size_bytes": row.file_size_bytes,
        "sha256": row.sha256,
        "metadata_json": row.metadata_json or {},
        "inferred_family": row.inferred_family,
        "inferred_base": row.inferred_base,
        "selector_value": row.selector_value,
        "source_kind": row.source_kind,
        "is_present": row.is_present,
        "first_seen_at": row.first_seen_at,
        "last_seen_at": row.last_seen_at,
        "mtime_ns": row.mtime_ns,
        "linked_model_variant_id": row.linked_model_variant_id,
        "linked_lora_id": row.linked_lora_id,
        "linked_workflow_template_id": row.linked_workflow_template_id,
        "created_at": row.created_at,
    }


def list_local_assets(
    db: Session,
    *,
    asset_type: str | None = None,
    family: str | None = None,
    base: str | None = None,
    present: bool | None = True,
    q: str | None = None,
    relative_prefix: str | None = None,
    duplicate_sha256: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    query = select(LocalRuntimeAsset).order_by(LocalRuntimeAsset.relative_path)
    if asset_type:
        if asset_type == "workflow":
            query = query.where(LocalRuntimeAsset.asset_type.like("workflow%"))
        elif asset_type == "checkpoint":
            query = query.where(LocalRuntimeAsset.asset_type == "checkpoint")
        else:
            query = query.where(LocalRuntimeAsset.asset_type == asset_type)
    if family:
        query = query.where(LocalRuntimeAsset.inferred_family == family)
    if base:
        query = query.where(LocalRuntimeAsset.inferred_base == base)
    if present is not None:
        query = query.where(LocalRuntimeAsset.is_present.is_(present))
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                LocalRuntimeAsset.name.ilike(like),
                LocalRuntimeAsset.relative_path.ilike(like),
                LocalRuntimeAsset.selector_value.ilike(like),
            )
        )
    if relative_prefix:
        query = query.where(LocalRuntimeAsset.relative_path.like(f"{relative_prefix}%"))
    if duplicate_sha256:
        query = query.where(LocalRuntimeAsset.sha256 == duplicate_sha256)

    rows = list(db.scalars(query.offset(max(offset, 0)).limit(min(max(limit, 1), 5000))))
    return [_row_dict(r) for r in rows]


def get_local_asset(db: Session, asset_id: UUID) -> dict | None:
    row = db.get(LocalRuntimeAsset, asset_id)
    if row is None:
        return None
    return _row_dict(row)


def local_assets_summary(db: Session) -> dict:
    rows = list(db.scalars(select(LocalRuntimeAsset).where(LocalRuntimeAsset.is_present.is_(True))))
    by_type = Counter(r.asset_type for r in rows)
    by_family = Counter(r.inferred_family or "unknown" for r in rows)
    total_bytes = sum(int(r.file_size_bytes or 0) for r in rows)
    hashed = sum(1 for r in rows if r.sha256)
    # duplicate hashes
    hash_counts = Counter(r.sha256 for r in rows if r.sha256)
    dup_groups = sum(1 for _, c in hash_counts.items() if c > 1)
    return {
        "present": len(rows),
        "total_size_bytes": total_bytes,
        "hashed": hashed,
        "by_type": dict(by_type),
        "by_family": dict(by_family),
        "duplicate_hash_groups": dup_groups,
    }


def resolve_asset_id(db: Session, asset_id: UUID) -> LocalRuntimeAsset | None:
    row = db.get(LocalRuntimeAsset, asset_id)
    if row is None or not row.is_present:
        return None
    return row
