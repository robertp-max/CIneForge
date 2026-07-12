"""Explicit voice preview worker.

Previews run only when requested. Shared GPU leases serialize voice preview
with video GPU work. Results store managed planning asset IDs only — never
audio bytes, base64, or raw provider responses.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.base import Story, VoicePreview, VoiceProfile
from backend.app.schemas.voice import (
    PARLER_UNAVAILABLE_MESSAGE,
    PreviewJobStatus,
    VoicePreviewJobRead,
    VoicePreviewRequest,
)
from backend.app.services.planning_assets import (
    PlanningAssetError,
    register_voice_preview_asset,
)
from backend.app.services.runtime.gpu_leases import (
    GpuLeaseError,
    acquire_voice_preview_lease,
    release_lease,
)
from backend.app.services.voice_design.providers.base import get_provider
from backend.app.services.voice_design.service import (
    VoiceDesignError,
    build_preview_design_metadata,
    get_recipe_for_profile,
    get_voice_profile,
    resolve_preview_provider_name,
)

# Ensure adapters are registered.
import backend.app.services.voice_design.providers.placeholder  # noqa: F401
import backend.app.services.voice_design.providers.existing  # noqa: F401
import backend.app.services.voice_design.providers.qwen  # noqa: F401
import backend.app.services.voice_design.providers.elevenlabs  # noqa: F401
import backend.app.services.voice_design.providers.parler  # noqa: F401
import backend.app.services.voice_design.providers.user_provided  # noqa: F401


@dataclass
class PreviewJobState:
    job_id: str
    voice_profile_id: UUID
    status: PreviewJobStatus = PreviewJobStatus.pending
    provider: str | None = None
    model: str | None = None
    preview_id: UUID | None = None
    planning_media_asset_id: UUID | None = None
    lease_id: UUID | None = None
    error_message: str | None = None
    message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_read(self) -> VoicePreviewJobRead:
        return VoicePreviewJobRead(
            job_id=self.job_id,
            voice_profile_id=self.voice_profile_id,
            status=self.status,
            provider=self.provider,
            model=self.model,
            preview_id=self.preview_id,
            planning_media_asset_id=self.planning_media_asset_id,
            lease_id=self.lease_id,
            error_message=self.error_message,
            message=self.message,
        )


# In-process job registry for Phase 1 explicit previews (not a durable queue).
_JOBS: dict[str, PreviewJobState] = {}


def get_preview_job(job_id: str) -> PreviewJobState | None:
    return _JOBS.get(job_id)


def _preview_output_dir(storage_root: Path, voice_profile_id: UUID, job_id: str) -> Path:
    path = storage_root / "voice_previews" / str(voice_profile_id) / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _project_id_for_profile(db: Session, profile: VoiceProfile) -> UUID:
    story = db.get(Story, profile.story_id)
    if story is None:
        raise VoiceDesignError(f"Story {profile.story_id} not found for voice profile.")
    return story.project_id


def run_voice_preview_job(
    db: Session,
    voice_profile_id: UUID,
    request: VoicePreviewRequest,
    *,
    storage_root: str | Path = "./storage",
    resource_key: str = "gpu0",
    worker_id: str | None = None,
) -> VoicePreviewJobRead:
    """Execute an explicit voice preview under a shared GPU lease."""
    job_id = str(uuid.uuid4())
    state = PreviewJobState(job_id=job_id, voice_profile_id=voice_profile_id)
    _JOBS[job_id] = state

    lease = None
    try:
        profile = get_voice_profile(db, voice_profile_id)
        recipe = get_recipe_for_profile(db, profile, request.recipe_id)

        provider_name = resolve_preview_provider_name(profile, request.provider)
        state.provider = provider_name
        state.model = request.model or (recipe.model if recipe else profile.provider_model_id)

        adapter = get_provider(provider_name)
        if adapter is None:
            state.status = PreviewJobStatus.failed
            state.error_message = f"No voice preview provider registered for {provider_name!r}."
            return state.to_read()

        # Shared lease: serialize with video GPU work.
        state.status = PreviewJobStatus.reserved
        try:
            lease = acquire_voice_preview_lease(
                db,
                owner=request.owner,
                workload_id=job_id,
                worker_id=worker_id,
                resource_key=resource_key,
                ttl_seconds=300,
                metadata={
                    "voice_profile_id": str(voice_profile_id),
                    "provider": provider_name,
                },
            )
            state.lease_id = lease.id
        except GpuLeaseError as exc:
            state.status = PreviewJobStatus.failed
            state.error_message = str(exc)
            return state.to_read()

        state.status = PreviewJobStatus.running
        design_meta = build_preview_design_metadata(
            profile,
            recipe=recipe,
            extra=request.design_metadata,
        )
        out_dir = _preview_output_dir(Path(storage_root), voice_profile_id, job_id)

        result = adapter.generate_preview(
            preview_text=request.preview_text,
            design_metadata=design_meta,
            model=state.model,
            output_dir=str(out_dir),
        )

        if not result.success:
            state.status = PreviewJobStatus.failed
            # Preserve exact Parler message.
            err = result.error_message or "Voice preview failed."
            if provider_name == "parler":
                err = PARLER_UNAVAILABLE_MESSAGE if "Parler-TTS" in err or not result.success else err
                # Force exact string when provider signals unavailability.
                if not result.success:
                    err = PARLER_UNAVAILABLE_MESSAGE
            state.error_message = err
            state.message = err
            return state.to_read()

        if not result.managed_uri:
            state.status = PreviewJobStatus.failed
            state.error_message = "Preview provider returned success without a managed URI."
            return state.to_read()

        project_id = _project_id_for_profile(db, profile)
        try:
            asset = register_voice_preview_asset(
                db,
                project_id=project_id,
                managed_uri=result.managed_uri,
                sha256=result.sha256,
                mime_type=result.mime_type,
                duration_sec=result.duration_sec,
                size_bytes=result.size_bytes,
                provider=result.provider,
                model=result.model,
                extra_metadata={
                    k: v
                    for k, v in (result.metadata or {}).items()
                    if str(k).lower()
                    not in {
                        "audio",
                        "audio_base64",
                        "base64",
                        "raw_response",
                        "data",
                        "bytes",
                    }
                },
            )
        except PlanningAssetError as exc:
            state.status = PreviewJobStatus.failed
            state.error_message = str(exc)
            return state.to_read()

        preview = VoicePreview(
            voice_profile_id=profile.id,
            voice_recipe_id=recipe.id if recipe else None,
            planning_media_asset_id=asset.id,
            provider=result.provider,
            model=result.model,
            preview_text=request.preview_text,
            selected=False,
            rejected=False,
        )
        db.add(preview)
        # Mirror preview text onto profile for convenience (asset id only for media).
        profile.preview_text = request.preview_text
        db.add(profile)
        db.commit()
        db.refresh(preview)

        state.preview_id = preview.id
        state.planning_media_asset_id = asset.id
        state.model = result.model
        state.status = PreviewJobStatus.complete
        state.message = "Preview complete; stored managed asset id only."
        return state.to_read()

    except VoiceDesignError as exc:
        state.status = PreviewJobStatus.failed
        state.error_message = str(exc)
        return state.to_read()
    except Exception as exc:  # defensive boundary for worker
        state.status = PreviewJobStatus.failed
        state.error_message = f"Voice preview failed: {exc}"
        return state.to_read()
    finally:
        if lease is not None:
            try:
                release_lease(db, lease.id)
            except GpuLeaseError:
                pass


def list_previews(db: Session, voice_profile_id: UUID) -> list[VoicePreview]:
    get_voice_profile(db, voice_profile_id)
    from sqlalchemy import select

    stmt = (
        select(VoicePreview)
        .where(VoicePreview.voice_profile_id == voice_profile_id)
        .order_by(VoicePreview.created_at.desc())
    )
    return list(db.scalars(stmt))
