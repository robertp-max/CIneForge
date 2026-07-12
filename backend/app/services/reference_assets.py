"""Managed planning-media reference asset service (Storyboard Phase 1).

Safety guarantees:
- Fixed managed root under settings.storage_root (no arbitrary paths).
- Generated on-disk names only; original filename is metadata only.
- MIME + extension allowlist per asset kind.
- Bounded upload size.
- SHA-256 content hashing with per-project duplicate detection (never cloning).
- Optional image/audio metadata extraction from safe existing deps / stdlib.
- Soft archive + constrained delete policy with audit trail.
- Clients receive asset IDs and controlled streams — never filesystem paths.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
import struct
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.base import (
    AuditLog,
    Character,
    CharacterReferenceAsset,
    PlanningMediaAsset,
    Project,
)


class ReferenceAssetError(ValueError):
    """Domain validation / policy failure (typically HTTP 422)."""


class ReferenceAssetNotFoundError(ReferenceAssetError):
    """Missing entity (typically HTTP 404)."""


class ReferenceAssetConflictError(Exception):
    """Conflict such as duplicate link order (typically HTTP 409)."""


# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

MANAGED_SUBDIR = "planning_media"
MANAGED_URI_SCHEME = "cineforge-planning"

ASSET_KINDS = frozenset(
    {
        "character_reference",
        "starting_image",
        "voice_source",
        "story_document",
    }
)

# Per-kind allowlists: MIME types, extensions (lowercase with dot), max bytes.
KIND_POLICY: dict[str, dict] = {
    "character_reference": {
        "mimes": frozenset({"image/png", "image/jpeg", "image/webp"}),
        "extensions": frozenset({".png", ".jpg", ".jpeg", ".webp"}),
        "max_bytes": 25 * 1024 * 1024,
        "category": "image",
    },
    "starting_image": {
        "mimes": frozenset({"image/png", "image/jpeg", "image/webp"}),
        "extensions": frozenset({".png", ".jpg", ".jpeg", ".webp"}),
        "max_bytes": 25 * 1024 * 1024,
        "category": "image",
    },
    "voice_source": {
        "mimes": frozenset(
            {
                "audio/wav",
                "audio/x-wav",
                "audio/wave",
                "audio/mpeg",
                "audio/mp3",
                "audio/ogg",
                "audio/flac",
            }
        ),
        "extensions": frozenset({".wav", ".mp3", ".ogg", ".flac"}),
        "max_bytes": 50 * 1024 * 1024,
        "category": "audio",
    },
    "story_document": {
        "mimes": frozenset(
            {
                "text/plain",
                "text/markdown",
                "text/x-markdown",
                "application/pdf",
                "application/json",
            }
        ),
        "extensions": frozenset({".txt", ".md", ".markdown", ".pdf", ".json"}),
        "max_bytes": 10 * 1024 * 1024,
        "category": "document",
    },
}

# Normalize common browser MIME aliases onto canonical allowlist entries.
MIME_ALIASES: dict[str, str] = {
    "image/jpg": "image/jpeg",
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/mp3": "audio/mpeg",
    "text/x-markdown": "text/markdown",
}

_SAFE_ORIGINAL_NAME = re.compile(r"[^A-Za-z0-9._\- ]+")


# ---------------------------------------------------------------------------
# Managed root / path safety
# ---------------------------------------------------------------------------


def managed_root() -> Path:
    """Fixed managed root abstraction under settings.storage_root."""
    root = (get_settings().storage_root / MANAGED_SUBDIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _project_dir(project_id: UUID) -> Path:
    path = managed_root() / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _kind_dir(project_id: UUID, kind: str) -> Path:
    path = _project_dir(project_id) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_managed_uri(project_id: UUID, kind: str, stored_name: str) -> str:
    """Logical URI only — never a raw filesystem path for clients."""
    return f"{MANAGED_URI_SCHEME}://{project_id}/{kind}/{stored_name}"


def resolve_managed_path(asset: PlanningMediaAsset) -> Path:
    """Resolve an asset's on-disk path strictly under the managed root."""
    uri = asset.managed_uri or ""
    prefix = f"{MANAGED_URI_SCHEME}://"
    if not uri.startswith(prefix):
        raise ReferenceAssetError("Asset managed_uri is not a recognized managed URI.")
    remainder = uri[len(prefix) :]
    parts = remainder.split("/")
    if len(parts) != 3:
        raise ReferenceAssetError("Asset managed_uri has unexpected shape.")
    project_part, kind_part, name_part = parts
    if project_part != str(asset.project_id):
        raise ReferenceAssetError("Asset managed_uri project mismatch.")
    if kind_part != asset.kind:
        raise ReferenceAssetError("Asset managed_uri kind mismatch.")
    if ".." in name_part or "/" in name_part or "\\" in name_part or not name_part:
        raise ReferenceAssetError("Asset managed_uri name is unsafe.")

    root = managed_root()
    candidate = (root / project_part / kind_part / name_part).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ReferenceAssetError("Resolved path escapes managed root.") from exc
    return candidate


