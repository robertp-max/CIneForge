from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings
from backend.app.db.base import (
    Base,
    ComfyJob,
    FFmpegJob,
    FileOutput,
    GeneratedAsset,
    GpuResourceLease,
    QueueStatus,
    WorkflowRun,
    WorkflowTemplate,
)
from backend.app.schemas.post_production import PostProductionAssemblyPlanCreate
from backend.app.services.comfy.runtime_manager import (
    ComfyRuntimeMutationBlocked,
    PinnedComfyRuntimeManager,
)
from backend.app.services.ffmpeg.executor import FFmpegExecutionBlocked, GatedFFmpegExecutor
from backend.app.services.ffmpeg.service import FFmpegService, sha256_file
from backend.app.services.post_production import PostProductionService
from backend.app.services.post_production_manifest import PostProductionPlanStore
from backend.app.services.queue.live_worker import LiveComfyQueueWorker
from backend.app.services.workflows.template_service import sha256_json


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'live-controls.db').as_posix()}", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _ready_workflow() -> dict[str, Any]:
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 1}},
    }


def _ready_manifest(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "template_id": "live-worker-test",
        "version": "1",
        "original_workflow_sha256": sha256_json(workflow),
        "comfyui_snapshot_ref": "test-object-info",
        "nodes": {
            "positive_prompt": {
                "node_id": "6",
                "class_type": "CLIPTextEncode",
                "input": "text",
                "runtime_parameter": "positive_prompt",
                "value_schema": {"type": "string"},
                "required": True,
            },
            "seed": {
                "node_id": "3",
                "class_type": "KSampler",
                "input": "seed",
                "runtime_parameter": "seed",
                "value_schema": {"type": "integer"},
                "required": True,
            },
        },
    }


def _object_info() -> dict[str, Any]:
    return {
        "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}}},
        "KSampler": {"input": {"required": {"seed": ["INT", {}]}}},
    }


