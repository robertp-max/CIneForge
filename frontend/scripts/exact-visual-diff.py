#!/usr/bin/env python3
"""Compare reference vs actual screenshots; write overlay, diff, and mismatch JSON.
No production dependency — development/acceptance only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageStat


def load_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def resize_to(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    if img.size == size:
        return img
    return img.resize(size, Image.Resampling.LANCZOS)


def compare(reference: Path, actual: Path, out_prefix: Path) -> dict:
    ref = load_rgb(reference)
    act = load_rgb(actual)

    # Capture at reference pixel dimensions for geometry match.
    target = ref.size
    act_r = resize_to(act, target)

    # Absolute per-channel difference
    diff = ImageChops.difference(ref, act_r)
    # Grayscale magnitude
    gray = diff.convert("L")
    # Threshold for "significant" pixel (antialiasing tolerance ~28/255)
    thr = 28
    mask = gray.point(lambda p: 255 if p > thr else 0)
    mismatch = sum(1 for p in mask.getdata() if p)
    total = target[0] * target[1]
    ratio = mismatch / total if total else 1.0

    # Overlay 50%
    overlay = Image.blend(ref, act_r, 0.5)
    overlay.save(out_prefix.with_name(out_prefix.name + "-overlay.png"))

    # Visual diff heat (boosted)
    heat = ImageEnhance.Brightness(diff).enhance(2.2)
    heat.save(out_prefix.with_name(out_prefix.name + "-diff.png"))

    # Copy/normalized actual at reference size
    act_r.save(out_prefix.with_name(out_prefix.name + "-actual.png"))
    ref.save(out_prefix.with_name(out_prefix.name + "-reference.png"))

    # Largest mismatch bbox
    bbox = mask.getbbox()
    result = {
        "reference": str(reference),
        "actual_source": str(actual),
        "size": {"width": target[0], "height": target[1]},
        "mismatch_pixels": mismatch,
        "total_pixels": total,
        "mismatch_ratio": ratio,
        "mismatch_percent": round(ratio * 100, 4),
        "threshold": thr,
        "largest_mismatch_bbox": list(bbox) if bbox else None,
        "pass": ratio <= 0.01,
        "structural_note": "pass threshold 1% after AA tolerance"
        if ratio <= 0.01
        else "FAIL: exceeds 1% mismatch — inspect overlay/diff",
    }
    out_prefix.with_name(out_prefix.name + "-comparison.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("usage: exact-visual-diff.py <reference.png> <actual.png> <out_prefix>")
        return 2
    ref, act, prefix = Path(argv[1]), Path(argv[2]), Path(argv[3])
    result = compare(ref, act, prefix)
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
