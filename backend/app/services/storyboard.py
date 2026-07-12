"""Authoritative, non-executing Storyboard Phase A domain services."""

from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    AIProposalRecord,
    AuditLog,
    Chapter,
    Character,
    Scene,
    Shot,
    ShotNarration,
    Story,
    StoryboardVersion,
    VoiceProfile,
)
from backend.app.schemas.storyboard import (
    ChapterCreate,
    CharacterCreate,
    ProposalCreate,
    SceneCreate,
    ShotCreate,
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
    """Optimistic concurrency / stale revision failures (HTTP 409)."""

    pass


def _story_or_error(db: Session, story_id: UUID) -> Story:
    story = db.get(Story, story_id)
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
    story = _story_or_error(db, story_id)
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
    db.commit()
    db.refresh(story)
    return story


def create_character(db: Session, story_id: UUID, payload: CharacterCreate) -> Character:
    _story_or_error(db, story_id)
    character = Character(story_id=story_id, **payload.model_dump())
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


def create_voice_profile(db: Session, story_id: UUID, payload: VoiceProfileCreate) -> VoiceProfile:
    _story_or_error(db, story_id)
    if payload.character_id:
        character = db.get(Character, payload.character_id)
        if character is None or character.story_id != story_id:
            raise StoryboardDomainError("Voice profile character must belong to the story.")
    voice = VoiceProfile(story_id=story_id, **payload.model_dump())
    db.add(voice)
    db.commit()
    db.refresh(voice)
    return voice


def create_chapter(db: Session, story_id: UUID, payload: ChapterCreate) -> Chapter:
    _story_or_error(db, story_id)
    chapter = Chapter(story_id=story_id, **payload.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


def create_scene(db: Session, chapter_id: UUID, payload: SceneCreate) -> Scene:
    if db.get(Chapter, chapter_id) is None:
        raise StoryboardDomainError("Chapter not found.")
    scene = Scene(chapter_id=chapter_id, **payload.model_dump())
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


def _story_for_shot(db: Session, shot_id: UUID) -> UUID | None:
    return db.scalar(
        select(Chapter.story_id)
        .join(Scene, Scene.chapter_id == Chapter.id)
        .join(Shot, Shot.scene_id == Scene.id)
        .where(Shot.id == shot_id)
    )


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
    target_story = _story_for_shot(db, shot.id)
    if target_story != _story_for_shot(db, source_id):
        raise StoryboardDomainError("Continuity source must belong to the same story.")
    source_pos, target_pos = _canonical_position(db, source_id), _canonical_position(db, shot.id)
    if source_pos is None or target_pos is None or source_pos >= target_pos:
        raise StoryboardDomainError("Continuity source must precede its target shot.")
    visited: set[UUID] = {shot.id}
    current = db.get(Shot, source_id)
    while current and current.continuity_source_shot_id:
        if current.id in visited:
            raise StoryboardDomainError("Continuity links may not form a cycle.")
        visited.add(current.id)
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
    if db.get(Scene, scene_id) is None:
        raise StoryboardDomainError("Scene not found.")
    min_sec, max_sec = _project_shot_bounds(db, scene_id)
    _enforce_shot_duration_policy(
        payload.duration_sec, payload.duration_override_reason, min_sec, max_sec
    )
    shot = Shot(scene_id=scene_id, **payload.model_dump())
    db.add(shot)
    db.flush()
    _validate_continuity(db, shot, payload.continuity_source_shot_id)
    db.commit()
    db.refresh(shot)
    return shot


def update_shot(db: Session, shot_id: UUID, payload: ShotCreate) -> Shot:
    shot = db.get(Shot, shot_id)
    if shot is None:
        raise StoryboardDomainError("Shot not found.")
    min_sec, max_sec = _project_shot_bounds(db, shot.scene_id)
    _enforce_shot_duration_policy(
        payload.duration_sec, payload.duration_override_reason, min_sec, max_sec
    )
    for field, value in payload.model_dump().items():
        setattr(shot, field, value)
    db.flush()
    _validate_continuity(db, shot, shot.continuity_source_shot_id)
    db.commit()
    db.refresh(shot)
    return shot


def reorder(
    db: Session,
    model: type[Chapter] | type[Scene] | type[Shot],
    parent_field: str,
    parent_id: UUID,
    ordered_ids: list[UUID],
) -> None:
    rows = list(
        db.scalars(select(model).where(getattr(model, parent_field) == parent_id).order_by(model.order_index))
    )
    if {row.id for row in rows} != set(ordered_ids) or len(ordered_ids) != len(rows):
        raise StoryboardDomainError("Reorder payload must contain every sibling exactly once.")
    try:
        for position, row in enumerate(rows):
            row.order_index = -(position + 1)
        db.flush()
        by_id = {row.id: row for row in rows}
        for position, item_id in enumerate(ordered_ids):
            by_id[item_id].order_index = position
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
            .where(Shot.scene_id.in_(scene_ids) if scene_ids else False)
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
            for c in db.scalars(select(Character).where(Character.story_id == story_id))
        ],
        "voices": [
            {
                "id": str(v.id),
                "name": v.name,
                "source_type": v.source_type,
                "consent_confirmed": v.consent_confirmed,
                "approval_state": v.approval_state,
            }
            for v in db.scalars(select(VoiceProfile).where(VoiceProfile.story_id == story_id))
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


def readiness(db: Session, story_id: UUID) -> dict:
    story = _story_or_error(db, story_id)
    settings = settings_service.get_or_create_settings(db, story.project_id)
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

    snapshot = snapshot_service.build_canonical_snapshot(db, story_id)
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

                if (
                    require_starting
                    and shot.get("starting_image_required")
                    and not shot.get("starting_image_asset_id")
                ):
                    reasons.append(
                        {
                            "code": "starting_image_missing",
                            "message": f"Shot {shot['title']} requires a starting image asset.",
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
    voices = list(db.scalars(select(VoiceProfile).where(VoiceProfile.story_id == story_id)))
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
    settings_row = settings_service.get_or_create_settings(db, story.project_id)

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


def approve(db: Session, story_id: UUID, approved_by: str) -> StoryboardVersion:
    """Immutable, transactional, idempotent production-plan approval."""
    try:
        status = readiness(db, story_id)
        if not status["ready"]:
            raise StoryboardDomainError("Production plan has blocking readiness issues.")

        story = _story_or_error(db, story_id)
        snapshot, content_hash = snapshot_service.build_snapshot_with_hash(db, story_id)

        # Idempotent: same content hash already approved → return existing immutable version.
        existing_same = db.scalar(
            select(StoryboardVersion)
            .where(
                StoryboardVersion.story_id == story_id,
                StoryboardVersion.status == "approved",
                StoryboardVersion.content_hash == content_hash,
            )
            .order_by(StoryboardVersion.version_number.desc())
            .limit(1)
        )
        if existing_same is not None:
            if story.active_storyboard_version_id != existing_same.id:
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
                select(StoryboardVersion).where(
                    StoryboardVersion.story_id == story_id,
                    StoryboardVersion.status == "approved",
                    StoryboardVersion.superseded_at.is_(None),
                )
            )
        )
        for previous in previous_approved:
            # Never mutate snapshot_json/content_hash; only lifecycle metadata.
            previous.superseded_at = now

        base_version_id = previous_approved[0].id if previous_approved else None
        version = StoryboardVersion(
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
                },
            )
        )
        db.commit()
        db.refresh(version)
        return version
    except Exception:
        db.rollback()
        raise


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
