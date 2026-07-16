from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Generator

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings
from backend.app.core.errors import UnsafePathError
from backend.app.db.base import (
    Base,
    Chapter,
    Project,
    Scene,
    Shot,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
    Story,
)
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.schemas.production import CompiledWorkflow, ProductionGateReport, SemanticGenerationRequest
from backend.app.services import storyboard as storyboard_service
from backend.app.services import storyboard_settings as settings_service
from backend.app.services import storyboard_snapshot as snapshot_service
from backend.app.services.local_generation import SemanticGenerationRequestManifestStore
from backend.app.services.local_presets import LocalPresetCatalogService
from backend.app.services.production_gates import ProductionGateService
from backend.app.services.workflows.registry import WorkflowRegistryService


def _temp_settings(tmp_path: Path) -> Settings:
    settings = Settings(storage_root=tmp_path / "storage", comfyui_output_root=tmp_path / "comfy-output")
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree("storage/presets", settings.storage_root / "presets")
    shutil.copytree("storage/workflow_registry", settings.storage_root / "workflow_registry")
    return settings


@pytest.fixture()
def storyboard_api(tmp_path: Path) -> Generator[tuple[TestClient, sessionmaker, Settings], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    settings = _temp_settings(tmp_path)

    def override_get_db() -> Generator[Session, None, None]:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), SessionLocal, settings
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def _seed_storyboard_story(db: Session, *, approved: bool) -> tuple[Story, Shot]:
    project = Project(name="Storyboard Handoff Project", description=None)
    db.add(project)
    db.flush()
    settings_service.get_or_create_settings(db, project.id)
    story = Story(
        project_id=project.id,
        title="Bridge Story",
        base_story="A bounded local handoff story.",
        target_duration_sec=10.0,
    )
    db.add(story)
    db.flush()
    chapter = Chapter(story_id=story.id, order_index=0, title="Chapter One")
    db.add(chapter)
    db.flush()
    scene = Scene(chapter_id=chapter.id, order_index=0, title="Scene One")
    db.add(scene)
    db.flush()
    shot = Shot(
        scene_id=scene.id,
        order_index=0,
        title="Hero Shot",
        duration_sec=10.0,
        visual_description="Fallback visual description.",
        story_purpose="Fallback story purpose.",
    )
    db.add(shot)
    db.flush()
    db.add(ShotNarration(shot_id=shot.id, narration_text="Narration line.", start_offset_sec=0))
    db.add(
        ShotPromptPackage(
            shot_id=shot.id,
            version=1,
            image_prompt="Earlier image prompt.",
            video_prompt="Earlier video prompt.",
            negative_prompt="earlier negative",
        )
    )
    db.add(
        ShotPromptPackage(
            shot_id=shot.id,
            version=2,
            image_prompt="Latest image prompt.",
            video_prompt="Latest approved video prompt.",
            negative_prompt="low quality",
        )
    )
    db.add(
        ShotModelRecommendation(
            shot_id=shot.id,
            recommendation_type="video",
            rationale="Manual workflow review required.",
            availability_status="unknown",
            benchmark_status="unknown",
        )
    )
    db.commit()
    db.refresh(story)
    db.refresh(shot)
    if approved:
        storyboard_service.approve(db, story.id, "reviewer@example.com", snapshot_service.current_revision(db, story.id))
        db.refresh(story)
    return story, shot


def _request(**overrides) -> SemanticGenerationRequest:
    payload = {
        "preset_id": "CF-PRESET-001",
        "archetype_id": "CF-VID-01",
        "quality_profile": "draft",
        "mode": "t2v",
        "prompt": "Safe offline semantic generation request.",
        "negative_prompt": "bad quality",
        "seed": 7,
        "aspect_ratio": "16:9",
        "width": 512,
        "height": 288,
        "frame_count": 17,
        "fps": 24,
        "target_duration_sec": 1.0,
        "upscale_factor": 1,
        "output_profile": "draft",
        "output_prefix": "M7 Project/shot 001",
        "production": True,
    }
    payload.update(overrides)
    return SemanticGenerationRequest(**payload)


class FailingCompiler:
    def compile(self, _request):
        raise AssertionError("blocked semantic manifests must not compile workflows")


