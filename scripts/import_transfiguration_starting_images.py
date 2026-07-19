"""Import reviewed Transfiguration starting images without invoking generation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from uuid import UUID

from backend.app.db.session import SessionLocal
from backend.app.services.transfiguration_starting_images import (
    PROJECT_ID,
    StartingImageImportError,
    load_mapping,
    preflight_inventory,
    run_import,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = REPO_ROOT / "examples" / "projects" / "transfiguration_5m" / "starting_images"
DEFAULT_INVENTORY = MANIFEST_ROOT / "starting_image_inventory.csv"
DEFAULT_MAPPING = MANIFEST_ROOT / "shot_starting_image_mapping.json"
DEFAULT_SOURCE_ROOT = Path(r"C:\Users\razer\Documents\transfiguration")


def _write_resolved_manifests(
    inventory_path: Path,
    mapping_path: Path,
    source_asset_ids: dict[str, str],
) -> None:
    mapping = load_mapping(mapping_path)
    for entry in mapping["entries"]:
        filename = entry.get("selected_source_filename")
        if filename:
            entry["asset_id"] = source_asset_ids[filename]
    mapping_temp = mapping_path.with_suffix(mapping_path.suffix + ".tmp")
    mapping_temp.write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    mapping_temp.replace(mapping_path)

    with inventory_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if not fieldnames:
        fieldnames = list(rows[0])
    for row in rows:
        asset_id = source_asset_ids.get(row["source_filename"])
        if asset_id:
            row["existing_or_reused_asset_id"] = asset_id
    inventory_temp = inventory_path.with_suffix(inventory_path.suffix + ".tmp")
    with inventory_temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    inventory_temp.replace(inventory_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preflight and import only the reviewed 73-file Transfiguration allowlist."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--project-id", type=UUID, default=PROJECT_ID)
    parser.add_argument("--minimum-confidence", type=float, default=0.80)
    args = parser.parse_args()
    if not 0 <= args.minimum_confidence <= 1:
        parser.error("--minimum-confidence must be between 0 and 1")

    source_root = args.source_root.expanduser().resolve()
    mapping_path = args.mapping.expanduser().resolve()
    inventory_path = args.inventory.expanduser().resolve()
    try:
        records = preflight_inventory(inventory_path, source_root)
        mapping = load_mapping(mapping_path)
        with SessionLocal() as db:
            result = run_import(
                db,
                project_id=args.project_id,
                records=records,
                mapping=mapping,
                apply=args.apply,
                minimum_confidence=args.minimum_confidence,
            )
        if args.apply:
            _write_resolved_manifests(
                inventory_path,
                mapping_path,
                result["source_asset_ids"],
            )
    except StartingImageImportError as exc:
        raise SystemExit(f"Starting-image import rejected: {exc}") from exc
    print(
        json.dumps(
            {
                **result,
                "project_id": str(args.project_id),
                "source_root": str(source_root),
                "inventory": str(inventory_path),
                "mapping": str(mapping_path),
                "rendering_enabled": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