def _pending_job(db: Session, *, output_prefix: str = "Project_A/run_01") -> ComfyJob:
    workflow = _ready_workflow()
    template = WorkflowTemplate(
        name=f"live-worker-{uuid4()}",
        version="1",
        workflow_api_json=workflow,
        manifest_json=_ready_manifest(workflow),
        sha256=sha256_json(workflow),
    )
    db.add(template)
    db.flush()
    run = WorkflowRun(
        workflow_template_id=template.id,
        patched_workflow_json=workflow,
        patch_payload_json={"output_prefix": output_prefix},
        status=QueueStatus.pending.value,
    )
    db.add(run)
    db.flush()
    job = ComfyJob(workflow_run_id=run.id, status=QueueStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


class _AsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None


class _PublicClient(_AsyncClient):
    def __init__(self, object_info: dict[str, Any]) -> None:
        self.object_info = object_info

    async def get_object_info(self) -> dict[str, Any]:
        return self.object_info


class _SubmissionAdapter(_AsyncClient):
    def __init__(self, on_submit=None) -> None:
        self.on_submit = on_submit

    async def submit_prompt(self, prompt: dict[str, Any], client_id: str, *, permit=None) -> dict[str, Any]:
        assert prompt == _ready_workflow()
        assert client_id.startswith("cineforge-")
        assert permit is not None
        if self.on_submit is not None:
            self.on_submit()
        return {"prompt_id": "prompt-live-1", "number": 1, "node_errors": {}}


class _WebSocket:
    def __init__(self, on_complete=None) -> None:
        self.events = [
            {"type": "execution_start", "data": {"prompt_id": "prompt-live-1"}},
            {"type": "executing", "data": {"prompt_id": "prompt-live-1", "node": None}},
        ]
        self.closed = False
        self.on_complete = on_complete

    async def recv(self) -> dict[str, Any]:
        if len(self.events) == 1 and self.on_complete is not None:
            self.on_complete()
        return self.events.pop(0)

    async def close(self) -> None:
        self.closed = True


class _RuntimeClient(_AsyncClient):
    def __init__(self, on_complete=None) -> None:
        self.websocket = _WebSocket(on_complete)

    async def connect_progress_websocket(self, client_id: str, *, permit=None):
        assert client_id.startswith("cineforge-")
        assert permit is not None
        return self.websocket

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        assert prompt_id == "prompt-live-1"
        return {}


@pytest.mark.asyncio
async def test_live_worker_composes_claim_submit_progress_collect_and_release(tmp_path: Path, db_session: Session):
    settings = Settings(
        storage_root=tmp_path / "storage",
        comfyui_output_root=tmp_path / "comfy-output",
        queue_worker_enabled=True,
        comfyui_progress_poll_interval_sec=0.25,
    )
    job = _pending_job(db_session)
    output_dir = settings.comfyui_output_root / "Project_A"

    def write_output() -> None:
        output_dir.mkdir(parents=True)
        (output_dir / "run_01_00001_.png").write_bytes(b"offline-image-fixture")

    runtime = _RuntimeClient(write_output)
    worker = LiveComfyQueueWorker(
        worker_id="worker-live-test",
        settings=settings,
        public_client_factory=lambda: _PublicClient(_object_info()),
        runtime_client_factory=lambda: runtime,
        submission_adapter_factory=_SubmissionAdapter,
    )

    result = await worker.run_once(db_session)

    db_session.expire_all()
    persisted = db_session.get(ComfyJob, job.id)
    lease = db_session.scalars(select(GpuResourceLease)).one()
    assert result.state == QueueStatus.complete.value
    assert result.prompt_id == "prompt-live-1"
    assert persisted is not None
    assert persisted.status == QueueStatus.complete
    assert persisted.attempt_count == 1
    assert runtime.websocket.closed is True
    assert lease.status == "released"
    assert len(db_session.scalars(select(FileOutput)).all()) == 1
    assert len(db_session.scalars(select(GeneratedAsset)).all()) == 1


@pytest.mark.asyncio
async def test_live_worker_retries_transient_object_info_failure_without_submission(tmp_path: Path, db_session: Session):
    settings = Settings(
        storage_root=tmp_path / "storage",
        comfyui_output_root=tmp_path / "comfy-output",
        queue_worker_enabled=True,
        comfyui_max_job_attempts=2,
    )
    job = _pending_job(db_session)

    def forbidden_factory():
        raise AssertionError("submission/runtime clients must not be constructed after object_info failure")

    worker = LiveComfyQueueWorker(
        worker_id="worker-retry-test",
        settings=settings,
        public_client_factory=lambda: _PublicClient({}),
        runtime_client_factory=forbidden_factory,
        submission_adapter_factory=forbidden_factory,
    )

    result = await worker.run_once(db_session)

    jobs = list(db_session.scalars(select(ComfyJob).order_by(ComfyJob.id)).all())
    original = db_session.get(ComfyJob, job.id)
    retry = next(candidate for candidate in jobs if candidate.id != job.id)
    assert result.state == QueueStatus.validation_failed.value
    assert "retry queued as" in (result.detail or "")
    assert original is not None
    assert original.status == QueueStatus.validation_failed
    assert original.recovery_metadata["retry_job_id"] == str(retry.id)
    assert retry.status == QueueStatus.pending
    assert retry.attempt_count == 1
    assert db_session.scalars(select(GpuResourceLease)).all() == []


def _runtime_settings(tmp_path: Path, *, operator_enabled: bool) -> Settings:
    root = tmp_path / "ComfyUI"
    root.mkdir()
    python_executable = tmp_path / "python.exe"
    python_executable.write_bytes(b"")
    main_script = root / "main.py"
    main_script.write_text("# fixture", encoding="utf-8")
    return Settings(
        storage_root=tmp_path / "storage",
        comfyui_root=root,
        comfyui_python_executable=python_executable,
        comfyui_main_script=main_script,
        comfyui_output_root=root / "output",
        hardware_operator_enabled=operator_enabled,
    )


def test_runtime_manager_is_passive_and_default_off(monkeypatch, tmp_path: Path):
    manager = PinnedComfyRuntimeManager(_runtime_settings(tmp_path, operator_enabled=False))
    monkeypatch.setattr(
        "backend.app.services.comfy.runtime_manager.httpx.Client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("passive status must not probe")),
    )
    monkeypatch.setattr(
        "backend.app.services.comfy.runtime_manager.subprocess.Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("disabled runtime must not start")),
    )

    status = manager.status(probe=False)
    assert status.configured is True
    assert status.reachable is False
    with pytest.raises(ComfyRuntimeMutationBlocked):
        manager.start()


def test_runtime_manager_retains_ownership_record_when_termination_fails(monkeypatch, tmp_path: Path):
    manager = PinnedComfyRuntimeManager(_runtime_settings(tmp_path, operator_enabled=True))
    command = manager._launch_command()
    manager._write_pid_record(424242, command)
    monkeypatch.setattr(manager, "_pid_exists", lambda _pid: True)
    monkeypatch.setattr(
        "backend.app.services.comfy.runtime_manager.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="access denied", stdout=""),
    )

    with pytest.raises(RuntimeError, match="access denied"):
        manager.terminate_process_tree("test failure")
    assert manager.pid_record_path.is_file()


def test_runtime_manager_fails_closed_for_malformed_ownership_record(monkeypatch, tmp_path: Path):
    manager = PinnedComfyRuntimeManager(_runtime_settings(tmp_path, operator_enabled=True))
    manager.runtime_state_root.mkdir(parents=True)
    manager.pid_record_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        "backend.app.services.comfy.runtime_manager.httpx.Client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(
        "backend.app.services.comfy.runtime_manager.subprocess.Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not start")),
    )

    with pytest.raises(ComfyRuntimeMutationBlocked, match="ownership record"):
        manager.start()
    assert manager.pid_record_path.read_text(encoding="utf-8") == "{not-json"


