"""Idempotent local ComfyUI asset synchronization into local_runtime_assets."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import LocalRuntimeAsset
from backend.app.services.local_assets.metadata import (
    infer_family_and_base,
    read_safetensors_header,
    stream_sha256,
)
from backend.app.services.local_assets.scanner import ScannedFile, scan_comfyui_root
from backend.app.services.local_assets.workflow_inspect import inspect_workflow


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _should_rehash(row: LocalRuntimeAsset | None, scanned: ScannedFile) -> bool:
    if row is None:
        return True
    if not row.sha256:
        return True
    if row.file_size_bytes != scanned.file_size_bytes:
        return True
    if row.mtime_ns is not None and row.mtime_ns != scanned.mtime_ns:
        return True
    return False


def _build_metadata(scanned: ScannedFile, compute_hash: bool) -> dict[str, Any]:
    meta: dict[str, Any] = {"source": "comfyui_filesystem"}
    path = scanned.absolute_path
    if scanned.asset_type.startswith("workflow"):
        meta["workflow"] = inspect_workflow(path)
    elif path.suffix.lower() == ".safetensors":
        meta["safetensors"] = read_safetensors_header(path)
    return meta


def sync_local_comfy_assets(
    db: Session,
    *,
    comfyui_root: Path,
    compute_hash: bool = True,
    hash_max_bytes: int | None = None,
) -> dict[str, Any]:
    """Scan ComfyUI root and upsert local_runtime_assets. Never deletes files on disk."""
    root = Path(comfyui_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"ComfyUI root not found: {root}")

    scanned = scan_comfyui_root(root)
    now = _utcnow()
    seen_paths: set[str] = set()

    added = 0
    updated = 0
    unchanged = 0
    hashed = 0
    errors: list[dict[str, str]] = []

    # Prefetch existing rows
    existing_rows = list(db.scalars(select(LocalRuntimeAsset)))
    by_path = {row.file_path: row for row in existing_rows}

    for item in scanned:
        abs_path = str(item.absolute_path)
        seen_paths.add(abs_path)
        row = by_path.get(abs_path)

        try:
            metadata = _build_metadata(item, compute_hash)
            family, base = infer_family_and_base(
                name=item.name,
                relative_path=item.relative_path,
                asset_type=item.asset_type,
                metadata=metadata.get("safetensors") or metadata.get("workflow") or {},
            )
            # Workflow family from inspection
            if item.asset_type.startswith("workflow"):
                wf = metadata.get("workflow") or {}
                guesses = wf.get("families_guess") or []
                if guesses and not family:
                    family = str(guesses[0])

            do_hash = bool(compute_hash) and _should_rehash(row, item)
            if do_hash and hash_max_bytes is not None and item.file_size_bytes > hash_max_bytes:
                do_hash = False
                metadata["hash_skipped"] = "over_hash_max_bytes"

            sha: str | None = row.sha256 if row and not do_hash else None
            if do_hash:
                sha = stream_sha256(item.absolute_path)
                hashed += 1

            if row is None:
                row = LocalRuntimeAsset(
                    id=uuid4(),
                    asset_type=item.asset_type,
                    name=item.name,
                    file_path=abs_path,
                    relative_path=item.relative_path,
                    model_category=item.model_category,
                    file_extension=item.file_extension,
                    file_size_bytes=item.file_size_bytes,
                    sha256=sha,
                    metadata_json=metadata,
                    inferred_family=family,
                    inferred_base=base,
                    selector_value=item.selector_value,
                    source_kind="comfyui_filesystem",
                    is_present=True,
                    first_seen_at=now,
                    last_seen_at=now,
                    mtime_ns=item.mtime_ns,
                )
                db.add(row)
                by_path[abs_path] = row
                added += 1
            else:
                changed = False
                fields = {
                    "asset_type": item.asset_type,
                    "name": item.name,
                    "relative_path": item.relative_path,
                    "model_category": item.model_category,
                    "file_extension": item.file_extension,
                    "file_size_bytes": item.file_size_bytes,
                    "metadata_json": metadata,
                    "inferred_family": family,
                    "inferred_base": base,
                    "selector_value": item.selector_value,
                    "is_present": True,
                    "last_seen_at": now,
                    "mtime_ns": item.mtime_ns,
                }
                if sha is not None:
                    fields["sha256"] = sha
                for key, value in fields.items():
                    if getattr(row, key) != value:
                        setattr(row, key, value)
                        changed = True
                if changed:
                    updated += 1
                else:
                    unchanged += 1
                    row.is_present = True
                    row.last_seen_at = now
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": abs_path, "error": str(exc)})

    missing = 0
    for path, row in by_path.items():
        if path not in seen_paths and row.is_present:
            row.is_present = False
            row.last_seen_at = now
            missing += 1

    db.commit()

    # Duplicate grouping report (by sha256)
    present = [r for r in by_path.values() if r.is_present and r.sha256]
    by_hash: dict[str, list[str]] = defaultdict(list)
    for r in present:
        by_hash[r.sha256 or ""].append(r.relative_path)
    duplicates = {
        h: paths for h, paths in by_hash.items() if h and len(paths) > 1
    }

    type_counts = Counter(r.asset_type for r in by_path.values() if r.is_present)
    total_bytes = sum(int(r.file_size_bytes or 0) for r in by_path.values() if r.is_present)

    return {
        "comfyui_root": str(root),
        "scanned": len(scanned),
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
        "marked_missing": missing,
        "hashed": hashed,
        "present": sum(1 for r in by_path.values() if r.is_present),
        "total_size_bytes": total_bytes,
        "by_type": dict(type_counts),
        "duplicate_hash_groups": len(duplicates),
        "duplicates_sample": {k: v for k, v in list(duplicates.items())[:20]},
        "errors": errors[:50],
        "synced_at": now.isoformat(),
    }
