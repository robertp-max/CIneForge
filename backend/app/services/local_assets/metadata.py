"""Safetensors header peek, streaming hash, and family inference."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any


def stream_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_safetensors_header(path: Path, max_header_bytes: int = 32 * 1024 * 1024) -> dict[str, Any]:
    """Read safetensors JSON header without loading tensors.

    Returns empty dict on non-safetensors or parse failure.
    """
    if path.suffix.lower() != ".safetensors":
        return {}
    try:
        with path.open("rb") as f:
            raw_len = f.read(8)
            if len(raw_len) < 8:
                return {}
            header_len = struct.unpack("<Q", raw_len)[0]
            if header_len <= 0 or header_len > max_header_bytes:
                return {"header_error": "invalid_header_length", "header_len": header_len}
            header_bytes = f.read(header_len)
            if len(header_bytes) < header_len:
                return {"header_error": "truncated_header"}
            header = json.loads(header_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — best-effort metadata
        return {"header_error": str(exc)}

    # Summarize without dumping full tensor map (can be huge)
    keys = [k for k in header.keys() if k != "__metadata__"]
    meta = header.get("__metadata__") if isinstance(header.get("__metadata__"), dict) else {}
    sample_keys = keys[:40]
    dtypes: dict[str, int] = {}
    for k in sample_keys:
        entry = header.get(k)
        if isinstance(entry, dict) and "dtype" in entry:
            dt = str(entry["dtype"])
            dtypes[dt] = dtypes.get(dt, 0) + 1

    return {
        "tensor_count_sample": len(sample_keys),
        "tensor_count_reported": len(keys),
        "sample_keys": sample_keys,
        "dtype_histogram_sample": dtypes,
        "embedded_metadata": {str(k): str(v)[:500] for k, v in list(meta.items())[:50]},
    }


def infer_family_and_base(
    *,
    name: str,
    relative_path: str,
    asset_type: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    blob = f"{name} {relative_path}".lower().replace("\\", "/")
    meta_blob = ""
    if metadata:
        emb = metadata.get("embedded_metadata") or {}
        if isinstance(emb, dict):
            meta_blob = " ".join(f"{k} {v}" for k, v in emb.items()).lower()
    text = f"{blob} {meta_blob}"

    family: str | None = None
    base: str | None = None

    if "ltx" in text or "ltxv" in text:
        family = "ltx"
        if "2.3" in text or "2_3" in text:
            base = "ltx-2.3"
        elif "2.0" in text or "ltx-2" in text:
            base = "ltx-2"
        else:
            base = "ltx"
    elif "flux.2" in text or "flux2" in text or "flux-2" in text or "klein" in text:
        family = "flux2"
        if "klein" in text and "9b" in text:
            base = "flux2-klein-9b"
        elif "klein" in text and "4b" in text:
            base = "flux2-klein-4b"
        elif "klein" in text:
            base = "flux2-klein"
        elif "dev" in text:
            base = "flux2-dev"
        else:
            base = "flux2"
    elif re.search(r"\bflux\b|flux1|flux\.1", text):
        family = "flux1"
        base = "flux1-dev" if "dev" in text else "flux1"
    elif "wan" in text:
        family = "wan"
        base = "wan"
    elif "sdxl" in text or "pony" in text:
        family = "sdxl"
        base = "sdxl"
    elif asset_type.startswith("workflow"):
        if "ltx" in text:
            family = "ltx"
        elif "klein" in text or "flux2" in text or "flux 2" in text:
            family = "flux2"
        elif "flux" in text:
            family = "flux1"

    return family, base
