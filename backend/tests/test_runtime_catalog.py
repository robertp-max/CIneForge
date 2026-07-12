"""Tests for factual runtime catalog reads (DB evidence only)."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import (
    Base,
    BenchmarkRun,
    HardwareProfile,
    Lora,
    Model,
    ModelVariant,
    Quantization,
    WorkflowTemplate,
)
from backend.app.services import runtime_catalog as catalog


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


def _seed(session):
    model = Model(
        family="demo",
        name="Demo Model",
        source_url=None,
        license="test",
        evidence_level="catalog_only",
        notes=None,
    )
    session.add(model)
    session.flush()

    known_path = ModelVariant(
        model_id=model.id,
        variant_name="with-path",
        params_b=7,
        file_path="/models/demo.safetensors",
        file_size_bytes=1234,
        sha256="a" * 64,
        precision="fp16",
        quantization=None,
        compatible_24gb_status="unknown",
        notes=None,
        native_voice_capability="unknown",
    )
    unknown_path = ModelVariant(
        model_id=model.id,
        variant_name="no-path",
        params_b=7,
        file_path=None,
        file_size_bytes=None,
        sha256=None,
        precision="fp16",
        quantization=None,
        compatible_24gb_status="unknown",
        notes=None,
        native_voice_capability="unsupported",
        native_voice_capability_source="manual_catalog",
    )
    session.add_all([known_path, unknown_path])

    wf = WorkflowTemplate(
        name="demo-wf",
        version="1.0.0",
        workflow_api_json={"1": {"class_type": "X", "inputs": {}}},
        manifest_json={"template_id": "demo-wf"},
        sha256="b" * 64,
        comfyui_commit=None,
        custom_node_snapshot=None,
    )
    session.add(wf)
    session.flush()

    hw = HardwareProfile(
        name="box",
        gpu_name="GPU",
        vram_mib=24576,
        ram_mib=65536,
    )
    session.add(hw)
    session.flush()

    bench = BenchmarkRun(
        hardware_profile_id=hw.id,
        workflow_template_id=wf.id,
        model_variant_id=known_path.id,
        quantization_id=None,
        settings={},
        metrics={"seconds": 1.0},
        decision="recorded",
        notes=None,
    )
    session.add(bench)

    session.add(
        Quantization(
            name="Q5",
            applies_to="demo",
            loader_node=None,
            evidence_level="documented",
            recommended_24gb=True,
            notes=None,
        )
    )
    session.add(
        Lora(
            name="style-lora",
            purpose="style",
            file_path=None,
            sha256=None,
            source_url=None,
            license=None,
            quantized_base_status="unknown",
            evidence_level="catalog_only",
            notes=None,
        )
    )
    session.commit()
    return model, known_path, unknown_path, wf


def test_full_catalog_is_evidence_only(db):
    model, known_path, unknown_path, wf = _seed(db)
    payload = catalog.full_catalog(db)

    assert payload["summary"]["models"] == 1
    assert payload["summary"]["model_variants"] == 2
    assert payload["summary"]["workflow_templates"] == 1
    assert payload["summary"]["benchmark_runs"] == 1
    assert "never probes" in payload["summary"]["evidence_note"].lower()

    by_name = {v["variant_name"]: v for v in payload["model_variants"]}

    with_path = by_name["with-path"]
    assert with_path["path_status"] == "path_recorded"
    assert with_path["checksum_status"] == "checksum_recorded"
    assert with_path["benchmark_status"] == "benchmark_recorded"
    assert with_path["benchmark_run_count"] == 1
    assert with_path["claims"]["installed"] is False
    assert with_path["claims"]["validated"] is False
    assert with_path["claims"]["benchmarked"] is True
    assert with_path["claims"]["downloaded"] is False
    assert with_path["native_voice_capability"] == "unknown"

    no_path = by_name["no-path"]
    assert no_path["path_status"] == "unknown"
    assert no_path["checksum_status"] == "unknown"
    assert no_path["benchmark_status"] == "unknown"
    assert no_path["claims"]["installed"] is False
    assert no_path["claims"]["benchmarked"] is False
    assert no_path["native_voice_capability"] == "unsupported"

    templates = payload["workflow_templates"]
    assert len(templates) == 1
    assert templates[0]["benchmark_status"] == "benchmark_recorded"
    assert templates[0]["claims"]["installed"] is False
    assert templates[0]["claims"]["validated"] is False
    assert templates[0]["claims"]["comfy_reachable"] is False

    loras = payload["loras"]
    assert loras[0]["path_status"] == "unknown"
    assert loras[0]["claims"]["installed"] is False


def test_get_variant_and_template(db):
    _, known_path, _, wf = _seed(db)
    item = catalog.get_model_variant(db, known_path.id)
    assert item is not None
    assert item["id"] == known_path.id
    assert catalog.get_model_variant(db, uuid.uuid4()) is None

    tmpl = catalog.get_workflow_template(db, wf.id)
    assert tmpl is not None
    assert tmpl["name"] == "demo-wf"
    assert catalog.get_workflow_template(db, uuid.uuid4()) is None


def test_unknown_stays_unknown_without_rows(db):
    summary = catalog.catalog_summary(db)
    assert summary["models"] == 0
    assert summary["model_variants"] == 0
    assert catalog.list_model_variants(db) == []
    assert catalog.list_workflow_templates(db) == []
