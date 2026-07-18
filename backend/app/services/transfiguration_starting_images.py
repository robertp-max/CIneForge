"""Fail-closed Transfiguration starting-image preflight, import and assignment."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import AuditLog, Chapter, PlanningMediaAsset, Project, Scene, Shot
from backend.app.services import reference_assets


PROJECT_ID = UUID("1823e5da-e926-5b61-9d45-4bf9bea10c94")
STORY_ID = UUID("6db487e3-76f5-5ac8-86a6-e2816536e8b8")
EXPECTED_ALLOWLIST = (
    "grok-01c39ba1-a7a7-4413-aecc-9cbca43ec378.jpg",
    "grok-02a5678c-1f87-4c44-b8c2-9eb9b49d302e.jpg",
    "grok-2ab55adc-cd2a-4675-83fc-187959f28d2e.jpg",
    "grok-2b0970c2-64eb-4825-b0bb-3f6d34eff343.jpg",
    "grok-2cde8c25-0ef4-44cf-adfa-9f0605ff5b7d.jpg",
    "grok-2e50c7db-2c4d-45f9-85dd-b53236cba840.jpg",
    "grok-2ffc15a9-1b13-4375-8075-35371ebdcfcc.jpg",
    "grok-3c55e4cb-62f4-4f5a-926d-3db86c1f7946.jpg",
    "grok-3e0dcf49-b318-4aca-bb22-a54fb7259485.jpg",
    "grok-3eb0ff92-400c-4381-bb06-5746366e0bc8.jpg",
    "grok-4c74fbe4-2ae3-4330-9f93-f9089edc20c9.jpg",
    "grok-5be4f39f-c714-4104-9054-63885add3ce9.jpg",
    "grok-5e2f5e95-281c-409e-99b3-3f66de2a5a8d.jpg",
    "grok-5eb8d776-69dd-4b23-85a6-667d26cfed40.jpg",
    "grok-5ebe55bb-1e0f-4eb1-9ce6-98f7ceb18b17.jpg",
    "grok-6c491b78-8976-4288-840e-8ffb42a01034.jpg",
    "grok-6c987f99-4af0-420f-9278-981b61ae005b.jpg",
    "grok-6f7f5607-cc48-4b60-ad0f-fd80c5d370d8.jpg",
    "grok-6f99d949-117a-436d-bc84-fe74bc9f26e8.jpg",
    "grok-07b39775-9649-46dc-902f-f7383847f952.jpg",
    "grok-7bf85ad9-bf5a-4bc9-8d65-9aa7f65f545d.jpg",
    "grok-7d984de4-9bca-4f16-bbd7-0ff91bd44d4c.jpg",
    "grok-7ef8857a-33bc-4f33-b287-23ee5a60c5e5.jpg",
    "grok-8b945d0d-4edc-48d2-bfb6-f8de47ef9e06.png",
    "grok-8fd43168-71b0-41e4-b5c0-604c5bbba0d9.jpg",
    "grok-8ff89ed4-1d10-4ec0-a2ab-41635205b626.jpg",
    "grok-9ade94cd-c9b3-4446-8e97-a50aea073af4.jpg",
    "grok-20d0c127-764a-4eeb-a4d8-8ef40ffd80bc.jpg",
    "grok-21cd5d00-d19e-4a7b-9674-35033b83dbf5.jpg",
    "grok-22a7718d-c5d1-4a1c-935c-ceceeb5860ea.jpg",
    "grok-38f7ec21-7029-4d47-a7e9-7c95e9df0c30.jpg",
    "grok-40caff64-dc6d-486b-9d69-8e68192f182e.jpg",
    "grok-053a76bc-f04e-46ef-b7c7-22b11909dc87.jpg",
    "grok-56da7230-10fb-4112-ad3e-84b76dd8e394.jpg",
    "grok-56e3d79c-00ff-41b8-afcc-5d70cd93a76a.jpg",
    "grok-57ed3ff4-3d1e-4f52-a76e-e399310464a6.png",
    "grok-58a5dc2a-f007-48fe-b770-bc03035e6bba.jpg",
    "grok-75e5e77f-5b02-4bf2-8375-13632a02ba84.jpg",
    "grok-76af0a63-e4c7-48da-9791-c51e979f6d4d.jpg",
    "grok-0095bd26-001b-46c2-8989-82905e946080.jpg",
    "grok-173ad0e9-4b71-441a-9745-009471ad40ca.jpg",
    "grok-364f88e2-3421-48c5-b6c2-adf58ebd9144.jpg",
    "grok-476a8e00-527b-4ca7-8516-0b850fbeee7f.jpg",
    "grok-576f2d58-b2cc-4c0b-8f37-7219fe5951fb.jpg",
    "grok-643ed305-d93e-4ed4-a91c-e72c4480e9b0.jpg",
    "grok-710b46d4-4ff2-41fb-bcf1-cc44fb916b1f.jpg",
    "grok-731c8d0d-10e6-4000-aac7-a37d147d0b56.jpg",
    "grok-762bcb3e-1f39-4af9-8e37-0b7ae095eca4.jpg",
    "grok-771fb3c3-e070-43f6-9ccb-e9c92cc38946.jpg",
    "grok-827bfded-2410-481b-9b2b-ca6fc88663f1.jpg",
    "grok-881ba075-d5e7-4ba9-b41c-02f32250133d.jpg",
    "grok-898f56ee-7e2a-43e2-83b0-c860158cecc3.jpg",
    "grok-973bb141-c42a-400a-aa56-36f5ee54a379.jpg",
    "grok-2969ac64-6401-423e-8e0f-025013430b79.jpg",
    "grok-4116cf3a-e7b8-4f02-a46e-d33e4fb5f722.jpg",
    "grok-4527ea0d-e104-4c32-9b02-e4242566032a.png",
)
KNOWN_REFERENCE_KINDS = {
    "grok-57ed3ff4-3d1e-4f52-a76e-e399310464a6.png": "character_reference",
    "grok-8b945d0d-4edc-48d2-bfb6-f8de47ef9e06.png": "art_direction_reference",
    "grok-4527ea0d-e104-4c32-9b02-e4242566032a.png": "art_direction_reference",
}
IMPORTABLE_CLASSES = {
    "clean single-shot starting-image candidate",
    "alternate candidate for a shot",
}
VALID_CLASSES = IMPORTABLE_CLASSES | {
    "character reference",
    "art-direction reference",
    "collage/contact sheet/multi-panel board",
    "duplicate",
    "unusable",
    "ambiguous",
}


class StartingImageImportError(ValueError):
    pass


@dataclass(frozen=True)
class PreflightRecord:
    filename: str
    path: Path
    data: bytes
    sha256: str
    mime_type: str
    width: int
    height: int
    classification: str
    suggested_shot_code: str | None
    confidence: float
    rationale: str
    existing_asset_id: UUID | None


def _mime_for(path: Path) -> str:
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if path.suffix.lower() == ".png":
        return "image/png"
    raise StartingImageImportError(f"Unsupported image extension: {path.name}")


def preflight_inventory(
    inventory_path: Path,
    source_root: Path,
    *,
    expected_allowlist: Iterable[str] = EXPECTED_ALLOWLIST,
) -> list[PreflightRecord]:
    source_root = source_root.expanduser().resolve()
    if not source_root.is_dir():
        raise StartingImageImportError(f"Source root is not a directory: {source_root}")
    expected = tuple(expected_allowlist)
    with inventory_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    names = [row.get("source_filename", "") for row in rows]
    if len(rows) != len(expected) or tuple(names) != expected or len(set(names)) != len(names):
        raise StartingImageImportError(
            "Inventory must contain the explicit allowlist exactly once and in reviewed order."
        )

    records: list[PreflightRecord] = []
    seen_hashes: dict[str, str] = {}
    for row in rows:
        filename = row["source_filename"]
        path = (source_root / filename).resolve()
        try:
            path.relative_to(source_root)
        except ValueError as exc:
            raise StartingImageImportError(f"Source path escapes the source root: {filename}") from exc
        if not path.is_file():
            raise StartingImageImportError(f"Allowlisted source is missing: {filename}")
        data = path.read_bytes()
        if not data:
            raise StartingImageImportError(f"Allowlisted source is empty: {filename}")
        digest = reference_assets.sha256_bytes(data)
        if digest != row["sha256"]:
            raise StartingImageImportError(f"Source SHA-256 changed for {filename}")
        mime_type = _mime_for(path)
        if row["detected_mime"] != mime_type or row["extension"] != path.suffix.lower():
            raise StartingImageImportError(f"Extension/MIME manifest mismatch for {filename}")
        if not reference_assets._image_bytes_are_decodable(data, mime_type):
            raise StartingImageImportError(f"Image decode failed for {filename}")
        width, height = reference_assets._image_dimensions(data, mime_type)
        if not width or not height or int(row["width"]) != width or int(row["height"]) != height:
            raise StartingImageImportError(f"Image dimensions changed for {filename}")
        classification = row["classification"]
        if classification not in VALID_CLASSES:
            raise StartingImageImportError(f"Unknown visual classification for {filename}")
        if digest in seen_hashes and classification != "duplicate":
            raise StartingImageImportError(
                f"Byte-identical sources require duplicate classification: {seen_hashes[digest]}, {filename}"
            )
        seen_hashes.setdefault(digest, filename)
        raw_asset_id = row.get("existing_or_reused_asset_id") or None
        records.append(
            PreflightRecord(
                filename=filename,
                path=path,
                data=data,
                sha256=digest,
                mime_type=mime_type,
                width=width,
                height=height,
                classification=classification,
                suggested_shot_code=row.get("suggested_shot_code") or None,
                confidence=float(row["confidence"]),
                rationale=row["visual_rationale"],
                existing_asset_id=UUID(raw_asset_id) if raw_asset_id else None,
            )
        )
    return records


def load_mapping(mapping_path: Path) -> dict:
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StartingImageImportError(f"Mapping could not be read: {exc}") from exc
    if mapping.get("schema_name") != "cineforge.transfiguration_starting_image_mapping.v1":
        raise StartingImageImportError("Unsupported starting-image mapping schema.")
    return mapping


def _target_shots(db: Session, project_id: UUID) -> list[Shot]:
    return list(
        db.scalars(
            select(Shot)
            .join(Scene, Shot.scene_id == Scene.id)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .where(Chapter.story_id == STORY_ID, Shot.archived_at.is_(None))
            .order_by(Chapter.order_index, Scene.order_index, Shot.order_index)
        )
    )


def validate_mapping(
    db: Session,
    *,
    project_id: UUID,
    mapping: dict,
    records: list[PreflightRecord],
    expected_shot_count: int = 40,
) -> tuple[list[Shot], dict[str, dict], dict[str, PreflightRecord]]:
    if project_id != PROJECT_ID or mapping.get("project_id") != str(project_id):
        raise StartingImageImportError("The mapping is not for the Transfiguration target project.")
    if db.get(Project, project_id) is None:
        raise StartingImageImportError(f"Target project does not exist: {project_id}")
    shots = _target_shots(db, project_id)
    entries = mapping.get("entries")
    if not isinstance(entries, list) or len(entries) != expected_shot_count or len(shots) != expected_shot_count:
        raise StartingImageImportError("Mapping and database must each contain exactly 40 target shots.")
    by_id = {str(shot.id): shot for shot in shots}
    entry_by_id: dict[str, dict] = {}
    records_by_name = {record.filename: record for record in records}
    selected_names: set[str] = set()
    for entry in entries:
        shot_id = entry.get("shot_id")
        shot = by_id.get(shot_id)
        if shot is None or shot_id in entry_by_id:
            raise StartingImageImportError(f"Mapping contains an unknown or duplicate shot: {shot_id}")
        code = shot.title.split("—", 1)[0].strip()
        if entry.get("shot_code") != code or entry.get("shot_title") != shot.title:
            raise StartingImageImportError(f"Shot identity mismatch for {shot_id}")
        filename = entry.get("selected_source_filename")
        if filename is not None:
            record = records_by_name.get(filename)
            if record is None:
                raise StartingImageImportError(f"Mapping selects a non-allowlisted source: {filename}")
            if record.classification != "clean single-shot starting-image candidate":
                raise StartingImageImportError(f"Mapping selects a non-clean source: {filename}")
            if filename in KNOWN_REFERENCE_KINDS:
                raise StartingImageImportError(f"Mapping selects a known non-starting reference: {filename}")
            if record.sha256 != entry.get("selected_sha256"):
                raise StartingImageImportError(f"Mapping SHA-256 mismatch for {filename}")
            if filename in selected_names:
                raise StartingImageImportError(f"One source is selected for multiple shots: {filename}")
            selected_names.add(filename)
        entry_by_id[shot_id] = entry
    return shots, entry_by_id, records_by_name


def _operation_id(records: list[PreflightRecord], mapping: dict) -> str:
    stable = {
        "sources": [
            [r.filename, r.sha256, r.classification, r.suggested_shot_code, r.confidence]
            for r in records
        ],
        "mapping": [
            [
                entry.get("shot_id"),
                entry.get("selected_source_filename"),
                entry.get("selected_sha256"),
                entry.get("confidence"),
            ]
            for entry in mapping["entries"]
        ],
    }
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _audit_once(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    action: str,
    details: dict,
) -> bool:
    rows = db.scalars(select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == entity_id))
    for row in rows:
        if all((row.details or {}).get(key) == value for key, value in details.items()):
            return False
    db.add(AuditLog(entity_type=entity_type, entity_id=entity_id, action=action, details=details))
    return True


def _source_was_audited(db: Session, operation_id: str, filename: str) -> bool:
    rows = db.scalars(
        select(AuditLog).where(
            AuditLog.action.in_(
                (
                    "transfiguration_starting_image_candidate_imported",
                    "transfiguration_starting_image_candidate_reused",
                )
            )
        )
    )
    return any(
        (row.details or {}).get("operation_id") == operation_id
        and (row.details or {}).get("source_filename") == filename
        for row in rows
    )


def _verify_known_references(db: Session, project_id: UUID, records: list[PreflightRecord]) -> None:
    by_name = {record.filename: record for record in records}
    for filename, kind in KNOWN_REFERENCE_KINDS.items():
        record = by_name[filename]
        asset = db.scalar(
            select(PlanningMediaAsset).where(
                PlanningMediaAsset.project_id == project_id,
                PlanningMediaAsset.sha256 == record.sha256,
            )
        )
        if asset is None or asset.kind != kind or asset.id != record.existing_asset_id:
            raise StartingImageImportError(f"Known reference SHA/ID/kind mismatch: {filename}")


def run_import(
    db: Session,
    *,
    project_id: UUID,
    records: list[PreflightRecord],
    mapping: dict,
    apply: bool,
    minimum_confidence: float = 0.80,
) -> dict:
    shots, entry_by_id, _ = validate_mapping(
        db, project_id=project_id, mapping=mapping, records=records
    )
    _verify_known_references(db, project_id, records)
    operation_id = _operation_id(records, mapping)
    importable = [record for record in records if record.classification in IMPORTABLE_CLASSES]
    skipped = [record for record in records if record.classification not in IMPORTABLE_CLASSES]
    existing_by_sha = {
        asset.sha256: asset
        for asset in db.scalars(
            select(PlanningMediaAsset).where(
                PlanningMediaAsset.project_id == project_id,
                PlanningMediaAsset.kind == "starting_image",
            )
        )
    }
    planned_reuse = sum(record.sha256 in existing_by_sha for record in importable)
    selected_entries = [
        entry
        for entry in mapping["entries"]
        if entry.get("selected_source_filename") and float(entry.get("confidence", 0)) >= minimum_confidence
    ]
    if not apply:
        return {
            "status": "dry_run_ok",
            "operation_id": operation_id,
            "preflight_count": len(records),
            "planned_imports": len(importable) - planned_reuse,
            "planned_reuse": planned_reuse,
            "skipped_sources": len(skipped),
            "planned_assignments": len(selected_entries),
            "unresolved_shots": len(shots) - len(selected_entries),
            "source_asset_ids": {
                record.filename: str(existing_by_sha[record.sha256].id)
                for record in importable
                if record.sha256 in existing_by_sha
            },
        }

    created_paths: list[Path] = []
    source_assets: dict[str, PlanningMediaAsset] = {}
    imported = reused = assigned = replaced = audits_created = 0
    selected_entry_by_filename = {
        entry["selected_source_filename"]: entry
        for entry in selected_entries
    }
    try:
        for record in importable:
            selected_entry = selected_entry_by_filename.get(record.filename)
            asset, created, created_path = reference_assets.stage_asset_for_transaction(
                db,
                project_id=project_id,
                kind="starting_image",
                data=record.data,
                original_filename=record.filename,
                content_type=record.mime_type,
                source_type="imported",
                approval_state="draft",
                extra_metadata={
                    "operation": "transfiguration_starting_image_assignment",
                    "operation_id": operation_id,
                    "source_filename": record.filename,
                    "classification": record.classification,
                    "suggested_shot_code": record.suggested_shot_code,
                    "confidence": record.confidence,
                    "visual_rationale": record.rationale,
                    "alternate_candidate_filenames": (
                        selected_entry.get("alternate_candidate_filenames", [])
                        if selected_entry
                        else []
                    ),
                    "validation_warnings": (
                        selected_entry.get("validation_warnings", []) if selected_entry else []
                    ),
                },
            )
            if created_path is not None:
                created_paths.append(created_path)
            source_assets[record.filename] = asset
            imported += int(created)
            reused += int(not created)
            if not _source_was_audited(db, operation_id, record.filename):
                audits_created += int(
                    _audit_once(
                        db,
                        entity_type="planning_media_asset",
                        entity_id=asset.id,
                        action=(
                            "transfiguration_starting_image_candidate_imported"
                            if created
                            else "transfiguration_starting_image_candidate_reused"
                        ),
                        details={
                            "operation_id": operation_id,
                            "source_filename": record.filename,
                            "sha256": record.sha256,
                        },
                    )
                )

        for record in skipped:
            entity_id = record.existing_asset_id or project_id
            audits_created += int(
                _audit_once(
                    db,
                    entity_type="project",
                    entity_id=entity_id,
                    action="transfiguration_starting_image_mapping_skipped",
                    details={
                        "operation_id": operation_id,
                        "source_filename": record.filename,
                        "reason": record.classification,
                    },
                )
            )

        for shot in shots:
            entry = entry_by_id[str(shot.id)]
            filename = entry.get("selected_source_filename")
            confidence = float(entry.get("confidence", 0))
            if not filename or confidence < minimum_confidence:
                audits_created += int(
                    _audit_once(
                        db,
                        entity_type="shot",
                        entity_id=shot.id,
                        action="transfiguration_starting_image_mapping_skipped",
                        details={
                            "operation_id": operation_id,
                            "shot_code": entry["shot_code"],
                            "reason": "unresolved" if not filename else "below_minimum_confidence",
                        },
                    )
                )
                continue
            asset = source_assets[filename]
            raw_manifest_asset_id = entry.get("asset_id")
            if raw_manifest_asset_id and UUID(raw_manifest_asset_id) != asset.id:
                raise StartingImageImportError(f"Resolved asset ID changed for {filename}")
            if shot.starting_image_asset_id == asset.id:
                continue
            previous = shot.starting_image_asset_id
            if previous is not None:
                replaced += 1
                audits_created += int(
                    _audit_once(
                        db,
                        entity_type="shot",
                        entity_id=shot.id,
                        action="transfiguration_starting_image_replaced",
                        details={
                            "operation_id": operation_id,
                            "previous_asset_id": str(previous),
                            "asset_id": str(asset.id),
                        },
                    )
                )
            shot.starting_image_asset_id = asset.id
            assigned += 1
            audits_created += int(
                _audit_once(
                    db,
                    entity_type="shot",
                    entity_id=shot.id,
                    action="transfiguration_starting_image_assigned",
                    details={
                        "operation_id": operation_id,
                        "shot_code": entry["shot_code"],
                        "source_filename": filename,
                        "asset_id": str(asset.id),
                        "confidence": confidence,
                    },
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        root = reference_assets.managed_root()
        for path in created_paths:
            try:
                path.resolve().relative_to(root)
                path.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
        raise

    unresolved = sum(
        not entry.get("selected_source_filename")
        or float(entry.get("confidence", 0)) < minimum_confidence
        for entry in mapping["entries"]
    )
    return {
        "status": "applied",
        "operation_id": operation_id,
        "preflight_count": len(records),
        "imported": imported,
        "reused": reused,
        "skipped_sources": len(skipped),
        "assigned": assigned,
        "replaced": replaced,
        "unchanged_assignments": len(selected_entries) - assigned,
        "unresolved_shots": unresolved,
        "audit_events_created": audits_created,
        "source_asset_ids": {name: str(asset.id) for name, asset in source_assets.items()},
        "selected_asset_ids": [
            str(source_assets[entry["selected_source_filename"]].id) for entry in selected_entries
        ],
    }