# ---------------------------------------------------------------------------
# Filename / MIME helpers
# ---------------------------------------------------------------------------


def _sanitize_original_filename(name: str | None) -> str | None:
    if not name:
        return None
    base = Path(name).name  # strip any path components
    cleaned = _SAFE_ORIGINAL_NAME.sub("_", base).strip(" .")
    if not cleaned:
        return None
    return cleaned[:240]


def _extension_for(original_filename: str | None, mime_type: str | None) -> str:
    if original_filename:
        ext = Path(original_filename).suffix.lower()
        if ext:
            return ext
    if mime_type:
        guessed = mimetypes.guess_extension(mime_type.split(";")[0].strip())
        if guessed == ".jpe":
            return ".jpg"
        if guessed:
            return guessed.lower()
    return ""


def _normalize_mime(content_type: str | None, extension: str) -> str | None:
    raw = (content_type or "").split(";")[0].strip().lower() or None
    if raw:
        raw = MIME_ALIASES.get(raw, raw)
        return raw
    if extension:
        guessed, _ = mimetypes.guess_type(f"file{extension}")
        if guessed:
            return MIME_ALIASES.get(guessed, guessed)
    return None


def _validate_kind_and_payload(
    kind: str,
    *,
    size_bytes: int,
    mime_type: str | None,
    extension: str,
) -> dict:
    if kind not in ASSET_KINDS:
        raise ReferenceAssetError(
            f"Unsupported asset kind '{kind}'. Allowed: {sorted(ASSET_KINDS)}."
        )
    policy = KIND_POLICY[kind]
    if size_bytes <= 0:
        raise ReferenceAssetError("Upload is empty.")
    if size_bytes > policy["max_bytes"]:
        raise ReferenceAssetError(
            f"Upload exceeds maximum size of {policy['max_bytes']} bytes for kind '{kind}'."
        )
    if extension not in policy["extensions"]:
        raise ReferenceAssetError(
            f"Extension '{extension or '(none)'}' is not allowed for kind '{kind}'. "
            f"Allowed: {sorted(policy['extensions'])}."
        )
    if not mime_type or mime_type not in policy["mimes"]:
        raise ReferenceAssetError(
            f"MIME type '{mime_type or '(none)'}' is not allowed for kind '{kind}'. "
            f"Allowed: {sorted(policy['mimes'])}."
        )
    return policy


# ---------------------------------------------------------------------------
# Metadata extraction (safe / optional)
# ---------------------------------------------------------------------------


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return None
    i = 2
    length = len(data)
    while i + 9 < length:
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        i += 2
        if marker in {0xD8, 0xD9}:
            continue
        if i + 2 > length:
            return None
        seg_len = struct.unpack(">H", data[i : i + 2])[0]
        if seg_len < 2:
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if i + 7 > length:
                return None
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            return int(width), int(height)
        i += seg_len
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        # Lossy bitstream: width/height in frame header (14-bit little endian).
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return int(width), int(height)
    if chunk == b"VP8L" and len(data) >= 25:
        b0, b1, b2, b3 = data[21:25]
        width = 1 + (((b1 & 0x3F) << 8) | b0)
        height = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        return int(width), int(height)
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return int(width), int(height)
    return None


def _image_dimensions(data: bytes, mime_type: str | None) -> tuple[int | None, int | None]:
    # Prefer lightweight header parsing; fall back to Pillow if present.
    dims = None
    if mime_type == "image/png" or data[:8] == b"\x89PNG\r\n\x1a\n":
        dims = _png_dimensions(data)
    elif mime_type == "image/jpeg" or data[:2] == b"\xff\xd8":
        dims = _jpeg_dimensions(data)
    elif mime_type == "image/webp" or (len(data) >= 12 and data[8:12] == b"WEBP"):
        dims = _webp_dimensions(data)

    if dims is None:
        try:
            from io import BytesIO

            from PIL import Image  # type: ignore

            with Image.open(BytesIO(data)) as img:
                dims = (int(img.width), int(img.height))
        except Exception:
            dims = None

    if dims is None:
        return None, None
    return dims[0], dims[1]