class FailingGateService:
    def evaluate_generation_request(self, _request):
        raise AssertionError("unsafe semantic requests must be rejected before gate evaluation")


def test_semantic_generation_store_persists_blocked_manifest_without_compiling(tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = SemanticGenerationRequestManifestStore(settings=settings, compiler=FailingCompiler())

    manifest = store.create(_request())

    assert manifest.state == "blocked_by_gates"
    assert manifest.generation_submitted is False
    assert manifest.comfy_prompt_id is None
    assert manifest.queue_job_id is None
    assert manifest.workflow_snapshot_path is None
    assert manifest.compiled_workflow_metadata is None
    assert manifest.gate_report.allowed is False
    codes = {reason.code.value for reason in manifest.gate_report.blocking_reasons}
    assert "PRESET_BENCHMARK_REQUIRED" in codes
    assert "WORKFLOW_NOT_ADMITTED" in codes
    assert manifest.manifest_path.is_file()
    assert (settings.storage_root / "local_generation" / "semantic_requests" / "events.jsonl").is_file()

    persisted = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    assert persisted["generation_submitted"] is False
    assert persisted["comfy_prompt_id"] is None
    assert persisted["queue_job_id"] is None
    assert persisted["request"]["preset_id"] == "CF-PRESET-001"
    assert [reason["code"] for reason in persisted["gate_report"]["blocking_reasons"]]
    assert persisted["request"]["output_prefix"] == "M7_Project/shot_001"

    loaded = store.get(manifest.request_id)
    assert loaded == manifest
    assert store.list()[0].request_id == manifest.request_id


def test_semantic_generation_store_persists_sanitized_request_prefix(tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = SemanticGenerationRequestManifestStore(settings=settings, compiler=FailingCompiler())

    manifest = store.create(_request(output_prefix="Project A/shot 001"))

    assert manifest.request.output_prefix == "Project_A/shot_001"
    persisted = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    assert persisted["request"]["output_prefix"] == "Project_A/shot_001"
    assert "Project A" not in manifest.manifest_path.read_text(encoding="utf-8")


def test_semantic_generation_store_rejects_unsafe_output_prefix_before_gates(tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = SemanticGenerationRequestManifestStore(
        settings=settings,
        gate_service=FailingGateService(),
        compiler=FailingCompiler(),
    )

    for output_prefix in ("../escape/run", "C:/escape", "Project\\run", "Project/scene/run"):
        with pytest.raises(UnsafePathError):
            store.create(_request(output_prefix=output_prefix))

    assert not (settings.storage_root / "local_generation" / "semantic_requests").exists()


class AllowingGateService:
    def evaluate_generation_request(self, _request):
        return ProductionGateReport(allowed=True, blocking_reasons=[])


class OfflineCompiler:
    def __init__(self, snapshot_path: Path) -> None:
        self.snapshot_path = snapshot_path
        self.calls = 0

    def compile(self, request: SemanticGenerationRequest) -> CompiledWorkflow:
        self.calls += 1
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text('{"offline": true}', encoding="utf-8")
        return CompiledWorkflow(
            archetype_id=request.archetype_id,
            template_id="offline-template",
            template_version="0.0-test",
            workflow_api_sha256="0" * 64,
            patch_payload={"output_prefix": request.output_prefix},
            patched_workflow={"offline": True},
            output_prefix=request.output_prefix,
            production=request.production,
            workflow_snapshot_path=self.snapshot_path,
        )


def test_semantic_generation_store_prepares_allowed_requests_offline_only(tmp_path: Path):
    settings = _temp_settings(tmp_path)
    compiler = OfflineCompiler(settings.workflow_snapshot_root / "semantic-offline.json")
    store = SemanticGenerationRequestManifestStore(
        settings=settings,
        gate_service=AllowingGateService(),
        compiler=compiler,
    )

    manifest = store.create(_request(production=False))

    assert manifest.state == "prepared_offline"
    assert manifest.gate_report.allowed is True
    assert compiler.calls == 1
    assert manifest.workflow_snapshot_path == compiler.snapshot_path
    assert manifest.workflow_snapshot_path.is_file()
    assert manifest.compiled_workflow_metadata is not None
    assert manifest.compiled_workflow_metadata.template_id == "offline-template"
    assert manifest.compiled_workflow_metadata.output_prefix == "M7_Project/shot_001"
    assert manifest.compiled_workflow_metadata.patch_payload == {"output_prefix": "M7_Project/shot_001"}
    assert manifest.request.output_prefix == "M7_Project/shot_001"
    assert manifest.generation_submitted is False
    assert manifest.comfy_prompt_id is None
    assert manifest.queue_job_id is None


def test_semantic_generation_route_creates_lists_and_gets_blocked_manifest(monkeypatch, tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = SemanticGenerationRequestManifestStore(settings=settings, compiler=FailingCompiler())
    monkeypatch.setattr("backend.app.api.routes.local_generation._store", lambda: store)
    client = TestClient(app)

    response = client.post("/local-generation/semantic-requests", json=_request().model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "blocked_by_gates"
    assert payload["generation_submitted"] is False
    assert payload["comfy_prompt_id"] is None
    assert payload["queue_job_id"] is None
    assert payload["workflow_snapshot_path"] is None
    assert payload["compiled_workflow_metadata"] is None
    assert payload["gate_report"]["allowed"] is False
    assert Path(payload["manifest_path"]).is_file()

    list_response = client.get("/local-generation/semantic-requests")
    assert list_response.status_code == 200
    assert list_response.json()[0]["request_id"] == payload["request_id"]

    get_response = client.get(f"/local-generation/semantic-requests/{payload['request_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["request_id"] == payload["request_id"]


def test_semantic_generation_route_rejects_unsafe_output_prefix(monkeypatch, tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = SemanticGenerationRequestManifestStore(settings=settings, compiler=FailingCompiler())
    monkeypatch.setattr("backend.app.api.routes.local_generation._store", lambda: store)

    response = TestClient(app).post(
        "/local-generation/semantic-requests",
        json=_request(output_prefix="Project/scene/run").model_dump(mode="json"),
    )

    assert response.status_code == 422
    assert not (settings.storage_root / "local_generation" / "semantic_requests").exists()


def test_semantic_generation_route_does_not_submit_to_comfyui(monkeypatch, tmp_path: Path):
    settings = _temp_settings(tmp_path)
    store = SemanticGenerationRequestManifestStore(settings=settings, compiler=FailingCompiler())
    monkeypatch.setattr("backend.app.api.routes.local_generation._store", lambda: store)

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("semantic manifest creation must not submit prompts")

    monkeypatch.setattr("backend.app.services.comfy.client.ComfyUIClient.submit_prompt", fail_if_called)

    response = TestClient(app).post(
        "/local-generation/semantic-requests",
        json=_request().model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json()["generation_submitted"] is False


def test_storyboard_handoff_blocks_unapproved_story_without_manifests(storyboard_api, monkeypatch):
    client, SessionLocal, settings = storyboard_api
    store = SemanticGenerationRequestManifestStore(settings=settings, compiler=FailingCompiler())
    monkeypatch.setattr("backend.app.api.routes.local_generation._store", lambda: store)
    with SessionLocal() as db:
        story, _shot = _seed_storyboard_story(db, approved=False)
        story_id = str(story.id)

    response = client.post("/local-generation/storyboard-handoffs", json={"story_id": story_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == story_id
    assert payload["selected_shot_count"] == 0
    assert payload["created_manifests"] == []
    assert payload["generation_submitted"] is False
    assert payload["execution_started"] is False
    assert payload["automatic_from_approval"] is False
    assert any("approval_state" in reason for reason in payload["blocked_reasons"])
    assert store.list() == []
    assert not (settings.storage_root / "local_generation" / "semantic_requests").exists()


def test_storyboard_handoff_explicit_approved_story_creates_blocked_semantic_manifest_without_submit(
    storyboard_api,
    monkeypatch,
):
    client, SessionLocal, settings = storyboard_api
    store = SemanticGenerationRequestManifestStore(settings=settings, compiler=FailingCompiler())
    monkeypatch.setattr("backend.app.api.routes.local_generation._store", lambda: store)

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("storyboard handoff must not submit prompts")

    monkeypatch.setattr("backend.app.services.comfy.client.ComfyUIClient.submit_prompt", fail_if_called)
    with SessionLocal() as db:
        story, shot = _seed_storyboard_story(db, approved=True)
        story_id = str(story.id)
        shot_id = str(shot.id)
        active_version_id = str(story.active_storyboard_version_id)

    response = client.post(
        "/local-generation/storyboard-handoffs",
        json={
            "story_id": story_id,
            "shot_id": shot_id,
            "output_project_key": "Bridge Project",
            "run_stem": "handoff run",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == story_id
    assert payload["active_storyboard_version_id"] == active_version_id
    assert payload["active_storyboard_content_hash"]
    assert payload["selected_shot_count"] == 1
    assert payload["blocked_reasons"] == []
    assert payload["generation_submitted"] is False
    assert payload["execution_started"] is False
    assert payload["automatic_from_approval"] is False
    assert "no ComfyUI submission" in payload["safety_note"]
    assert len(payload["created_manifests"]) == 1
    summary = payload["created_manifests"][0]
    assert summary["shot_id"] == shot_id
    assert summary["state"] == "blocked_by_gates"
    assert summary["generation_submitted"] is False
    assert "PRESET_BENCHMARK_REQUIRED" in summary["blocking_codes"]

    manifests = store.list()
    assert len(manifests) == 1
    manifest = manifests[0]
    assert str(manifest.request_id) == summary["request_id"]
    assert manifest.state == "blocked_by_gates"
    assert manifest.generation_submitted is False
    assert manifest.comfy_prompt_id is None
    assert manifest.queue_job_id is None
    assert manifest.request.prompt == "Latest approved video prompt."
    assert manifest.request.negative_prompt == "low quality"
    assert manifest.request.frame_count % 8 == 1
    assert manifest.request.fps == 24
    assert manifest.request.mode == "t2v"
    assert manifest.request.output_prefix.startswith("Bridge_Project/")
    assert "handoff_run" in manifest.request.output_prefix


def test_storyboard_approval_route_does_not_create_handoff_automatically(storyboard_api):
    client, SessionLocal, settings = storyboard_api
    with SessionLocal() as db:
        story, _shot = _seed_storyboard_story(db, approved=False)
        story_id = str(story.id)
        revision = snapshot_service.current_revision(db, story.id)

    response = client.post(
        f"/storyboard/stories/{story_id}/approve",
        json={"approved_by": "reviewer@example.com", "expected_revision": revision},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert not (settings.storage_root / "local_generation" / "semantic_requests").exists()


def test_local_generation_routes_do_not_expose_execute_submit_run_or_prompt_children():
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    method_paths = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    local_generation_paths = {path for path in paths if path.startswith("/local-generation")}

    assert "/prompt" not in paths
    assert "/local-generation/prompt" not in local_generation_paths
    assert local_generation_paths == {
        "/local-generation/storyboard-handoffs",
        "/local-generation/semantic-requests",
        "/local-generation/semantic-requests/{request_id}",
    }
    forbidden_local_generation_children = ("/execute", "/submit", "/run", "/prompt")
    assert not any(
        child in path
        for path in local_generation_paths
        for child in forbidden_local_generation_children
    )
    assert not any(
        path.startswith("/local-generation/")
        and any(path.endswith(child) or f"{child}/" in path for child in forbidden_local_generation_children)
        for path in paths
    )
    assert {method for method, path in method_paths if path == "/local-generation/storyboard-handoffs"} == {"POST"}
    assert {method for method, path in method_paths if path == "/local-generation/semantic-requests"} == {"GET", "POST"}
    assert {method for method, path in method_paths if path == "/local-generation/semantic-requests/{request_id}"} == {"GET"}


def test_current_catalog_keeps_cf_preset_001_blocked_by_benchmark_required():
    preset = LocalPresetCatalogService().get_preset("CF-PRESET-001")
    assert preset is not None
    assert preset.readiness == "benchmark_required"
    assert preset.enabled is False

    report = ProductionGateService(
        registry=WorkflowRegistryService(),
        presets=LocalPresetCatalogService(),
    ).evaluate_generation_request(_request())

    assert report.allowed is False
    assert any(reason.code.value == "PRESET_BENCHMARK_REQUIRED" for reason in report.blocking_reasons)
    assert any(
        reason.evidence.get("preset_id") == "CF-PRESET-001"
        and "benchmark_required" in reason.message
        for reason in report.blocking_reasons
    )
