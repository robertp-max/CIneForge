"""Tests for local ComfyUI filesystem asset catalog."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base, LocalRuntimeAsset
from backend.app.services.local_assets import catalog as local_catalog
from backend.app.services.local_assets.metadata import (
    infer_family_and_base,
    read_safetensors_header,
    stream_sha256,
)
from backend.app.services.local_assets.scanner import scan_comfyui_root
from backend.app.services.local_assets.sync import sync_local_comfy_assets
from backend.app.services.local_assets.resolver import (
    AssetResolutionError,
    resolve_generation_assets,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    yield session
    session.close()


def _write_safetensors(path: Path, tensors: dict | None = None) -> None:
    """Minimal safetensors writer for tests (empty tensors)."""
    header = tensors or {
        "__metadata__": {"ss_base_model_name": "flux2"},
        "weight": {"dtype": "F16", "shape": [1, 1], "data_offsets": [0, 2]},
    }
    raw = json.dumps(header).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(struct.pack("<Q", len(raw)))
        f.write(raw)
        f.write(b"\x00\x00")  # 2 bytes of "tensor" data


def _fake_comfy(tmp_path: Path) -> Path:
    root = tmp_path / "ComfyUI"
    (root / "models" / "checkpoints").mkdir(parents=True)
    (root / "models" / "loras" / "FLUX2").mkdir(parents=True)
    (root / "models" / "vae").mkdir(parents=True)
    (root / "user" / "default" / "workflows").mkdir(parents=True)

    _write_safetensors(root / "models" / "checkpoints" / "flux-2-klein-9b.safetensors")
    _write_safetensors(root / "models" / "loras" / "FLUX2" / "V4_flux_klein.safetensors")
    _write_safetensors(root / "models" / "loras" / "Fantasy_Realism.safetensors")
    _write_safetensors(root / "models" / "vae" / "ae.safetensors")

    wf = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "flux-2-klein-9b.safetensors"},
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "FLUX2/V4_flux_klein.safetensors", "strength_model": 1.0},
        },
    }
    (root / "user" / "default" / "workflows" / "klein_edit.json").write_text(
        json.dumps(wf), encoding="utf-8"
    )
    return root


def test_scanner_categorizes_files(tmp_path: Path):
    root = _fake_comfy(tmp_path)
    files = scan_comfyui_root(root)
    types = {f.asset_type for f in files}
    assert "checkpoint" in types
    assert "lora" in types
    assert "vae" in types
    assert "workflow_json" in types
    lora = next(f for f in files if f.name == "V4_flux_klein.safetensors")
    assert lora.selector_value == "FLUX2/V4_flux_klein.safetensors"


def test_safetensors_header_and_hash(tmp_path: Path):
    path = tmp_path / "demo.safetensors"
    _write_safetensors(path)
    header = read_safetensors_header(path)
    assert "embedded_metadata" in header or "tensor_count_reported" in header
    digest = stream_sha256(path)
    assert len(digest) == 64


def test_infer_family():
    fam, base = infer_family_and_base(
        name="flux-2-klein-9b.safetensors",
        relative_path="models/checkpoints/flux-2-klein-9b.safetensors",
        asset_type="checkpoint",
    )
    assert fam == "flux2"
    assert base and "klein" in base


def test_sync_idempotent(db, tmp_path: Path):
    root = _fake_comfy(tmp_path)
    s1 = sync_local_comfy_assets(db, comfyui_root=root, compute_hash=True)
    assert s1["added"] >= 4
    assert s1["present"] >= 4
    s2 = sync_local_comfy_assets(db, comfyui_root=root, compute_hash=True)
    assert s2["added"] == 0
    assert s2["present"] == s1["present"]


def test_catalog_filters_and_resolve(db, tmp_path: Path):
    root = _fake_comfy(tmp_path)
    sync_local_comfy_assets(db, comfyui_root=root, compute_hash=True)
    checkpoints = local_catalog.list_local_assets(db, asset_type="checkpoint")
    loras = local_catalog.list_local_assets(db, asset_type="lora")
    workflows = local_catalog.list_local_assets(db, asset_type="workflow")
    assert len(checkpoints) >= 1
    assert len(loras) >= 2
    assert len(workflows) >= 1

    ckpt = checkpoints[0]
    lora = next(x for x in loras if "V4" in x["name"])
    resolved = resolve_generation_assets(
        db,
        checkpoint_asset_id=ckpt["id"],
        workflow_asset_id=workflows[0]["id"],
        loras=[{"asset_id": lora["id"], "strength_model": 0.8, "strength_clip": 0.7}],
    )
    assert resolved.checkpoint is not None
    assert resolved.loras[0].strength_model == 0.8

    with pytest.raises(AssetResolutionError):
        resolve_generation_assets(db, checkpoint_asset_id=lora["id"])


def test_summary(db, tmp_path: Path):
    root = _fake_comfy(tmp_path)
    sync_local_comfy_assets(db, comfyui_root=root, compute_hash=False)
    summary = local_catalog.local_assets_summary(db)
    assert summary["present"] >= 4
    assert "checkpoint" in summary["by_type"] or "lora" in summary["by_type"]