def _wav_duration_sec(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return round(frames / float(rate), 6)
    except Exception:
        return None


def _extract_metadata(
    *,
    category: str,
    data: bytes,
    mime_type: str | None,
    path: Path | None = None,
) -> dict:
    meta: dict = {"extraction": "none"}
    width = height = None
    duration_sec = None

    if category == "image":
        width, height = _image_dimensions(data, mime_type)
        if width is not None:
            meta["extraction"] = "image_headers_or_pillow"
    elif category == "audio":
        if mime_type in {"audio/wav", "audio/x-wav", "audio/wave"} and path is not None:
            duration_sec = _wav_duration_sec(path)
            if duration_sec is not None:
                meta["extraction"] = "stdlib_wave"
        # Intentionally no FFmpeg / ffprobe — never call external media tools.

    return {
        "width": width,
        "height": height,
        "duration_sec": duration_sec,
        "metadata_json": meta,
    }


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


def _project_or_error(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ReferenceAssetNotFoundError("Project not found.")
    return project


def _asset_or_error(db: Session, asset_id: UUID, *, include_archived: bool = True) -> PlanningMediaAsset:
    asset = db.get(PlanningMediaAsset, asset_id)
    if asset is None:
        raise ReferenceAssetNotFoundError("Asset not found.")
    if not include_archived and asset.archived_at is not None:
        raise ReferenceAssetNotFoundError("Asset is archived.")
    return asset


def _audit(
    db: Session,
    *,
    entity_id: UUID | None,
    action: str,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            entity_type="planning_media_asset",
            entity_id=entity_id,
            action=action,
            details=details or {},
        )
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_duplicate(db: Session, project_id: UUID, digest: str) -> PlanningMediaAsset | None:
    return db.scalar(
        select(PlanningMediaAsset).where(
            PlanningMediaAsset.project_id == project_id,
            PlanningMediaAsset.sha256 == digest,
        )
    )


def upload_asset(
    db: Session,
    *,
    project_id: UUID,
    kind: str,
    data: bytes,
    original_filename: str | None = None,
    content_type: str | None = None,
    source_type: str = "user_upload",
    approval_state: str = "draft",
    extra_metadata: dict | None = None,
    consent_confirmed: bool | None = None,
) -> tuple[PlanningMediaAsset, bool]:
    """Store a managed asset.

    Returns (asset, created) where created=False means a same-project SHA-256
    duplicate was returned without cloning bytes or creating a second row.
    """
    _project_or_error(db, project_id)

    if kind == "voice_source" and consent_confirmed is not True:
        raise ReferenceAssetError(
            "Voice source uploads require explicit consent_confirmed=true."
        )

    safe_name = _sanitize_original_filename(original_filename)
    extension = _extension_for(safe_name, content_type)
    mime_type = _normalize_mime(content_type, extension)
    policy = _validate_kind_and_payload(
        kind,
        size_bytes=len(data),
        mime_type=mime_type,
        extension=extension,
    )

    digest = sha256_bytes(data)
    existing = find_duplicate(db, project_id, digest)
    if existing is not None:
        # Never clone: return the existing record. Optionally un-archive if needed.
        if existing.archived_at is not None:
            existing.archived_at = None
            if existing.approval_state == "archived":
                existing.approval_state = "draft"
            _audit(
                db,
                entity_id=existing.id,
                action="planning_media_asset_duplicate_reused_unarchived",
                details={"sha256": digest, "kind": kind},
            )
            db.commit()
            db.refresh(existing)
        else:
            _audit(
                db,
                entity_id=existing.id,
                action="planning_media_asset_duplicate_reused",
                details={"sha256": digest, "kind": kind, "requested_kind": kind},
            )
            db.commit()
        return existing, False

    stored_name = f"{uuid.uuid4().hex}{extension}"
    dest_dir = _kind_dir(project_id, kind)
    dest_path = (dest_dir / stored_name).resolve()
    try:
        dest_path.relative_to(managed_root())
    except ValueError as exc:
        raise ReferenceAssetError("Generated path escapes managed root.") from exc

    # Write bytes, then extract metadata (audio duration needs a path for wave).
    dest_path.write_bytes(data)
    try:
        extracted = _extract_metadata(
            category=policy["category"],
            data=data,
            mime_type=mime_type,
            path=dest_path,
        )
        metadata = dict(extracted["metadata_json"])
        if extra_metadata:
            metadata["client"] = extra_metadata
        if kind == "voice_source":
            metadata["consent_confirmed"] = True

        asset = PlanningMediaAsset(
            project_id=project_id,
            kind=kind,
            source_type=source_type,
            managed_uri=build_managed_uri(project_id, kind, stored_name),
            sha256=digest,
            mime_type=mime_type,
            width=extracted["width"],
            height=extracted["height"],
            duration_sec=extracted["duration_sec"],
            approval_state=approval_state,
            metadata_json=metadata,
            original_filename=safe_name,
            size_bytes=len(data),
        )
        db.add(asset)
        db.flush()
        _audit(
            db,
            entity_id=asset.id,
            action="planning_media_asset_uploaded",
            details={
                "kind": kind,
                "sha256": digest,
                "size_bytes": len(data),
                "mime_type": mime_type,
                "original_filename": safe_name,
            },
        )
        db.commit()
        db.refresh(asset)
        return asset, True
    except Exception:
        # Best-effort cleanup of orphaned bytes on failure.
        try:
            if dest_path.exists():
                dest_path.unlink()
        except OSError:
            pass
        db.rollback()
        raise


def upload_asset_from_fileobj(
    db: Session,
    *,
    project_id: UUID,
    kind: str,
    fileobj: BinaryIO,
    original_filename: str | None = None,
    content_type: str | None = None,
    max_read_bytes: int | None = None,
    source_type: str = "user_upload",
    consent_confirmed: bool | None = None,
    extra_metadata: dict | None = None,
) -> tuple[PlanningMediaAsset, bool]:
    """Read a file object with an upper bound, then delegate to upload_asset."""
    if kind not in ASSET_KINDS:
        raise ReferenceAssetError(
            f"Unsupported asset kind '{kind}'. Allowed: {sorted(ASSET_KINDS)}."
        )
    limit = max_read_bytes or KIND_POLICY[kind]["max_bytes"]
    # Read one extra byte to detect oversize without trusting client Content-Length.
    data = fileobj.read(limit + 1)
    if data is None:
        data = b""
    if len(data) > limit:
        raise ReferenceAssetError(
            f"Upload exceeds maximum size of {limit} bytes for kind '{kind}'."
        )
    return upload_asset(
        db,
        project_id=project_id,
        kind=kind,
        data=data,
        original_filename=original_filename,
        content_type=content_type,
        source_type=source_type,
        consent_confirmed=consent_confirmed,
        extra_metadata=extra_metadata,
    )


def get_asset(
    db: Session,
    asset_id: UUID,
    *,
    include_archived: bool = True,
) -> PlanningMediaAsset:
    return _asset_or_error(db, asset_id, include_archived=include_archived)


def list_assets(
    db: Session,
    project_id: UUID,
    *,
    kind: str | None = None,
    include_archived: bool = False,
) -> list[PlanningMediaAsset]:
    _project_or_error(db, project_id)
    query = select(PlanningMediaAsset).where(PlanningMediaAsset.project_id == project_id)
    if kind is not None:
        if kind not in ASSET_KINDS:
            raise ReferenceAssetError(
                f"Unsupported asset kind '{kind}'. Allowed: {sorted(ASSET_KINDS)}."
            )
        query = query.where(PlanningMediaAsset.kind == kind)
    if not include_archived:
        query = query.where(PlanningMediaAsset.archived_at.is_(None))
    query = query.order_by(PlanningMediaAsset.created_at.desc())
    return list(db.scalars(query))


def archive_asset(
    db: Session,
    asset_id: UUID,
    *,
    reason: str | None = None,
) -> PlanningMediaAsset:
    asset = _asset_or_error(db, asset_id, include_archived=True)
    if asset.archived_at is not None:
        return asset
    asset.archived_at = datetime.utcnow()
    asset.approval_state = "archived"
    _audit(
        db,
        entity_id=asset.id,
        action="planning_media_asset_archived",
        details={"reason": reason, "kind": asset.kind},
    )
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(
    db: Session,
    asset_id: UUID,
    *,
    reason: str | None = None,
    force: bool = False,
) -> None:
    """Delete policy:

    - Prefer archive over delete.
    - Hard delete only when archived (or force=True for draft assets).
    - Removes managed file when path resolves safely under managed root.
    """
    asset = _asset_or_error(db, asset_id, include_archived=True)
    is_draft = (asset.approval_state or "") in {"draft", "archived"}
    if asset.archived_at is None and not (force and is_draft):
        raise ReferenceAssetError(
            "Hard delete requires the asset to be archived first "
            "(or force=true on a draft asset). Prefer archive."
        )

    path: Path | None = None
    try:
        path = resolve_managed_path(asset)
    except ReferenceAssetError:
        path = None

    details = {
        "reason": reason,
        "kind": asset.kind,
        "sha256": asset.sha256,
        "force": force,
        "file_removed": False,
    }

    # Detach character reference links first (FK is CASCADE, but be explicit).
    links = list(
        db.scalars(
            select(CharacterReferenceAsset).where(CharacterReferenceAsset.asset_id == asset_id)
        )
    )
    for link in links:
        db.delete(link)

    db.delete(asset)
    _audit(
        db,
        entity_id=asset_id,
        action="planning_media_asset_deleted",
        details=details,
    )
    db.commit()

    if path is not None and path.exists() and path.is_file():
        try:
            path.unlink()
            details["file_removed"] = True
        except OSError:
            # DB row is gone; leftover file is non-fatal. Log via audit already committed.
            pass


def open_asset_for_stream(
    db: Session,
    asset_id: UUID,
) -> tuple[PlanningMediaAsset, Path]:
    """Resolve a controlled stream path for an asset ID (no path input from client)."""
    asset = _asset_or_error(db, asset_id, include_archived=False)
    path = resolve_managed_path(asset)
    if not path.exists() or not path.is_file():
        raise ReferenceAssetNotFoundError("Asset bytes are not available on disk.")
    return asset, path


def to_public_dict(asset: PlanningMediaAsset, *, is_duplicate: bool = False) -> dict:
    """Serialize without exposing filesystem paths."""
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "kind": asset.kind,
        "source_type": asset.source_type,
        "managed_uri": asset.managed_uri,
        "sha256": asset.sha256,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "duration_sec": float(asset.duration_sec) if asset.duration_sec is not None else None,
        "approval_state": asset.approval_state,
        "metadata_json": asset.metadata_json or {},
        "original_filename": asset.original_filename,
        "size_bytes": asset.size_bytes,
        "archived_at": asset.archived_at,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
        "is_duplicate": is_duplicate,
    }


# ---------------------------------------------------------------------------
# Character reference linking
# ---------------------------------------------------------------------------


def link_character_reference(
    db: Session,
    *,
    character_id: UUID,
    asset_id: UUID,
    reference_role: str = "primary",
    approved: bool = False,
    order_index: int = 0,
) -> CharacterReferenceAsset:
    character = db.get(Character, character_id)
    if character is None:
        raise ReferenceAssetNotFoundError("Character not found.")
    asset = _asset_or_error(db, asset_id, include_archived=False)
    if asset.kind != "character_reference":
        raise ReferenceAssetError("Only character_reference assets may be linked to characters.")

    # Asset must belong to the same project as the character's story.
    from backend.app.db.base import Story

    story = db.get(Story, character.story_id)
    if story is None or story.project_id != asset.project_id:
        raise ReferenceAssetError("Asset project must match the character's story project.")

    existing_order = db.scalar(
        select(CharacterReferenceAsset).where(
            CharacterReferenceAsset.character_id == character_id,
            CharacterReferenceAsset.order_index == order_index,
        )
    )
    if existing_order is not None:
        raise ReferenceAssetConflictError(
            f"Character already has a reference at order_index={order_index}."
        )

    link = CharacterReferenceAsset(
        character_id=character_id,
        asset_id=asset_id,
        reference_role=reference_role,
        approved=approved,
        order_index=order_index,
    )
    db.add(link)
    db.flush()
    _audit(
        db,
        entity_id=asset_id,
        action="character_reference_linked",
        details={
            "character_id": str(character_id),
            "reference_role": reference_role,
            "order_index": order_index,
            "link_id": str(link.id),
        },
    )
    db.commit()
    db.refresh(link)
    return link


def list_character_references(
    db: Session,
    character_id: UUID,
) -> list[CharacterReferenceAsset]:
    character = db.get(Character, character_id)
    if character is None:
        raise ReferenceAssetNotFoundError("Character not found.")
    return list(
        db.scalars(
            select(CharacterReferenceAsset)
            .where(CharacterReferenceAsset.character_id == character_id)
            .order_by(CharacterReferenceAsset.order_index)
        )
    )


def unlink_character_reference(db: Session, link_id: UUID) -> None:
    link = db.get(CharacterReferenceAsset, link_id)
    if link is None:
        raise ReferenceAssetNotFoundError("Character reference link not found.")
    asset_id = link.asset_id
    character_id = link.character_id
    db.delete(link)
    _audit(
        db,
        entity_id=asset_id,
        action="character_reference_unlinked",
        details={"character_id": str(character_id), "link_id": str(link_id)},
    )
    db.commit()
