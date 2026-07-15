"""Shared GPU resource leases.

Serializes explicit voice preview work with video GPU workloads via exclusive
groups / resource keys. This is a lease boundary only — not a render queue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.db.base import GpuResourceLease
from backend.app.schemas.voice import GpuLeaseAcquireRequest

# Workload types that share the exclusive GPU group with voice previews.
VOICE_PREVIEW_WORKLOAD = "voice_preview"
VIDEO_GPU_WORKLOADS = frozenset(
    {
        "video_render",
        "comfy_job",
        "workflow_run",
        "gpu_video",
        "image_render",
    }
)
DEFAULT_EXCLUSIVE_GROUP = "gpu-shared"
DEFAULT_RESOURCE_KEY = "gpu0"


class GpuLeaseError(Exception):
    """Raised when a lease cannot be acquired or mutated."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def expire_stale_leases(db: Session, *, now: datetime | None = None) -> int:
    """Mark active leases past expires_at as expired. Returns count expired."""
    ts = _as_utc(now) if now is not None else _utcnow()
    stmt = select(GpuResourceLease).where(
        GpuResourceLease.status == "active",
        GpuResourceLease.expires_at.is_not(None),
        GpuResourceLease.expires_at <= ts,
    )
    count = 0
    for lease in db.scalars(stmt):
        lease.status = "expired"
        lease.released_at = ts
        db.add(lease)
        count += 1
    if count:
        db.commit()
    return count


def _active_conflict(
    db: Session,
    *,
    resource_key: str,
    exclusive_group: str | None,
    now: datetime,
) -> GpuResourceLease | None:
    """Find an active lease that conflicts on resource_key or exclusive_group."""
    expire_stale_leases(db, now=now)

    clauses = [GpuResourceLease.resource_key == resource_key]
    if exclusive_group:
        clauses.append(GpuResourceLease.exclusive_group == exclusive_group)

    stmt = select(GpuResourceLease).where(
        GpuResourceLease.status == "active",
        or_(*clauses),
    )
    return db.scalars(stmt).first()


def acquire_lease(db: Session, request: GpuLeaseAcquireRequest) -> GpuResourceLease:
    now = _utcnow()
    exclusive_group = request.exclusive_group or DEFAULT_EXCLUSIVE_GROUP
    resource_key = request.resource_key or DEFAULT_RESOURCE_KEY

    conflict = _active_conflict(
        db,
        resource_key=resource_key,
        exclusive_group=exclusive_group,
        now=now,
    )
    if conflict is not None:
        raise GpuLeaseError(
            "GPU resource is leased by another workload: "
            f"lease_id={conflict.id} workload_type={conflict.workload_type} "
            f"owner={conflict.owner} resource_key={conflict.resource_key} "
            f"exclusive_group={conflict.exclusive_group}"
        )

    lease = GpuResourceLease(
        resource_key=resource_key,
        exclusive_group=exclusive_group,
        workload_type=request.workload_type,
        workload_id=request.workload_id,
        owner=request.owner,
        worker_id=request.worker_id,
        status="active",
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(seconds=request.ttl_seconds),
        metadata_json=dict(request.metadata or {}),
    )
    db.add(lease)
    try:
        db.commit()
    except Exception as exc:  # unique active index race
        db.rollback()
        raise GpuLeaseError(f"Failed to acquire GPU lease (conflict): {exc}") from exc
    db.refresh(lease)
    return lease


def heartbeat_lease(
    db: Session,
    lease_id: UUID,
    *,
    extend_seconds: int = 300,
) -> GpuResourceLease:
    lease = db.get(GpuResourceLease, lease_id)
    if lease is None:
        raise GpuLeaseError(f"GPU lease {lease_id} not found.")
    if lease.status != "active":
        raise GpuLeaseError(f"GPU lease {lease_id} is not active (status={lease.status}).")

    now = _utcnow()
    expires_at = _as_utc(lease.expires_at) if lease.expires_at is not None else None
    if expires_at is not None and expires_at <= now:
        lease.status = "expired"
        lease.released_at = now
        db.add(lease)
        db.commit()
        raise GpuLeaseError(f"GPU lease {lease_id} has expired.")

    lease.heartbeat_at = now
    lease.expires_at = now + timedelta(seconds=extend_seconds)
    db.add(lease)
    db.commit()
    db.refresh(lease)
    return lease


def release_lease(db: Session, lease_id: UUID) -> GpuResourceLease:
    lease = db.get(GpuResourceLease, lease_id)
    if lease is None:
        raise GpuLeaseError(f"GPU lease {lease_id} not found.")
    if lease.status != "active":
        return lease

    now = _utcnow()
    lease.status = "released"
    lease.released_at = now
    db.add(lease)
    db.commit()
    db.refresh(lease)
    return lease


def acquire_voice_preview_lease(
    db: Session,
    *,
    owner: str,
    workload_id: str | None,
    worker_id: str | None = None,
    resource_key: str = DEFAULT_RESOURCE_KEY,
    ttl_seconds: int = 300,
    metadata: dict | None = None,
) -> GpuResourceLease:
    """Acquire a lease that serializes with video GPU work via exclusive_group."""
    return acquire_lease(
        db,
        GpuLeaseAcquireRequest(
            resource_key=resource_key,
            exclusive_group=DEFAULT_EXCLUSIVE_GROUP,
            workload_type=VOICE_PREVIEW_WORKLOAD,
            workload_id=workload_id,
            owner=owner,
            worker_id=worker_id,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {"serializes_with": sorted(VIDEO_GPU_WORKLOADS)},
        ),
    )
