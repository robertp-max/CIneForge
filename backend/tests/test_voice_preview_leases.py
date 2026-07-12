"""Tests for shared GPU leases and explicit voice preview worker behavior."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.app.schemas.voice import (
    PARLER_UNAVAILABLE_MESSAGE,
    GpuLeaseAcquireRequest,
    PreviewJobStatus,
    VoicePreviewRequest,
)
from backend.app.services.runtime.gpu_leases import (
    DEFAULT_EXCLUSIVE_GROUP,
    GpuLeaseError,
    VOICE_PREVIEW_WORKLOAD,
    acquire_lease,
    acquire_voice_preview_lease,
    release_lease,
)


class _MemDB:
    """Minimal stand-in for Session used by lease helpers in unit tests."""

    def __init__(self):
        self._rows: dict[uuid.UUID, object] = {}
        self._pending: list[object] = []

    def add(self, obj):
        self._pending.append(obj)

    def commit(self):
        for obj in self._pending:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            self._rows[obj.id] = obj
        self._pending.clear()

    def rollback(self):
        self._pending.clear()

    def refresh(self, obj):
        return obj

    def get(self, model, ident):  # noqa: ANN001
        return self._rows.get(ident)

    def scalars(self, stmt):  # noqa: ANN001
        # Extremely small fake: filter active leases from memory.
        rows = list(self._rows.values())

        class _Result:
            def __init__(self, items):
                self._items = items

            def first(self):
                return self._items[0] if self._items else None

            def __iter__(self):
                return iter(self._items)

        active = [
            r
            for r in rows
            if getattr(r, "status", None) == "active"
        ]
        return _Result(active)


# Patch GpuResourceLease construction used by gpu_leases by injecting a simple namespace factory.
@pytest.fixture
def lease_db(monkeypatch):
    from backend.app.services.runtime import gpu_leases as gl

    def factory(**kwargs):
        obj = SimpleNamespace(**kwargs)
        obj.id = None
        return obj

    monkeypatch.setattr(gl, "GpuResourceLease", factory)
    return _MemDB()


def test_voice_preview_lease_uses_shared_exclusive_group(lease_db):
    lease = acquire_voice_preview_lease(
        lease_db,
        owner="test",
        workload_id="job-1",
        resource_key="gpu0",
    )
    assert lease.workload_type == VOICE_PREVIEW_WORKLOAD
    assert lease.exclusive_group == DEFAULT_EXCLUSIVE_GROUP
    assert lease.status == "active"


def test_video_and_voice_preview_serialize_via_exclusive_group(lease_db):
    video = acquire_lease(
        lease_db,
        GpuLeaseAcquireRequest(
            resource_key="gpu0",
            exclusive_group=DEFAULT_EXCLUSIVE_GROUP,
            workload_type="video_render",
            workload_id="vid-1",
            owner="video-worker",
        ),
    )
    assert video.status == "active"

    with pytest.raises(GpuLeaseError):
        acquire_voice_preview_lease(
            lease_db,
            owner="voice-worker",
            workload_id="voice-1",
            resource_key="gpu0",
        )

    release_lease(lease_db, video.id)

    voice = acquire_voice_preview_lease(
        lease_db,
        owner="voice-worker",
        workload_id="voice-1",
        resource_key="gpu0",
    )
    assert voice.status == "active"
    assert voice.workload_type == VOICE_PREVIEW_WORKLOAD


def test_parler_worker_message_constant():
    # Ensure worker module imports the exact required string.
    from backend.app.workers import voice_preview as vp

    assert vp.PARLER_UNAVAILABLE_MESSAGE == "Parler-TTS is not installed or approved."
    assert PARLER_UNAVAILABLE_MESSAGE == vp.PARLER_UNAVAILABLE_MESSAGE


def test_preview_request_forbids_embedded_audio():
    with pytest.raises(Exception):
        VoicePreviewRequest(
            preview_text="Hello there",
            design_metadata={"audio_base64": "AAAA"},
        )


def test_preview_job_state_to_read():
    from backend.app.workers.voice_preview import PreviewJobState

    state = PreviewJobState(
        job_id="abc",
        voice_profile_id=uuid.uuid4(),
        status=PreviewJobStatus.complete,
        planning_media_asset_id=uuid.uuid4(),
    )
    read = state.to_read()
    assert read.job_id == "abc"
    assert read.status == PreviewJobStatus.complete
    assert read.planning_media_asset_id is not None
