"""Authoritative, non-executing Storyboard Phase A domain services."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from io import StringIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.app.db.base import (
    AIProposalRecord,
    AuditLog,
    Chapter,
    Character,
    CharacterReferenceAsset,
    PlanningMediaAsset,
    Scene,
    Shot,
    ShotCharacter,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
    Story,
    StoryboardVersion,
    VoiceProfile,
)
from backend.app.schemas.storyboard import (
    ChapterCreate,
    ChapterUpdate,
    CharacterCreate,
    CharacterUpdate,
    ProposalCreate,
    SceneCreate,
    SceneUpdate,
    ShotCreate,
    ShotCharacterLinkCreate,
    ShotUpdate,
    StoryCreate,
    StoryUpdate,
    VoiceProfileCreate,
)
from backend.app.schemas.storyboard_settings import (
    DEFAULT_APPROVAL_POLICY,
    DEFAULT_CONTINUITY_POLICY,
    DEFAULT_PROMPTING_POLICY,
    DEFAULT_SHOT_DURATION_MAX_SEC,
    DEFAULT_SHOT_DURATION_MIN_SEC,
    DEFAULT_VOICE_POLICY,
)
from backend.app.services import storyboard_settings as settings_service
from backend.app.services import storyboard_snapshot as snapshot_service


class StoryboardDomainError(ValueError):
    pass


class StoryboardConflictError(Exception):
    """Optimistic concurrency, protected-history, or reference conflicts (HTTP 409)."""

    pass


def _story_or_error(db: Session, story_id: UUID) -> Story:
    story = db.get(Story, story_id)
    if story is None:
        raise StoryboardDomainError("Story not found.")
    return story


def mark_story_draft(db: Session, story_id: UUID) -> Story:
    story = _story_or_error(db, story_id)
    story.approval_state = "draft"
    story.updated_at = datetime.utcnow()
    return story


def _lock_story_for_mutation(db: Session, story_id: UUID) -> Story:
    story = db.scalar(
        select(Story)
        .where(Story.id == story_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if story is None:
        raise StoryboardDomainError("Story not found.")
    return story


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _datetimes_match(left: datetime, right: datetime) -> bool:
    return _as_naive_utc(left) == _as_naive_utc(right)


def create_story(db: Session, payload: StoryCreate) -> Story:
    from backend.app.db.base import Project

    if db.get(Project, payload.project_id) is None:
        raise StoryboardDomainError("Project not found.")
    story = Story(**payload.model_dump())
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


def update_story(db: Session, story_id: UUID, payload: StoryUpdate) -> Story:
    story = _lock_story_for_mutation(db, story_id)
    data = payload.model_dump(exclude_unset=True)
    expected_updated_at = data.pop("expected_updated_at", None)
    expected_revision = data.pop("expected_revision", None)

    if expected_updated_at is not None and not _datetimes_match(story.updated_at, expected_updated_at):
        raise StoryboardConflictError("Stale story revision: expected_updated_at does not match.")

    if expected_revision is not None:
        current = snapshot_service.current_revision(db, story_id)
        if current != expected_revision:
            raise StoryboardConflictError("Stale story revision: expected_revision does not match.")

    for field, value in data.items():
        setattr(story, field, value)
    if data:
        story.approval_state = "draft"
    db.commit()
    db.refresh(story)
    return story


def create_character(db: Session, story_id: UUID, payload: CharacterCreate) -> Character:
    _lock_story_for_mutation(db, story_id)
    character = Character(story_id=story_id, **payload.model_dump())
    db.add(character)
    mark_story_draft(db, story_id)
    db.commit()
    db.refresh(character)
    return character


def update_character(db: Session, character_id: UUID, payload: CharacterUpdate) -> Character:
    character = db.get(Character, character_id)
    if character is None or character.archived_at is not None:
        raise StoryboardDomainError("Character not found.")
    _lock_story_for_mutation(db, character.story_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(character, field, value)
    mark_story_draft(db, character.story_id)
    db.commit()
    db.refresh(character)
    return character


def create_voice_profile(db: Session, story_id: UUID, payload: VoiceProfileCreate) -> VoiceProfile:
    _lock_story_for_mutation(db, story_id)
    if payload.character_id:
        character = db.get(Character, payload.character_id)
        if character is None or character.story_id != story_id:
            raise StoryboardDomainError("Voice profile character must belong to the story.")
    voice = VoiceProfile(story_id=story_id, **payload.model_dump())
    db.add(voice)
    mark_story_draft(db, story_id)
    db.commit()
    db.refresh(voice)
    return voice


def create_chapter(db: Session, story_id: UUID, payload: ChapterCreate) -> Chapter:
    _lock_story_for_mutation(db, story_id)
    chapter = Chapter(story_id=story_id, **payload.model_dump())
    db.add(chapter)
    mark_story_draft(db, story_id)
    db.commit()
    db.refresh(chapter)
    return chapter


def update_chapter(db: Session, chapter_id: UUID, payload: ChapterUpdate) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.archived_at is not None:
        raise StoryboardDomainError("Chapter not found.")
    _lock_story_for_mutation(db, chapter.story_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, field, value)
    mark_story_draft(db, chapter.story_id)
    db.commit()
    db.refresh(chapter)
    return chapter


def create_scene(db: Session, chapter_id: UUID, payload: SceneCreate) -> Scene:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.archived_at is not None:
        raise StoryboardDomainError("Chapter not found.")
    _lock_story_for_mutation(db, chapter.story_id)
    scene = Scene(chapter_id=chapter_id, **payload.model_dump())
    db.add(scene)
    mark_story_draft(db, chapter.story_id)
    db.commit()
    db.refresh(scene)
    return scene


def update_scene(db: Session, scene_id: UUID, payload: SceneUpdate) -> Scene:
    scene = db.get(Scene, scene_id)
    if scene is None or scene.archived_at is not None:
        raise StoryboardDomainError("Scene not found.")
    chapter = db.get(Chapter, scene.chapter_id)
    if chapter is None or chapter.archived_at is not None:
        raise StoryboardDomainError("Chapter not found.")
    _lock_story_for_mutation(db, chapter.story_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scene, field, value)
    mark_story_draft(db, chapter.story_id)
    db.commit()
    db.refresh(scene)
    return scene


def _archive_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    story_id: UUID,
    reason: str | None,
    details: dict | None = None,
) -> None:
    payload = {
        "story_id": str(story_id),
        "reason": (reason or "").strip() or None,
        **(details or {}),
    }
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=f"{entity_type}_archived",
            details=payload,
        )
    )


def _reindex_active_siblings(
    db: Session,
    model: type[Chapter] | type[Scene] | type[Shot],
    parent_field: str,
    parent_id: UUID,
) -> None:
    """Keep active order contiguous while retaining archived rows as tombstones.

    The Phase 1 schema intentionally keeps a non-partial sibling uniqueness
    constraint so archived history cannot be overwritten accidentally.  All
    rows are staged before active rows receive 0..N-1 and archived rows receive
    private negative positions.  The archive audit retains the deleted row's
    original visible position.
    """

    rows = list(
        db.scalars(
            select(model)
            .where(getattr(model, parent_field) == parent_id)
            .order_by(model.order_index, model.id)
        )
    )
    if not rows:
        return
    active = sorted(
        (row for row in rows if row.archived_at is None),
        key=lambda row: (int(row.order_index), str(row.id)),
    )
    archived = sorted(
        (row for row in rows if row.archived_at is not None),
        key=lambda row: str(row.id),
    )
    staging_base = max(abs(int(row.order_index)) for row in rows) + len(rows) + 1
    for offset, row in enumerate(rows):
        row.order_index = staging_base + offset
    db.flush()
    for order_index, row in enumerate(active):
        row.order_index = order_index
    for offset, row in enumerate(archived, start=1):
        row.order_index = -offset
    db.flush()


def _approved_shot_tree_conflicts(db: Session, shots: list[Shot]) -> list[str]:
    conflicts = [f"approved shot {shot.id}" for shot in shots if shot.approval_state == "approved"]
    shot_ids = [shot.id for shot in shots]
    if not shot_ids:
        return conflicts
    approved_narrations = list(
        db.scalars(
            select(ShotNarration).where(
                ShotNarration.shot_id.in_(shot_ids),
                ShotNarration.approval_state == "approved",
            )
        )
    )
    approved_packages = list(
        db.scalars(
            select(ShotPromptPackage).where(
                ShotPromptPackage.shot_id.in_(shot_ids),
                ShotPromptPackage.approval_state == "approved",
            )
        )
    )
    approved_recommendations = list(
        db.scalars(
            select(ShotModelRecommendation).where(
                ShotModelRecommendation.shot_id.in_(shot_ids),
                ShotModelRecommendation.approval_state == "approved",
            )
        )
    )
    conflicts.extend(f"approved narration {row.id}" for row in approved_narrations)
    conflicts.extend(f"approved prompt package {row.id}" for row in approved_packages)
    conflicts.extend(f"approved model recommendation {row.id}" for row in approved_recommendations)
    return conflicts


def _external_continuity_dependents(db: Session, shot_ids: set[UUID]) -> list[UUID]:
    if not shot_ids:
        return []
    return list(
        db.scalars(
            select(Shot.id)
            .join(Scene, Shot.scene_id == Scene.id)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .where(
                Shot.archived_at.is_(None),
                Scene.archived_at.is_(None),
                Chapter.archived_at.is_(None),
                Shot.id.not_in(shot_ids),
                Shot.continuity_source_shot_id.in_(shot_ids),
            )
            .order_by(Shot.id)
        )
    )


def _preflight_hierarchy_archive(
    db: Session,
    *,
    entity_label: str,
    approved_nodes: list[Chapter | Scene],
    shots: list[Shot],
) -> None:
    conflicts = [
        f"approved {type(row).__name__.lower()} {row.id}"
        for row in approved_nodes
        if row.approval_state == "approved"
    ]
    conflicts.extend(_approved_shot_tree_conflicts(db, shots))
    dependents = _external_continuity_dependents(db, {shot.id for shot in shots})
    if dependents:
        conflicts.append(
            "continuity source for active shot(s) " + ", ".join(str(item) for item in dependents)
        )
    if conflicts:
        raise StoryboardConflictError(
            f"Cannot archive {entity_label}; protected or referenced records remain: "
            + "; ".join(conflicts)
            + "."
        )


def archive_chapter(
    db: Session,
    chapter_id: UUID,
    *,
    reason: str | None = None,
) -> None:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.archived_at is not None:
        raise StoryboardDomainError("Chapter not found.")
    story = _lock_story_for_mutation(db, chapter.story_id)
    scenes = list(db.scalars(select(Scene).where(Scene.chapter_id == chapter.id)))
    scene_ids = [scene.id for scene in scenes]
    active_scenes = [scene for scene in scenes if scene.archived_at is None]
    active_shots = list(
        db.scalars(
            select(Shot).where(
                Shot.scene_id.in_(scene_ids) if scene_ids else False,
                Shot.archived_at.is_(None),
            )
        )
    )
    _preflight_hierarchy_archive(
        db,
        entity_label=f"chapter {chapter.id}",
        approved_nodes=[chapter, *active_scenes],
        shots=active_shots,
    )

    original_order = int(chapter.order_index)
    now = datetime.utcnow()
    try:
        chapter.archived_at = now
        chapter.updated_at = now
        for scene in active_scenes:
            scene.archived_at = now
            scene.updated_at = now
        for shot in active_shots:
            shot.archived_at = now
            shot.updated_at = now
        _reindex_active_siblings(db, Chapter, "story_id", story.id)
        mark_story_draft(db, story.id)
        _archive_audit(
            db,
            entity_type="chapter",
            entity_id=chapter.id,
            story_id=story.id,
            reason=reason,
            details={
                "original_order_index": original_order,
                "archived_scene_ids": [str(scene.id) for scene in active_scenes],
                "archived_shot_ids": [str(shot.id) for shot in active_shots],
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def archive_scene(
    db: Session,
    scene_id: UUID,
    *,
    reason: str | None = None,
) -> None:
    scene = db.get(Scene, scene_id)
    if scene is None or scene.archived_at is not None:
        raise StoryboardDomainError("Scene not found.")
    chapter = db.get(Chapter, scene.chapter_id)
    if chapter is None or chapter.archived_at is not None:
        raise StoryboardDomainError("Chapter not found.")
    story = _lock_story_for_mutation(db, chapter.story_id)
    active_shots = list(
        db.scalars(
            select(Shot).where(Shot.scene_id == scene.id, Shot.archived_at.is_(None))
        )
    )
    _preflight_hierarchy_archive(
        db,
        entity_label=f"scene {scene.id}",
        approved_nodes=[scene],
        shots=active_shots,
    )

    original_order = int(scene.order_index)
    now = datetime.utcnow()
    try:
        scene.archived_at = now
        scene.updated_at = now
        for shot in active_shots:
            shot.archived_at = now
            shot.updated_at = now
        _reindex_active_siblings(db, Scene, "chapter_id", chapter.id)
        mark_story_draft(db, story.id)
        _archive_audit(
            db,
            entity_type="scene",
            entity_id=scene.id,
            story_id=story.id,
            reason=reason,
            details={
                "original_order_index": original_order,
                "chapter_id": str(chapter.id),
                "archived_shot_ids": [str(shot.id) for shot in active_shots],
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def archive_shot(
    db: Session,
    shot_id: UUID,
    *,
    reason: str | None = None,
) -> None:
    shot, scene, chapter, story = _active_shot_context(db, shot_id)
    story = _lock_story_for_mutation(db, story.id)
    _preflight_hierarchy_archive(
        db,
        entity_label=f"shot {shot.id}",
        approved_nodes=[],
        shots=[shot],
    )

    original_order = int(shot.order_index)
    now = datetime.utcnow()
    try:
        shot.archived_at = now
        shot.updated_at = now
        _reindex_active_siblings(db, Shot, "scene_id", scene.id)
        mark_story_draft(db, story.id)
        _archive_audit(
            db,
            entity_type="shot",
            entity_id=shot.id,
            story_id=story.id,
            reason=reason,
            details={
                "original_order_index": original_order,
                "scene_id": str(scene.id),
                "chapter_id": str(chapter.id),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def archive_character(
    db: Session,
    character_id: UUID,
    *,
    reason: str | None = None,
) -> None:
    character = db.get(Character, character_id)
    if character is None or character.archived_at is not None:
        raise StoryboardDomainError("Character not found.")
    story = _lock_story_for_mutation(db, character.story_id)
    conflicts: list[str] = []
    if character.approval_state == "approved":
        conflicts.append("character is approved")
    active_shot_links = list(
        db.scalars(
            select(ShotCharacter.shot_id)
            .join(Shot, ShotCharacter.shot_id == Shot.id)
            .join(Scene, Shot.scene_id == Scene.id)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .where(
                ShotCharacter.character_id == character.id,
                Shot.archived_at.is_(None),
                Scene.archived_at.is_(None),
                Chapter.archived_at.is_(None),
            )
        )
    )
    if active_shot_links:
        conflicts.append(
            "linked to active shot(s) " + ", ".join(str(item) for item in active_shot_links)
        )
    active_voice_links = list(
        db.scalars(
            select(VoiceProfile.id).where(
                VoiceProfile.story_id == story.id,
                VoiceProfile.character_id == character.id,
                VoiceProfile.archived_at.is_(None),
            )
        )
    )
    if active_voice_links:
        conflicts.append(
            "referenced by active voice profile(s) "
            + ", ".join(str(item) for item in active_voice_links)
        )
    reference_links = list(
        db.scalars(
            select(CharacterReferenceAsset.id).where(
                CharacterReferenceAsset.character_id == character.id
            )
        )
    )
    if reference_links:
        conflicts.append(
            "owns character reference link(s) "
            + ", ".join(str(item) for item in reference_links)
        )
    if conflicts:
        raise StoryboardConflictError(
            f"Cannot archive character {character.id}; " + "; ".join(conflicts) + "."
        )

    now = datetime.utcnow()
    try:
        character.archived_at = now
        character.updated_at = now
        mark_story_draft(db, story.id)
        _archive_audit(
            db,
            entity_type="character",
            entity_id=character.id,
            story_id=story.id,
            reason=reason,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def _story_for_shot(db: Session, shot_id: UUID) -> UUID | None:
    return db.scalar(
        select(Chapter.story_id)
        .join(Scene, Scene.chapter_id == Chapter.id)
        .join(Shot, Shot.scene_id == Scene.id)
        .where(Shot.id == shot_id)
    )


def _active_scene_context(db: Session, scene_id: UUID) -> tuple[Scene, Chapter, Story]:
    scene = db.get(Scene, scene_id)
    if scene is None or scene.archived_at is not None:
        raise StoryboardDomainError("Scene not found.")
    chapter = db.get(Chapter, scene.chapter_id)
    if chapter is None or chapter.archived_at is not None:
        raise StoryboardDomainError("Chapter not found.")
    return scene, chapter, _story_or_error(db, chapter.story_id)


def _active_shot_context(db: Session, shot_id: UUID) -> tuple[Shot, Scene, Chapter, Story]:
    shot = db.get(Shot, shot_id)
    if shot is None or shot.archived_at is not None:
        raise StoryboardDomainError("Shot not found.")
    scene, chapter, story = _active_scene_context(db, shot.scene_id)
    return shot, scene, chapter, story


def _canonical_position(db: Session, shot_id: UUID) -> tuple[int, int, int] | None:
    return db.execute(
        select(Chapter.order_index, Scene.order_index, Shot.order_index)
        .join(Scene, Scene.chapter_id == Chapter.id)
        .join(Shot, Shot.scene_id == Scene.id)
        .where(Shot.id == shot_id)
    ).one_or_none()


def _validate_continuity(db: Session, shot: Shot, source_id: UUID | None) -> None:
    if source_id is None:
        return
    if source_id == shot.id:
        raise StoryboardDomainError("A shot cannot use itself as its continuity source.")
    _, _, _, target_story = _active_shot_context(db, shot.id)
    _, _, _, source_story = _active_shot_context(db, source_id)
    if target_story.id != source_story.id:
        raise StoryboardDomainError("Continuity source must belong to the same story.")
    source_pos, target_pos = _canonical_position(db, source_id), _canonical_position(db, shot.id)
    if source_pos is None or target_pos is None or source_pos >= target_pos:
        raise StoryboardDomainError("Continuity source must precede its target shot.")
    visited: set[UUID] = {shot.id}
    current = db.get(Shot, source_id)
    while current:
        _active_shot_context(db, current.id)
        if current.id in visited:
            raise StoryboardDomainError("Continuity links may not form a cycle.")
        visited.add(current.id)
        if current.continuity_source_shot_id is None:
            break
        current = db.get(Shot, current.continuity_source_shot_id)


def _enforce_shot_duration_policy(
    duration_sec: float,
    override_reason: str | None,
    min_sec: float,
    max_sec: float,
) -> None:
    if min_sec <= duration_sec <= max_sec:
        return
    if not (override_reason or "").strip():
        raise StoryboardDomainError(
            f"Shots outside {min_sec:g}–{max_sec:g} seconds require a duration override reason."
        )


def _project_shot_bounds(db: Session, scene_id: UUID) -> tuple[float, float]:
    story_id = db.scalar(
        select(Chapter.story_id).join(Scene, Scene.chapter_id == Chapter.id).where(Scene.id == scene_id)
    )
    if story_id is None:
        return DEFAULT_SHOT_DURATION_MIN_SEC, DEFAULT_SHOT_DURATION_MAX_SEC
    story = db.get(Story, story_id)
    if story is None:
        return DEFAULT_SHOT_DURATION_MIN_SEC, DEFAULT_SHOT_DURATION_MAX_SEC
    settings = settings_service.get_settings_row(db, story.project_id)
    if settings is None:
        return DEFAULT_SHOT_DURATION_MIN_SEC, DEFAULT_SHOT_DURATION_MAX_SEC
    return float(settings.shot_duration_min_sec), float(settings.shot_duration_max_sec)


def create_shot(db: Session, scene_id: UUID, payload: ShotCreate) -> Shot:
    scene, _, story = _active_scene_context(db, scene_id)
    story = _lock_story_for_mutation(db, story.id)
    min_sec, max_sec = _project_shot_bounds(db, scene_id)
    _enforce_shot_duration_policy(
        payload.duration_sec, payload.duration_override_reason, min_sec, max_sec
    )
    shot = Shot(scene_id=scene_id, **payload.model_dump())
    db.add(shot)
    db.flush()
    _validate_continuity(db, shot, payload.continuity_source_shot_id)
    mark_story_draft(db, story.id)
    db.commit()
    db.refresh(shot)
    return shot


def update_shot(db: Session, shot_id: UUID, payload: ShotCreate) -> Shot:
    shot, _, _, story = _active_shot_context(db, shot_id)
    story = _lock_story_for_mutation(db, story.id)
    min_sec, max_sec = _project_shot_bounds(db, shot.scene_id)
    _enforce_shot_duration_policy(
        payload.duration_sec, payload.duration_override_reason, min_sec, max_sec
    )
    for field, value in payload.model_dump().items():
        setattr(shot, field, value)
    db.flush()
    _validate_continuity(db, shot, shot.continuity_source_shot_id)
    mark_story_draft(db, story.id)
    db.commit()
    db.refresh(shot)
    return shot


def patch_shot(db: Session, shot_id: UUID, payload: ShotUpdate) -> Shot:
    shot, _, _, story = _active_shot_context(db, shot_id)
    story = _lock_story_for_mutation(db, story.id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return shot
    if "approval_state" in data and hasattr(data["approval_state"], "value"):
        data["approval_state"] = data["approval_state"].value

    duration = float(data.get("duration_sec", shot.duration_sec))
    override_reason = data.get("duration_override_reason", shot.duration_override_reason)
    min_sec, max_sec = _project_shot_bounds(db, shot.scene_id)
    _enforce_shot_duration_policy(duration, override_reason, min_sec, max_sec)

    if "order_index" in data and data["order_index"] != shot.order_index:
        collision = db.scalar(
            select(Shot.id).where(
                Shot.scene_id == shot.scene_id,
                Shot.archived_at.is_(None),
                Shot.order_index == data["order_index"],
                Shot.id != shot.id,
            )
        )
        if collision is not None:
            raise StoryboardDomainError(
                "Shot order_index is already occupied; use the reorder endpoint."
            )

    if data.get("continuity_source_type") == "none" and "continuity_source_shot_id" not in data:
        data["continuity_source_shot_id"] = None
    continuity_source_id = data.get(
        "continuity_source_shot_id", shot.continuity_source_shot_id
    )
    _validate_continuity(db, shot, continuity_source_id)

    production_status = data.get("production_status", shot.production_status)
    blocked_reason = data.get("blocked_reason", shot.blocked_reason)
    if production_status == "blocked" and not (blocked_reason or "").strip():
        raise StoryboardDomainError("Blocked shots require a blocked_reason.")
    if production_status != "blocked":
        data["blocked_reason"] = None

    try:
        for field, value in data.items():
            setattr(shot, field, value)
        db.flush()
        _validate_continuity(db, shot, shot.continuity_source_shot_id)
        mark_story_draft(db, story.id)
        db.commit()
        db.refresh(shot)
        return shot
    except Exception:
        db.rollback()
        raise


def _character_for_shot_story(db: Session, character_id: UUID, story_id: UUID) -> Character:
    character = db.get(Character, character_id)
    if (
        character is None
        or character.archived_at is not None
        or character.story_id != story_id
    ):
        raise StoryboardDomainError(
            "Shot character must be active and belong to the same story."
        )
    return character


def list_shot_characters(db: Session, shot_id: UUID) -> list[ShotCharacter]:
    _, _, _, story = _active_shot_context(db, shot_id)
    rows = list(
        db.scalars(
            select(ShotCharacter)
            .where(ShotCharacter.shot_id == shot_id)
            .order_by(ShotCharacter.order_index, ShotCharacter.character_id)
        )
    )
    for row in rows:
        _character_for_shot_story(db, row.character_id, story.id)
    return rows


def replace_shot_characters(
    db: Session, shot_id: UUID, links: list[ShotCharacterLinkCreate]
) -> list[ShotCharacter]:
    _, _, _, story = _active_shot_context(db, shot_id)
    story = _lock_story_for_mutation(db, story.id)
    for link in links:
        _character_for_shot_story(db, link.character_id, story.id)

    existing = list(
        db.scalars(select(ShotCharacter).where(ShotCharacter.shot_id == shot_id))
    )
    for row in existing:
        db.delete(row)
    db.flush()
    for link in links:
        db.add(ShotCharacter(shot_id=shot_id, **link.model_dump()))
    mark_story_draft(db, story.id)
    db.commit()
    return list_shot_characters(db, shot_id)


def create_shot_character_link(
    db: Session, shot_id: UUID, link: ShotCharacterLinkCreate
) -> ShotCharacter:
    _, _, _, story = _active_shot_context(db, shot_id)
    story = _lock_story_for_mutation(db, story.id)
    _character_for_shot_story(db, link.character_id, story.id)
    existing = db.get(ShotCharacter, (shot_id, link.character_id))
    if existing is not None:
        raise StoryboardDomainError("Character is already linked to this shot.")
    order_collision = db.scalar(
        select(ShotCharacter.character_id).where(
            ShotCharacter.shot_id == shot_id,
            ShotCharacter.order_index == link.order_index,
        )
    )
    if order_collision is not None:
        raise StoryboardDomainError("Shot character order_index is already occupied.")
    row = ShotCharacter(shot_id=shot_id, **link.model_dump())
    db.add(row)
    mark_story_draft(db, story.id)
    db.commit()
    return row


def delete_shot_character_link(db: Session, shot_id: UUID, character_id: UUID) -> None:
    _, _, _, story = _active_shot_context(db, shot_id)
    story = _lock_story_for_mutation(db, story.id)
    _character_for_shot_story(db, character_id, story.id)
    row = db.get(ShotCharacter, (shot_id, character_id))
    if row is None:
        raise StoryboardDomainError("Shot character link not found.")
    db.delete(row)
    mark_story_draft(db, story.id)
    db.commit()


def reorder(
    db: Session,
    model: type[Chapter] | type[Scene] | type[Shot],
    parent_field: str,
    parent_id: UUID,
    ordered_ids: list[UUID],
) -> None:
    if model is Chapter and parent_field == "story_id":
        story = _lock_story_for_mutation(db, parent_id)
    elif model is Scene and parent_field == "chapter_id":
        chapter = db.get(Chapter, parent_id)
        if chapter is None or chapter.archived_at is not None:
            raise StoryboardDomainError("Chapter not found.")
        story = _lock_story_for_mutation(db, chapter.story_id)
    elif model is Shot and parent_field == "scene_id":
        _, _, story = _active_scene_context(db, parent_id)
        story = _lock_story_for_mutation(db, story.id)
    else:
        raise StoryboardDomainError("Unsupported hierarchy reorder target.")

    all_rows = list(
        db.scalars(
            select(model)
            .where(getattr(model, parent_field) == parent_id)
            .order_by(model.order_index)
        )
    )
    rows = [row for row in all_rows if row.archived_at is None]
    active_ids = {row.id for row in rows}
    if active_ids != set(ordered_ids) or len(ordered_ids) != len(rows):
        raise StoryboardDomainError(
            "Reorder payload must contain every active sibling exactly once; "
            "archived or mismatched IDs are not allowed."
        )

    # Preserve the active rows' existing slots. This avoids mutating archived
    # siblings while satisfying the non-partial unique order constraints.
    target_positions = sorted(int(row.order_index) for row in rows)
    highest_position = max((int(row.order_index) for row in all_rows), default=-1)
    staging_base = highest_position + len(rows) + 1
    try:
        for position, row in enumerate(rows):
            row.order_index = staging_base + position
        db.flush()
        by_id = {row.id: row for row in rows}
        for position, item_id in zip(target_positions, ordered_ids, strict=True):
            by_id[item_id].order_index = position
        db.flush()
        active_story_shots = list(
            db.scalars(
                select(Shot)
                .join(Scene, Shot.scene_id == Scene.id)
                .join(Chapter, Scene.chapter_id == Chapter.id)
                .where(
                    Chapter.story_id == story.id,
                    Chapter.archived_at.is_(None),
                    Scene.archived_at.is_(None),
                    Shot.archived_at.is_(None),
                )
            )
        )
        for active_shot in active_story_shots:
            _validate_continuity(
                db, active_shot, active_shot.continuity_source_shot_id
            )
        mark_story_draft(db, story.id)
        db.commit()
    except Exception:
        db.rollback()
        raise


def aggregate(db: Session, story_id: UUID) -> dict:
    """Public aggregate tree. Existing keys remain compatible; revision fields are additive."""
    story = _story_or_error(db, story_id)
    chapters = list(
        db.scalars(
            select(Chapter)
            .where(Chapter.story_id == story_id, Chapter.archived_at.is_(None))
            .order_by(Chapter.order_index)
        )
    )
    chapter_ids = [chapter.id for chapter in chapters]
    scenes = list(
        db.scalars(
            select(Scene)
            .where(
                Scene.chapter_id.in_(chapter_ids) if chapter_ids else False,
                Scene.archived_at.is_(None),
            )
            .order_by(Scene.order_index)
        )
    )
    scene_ids = [scene.id for scene in scenes]
    shots = list(
        db.scalars(
            select(Shot)
            .where(
                Shot.scene_id.in_(scene_ids) if scene_ids else False,
                Shot.archived_at.is_(None),
            )
            .order_by(Shot.order_index)
        )
    )
    narrations = {
        item.shot_id: item
        for item in db.scalars(
            select(ShotNarration).where(ShotNarration.shot_id.in_([s.id for s in shots] or [None]))
        )
    }
    scene_payload = {
        scene.id: {
            "id": str(scene.id),
            "order_index": scene.order_index,
            "title": scene.title,
            "summary": scene.summary,
            "duration_sec": 0.0,
            "shots": [],
        }
        for scene in scenes
    }
    chapters_payload = {
        chapter.id: {
            "id": str(chapter.id),
            "order_index": chapter.order_index,
            "title": chapter.title,
            "summary": chapter.summary,
            "duration_sec": 0.0,
            "scenes": [],
        }
        for chapter in chapters
    }
    for scene in scenes:
        chapters_payload[scene.chapter_id]["scenes"].append(scene_payload[scene.id])
    for shot in shots:
        item = {
            "id": str(shot.id),
            "order_index": shot.order_index,
            "display_label": chr(65 + shot.order_index) if shot.order_index < 26 else str(shot.order_index + 1),
            "title": shot.title,
            "duration_sec": float(shot.duration_sec),
            "duration_override_reason": shot.duration_override_reason,
            "visual_description": shot.visual_description,
            "approval_state": shot.approval_state,
            "production_status": shot.production_status,
            "blocked_reason": shot.blocked_reason,
            "continuity_source_shot_id": str(shot.continuity_source_shot_id)
            if shot.continuity_source_shot_id
            else None,
            "narration": narrations.get(shot.id).narration_text if shot.id in narrations else None,
        }
        scene_payload[shot.scene_id]["shots"].append(item)
        scene_payload[shot.scene_id]["duration_sec"] += float(shot.duration_sec)
    for chapter in chapters:
        for scene in chapters_payload[chapter.id]["scenes"]:
            chapters_payload[chapter.id]["duration_sec"] += scene["duration_sec"]

    snapshot, content_hash = snapshot_service.build_snapshot_with_hash(db, story_id)
    planned = float(snapshot["totals"]["planned_duration_sec"])
    target = float(story.target_duration_sec)

    return {
        "story": {
            "id": str(story.id),
            "project_id": str(story.project_id),
            "title": story.title,
            "base_story": story.base_story,
            "target_duration_sec": target,
            "approval_state": story.approval_state,
        },
        "chapters": list(chapters_payload.values()),
        "characters": [
            {
                "id": str(c.id),
                "name": c.name,
                "role": c.role,
                "approval_state": c.approval_state,
            }
            for c in db.scalars(
                select(Character).where(
                    Character.story_id == story_id, Character.archived_at.is_(None)
                )
            )
        ],
        "voices": [
            {
                "id": str(v.id),
                "name": v.name,
                "source_type": v.source_type,
                "consent_confirmed": v.consent_confirmed,
                "approval_state": v.approval_state,
            }
            for v in db.scalars(
                select(VoiceProfile).where(
                    VoiceProfile.story_id == story_id, VoiceProfile.archived_at.is_(None)
                )
            )
        ],
        # Additive Phase 1 fields (safe for existing clients that ignore unknown keys).
        "revision": content_hash,
        "content_hash": content_hash,
        "planned_duration_sec": planned,
        "discrepancy_sec": round(planned - target, 4),
        "active_storyboard_version_id": str(story.active_storyboard_version_id)
        if story.active_storyboard_version_id
        else None,
    }


def _policy_bool(policy: dict, key: str, default: bool) -> bool:
    value = policy.get(key, default)
    return bool(value) if value is not None else default


def _voice_is_placeholder_or_manual(voice: VoiceProfile) -> bool:
    setup = (voice.setup_mode or "").lower()
    source = (voice.source_type or "").lower()
    return setup in {"placeholder", "manual"} or source in {"placeholder"}


def readiness(db: Session, story_id: UUID, *, _snapshot: dict | None = None) -> dict:
    story = _story_or_error(db, story_id)
    settings = settings_service.get_settings(db, story.project_id)
    approval_policy = {
        **DEFAULT_APPROVAL_POLICY,
        **(settings.approval_policy_json or {}),
    }
    voice_policy = {
        **DEFAULT_VOICE_POLICY,
        **(settings.voice_policy_json or {}),
    }
    continuity_policy = {
        **DEFAULT_CONTINUITY_POLICY,
        **(settings.continuity_policy_json or {}),
    }
    prompting_policy = {
        **DEFAULT_PROMPTING_POLICY,
        **(settings.prompting_policy_json or {}),
    }

    snapshot = _snapshot or snapshot_service.build_canonical_snapshot(db, story_id)
    planned = float(snapshot["totals"]["planned_duration_sec"])
    target = float(story.target_duration_sec)
    discrepancy = round(planned - target, 4)
    reasons: list[dict] = []

    chapter_count = int(snapshot["totals"]["chapter_count"])
    scene_count = int(snapshot["totals"]["scene_count"])
    shot_count = int(snapshot["totals"]["shot_count"])

    if _policy_bool(approval_policy, "require_at_least_one_chapter", True) and chapter_count == 0:
        reasons.append(
            {
                "code": "chapters_missing",
                "message": "At least one chapter is required.",
                "entity_id": None,
                "blocking": True,
            }
        )
    if _policy_bool(approval_policy, "require_at_least_one_scene", True) and scene_count == 0:
        reasons.append(
            {
                "code": "scenes_missing",
                "message": "At least one scene is required.",
                "entity_id": None,
                "blocking": True,
            }
        )
    if _policy_bool(approval_policy, "require_at_least_one_shot", True) and shot_count == 0:
        reasons.append(
            {
                "code": "shots_missing",
                "message": "At least one shot is required.",
                "entity_id": None,
                "blocking": True,
            }
        )

    if _policy_bool(approval_policy, "require_exact_duration", True) and discrepancy != 0:
        reasons.append(
            {
                "code": "duration_mismatch",
                "message": f"Planned duration differs from target by {discrepancy:+g} seconds.",
                "entity_id": None,
                "blocking": True,
            }
        )

    min_sec = float(settings.shot_duration_min_sec)
    max_sec = float(settings.shot_duration_max_sec)
    require_narration = _policy_bool(approval_policy, "require_narration_or_exception", True)
    require_prompt_package = _policy_bool(
        approval_policy, "require_prompt_package_or_exception", True
    )
    require_model_recommendation = _policy_bool(
        approval_policy, "require_model_recommendation_or_exception", True
    )
    prompt_exceptions = approval_policy.get("prompt_package_exceptions") or {}
    recommendation_exceptions = approval_policy.get("model_recommendation_exceptions") or {}
    if not isinstance(prompt_exceptions, dict):
        prompt_exceptions = {}
    if not isinstance(recommendation_exceptions, dict):
        recommendation_exceptions = {}
    block_on_blocked = _policy_bool(approval_policy, "block_on_shot_blocked", True)
    require_starting = _policy_bool(continuity_policy, "require_starting_image_when_flagged", True)
    require_visual = _policy_bool(prompting_policy, "require_visual_description", False)
    require_purpose = _policy_bool(prompting_policy, "require_story_purpose", False)

    for chapter in snapshot["chapters"]:
        for scene in chapter["scenes"]:
            for shot in scene["shots"]:
                duration = float(shot["duration_sec"])
                override = (shot.get("duration_override_reason") or "").strip()
                if not (min_sec <= duration <= max_sec) and not override:
                    reasons.append(
                        {
                            "code": "duration_override_required",
                            "message": (
                                f"Shot {shot['title']} is outside {min_sec:g}–{max_sec:g}s "
                                "and needs a duration override reason."
                            ),
                            "entity_id": shot["id"],
                            "blocking": True,
                        }
                    )

                if require_narration:
                    narration = shot.get("narration")
                    has_text = bool(
                        narration and (narration.get("narration_text") or "").strip()
                    )
                    has_exception = bool(
                        narration and (narration.get("narration_exception_reason") or "").strip()
                    )
                    if not has_text and not has_exception:
                        reasons.append(
                            {
                                "code": "narration_missing",
                                "message": f"Shot {shot['title']} needs narration or an exception.",
                                "entity_id": shot["id"],
                                "blocking": True,
                            }
                        )

                if block_on_blocked and shot.get("production_status") == "blocked":
                    reasons.append(
                        {
                            "code": "shot_blocked",
                            "message": shot.get("blocked_reason")
                            or f"Shot {shot['title']} is blocked.",
                            "entity_id": shot["id"],
                            "blocking": True,
                        }
                    )

                if require_starting and shot.get("starting_image_required"):
                    raw_asset_id = shot.get("starting_image_asset_id")
                    asset = None
                    if raw_asset_id:
                        try:
                            asset = db.get(PlanningMediaAsset, UUID(str(raw_asset_id)))
                        except (TypeError, ValueError):
                            asset = None

                    if asset is None:
                        reasons.append(
                            {
                                "code": "starting_image_missing",
                                "message": f"Shot {shot['title']} requires an existing starting image asset.",
                                "entity_id": shot["id"],
                                "blocking": True,
                            }
                        )
                    elif asset.archived_at is not None:
                        reasons.append(
                            {
                                "code": "starting_image_archived",
                                "message": f"Shot {shot['title']} references an archived starting image asset.",
                                "entity_id": shot["id"],
                                "blocking": True,
                            }
                        )
                    elif asset.project_id != story.project_id:
                        reasons.append(
                            {
                                "code": "starting_image_project_mismatch",
                                "message": f"Shot {shot['title']} references an asset from another project.",
                                "entity_id": shot["id"],
                                "blocking": True,
                            }
                        )
                    elif asset.kind != "starting_image":
                        reasons.append(
                            {
                                "code": "starting_image_kind_invalid",
                                "message": f"Shot {shot['title']} requires an asset of kind starting_image.",
                                "entity_id": shot["id"],
                                "blocking": True,
                            }
                        )
                    elif asset.approval_state != "approved":
                        reasons.append(
                            {
                                "code": "starting_image_not_approved",
                                "message": f"Shot {shot['title']} requires an approved starting image asset.",
                                "entity_id": shot["id"],
                                "blocking": True,
                            }
                        )

                shot_id = str(shot["id"])
                prompt_exception = str(prompt_exceptions.get(shot_id) or "").strip()
                if (
                    require_prompt_package
                    and not shot.get("prompt_packages")
                    and not prompt_exception
                ):
                    reasons.append(
                        {
                            "code": "prompt_package_missing",
                            "message": (
                                f"Shot {shot['title']} needs a prompt package or an "
                                "explicit policy exception."
                            ),
                            "entity_id": shot["id"],
                            "blocking": True,
                        }
                    )

                recommendation_exception = str(
                    recommendation_exceptions.get(shot_id) or ""
                ).strip()
                if (
                    require_model_recommendation
                    and not shot.get("recommendations")
                    and not recommendation_exception
                ):
                    reasons.append(
                        {
                            "code": "model_recommendation_missing",
                            "message": (
                                f"Shot {shot['title']} needs a model/workflow recommendation "
                                "or an explicit policy exception."
                            ),
                            "entity_id": shot["id"],
                            "blocking": True,
                        }
                    )

                if require_visual and not (shot.get("visual_description") or "").strip():
                    reasons.append(
                        {
                            "code": "visual_description_missing",
                            "message": f"Shot {shot['title']} requires a visual description.",
                            "entity_id": shot["id"],
                            "blocking": True,
                        }
                    )

                if require_purpose and not (shot.get("story_purpose") or "").strip():
                    reasons.append(
                        {
                            "code": "story_purpose_missing",
                            "message": f"Shot {shot['title']} requires a story purpose.",
                            "entity_id": shot["id"],
                            "blocking": True,
                        }
                    )

    # Voice gates: placeholder/manual are non-blocking when policy permits.
    voices = list(
        db.scalars(
            select(VoiceProfile).where(
                VoiceProfile.story_id == story_id, VoiceProfile.archived_at.is_(None)
            )
        )
    )
    allow_placeholder = _policy_bool(voice_policy, "allow_placeholder_for_approval", True)
    allow_manual = _policy_bool(voice_policy, "allow_manual_for_approval", True)
    require_consent = bool(settings.require_voice_consent) and _policy_bool(
        voice_policy, "require_consent_when_required", True
    )
    block_unresolved = _policy_bool(voice_policy, "block_unresolved_provider_voices", False)

    for voice in voices:
        setup = (voice.setup_mode or "").lower()
        source = (voice.source_type or "").lower()
        is_placeholder = setup == "placeholder" or source == "placeholder"
        is_manual = setup == "manual"

        if require_consent and voice.consent_required and not voice.consent_confirmed:
            reasons.append(
                {
                    "code": "voice_consent_required",
                    "message": f"Voice profile {voice.name} requires confirmed consent.",
                    "entity_id": str(voice.id),
                    "blocking": True,
                }
            )
            continue

        if is_placeholder and allow_placeholder:
            continue
        if is_manual and allow_manual:
            continue

        if block_unresolved and not _voice_is_placeholder_or_manual(voice):
            unresolved = (
                (voice.provider_configuration_status or "unknown") not in {"ready", "configured"}
                and not (voice.provider_voice_reference or "").strip()
            )
            if unresolved:
                reasons.append(
                    {
                        "code": "voice_unresolved",
                        "message": f"Voice profile {voice.name} is not fully resolved for approval.",
                        "entity_id": str(voice.id),
                        "blocking": True,
                    }
                )

    blocking = [reason for reason in reasons if reason.get("blocking", True)]
    return {
        "ready": not blocking,
        "planned_duration_sec": planned,
        "target_duration_sec": target,
        "discrepancy_sec": discrepancy,
        "reasons": reasons,
    }


def phase_a_snapshot(db: Session, story_id: UUID) -> dict:
    """Revision-aware Phase A payload for frontend clients."""
    story = _story_or_error(db, story_id)
    snapshot, content_hash = snapshot_service.build_snapshot_with_hash(db, story_id)
    status = readiness(db, story_id)
    settings_row = settings_service.get_settings(db, story.project_id)

    return {
        "revision": content_hash,
        "content_hash": content_hash,
        "planned_duration_sec": status["planned_duration_sec"],
        "target_duration_sec": status["target_duration_sec"],
        "discrepancy_sec": status["discrepancy_sec"],
        "story": snapshot["story"],
        "settings": settings_service.settings_public_dict(settings_row),
        "readiness": status,
        "chapters": snapshot["chapters"],
        "characters": snapshot["characters"],
        "voices": snapshot["voice_profiles"],
        "active_storyboard_version_id": story.active_storyboard_version_id,
    }


def _lock_story_for_approval(db: Session, story_id: UUID) -> Story:
    """Serialize approval with domain writes that also update the story row.

    PostgreSQL honors ``FOR UPDATE``. SQLite safely ignores the clause; its
    write serialization is paired with the bounded retry in :func:`approve`.
    ``populate_existing`` prevents a long-lived Session identity-map entry
    from bypassing the freshness guaranteed by the lock query.
    """

    story = db.scalar(
        select(Story)
        .where(Story.id == story_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if story is None:
        raise StoryboardDomainError("Story not found.")
    return story


def _is_retryable_approval_operational_error(error: OperationalError) -> bool:
    original = getattr(error, "orig", error)
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate in {"40001", "40P01"}:  # serialization failure / deadlock
        return True
    message = str(original).lower()
    return any(
        marker in message
        for marker in (
            "database is locked",
            "database table is locked",
            "deadlock detected",
            "could not serialize access",
        )
    )


def _approve_once(
    db: Session,
    story_id: UUID,
    approved_by: str,
    expected_revision: str,
) -> StoryboardVersion:
    story = _lock_story_for_approval(db, story_id)
    snapshot, content_hash = snapshot_service.build_snapshot_with_hash(db, story_id)
    if content_hash != expected_revision:
        raise StoryboardConflictError(
            "Stale production-plan revision: expected_revision does not match."
        )

    # Readiness is evaluated against the exact immutable snapshot that will be
    # versioned, under the same transaction and story-row lock.
    status = readiness(db, story_id, _snapshot=snapshot)
    if not status["ready"]:
        raise StoryboardDomainError("Production plan has blocking readiness issues.")

    # Idempotent: the same currently-approved content hash returns the existing
    # immutable version rather than allocating another version number.
    existing_same = db.scalar(
        select(StoryboardVersion)
        .where(
            StoryboardVersion.story_id == story_id,
            StoryboardVersion.status == "approved",
            StoryboardVersion.content_hash == content_hash,
            StoryboardVersion.superseded_at.is_(None),
        )
        .order_by(StoryboardVersion.version_number.desc())
        .limit(1)
    )
    if existing_same is not None:
        story.active_storyboard_version_id = existing_same.id
        story.approval_state = "approved"
        db.commit()
        db.refresh(existing_same)
        return existing_same

    current = (
        db.scalar(
            select(StoryboardVersion.version_number)
            .where(StoryboardVersion.story_id == story_id)
            .order_by(StoryboardVersion.version_number.desc())
            .limit(1)
        )
        or 0
    )
    now = datetime.utcnow()
    previous_approved = list(
        db.scalars(
            select(StoryboardVersion)
            .where(
                StoryboardVersion.story_id == story_id,
                StoryboardVersion.status == "approved",
                StoryboardVersion.superseded_at.is_(None),
            )
            .order_by(StoryboardVersion.version_number.desc())
        )
    )
    for previous in previous_approved:
        # Never mutate snapshot_json/content_hash; only lifecycle metadata.
        previous.superseded_at = now

    base_version_id = previous_approved[0].id if previous_approved else None
    version_id = uuid4()
    # Approval lifecycle fields are excluded from the content hash, so store
    # the immutable version with its truthful approved state and self pointer.
    snapshot["story"]["approval_state"] = "approved"
    snapshot["story"]["active_storyboard_version_id"] = str(version_id)
    version = StoryboardVersion(
        id=version_id,
        story_id=story_id,
        version_number=current + 1,
        status="approved",
        snapshot_json=snapshot,
        content_hash=content_hash,
        created_by=approved_by,
        approved_by=approved_by,
        approved_at=now,
        base_version_id=base_version_id,
    )
    db.add(version)
    db.flush()
    story.active_storyboard_version_id = version.id
    story.approval_state = "approved"
    db.add(
        AuditLog(
            entity_type="story",
            entity_id=story_id,
            action="storyboard_production_plan_approved",
            details={
                "version_number": current + 1,
                "approved_by": approved_by,
                "content_hash": content_hash,
                "expected_revision": expected_revision,
            },
        )
    )
    db.commit()
    db.refresh(version)
    return version


def approve(
    db: Session,
    story_id: UUID,
    approved_by: str,
    expected_revision: str,
) -> StoryboardVersion:
    """Approve exactly one reviewed revision, transactionally and idempotently."""

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            return _approve_once(db, story_id, approved_by, expected_revision)
        except (StoryboardDomainError, StoryboardConflictError):
            db.rollback()
            raise
        except IntegrityError as error:
            # SQLite cannot honor FOR UPDATE; a racing allocation is resolved
            # by the unique (story_id, version_number) constraint and retry.
            db.rollback()
            if attempt == max_attempts - 1:
                raise StoryboardConflictError(
                    "Concurrent production-plan approval could not be serialized."
                ) from error
        except OperationalError as error:
            db.rollback()
            if not _is_retryable_approval_operational_error(error):
                raise
            if attempt == max_attempts - 1:
                raise StoryboardConflictError(
                    "Concurrent production-plan approval could not be serialized."
                ) from error
        except Exception:
            db.rollback()
            raise
        time.sleep(0.01 * (attempt + 1))

    raise StoryboardConflictError("Concurrent production-plan approval could not be serialized.")


def create_proposal(db: Session, payload: ProposalCreate) -> AIProposalRecord:
    proposal = AIProposalRecord(
        proposal_type=payload.proposal_type,
        payload=payload.payload,
        status="pending_review",
        validation_errors=[],
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def export_csv(db: Session, story_id: UUID) -> str:
    data = aggregate(db, story_id)
    output = StringIO()
    output.write("chapter,scene,shot_id,shot_label,title,duration_sec,narration,approval_state\r\n")
    for chapter in data["chapters"]:
        for scene in chapter["scenes"]:
            for shot in scene["shots"]:
                values = [
                    chapter["title"],
                    scene["title"],
                    shot["id"],
                    shot["display_label"],
                    shot["title"],
                    str(shot["duration_sec"]),
                    shot["narration"] or "",
                    shot["approval_state"],
                ]
                output.write(",".join('"' + str(value).replace('"', '""') + '"' for value in values) + "\r\n")
    return output.getvalue()
