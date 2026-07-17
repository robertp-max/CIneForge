"""Remaining Storyboard Phase 1 planning CRUD services.

Covers narrations, prompt packages/versions, model/workflow recommendations,
provider profiles, task-provider assignments, proposals, and storyboard-version
list/get. Uses existing ORM models and transactional service conventions from
backend.app.services.storyboard. Never executes providers, ComfyUI, or renders.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    AIProposalRecord,
    AuditLog,
    Chapter,
    ModelVariant,
    ProviderProfile,
    Scene,
    Shot,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
    Story,
    StoryboardVersion,
    TaskProviderAssignment,
    VoiceProfile,
    WorkflowTemplate,
)
from backend.app.schemas.storyboard_crud import (
    ProposalCreateExtended,
    ProposalUpdate,
    ProviderProfileCreate,
    ProviderProfileUpdate,
    ShotModelRecommendationCreate,
    ShotModelRecommendationUpdate,
    ShotNarrationCreate,
    ShotNarrationUpdate,
    ShotPromptPackageCreate,
    ShotPromptPackageUpdate,
    TaskProviderAssignmentCreate,
    TaskProviderAssignmentUpdate,
)


class StoryboardCrudError(ValueError):
    """Domain validation failure (typically HTTP 422)."""


class StoryboardCrudNotFoundError(StoryboardCrudError):
    """Missing entity (typically HTTP 404)."""


class StoryboardCrudConflictError(Exception):
    """Unique/constraint conflict (typically HTTP 409)."""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID | None,
    action: str,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details=details or {},
        )
    )


def _shot_or_error(db: Session, shot_id: UUID) -> Shot:
    shot = db.get(Shot, shot_id)
    if shot is None or shot.archived_at is not None:
        raise StoryboardCrudNotFoundError("Shot not found.")
    scene = db.get(Scene, shot.scene_id)
    if scene is None or scene.archived_at is not None:
        raise StoryboardCrudNotFoundError("Shot not found.")
    chapter = db.get(Chapter, scene.chapter_id)
    if chapter is None or chapter.archived_at is not None:
        raise StoryboardCrudNotFoundError("Shot not found.")
    _story_or_error(db, chapter.story_id)
    return shot


def _story_or_error(db: Session, story_id: UUID) -> Story:
    story = db.get(Story, story_id)
    if story is None:
        raise StoryboardCrudNotFoundError("Story not found.")
    return story


def _story_for_active_shot(db: Session, shot_id: UUID) -> Story:
    shot = _shot_or_error(db, shot_id)
    scene = db.get(Scene, shot.scene_id)
    chapter = db.get(Chapter, scene.chapter_id) if scene is not None else None
    if chapter is None:
        raise StoryboardCrudNotFoundError("Shot not found.")
    return _lock_story_for_mutation(db, chapter.story_id)


def _mark_story_draft(story: Story) -> None:
    story.approval_state = "draft"
    story.updated_at = _now()


def _lock_story_for_mutation(db: Session, story_id: UUID) -> Story:
    story = db.scalar(
        select(Story)
        .where(Story.id == story_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if story is None:
        raise StoryboardCrudNotFoundError("Story not found.")
    return story


def _lock_and_mark_provider_stories(db: Session, profile_id: UUID) -> None:
    story_ids = set(
        db.scalars(select(Story.id).where(Story.default_provider_profile_id == profile_id))
    )
    story_ids.update(
        db.scalars(
            select(TaskProviderAssignment.story_id).where(
                TaskProviderAssignment.provider_profile_id == profile_id
            )
        )
    )
    story_ids.update(
        db.scalars(
            select(Chapter.story_id)
            .join(Scene, Scene.chapter_id == Chapter.id)
            .join(Shot, Shot.scene_id == Scene.id)
            .join(ShotPromptPackage, ShotPromptPackage.shot_id == Shot.id)
            .where(ShotPromptPackage.provider_profile_id == profile_id)
        )
    )
    if not story_ids:
        return
    stories = list(
        db.scalars(
            select(Story)
            .where(Story.id.in_(story_ids))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    for story in stories:
        _mark_story_draft(story)


def _content_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Shot narrations
# ---------------------------------------------------------------------------


def get_narration(db: Session, shot_id: UUID) -> ShotNarration | None:
    _shot_or_error(db, shot_id)
    return db.scalar(select(ShotNarration).where(ShotNarration.shot_id == shot_id))


def upsert_narration(
    db: Session,
    shot_id: UUID,
    payload: ShotNarrationCreate | ShotNarrationUpdate,
    *,
    partial: bool = False,
) -> ShotNarration:
    shot = _shot_or_error(db, shot_id)
    story = _story_for_active_shot(db, shot_id)
    existing = db.scalar(select(ShotNarration).where(ShotNarration.shot_id == shot_id))

    if isinstance(payload, ShotNarrationCreate):
        data = payload.model_dump()
    else:
        data = payload.model_dump(exclude_unset=True)

    voice_id = data.get("voice_profile_id", None if not partial else ...)
    if voice_id not in (None, ...) and voice_id is not None:
        voice = db.get(VoiceProfile, voice_id)
        if voice is None:
            raise StoryboardCrudError("Voice profile not found.")
        # Voice must belong to the same story as the shot.
        from backend.app.db.base import Chapter, Scene

        story_id = db.scalar(
            select(Chapter.story_id)
            .join(Scene, Scene.chapter_id == Chapter.id)
            .where(Scene.id == shot.scene_id)
        )
        if voice.story_id != story_id:
            raise StoryboardCrudError("Voice profile must belong to the same story as the shot.")

    if existing is None:
        if partial and not isinstance(payload, ShotNarrationCreate):
            # Allow partial only when creating via full create schema or empty create defaults.
            create_payload = ShotNarrationCreate(**{k: v for k, v in data.items() if v is not ...})
            data = create_payload.model_dump()
        row = ShotNarration(shot_id=shot_id, **data)
        db.add(row)
        action = "shot_narration_created"
    else:
        # Merge for partial updates; validate text-or-exception after merge.
        for field, value in data.items():
            setattr(existing, field, value)
        has_text = bool((existing.narration_text or "").strip())
        has_exception = bool((existing.narration_exception_reason or "").strip())
        if not has_text and not has_exception:
            raise StoryboardCrudError("Narration requires text or an exception reason.")
        row = existing
        action = "shot_narration_updated"

    db.flush()
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="shot_narration",
        entity_id=row.id,
        action=action,
        details={"shot_id": str(shot_id)},
    )
    db.commit()
    db.refresh(row)
    return row


def delete_narration(db: Session, shot_id: UUID) -> None:
    story = _story_for_active_shot(db, shot_id)
    row = get_narration(db, shot_id)
    if row is None:
        raise StoryboardCrudNotFoundError("Narration not found.")
    narration_id = row.id
    db.delete(row)
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="shot_narration",
        entity_id=narration_id,
        action="shot_narration_deleted",
        details={"shot_id": str(shot_id)},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Prompt packages / versions
# ---------------------------------------------------------------------------


def list_prompt_packages(db: Session, shot_id: UUID) -> list[ShotPromptPackage]:
    _shot_or_error(db, shot_id)
    return list(
        db.scalars(
            select(ShotPromptPackage)
            .where(ShotPromptPackage.shot_id == shot_id)
            .order_by(ShotPromptPackage.version.desc())
        )
    )


def get_prompt_package(db: Session, package_id: UUID) -> ShotPromptPackage:
    row = db.get(ShotPromptPackage, package_id)
    if row is None:
        raise StoryboardCrudNotFoundError("Prompt package not found.")
    _shot_or_error(db, row.shot_id)
    return row


def get_prompt_package_version(
    db: Session, shot_id: UUID, version: int
) -> ShotPromptPackage:
    _shot_or_error(db, shot_id)
    row = db.scalar(
        select(ShotPromptPackage).where(
            ShotPromptPackage.shot_id == shot_id,
            ShotPromptPackage.version == version,
        )
    )
    if row is None:
        raise StoryboardCrudNotFoundError("Prompt package version not found.")
    return row


def create_prompt_package(
    db: Session, shot_id: UUID, payload: ShotPromptPackageCreate
) -> ShotPromptPackage:
    story = _story_for_active_shot(db, shot_id)
    data = payload.model_dump()
    explicit_version = data.pop("version", None)

    if data.get("provider_profile_id") is not None:
        if db.get(ProviderProfile, data["provider_profile_id"]) is None:
            raise StoryboardCrudError("Provider profile not found.")
    if data.get("proposal_id") is not None:
        if db.get(AIProposalRecord, data["proposal_id"]) is None:
            raise StoryboardCrudError("Proposal not found.")

    if explicit_version is not None:
        collision = db.scalar(
            select(ShotPromptPackage).where(
                ShotPromptPackage.shot_id == shot_id,
                ShotPromptPackage.version == explicit_version,
            )
        )
        if collision is not None:
            raise StoryboardCrudConflictError(
                f"Prompt package version {explicit_version} already exists for this shot."
            )
        version = explicit_version
    else:
        current = (
            db.scalar(
                select(ShotPromptPackage.version)
                .where(ShotPromptPackage.shot_id == shot_id)
                .order_by(ShotPromptPackage.version.desc())
                .limit(1)
            )
            or 0
        )
        version = int(current) + 1

    row = ShotPromptPackage(shot_id=shot_id, version=version, **data)
    db.add(row)
    db.flush()
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="shot_prompt_package",
        entity_id=row.id,
        action="shot_prompt_package_created",
        details={"shot_id": str(shot_id), "version": version},
    )
    db.commit()
    db.refresh(row)
    return row


def update_prompt_package(
    db: Session, package_id: UUID, payload: ShotPromptPackageUpdate
) -> ShotPromptPackage:
    row = get_prompt_package(db, package_id)
    story = _story_for_active_shot(db, row.shot_id)
    data = payload.model_dump(exclude_unset=True)
    if "provider_profile_id" in data and data["provider_profile_id"] is not None:
        if db.get(ProviderProfile, data["provider_profile_id"]) is None:
            raise StoryboardCrudError("Provider profile not found.")
    if "proposal_id" in data and data["proposal_id"] is not None:
        if db.get(AIProposalRecord, data["proposal_id"]) is None:
            raise StoryboardCrudError("Proposal not found.")
    for field, value in data.items():
        setattr(row, field, value)
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="shot_prompt_package",
        entity_id=row.id,
        action="shot_prompt_package_updated",
        details={"shot_id": str(row.shot_id), "version": row.version},
    )
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Model / workflow recommendations
# ---------------------------------------------------------------------------


def list_recommendations(db: Session, shot_id: UUID) -> list[ShotModelRecommendation]:
    _shot_or_error(db, shot_id)
    return list(
        db.scalars(
            select(ShotModelRecommendation)
            .where(ShotModelRecommendation.shot_id == shot_id)
            .order_by(ShotModelRecommendation.created_at.desc())
        )
    )


def get_recommendation(db: Session, recommendation_id: UUID) -> ShotModelRecommendation:
    row = db.get(ShotModelRecommendation, recommendation_id)
    if row is None:
        raise StoryboardCrudNotFoundError("Recommendation not found.")
    _shot_or_error(db, row.shot_id)
    return row


def create_recommendation(
    db: Session, shot_id: UUID, payload: ShotModelRecommendationCreate
) -> ShotModelRecommendation:
    story = _story_for_active_shot(db, shot_id)
    data = payload.model_dump()
    # Coerce enums to values for ORM.
    if hasattr(data.get("recommendation_type"), "value"):
        data["recommendation_type"] = data["recommendation_type"].value
    if hasattr(data.get("approval_state"), "value"):
        data["approval_state"] = data["approval_state"].value

    if data.get("generation_model_variant_id") is not None:
        if db.get(ModelVariant, data["generation_model_variant_id"]) is None:
            raise StoryboardCrudError("Model variant not found.")
    if data.get("workflow_template_id") is not None:
        if db.get(WorkflowTemplate, data["workflow_template_id"]) is None:
            raise StoryboardCrudError("Workflow template not found.")

    # Factual defaults: do not invent availability/benchmark beyond caller input,
    # but normalize empty to unknown.
    data["availability_status"] = (data.get("availability_status") or "unknown").lower()
    data["benchmark_status"] = (data.get("benchmark_status") or "unknown").lower()

    row = ShotModelRecommendation(shot_id=shot_id, **data)
    db.add(row)
    db.flush()
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="shot_model_recommendation",
        entity_id=row.id,
        action="shot_model_recommendation_created",
        details={
            "shot_id": str(shot_id),
            "recommendation_type": row.recommendation_type,
            "availability_status": row.availability_status,
            "benchmark_status": row.benchmark_status,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def update_recommendation(
    db: Session, recommendation_id: UUID, payload: ShotModelRecommendationUpdate
) -> ShotModelRecommendation:
    row = get_recommendation(db, recommendation_id)
    story = _story_for_active_shot(db, row.shot_id)
    data = payload.model_dump(exclude_unset=True)
    acknowledge = data.pop("acknowledge", None)

    if "recommendation_type" in data and hasattr(data["recommendation_type"], "value"):
        data["recommendation_type"] = data["recommendation_type"].value
    if "approval_state" in data and hasattr(data["approval_state"], "value"):
        data["approval_state"] = data["approval_state"].value

    if data.get("generation_model_variant_id") is not None:
        if db.get(ModelVariant, data["generation_model_variant_id"]) is None:
            raise StoryboardCrudError("Model variant not found.")
    if data.get("workflow_template_id") is not None:
        if db.get(WorkflowTemplate, data["workflow_template_id"]) is None:
            raise StoryboardCrudError("Workflow template not found.")

    for field, value in data.items():
        setattr(row, field, value)

    if acknowledge is True and row.acknowledged_at is None:
        row.acknowledged_at = _now()

    _mark_story_draft(story)

    _audit(
        db,
        entity_type="shot_model_recommendation",
        entity_id=row.id,
        action="shot_model_recommendation_updated",
        details={"shot_id": str(row.shot_id)},
    )
    db.commit()
    db.refresh(row)
    return row


def delete_recommendation(db: Session, recommendation_id: UUID) -> None:
    row = get_recommendation(db, recommendation_id)
    story = _story_for_active_shot(db, row.shot_id)
    shot_id = row.shot_id
    db.delete(row)
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="shot_model_recommendation",
        entity_id=recommendation_id,
        action="shot_model_recommendation_deleted",
        details={"shot_id": str(shot_id)},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Provider profiles
# ---------------------------------------------------------------------------


def _declared_capabilities_payload(raw: dict | None) -> dict[str, list[str]]:
    """Normalize profile input as declarations, never verified capability facts."""

    value = dict(raw or {})
    candidates = value.get("declared_capabilities", value.get("capabilities"))
    if isinstance(candidates, list):
        labels = {str(item).strip() for item in candidates if str(item).strip()}
    else:
        # Backward-compatible declaration syntax: {"planning": true}.
        labels = {
            str(key).strip()
            for key, enabled in value.items()
            if isinstance(enabled, bool) and enabled and str(key).strip()
        }
    if len(labels) > 64 or any(len(label) > 80 for label in labels):
        raise StoryboardCrudError(
            "Declared capabilities are limited to 64 labels of 80 characters each."
        )
    return {"declared_capabilities": sorted(labels)}


def list_provider_profiles(db: Session) -> list[ProviderProfile]:
    return list(
        db.scalars(select(ProviderProfile).order_by(ProviderProfile.display_name))
    )


def get_provider_profile(db: Session, profile_id: UUID) -> ProviderProfile:
    row = db.get(ProviderProfile, profile_id)
    if row is None:
        raise StoryboardCrudNotFoundError("Provider profile not found.")
    return row


def create_provider_profile(
    db: Session, payload: ProviderProfileCreate
) -> ProviderProfile:
    data = payload.model_dump()
    if hasattr(data.get("execution_mode"), "value"):
        data["execution_mode"] = data["execution_mode"].value
    # Profile CRUD is a declaration boundary.  Runtime/provider facts may only
    # come from the provider registry or an explicit bounded connection test.
    if data.get("availability_status") not in {None, "unknown"}:
        raise StoryboardCrudError(
            "Provider availability is factual and cannot be asserted by profile CRUD."
        )
    data["availability_status"] = "unknown"
    declaration_supplied = bool(
        {"capabilities_json", "capability_source"} & payload.model_fields_set
    )
    data["capabilities_json"] = _declared_capabilities_payload(
        data.get("capabilities_json")
    )
    data["capability_source"] = (
        "user_declared" if declaration_supplied else None
    )
    # capabilities_checked_at and health_checked_at are intentionally absent
    # from all CRUD request schemas and therefore remain unset here.
    row = ProviderProfile(**data)
    db.add(row)
    db.flush()
    _audit(
        db,
        entity_type="provider_profile",
        entity_id=row.id,
        action="provider_profile_created",
        details={
            "provider_identifier": row.provider_identifier,
            "execution_mode": row.execution_mode,
            "availability_status": row.availability_status,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def update_provider_profile(
    db: Session, profile_id: UUID, payload: ProviderProfileUpdate
) -> ProviderProfile:
    row = get_provider_profile(db, profile_id)
    data = payload.model_dump(exclude_unset=True)
    if "execution_mode" in data and hasattr(data["execution_mode"], "value"):
        data["execution_mode"] = data["execution_mode"].value
    if "availability_status" in data and data["availability_status"] is not None:
        if data["availability_status"] != "unknown":
            raise StoryboardCrudError(
                "Provider availability is factual and cannot be asserted by profile CRUD."
            )
        data["availability_status"] = "unknown"
    if "capabilities_json" in data:
        data["capabilities_json"] = _declared_capabilities_payload(
            data["capabilities_json"]
        )
        data["capability_source"] = "user_declared"
    elif "capability_source" in data:
        # A source label cannot elevate an existing declaration to a verified
        # fact.  Keep the only write-side source explicit.
        data["capability_source"] = (
            "user_declared"
            if _declared_capabilities_payload(row.capabilities_json)[
                "declared_capabilities"
            ]
            else None
        )
    if data:
        _lock_and_mark_provider_stories(db, profile_id)
    for field, value in data.items():
        setattr(row, field, value)
    _audit(
        db,
        entity_type="provider_profile",
        entity_id=row.id,
        action="provider_profile_updated",
        details={"provider_identifier": row.provider_identifier},
    )
    db.commit()
    db.refresh(row)
    return row


def delete_provider_profile(db: Session, profile_id: UUID) -> None:
    row = get_provider_profile(db, profile_id)
    # Block delete when assignments still reference the profile.
    assignment = db.scalar(
        select(TaskProviderAssignment.id)
        .where(TaskProviderAssignment.provider_profile_id == profile_id)
        .limit(1)
    )
    if assignment is not None:
        raise StoryboardCrudConflictError(
            "Cannot delete provider profile while task assignments reference it."
        )
    _lock_and_mark_provider_stories(db, profile_id)
    db.delete(row)
    _audit(
        db,
        entity_type="provider_profile",
        entity_id=profile_id,
        action="provider_profile_deleted",
        details={},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Task provider assignments
# ---------------------------------------------------------------------------


def list_task_assignments(db: Session, story_id: UUID) -> list[TaskProviderAssignment]:
    _story_or_error(db, story_id)
    return list(
        db.scalars(
            select(TaskProviderAssignment)
            .where(TaskProviderAssignment.story_id == story_id)
            .order_by(TaskProviderAssignment.priority.desc(), TaskProviderAssignment.task_type)
        )
    )


def get_task_assignment(db: Session, assignment_id: UUID) -> TaskProviderAssignment:
    row = db.get(TaskProviderAssignment, assignment_id)
    if row is None:
        raise StoryboardCrudNotFoundError("Task provider assignment not found.")
    return row


def create_task_assignment(
    db: Session, story_id: UUID, payload: TaskProviderAssignmentCreate
) -> TaskProviderAssignment:
    story = _lock_story_for_mutation(db, story_id)
    data = payload.model_dump()
    if hasattr(data.get("assignment_mode"), "value"):
        data["assignment_mode"] = data["assignment_mode"].value

    if db.get(ProviderProfile, data["provider_profile_id"]) is None:
        raise StoryboardCrudError("Provider profile not found.")

    existing = db.scalar(
        select(TaskProviderAssignment).where(
            TaskProviderAssignment.story_id == story_id,
            TaskProviderAssignment.task_type == data["task_type"],
        )
    )
    if existing is not None:
        raise StoryboardCrudConflictError(
            f"Task type '{data['task_type']}' already has a provider assignment for this story."
        )

    row = TaskProviderAssignment(story_id=story_id, **data)
    db.add(row)
    db.flush()
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="task_provider_assignment",
        entity_id=row.id,
        action="task_provider_assignment_created",
        details={
            "story_id": str(story_id),
            "task_type": row.task_type,
            "provider_profile_id": str(row.provider_profile_id),
        },
    )
    db.commit()
    db.refresh(row)
    return row


def update_task_assignment(
    db: Session, assignment_id: UUID, payload: TaskProviderAssignmentUpdate
) -> TaskProviderAssignment:
    row = get_task_assignment(db, assignment_id)
    story = _lock_story_for_mutation(db, row.story_id)
    data = payload.model_dump(exclude_unset=True)
    if "assignment_mode" in data and hasattr(data["assignment_mode"], "value"):
        data["assignment_mode"] = data["assignment_mode"].value
    if data.get("provider_profile_id") is not None:
        if db.get(ProviderProfile, data["provider_profile_id"]) is None:
            raise StoryboardCrudError("Provider profile not found.")
    for field, value in data.items():
        setattr(row, field, value)
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="task_provider_assignment",
        entity_id=row.id,
        action="task_provider_assignment_updated",
        details={"story_id": str(row.story_id), "task_type": row.task_type},
    )
    db.commit()
    db.refresh(row)
    return row


def delete_task_assignment(db: Session, assignment_id: UUID) -> None:
    row = get_task_assignment(db, assignment_id)
    story = _lock_story_for_mutation(db, row.story_id)
    story_id = row.story_id
    task_type = row.task_type
    db.delete(row)
    _mark_story_draft(story)
    _audit(
        db,
        entity_type="task_provider_assignment",
        entity_id=assignment_id,
        action="task_provider_assignment_deleted",
        details={"story_id": str(story_id), "task_type": task_type},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


def create_proposal(db: Session, payload: ProposalCreateExtended) -> AIProposalRecord:
    data = payload.model_dump()
    if data.get("story_id") is not None:
        _story_or_error(db, data["story_id"])
    if data.get("base_storyboard_version_id") is not None:
        version = db.get(StoryboardVersion, data["base_storyboard_version_id"])
        if version is None:
            raise StoryboardCrudError("Base storyboard version not found.")

    content_hash = _content_hash(
        {"proposal_type": data["proposal_type"], "payload": data["payload"]}
    )
    row = AIProposalRecord(
        proposal_type=data["proposal_type"],
        payload=data["payload"],
        status="pending_review",
        validation_errors=[],
        story_id=data.get("story_id"),
        orchestration_run_id=data.get("orchestration_run_id"),
        base_storyboard_version_id=data.get("base_storyboard_version_id"),
        schema_name=data.get("schema_name"),
        content_hash=content_hash,
        validation_status="pending",
        validation_report_json={},
        warnings_json=[],
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        entity_type="ai_proposal_record",
        entity_id=row.id,
        action="ai_proposal_created",
        details={
            "proposal_type": row.proposal_type,
            "story_id": str(row.story_id) if row.story_id else None,
            "content_hash": content_hash,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def list_proposals(
    db: Session,
    *,
    story_id: UUID | None = None,
    status_filter: str | None = None,
) -> list[AIProposalRecord]:
    query = select(AIProposalRecord).order_by(AIProposalRecord.created_at.desc())
    if story_id is not None:
        query = query.where(AIProposalRecord.story_id == story_id)
    if status_filter is not None:
        query = query.where(AIProposalRecord.status == status_filter)
    return list(db.scalars(query))


def get_proposal(db: Session, proposal_id: UUID) -> AIProposalRecord:
    row = db.get(AIProposalRecord, proposal_id)
    if row is None:
        raise StoryboardCrudNotFoundError("Proposal not found.")
    return row


def update_proposal(
    db: Session, proposal_id: UUID, payload: ProposalUpdate
) -> AIProposalRecord:
    row = get_proposal(db, proposal_id)
    data = payload.model_dump(exclude_unset=True)
    now = _now()

    new_status = data.get("status")
    if new_status is not None:
        row.status = new_status
        if new_status in {"reviewed", "approved", "rejected", "applied"} and data.get(
            "reviewed_by"
        ):
            row.reviewed_by = data["reviewed_by"]
            row.reviewed_at = now
        if new_status == "applied":
            row.applied_at = now
        if new_status == "rejected":
            row.rejected_at = now
            if data.get("rejection_reason"):
                row.rejection_reason = data["rejection_reason"]

    for field in (
        "validation_status",
        "validation_errors",
        "validation_report_json",
        "warnings_json",
        "reviewed_by",
        "rejection_reason",
    ):
        if field in data and data[field] is not None:
            setattr(row, field, data[field])

    if "reviewed_by" in data and data["reviewed_by"] and row.reviewed_at is None:
        row.reviewed_at = now

    _audit(
        db,
        entity_type="ai_proposal_record",
        entity_id=row.id,
        action="ai_proposal_updated",
        details={"status": row.status, "validation_status": row.validation_status},
    )
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Storyboard versions (list / get only — approval remains in storyboard service)
# ---------------------------------------------------------------------------


def list_storyboard_versions(
    db: Session,
    story_id: UUID,
    *,
    status_filter: str | None = None,
) -> list[StoryboardVersion]:
    _story_or_error(db, story_id)
    query = (
        select(StoryboardVersion)
        .where(StoryboardVersion.story_id == story_id)
        .order_by(StoryboardVersion.version_number.desc())
    )
    if status_filter is not None:
        query = query.where(StoryboardVersion.status == status_filter)
    return list(db.scalars(query))


def get_storyboard_version(db: Session, version_id: UUID) -> StoryboardVersion:
    row = db.get(StoryboardVersion, version_id)
    if row is None:
        raise StoryboardCrudNotFoundError("Storyboard version not found.")
    return row


def get_storyboard_version_for_story(
    db: Session, story_id: UUID, version_id: UUID
) -> StoryboardVersion:
    row = get_storyboard_version(db, version_id)
    if row.story_id != story_id:
        raise StoryboardCrudNotFoundError("Storyboard version not found for story.")
    return row
