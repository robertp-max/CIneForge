"""Export the non-executing workflow candidate registry to storage JSON."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.services.workflows.candidate_catalog import catalog_document


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPOSITORY_ROOT / "storage" / "workflow_candidates" / "catalog.json"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(catalog_document(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