def _post_store(settings: Settings) -> PostProductionPlanStore:
    ffmpeg = FFmpegService(storage_root=settings.storage_root)
    post = PostProductionService(ffmpeg)
    return PostProductionPlanStore(settings, root=settings.storage_root / "plans", service=post)


def _post_request(storage_root: Path) -> PostProductionAssemblyPlanCreate:
    input_path = storage_root / "clips" / "shot-a.mp4"
    input_path.parent.mkdir(parents=True)
    input_path.write_bytes(b"offline-video-fixture")
    return PostProductionAssemblyPlanCreate.model_validate(
        {
            "clips": [
                {
                    "path": "clips/shot-a.mp4",
                    "duration_sec": 2.0,
                    "start_sec": 0.0,
                    "timeline_duration_sec": 2.0,
                    "sha256": sha256_file(input_path),
                    "probe_json": {"streams": [{"codec_type": "video", "codec_name": "h264"}]},
                }
            ],
            "target_duration_sec": 2.0,
            "geometry": {
                "aspect_ratio": "16:9",
                "quality_profile": "draft",
                "generation_width": 512,
                "generation_height": 288,
                "preview_width": 512,
                "preview_height": 288,
                "delivery_width": 1280,
                "delivery_height": 720,
            },
            "fps": 24,
            "output_path": "delivery/final.mp4",
        }
    )


def test_ffmpeg_executor_is_default_off_before_subprocess(tmp_path: Path, db_session: Session):
    settings = Settings(storage_root=tmp_path / "storage", ffmpeg_operator_enabled=False)
    store = _post_store(settings)
    manifest = store.create_from_request(_post_request(settings.storage_root))
    executor = GatedFFmpegExecutor(
        settings=settings,
        store=store,
        ffmpeg=store.service.ffmpeg,
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("FFmpeg must stay disabled")),
    )

    with pytest.raises(FFmpegExecutionBlocked):
        executor.execute_plan(db_session, manifest.plan_id, requested_by="test")
    assert db_session.scalars(select(FFmpegJob)).all() == []


def test_ffmpeg_executor_verifies_hash_runs_structured_command_and_records_provenance(
    monkeypatch,
    tmp_path: Path,
    db_session: Session,
):
    settings = Settings(storage_root=tmp_path / "storage", ffmpeg_operator_enabled=True)
    store = _post_store(settings)
    manifest = store.create_from_request(_post_request(settings.storage_root))
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"offline-final-fixture")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    executor = GatedFFmpegExecutor(
        settings=settings,
        store=store,
        ffmpeg=store.service.ffmpeg,
        runner=fake_runner,
    )
    monkeypatch.setattr(executor, "_probe", lambda path: {"format": {"filename": str(path)}})

    completed = executor.execute_plan(db_session, manifest.plan_id, requested_by="uat-test")

    job = db_session.scalars(select(FFmpegJob)).one()
    assert calls == [manifest.command]
    assert completed.state == "complete"
    assert completed.execution_submitted is True
    assert completed.ffmpeg_job_id == job.id
    assert completed.output_sha256 == sha256_file(settings.storage_root / completed.output_path)
    assert job.status == "complete"
    assert job.input_manifest["requested_by"] == "uat-test"


def test_ffmpeg_executor_refuses_changed_input_before_subprocess(tmp_path: Path, db_session: Session):
    settings = Settings(storage_root=tmp_path / "storage", ffmpeg_operator_enabled=True)
    store = _post_store(settings)
    manifest = store.create_from_request(_post_request(settings.storage_root))
    (settings.storage_root / manifest.input_paths[0]).write_bytes(b"changed-after-plan")
    executor = GatedFFmpegExecutor(
        settings=settings,
        store=store,
        ffmpeg=store.service.ffmpeg,
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("hash mismatch must block")),
    )

    with pytest.raises(Exception, match="Input hash changed"):
        executor.execute_plan(db_session, manifest.plan_id, requested_by="test")
    assert db_session.scalars(select(FFmpegJob)).all() == []
