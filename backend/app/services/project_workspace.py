"""Atomic and idempotent project workspace creation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import (
    Project,
    ProjectStoryboardSettings,
    ProjectWorkspaceCreation,
    Story,
)
from backend.app.schemas.api import ProjectWorkspaceCreate
from backend.app.services.storyboard_settings import default_settings_values


class ProjectWorkspaceConflictError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectWorkspaceResult:
    project: Project
    story: Story
    settings: ProjectStoryboardSettings
    idempotent_replay: bool


def _request_hash(payload: ProjectWorkspaceCreate) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json", exclude={"idempotency_key"}),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _new_story(project_id, payload: ProjectWorkspaceCreate) -> Story:
    return Story(
        project_id=project_id,
        title=payload.story_title,
        base_story=payload.base_story,
        target_duration_sec=payload.target_duration_sec,
        audience=payload.audience,
        genre=payload.genre,
        tone=payload.tone,
        point_of_view=payload.point_of_view,
        visual_style=payload.visual_style,
        production_notes=payload.production_notes,
        approval_state="draft",
    )


def _new_settings(project_id, payload: ProjectWorkspaceCreate) -> ProjectStoryboardSettings:
    values = default_settings_values()
    values.update(
        {
            "aspect_ratio": payload.aspect_ratio,
            "preview_width": payload.preview_width,
            "preview_height": payload.preview_height,
            "final_width": payload.final_width,
            "final_height": payload.final_height,
            "fps": payload.fps,
            "captions_enabled": payload.captions_enabled,
            "audio_enabled": payload.audio_enabled,
            "speaking_rate": payload.speaking_rate,
            "prefer_hosted_providers": payload.prefer_hosted_providers,
            "prefer_local_providers": payload.prefer_local_providers,
            "allow_model_download": False,
            "allow_rendering": False,
            "require_production_plan_approval": True,
        }
    )
    values["prompting_policy_json"] = {
        **values["prompting_policy_json"],
        "orchestration_mode": payload.orchestration_mode,
        "privacy_preference": payload.privacy_preference,
        "quality_preference": payload.quality_preference,
        "cost_sensitivity": payload.cost_sensitivity,
    }
    return ProjectStoryboardSettings(project_id=project_id, **values)


def _load_replay(
    db: Session, record: ProjectWorkspaceCreation, request_hash: str
) -> ProjectWorkspaceResult:
    if record.request_hash != request_hash:
        raise ProjectWorkspaceConflictError(
            "That idempotency key was already used for a different project workspace request."
        )
    project = db.get(Project, record.project_id)
    story = db.get(Story, record.story_id)
    settings = db.get(ProjectStoryboardSettings, record.settings_id)
    if project is None or story is None or settings is None:
        raise RuntimeError("The project workspace replay record is incomplete.")
    return ProjectWorkspaceResult(project, story, settings, True)


def create_project_workspace(db: Session, payload: ProjectWorkspaceCreate) -> ProjectWorkspaceResult:
    request_hash = _request_hash(payload)
    existing = db.scalar(
        select(ProjectWorkspaceCreation).where(
            ProjectWorkspaceCreation.idempotency_key == payload.idempotency_key
        )
    )
    if existing is not None:
        return _load_replay(db, existing, request_hash)

    try:
        project = Project(name=payload.name, description=payload.description)
        db.add(project)
        db.flush()

        story = _new_story(project.id, payload)
        settings = _new_settings(project.id, payload)
        db.add_all((story, settings))
        db.flush()

        db.add(
            ProjectWorkspaceCreation(
                idempotency_key=payload.idempotency_key,
                request_hash=request_hash,
                project_id=project.id,
                story_id=story.id,
                settings_id=settings.id,
            )
        )
        db.commit()
        db.refresh(project)
        db.refresh(story)
        db.refresh(settings)
        return ProjectWorkspaceResult(project, story, settings, False)
    except IntegrityError:
        db.rollback()
        replay = db.scalar(
            select(ProjectWorkspaceCreation).where(
                ProjectWorkspaceCreation.idempotency_key == payload.idempotency_key
            )
        )
        if replay is None:
            raise
        return _load_replay(db, replay, request_hash)
    except Exception:
        db.rollback()
        raise
