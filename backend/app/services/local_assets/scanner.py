"""Filesystem traversal and categorization for local ComfyUI assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

WEIGHT_EXTS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx", ".sft"}
WORKFLOW_EXTS = {".json", ".png", ".zip", ".webp", ".jpeg", ".jpg"}

# Relative to ComfyUI root: category key -> (subdir, default asset_type)
SCAN_DIRS: list[tuple[str, str, str]] = [
    ("models/checkpoints", "checkpoint", "checkpoint"),
    ("models/diffusion_models", "checkpoint", "checkpoint"),  # rare; still cataloged as checkpoint
    ("models/loras", "lora", "lora"),
    ("models/text_encoders", "text_encoder", "text_encoder"),
    ("models/clip", "text_encoder", "text_encoder"),
    ("models/clip_vision", "clip_vision", "clip_vision"),
    ("models/vae", "vae", "vae"),
    ("models/latent_upscale_models", "latent_upscaler", "latent_upscaler"),
    ("models/upscale_models", "upscaler", "upscaler"),
    ("models/controlnet", "controlnet", "controlnet"),
    ("models/style_models", "other_model", "other_model"),
    ("models/ultralytics", "other_model", "other_model"),
    ("models/sams", "other_model", "other_model"),
    ("models/insightface", "other_model", "other_model"),
    ("user/default/workflows", "workflow", "workflow_json"),
]


@dataclass(frozen=True)
class ScannedFile:
    absolute_path: Path
    relative_path: str
    asset_type: str
    model_category: str
    selector_value: str
    file_extension: str
    file_size_bytes: int
    mtime_ns: int
    name: str


def _infer_workflow_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".json":
        return "workflow_json"
    if ext in {".png", ".webp", ".jpeg", ".jpg"}:
        return "workflow_png"
    if ext == ".zip":
        return "workflow_zip"
    return "other_model"


def _selector_for(category: str, rel_to_category_root: Path, filename: str) -> str:
    """ComfyUI-style selector relative to the category folder."""
    if category == "workflow":
        return rel_to_category_root.as_posix()
    # nested loras: FLUX2/foo.safetensors
    if rel_to_category_root.parent != Path("."):
        return rel_to_category_root.as_posix()
    return filename


def scan_comfyui_root(comfyui_root: Path) -> list[ScannedFile]:
    root = comfyui_root.resolve()
    found: list[ScannedFile] = []
    seen: set[str] = set()

    for rel_dir, model_category, default_type in SCAN_DIRS:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            # skip caches / partials
            name = path.name
            if name.startswith(".") or name.endswith(".partial") or name == "desktop.ini":
                continue
            ext = path.suffix.lower()
            if model_category == "workflow":
                if ext not in WORKFLOW_EXTS:
                    continue
                asset_type = _infer_workflow_type(path)
            else:
                if ext not in WEIGHT_EXTS:
                    continue
                asset_type = default_type

            abs_key = str(path.resolve())
            if abs_key in seen:
                continue
            seen.add(abs_key)

            try:
                st = path.stat()
            except OSError:
                continue

            rel_to_root = path.relative_to(root).as_posix()
            rel_to_cat = path.relative_to(base)
            selector = _selector_for(model_category, rel_to_cat, path.name)

            found.append(
                ScannedFile(
                    absolute_path=path.resolve(),
                    relative_path=rel_to_root,
                    asset_type=asset_type,
                    model_category=model_category,
                    selector_value=selector,
                    file_extension=ext.lstrip(".") or ext,
                    file_size_bytes=int(st.st_size),
                    mtime_ns=int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
                    name=path.name,
                )
            )

    found.sort(key=lambda f: f.relative_path.lower())
    return found
