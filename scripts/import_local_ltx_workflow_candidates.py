"""Import installed official LTX examples as disabled CineForge candidates.

The source graph is preserved byte-for-byte for provenance. A normalized copy
changes only known base-loader widget values to the exact CineForge video model
contract. Nothing is submitted to ComfyUI.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.services.generation_model_contract import (
    BASE_MODEL_LOADER_TYPES,
    VIDEO_MODEL,
    validate_workflow_base_models,
)
from backend.app.services.workflows.candidate_catalog import CANDIDATES


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOCAL_LTX_ROOT = Path(
    "C:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/"
    "ComfyUI-LTXVideo/example_workflows/2.3"
)

LOCAL_SOURCE_BY_CANDIDATE = {
    "CF-CAND-VID-001": "LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json",
    "CF-CAND-VID-002": "LTX-2.3_T2V_I2V_Two_Stage_Distilled.json",
    "CF-CAND-VID-004": "LTX-2.3_ICLoRA_Union_Control_Distilled.json",
    "CF-CAND-VID-005": "LTX-2.3_ICLoRA_Motion_Track_Distilled.json",
    "CF-CAND-VID-007": "LTX-2.3_ICLoRA_Lipdub_Two_Stage_Distilled.json",
    "CF-CAND-VID-012": "LTX-2.3_ICLoRA_HDR_Distilled.json",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_base_loader(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Expected a ComfyUI UI-format workflow with nodes.")

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type") or node.get("class_type")
        if node_type not in BASE_MODEL_LOADER_TYPES:
            continue
        widgets = node.get("widgets_values")
        if not isinstance(widgets, list):
            continue
        for index, value in enumerate(widgets):
            if not isinstance(value, str):
                continue
            if not value.lower().endswith((".safetensors", ".gguf", ".ckpt", ".pt")):
                continue
            if value != VIDEO_MODEL:
                changes.append(
                    {
                        "node_id": node.get("id"),
                        "node_type": node_type,
                        "widget_index": index,
                        "from": value,
                        "to": VIDEO_MODEL,
                    }
                )
                widgets[index] = VIDEO_MODEL
            break

    if not changes:
        validate_workflow_base_models(workflow, "video")
    return changes


def main() -> None:
    candidates = {item.candidate_id: item for item in CANDIDATES}
    imported = 0
    missing: list[str] = []

    for candidate_id, source_filename in LOCAL_SOURCE_BY_CANDIDATE.items():
        candidate = candidates[candidate_id]
        if not candidate.relative_path:
            raise ValueError(f"{candidate_id} has no registered candidate path.")
        source_path = LOCAL_LTX_ROOT / source_filename
        if not source_path.is_file():
            missing.append(str(source_path))
            continue

        source_bytes = source_path.read_bytes()
        source_workflow = json.loads(source_bytes.decode("utf-8-sig"))
        normalized_workflow = copy.deepcopy(source_workflow)
        changes = _normalize_base_loader(normalized_workflow)
        references = validate_workflow_base_models(normalized_workflow, "video")
        if references != (VIDEO_MODEL,):
            raise ValueError(
                f"{candidate_id} produced unexpected base references {references}."
            )

        destination = REPOSITORY_ROOT / candidate.relative_path
        original_destination = (
            destination.parent / "original" / destination.name
        )
        provenance_destination = destination.with_suffix(
            destination.suffix + ".provenance.json"
        )
        original_destination.parent.mkdir(parents=True, exist_ok=True)
        destination.parent.mkdir(parents=True, exist_ok=True)

        original_destination.write_bytes(source_bytes)
        normalized_bytes = (
            json.dumps(normalized_workflow, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        destination.write_bytes(normalized_bytes)
        provenance_destination.write_text(
            json.dumps(
                {
                    "candidate_id": candidate_id,
                    "source_url": candidate.source_url,
                    "source_tier": candidate.source_tier,
                    "local_source_path": str(source_path),
                    "original_candidate_path": str(
                        original_destination.relative_to(REPOSITORY_ROOT)
                    ).replace("\\", "/"),
                    "normalized_candidate_path": candidate.relative_path,
                    "source_sha256": _sha256(source_bytes),
                    "normalized_sha256": _sha256(normalized_bytes),
                    "base_model_changes": changes,
                    "base_model_references": list(references),
                    "enabled": False,
                    "admission_state": "benchmark_required",
                    "execution_performed": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        imported += 1

    print(json.dumps({"imported": imported, "missing": missing}, indent=2))


if __name__ == "__main__":
    main()

