#!/usr/bin/env python3
"""Synchronize local ComfyUI filesystem assets into CineForge local_runtime_assets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import get_settings  # noqa: E402
from backend.app.db.session import SessionLocal  # noqa: E402
from backend.app.services.local_assets.sync import sync_local_comfy_assets  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comfyui-root",
        type=Path,
        default=Path(r"C:\AI\ComfyUI_windows_portable\ComfyUI"),
        help="Path to ComfyUI installation root",
    )
    parser.add_argument(
        "--skip-hash",
        action="store_true",
        help="Skip SHA-256 computation (faster; hashes remain unknown/prior)",
    )
    parser.add_argument(
        "--hash-max-bytes",
        type=int,
        default=None,
        help="Skip hashing files larger than this many bytes",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write JSON summary",
    )
    args = parser.parse_args()

    # Ensure settings/database path exists
    settings = get_settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        summary = sync_local_comfy_assets(
            db,
            comfyui_root=args.comfyui_root,
            compute_hash=not args.skip_hash,
            hash_max_bytes=args.hash_max_bytes,
        )
    finally:
        db.close()

    text = json.dumps(summary, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    return 0 if not summary.get("errors") else 2


if __name__ == "__main__":
    raise SystemExit(main())
