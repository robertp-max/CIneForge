"""Tests for shared GPU leases and explicit voice preview worker behavior."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.schemas.voice import (
    PARLER_UNAVAILABLE_MESSAGE,
    GpuLeaseAcquireRequest,
    PreviewJobStatus,
    VoicePreviewRequest,
)
from backend.app.db.base import Base, GpuResourceLease
from backend.app.services.runtime.gpu_leases import (
    DEFAULT_EXCLUSIVE_GROUP,
    GpuLeaseError,
    VOICE_PREVIEW_WORKLOAD,
    acquire_lease,
    acquire_voice_preview_lease,
    release_lease,
)


@pytest.fixture
def lease_db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(bind=engine, tables=[GpuResourceLease.__table__])
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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
