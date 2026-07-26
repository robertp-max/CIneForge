"""Inspect local ComfyUI workflow JSON / PNG / ZIP without executing graphs."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


def inspect_workflow_json(path: Path, max_bytes: int = 20 * 1024 * 1024) -> dict[str, Any]:
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return {"format": "json", "too_large": True, "size_bytes": size}
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {"format": "json", "error": str(exc)}

    nodes: list[Any] = []
    class_types: set[str] = set()
    model_refs: list[str] = []
    lora_refs: list[str] = []

    if isinstance(data, dict) and "nodes" in data and isinstance(data["nodes"], list):
        # UI format
        nodes = data["nodes"]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            t = n.get("type")
            if t:
                class_types.add(str(t))
            for w in n.get("widgets_values") or []:
                if isinstance(w, str) and any(
                    w.lower().endswith(ext)
                    for ext in (".safetensors", ".ckpt", ".gguf", ".pt", ".bin")
                ):
                    if "lora" in str(t or "").lower() or "lora" in w.lower():
                        lora_refs.append(w)
                    else:
                        model_refs.append(w)
    elif isinstance(data, dict):
        # API prompt format {node_id: {class_type, inputs}}
        for node in data.values():
            if not isinstance(node, dict):
                continue
            ct = node.get("class_type")
            if ct:
                class_types.add(str(ct))
            inputs = node.get("inputs") or {}
            if isinstance(inputs, dict):
                for k, v in inputs.items():
                    if isinstance(v, str) and any(
                        v.lower().endswith(ext)
                        for ext in (".safetensors", ".ckpt", ".gguf", ".pt", ".bin")
                    ):
                        if "lora" in k.lower() or "lora" in v.lower():
                            lora_refs.append(v)
                        else:
                            model_refs.append(v)

    blob = " ".join(class_types).lower()
    families: list[str] = []
    if "ltx" in blob:
        families.append("ltx")
    if "flux" in blob or "klein" in blob:
        families.append("flux")
    if "wan" in blob:
        families.append("wan")

    return {
        "format": "json",
        "node_count_estimate": len(nodes) if nodes else len(class_types),
        "class_types": sorted(class_types)[:80],
        "model_refs": sorted(set(model_refs))[:40],
        "lora_refs": sorted(set(lora_refs))[:40],
        "families_guess": families,
        "is_api_format": isinstance(data, dict) and "nodes" not in data,
    }


def inspect_workflow_zip(path: Path, max_entries: int = 200) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()[:max_entries]
            json_members = [n for n in names if n.lower().endswith(".json")]
            return {
                "format": "zip",
                "entry_count": len(zf.namelist()),
                "entries_sample": names[:50],
                "json_members": json_members[:40],
            }
    except Exception as exc:  # noqa: BLE001
        return {"format": "zip", "error": str(exc)}


def inspect_workflow_png(path: Path) -> dict[str, Any]:
    """Best-effort: note PNG workflow container; full tEXt parse is optional."""
    info: dict[str, Any] = {"format": "png", "has_embedded_workflow": False}
    try:
        data = path.read_bytes()[:512_000]
        # ComfyUI often embeds workflow in tEXt/iTXt; look for markers
        if b"workflow" in data.lower() or b"prompt" in data.lower():
            info["has_embedded_workflow"] = True
            info["marker_found"] = True
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
    return info


def inspect_workflow(path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    if ext == ".json":
        return inspect_workflow_json(path)
    if ext == ".zip":
        return inspect_workflow_zip(path)
    if ext in {".png", ".webp", ".jpeg", ".jpg"}:
        return inspect_workflow_png(path)
    return {"format": ext.lstrip("."), "unsupported": True}
