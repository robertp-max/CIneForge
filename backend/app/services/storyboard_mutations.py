"""Non-committing storyboard mutations for atomic proposal apply.

These helpers intentionally never call commit/rollback. Callers own the
transaction boundary (proposal_apply).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    Chapter,
    Character,
    CharacterReferenceAsset,
    Scene,
    Shot,
    ShotCharacter,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
    Story,
    VoiceProfile,
)


class MutationError(ValueError):
    pass


def _now() -> datetime:
    return datetime.utcnow()


def _optional_uuid(value: Any) -> UUID | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def upsert_story_fields(story: Story, proposed: dict[str, Any]) -> None:
    for field in (
        "title",
        "base_story",
        "logline",
        "synopsis",
        "audience",
        "tone",
        "genre",
        "visual_style",
        "point_of_view",
        "production_notes",
    ):
        if field in proposed and proposed[field] is not None:
            setattr(story, field, proposed[field])
    if "target_duration_sec" in proposed and proposed["target_duration_sec"] is not None:
        story.target_duration_sec = proposed["target_duration_sec"]
    story.updated_at = _now()


def upsert_voices(
    db: Session,
    story_id: UUID,
    proposed_voices: list[dict[str, Any]],
) -> dict[str, VoiceProfile]:
    """Create/update voices; preserve identity fields on approved rows."""
    existing = {
        str(row.id): row
        for row in db.scalars(select(VoiceProfile).where(VoiceProfile.story_id == story_id))
    }
    by_client: dict[str, VoiceProfile] = {}
    protected = {
        "provider",
        "provider_voice_reference",
        "setup_mode",
        "source_type",
        "provider_model_id",
        "consent_confirmed",
        "consent_required",
    }
    mutable = {
        "name",
        "language",
        "accent",
        "presentation",
        "tone",
        "speaking_directions",
        "pacing",
        "energy",
        "pronunciation_notes",
        "source_description",
        "consent_notes",
        "usage_notes",
        "recipe_name",
        "recipe_description",
        "design_description",
        "preview_text",
        "gender_presentation",
        "pitch",
        "style",
    }

    for item in proposed_voices:
        client_id = item["client_id"]
        existing_id = item.get("existing_id")
        row = existing.get(str(existing_id)) if existing_id else None
        if row is None:
            row = VoiceProfile(
                id=uuid4(),
                story_id=story_id,
                name=item["name"],
                source_type=item.get("source_type") or "placeholder",
                setup_mode=item.get("setup_mode") or "manual",
            )
            db.add(row)
        else:
            if row.approval_state == "approved":
                for field in protected:
                    if field in item and item[field] != getattr(row, field):
                        raise MutationError(
                            f"Cannot modify approved voice field '{field}' on {row.id}"
                        )
            row.archived_at = None

        for field in mutable:
            if field in item:
                setattr(row, field, item[field])
        if row.approval_state != "approved":
            for field in protected:
                if field in item and item[field] is not None:
                    setattr(row, field, item[field])
            if "source_asset_id" in item:
                row.source_asset_id = item.get("source_asset_id")
        row.updated_at = _now()
        by_client[client_id] = row

    db.flush()
    return by_client


def upsert_characters(
    db: Session,
    story_id: UUID,
    proposed_characters: list[dict[str, Any]],
    voices_by_client: dict[str, VoiceProfile],
) -> dict[str, Character]:
    existing = {
        str(row.id): row
        for row in db.scalars(select(Character).where(Character.story_id == story_id))
    }
    by_client: dict[str, Character] = {}
    fields = (
        "name",
        "role",
        "age_range",
        "physical_description",
        "personality",
        "speaking_style",
        "wardrobe",
        "consistency_prompt",
        "negative_identity_prompt",
        "identity_method",
    )
    for item in proposed_characters:
        client_id = item["client_id"]
        existing_id = item.get("existing_id")
        row = existing.get(str(existing_id)) if existing_id else None
        if row is None:
            row = Character(id=uuid4(), story_id=story_id, name=item["name"])
            db.add(row)
        else:
            row.archived_at = None
        for field in fields:
            if field in item:
                setattr(row, field, item[field])
        voice_client = item.get("assigned_voice_client_id")
        if voice_client:
            voice = voices_by_client.get(voice_client)
            if voice is None:
                raise MutationError(f"Unknown voice client_id '{voice_client}' for character {client_id}")
            if row.assigned_voice_profile_id not in (None, voice.id):
                current_voice = db.get(VoiceProfile, row.assigned_voice_profile_id)
                if current_voice is not None and current_voice.approval_state == "approved":
                    raise MutationError(
                        f"Cannot replace approved voice assignment for character {client_id}"
                    )
            row.assigned_voice_profile_id = voice.id
        row.updated_at = _now()
        by_client[client_id] = row
        db.flush()

        # Replace reference assets when provided.
        if "reference_asset_ids" in item:
            current_refs = list(
                db.scalars(
                    select(CharacterReferenceAsset).where(CharacterReferenceAsset.character_id == row.id)
                )
            )
            for ref in current_refs:
                db.delete(ref)
            db.flush()
            for order_index, asset_id in enumerate(item.get("reference_asset_ids") or []):
                db.add(
                    CharacterReferenceAsset(
                        id=uuid4(),
                        character_id=row.id,
                        asset_id=asset_id if isinstance(asset_id, UUID) else UUID(str(asset_id)),
                        reference_role="identity",
                        approved=False,
                        order_index=order_index,
                    )
                )
    db.flush()
    return by_client


def _archive_missing_chapters(db: Session, story_id: UUID, keep_ids: set[UUID]) -> None:
    rows = list(db.scalars(select(Chapter).where(Chapter.story_id == story_id, Chapter.archived_at.is_(None))))
    now = _now()
    for row in rows:
        if row.id not in keep_ids:
            row.archived_at = now
            row.updated_at = now


def _archive_omitted_identities(
    db: Session,
    story_id: UUID,
    keep_character_ids: set[UUID],
    keep_voice_ids: set[UUID],
) -> None:
    """Soft-archive omitted identities after the replacement graph is final.

    Approved identities and identities still referenced by the active graph are
    never silently removed. The preflight completes before any archive marker
    is written so a conflict leaves the transaction graph untouched.
    """

    omitted_voices = list(
        db.scalars(
            select(VoiceProfile).where(
                VoiceProfile.story_id == story_id,
                VoiceProfile.archived_at.is_(None),
                VoiceProfile.id.not_in(keep_voice_ids) if keep_voice_ids else True,
            )
        )
    )
    omitted_characters = list(
        db.scalars(
            select(Character).where(
                Character.story_id == story_id,
                Character.archived_at.is_(None),
                Character.id.not_in(keep_character_ids) if keep_character_ids else True,
            )
        )
    )

    active_shot_ids = select(Shot.id).join(Scene, Shot.scene_id == Scene.id).join(
        Chapter, Scene.chapter_id == Chapter.id
    ).where(
        Chapter.story_id == story_id,
        Chapter.archived_at.is_(None),
        Scene.archived_at.is_(None),
        Shot.archived_at.is_(None),
    )
    referenced_voice_ids = {
        voice_id
        for voice_id in db.scalars(
            select(Character.assigned_voice_profile_id).where(
                Character.story_id == story_id,
                Character.archived_at.is_(None),
                Character.id.in_(keep_character_ids) if keep_character_ids else False,
                Character.assigned_voice_profile_id.is_not(None),
            )
        )
        if voice_id is not None
    }
    referenced_voice_ids.update(
        voice_id
        for voice_id in db.scalars(
            select(ShotNarration.voice_profile_id).where(
                ShotNarration.shot_id.in_(active_shot_ids),
                ShotNarration.voice_profile_id.is_not(None),
            )
        )
        if voice_id is not None
    )

    referenced_character_ids = set(
        db.scalars(
            select(ShotCharacter.character_id).where(
                ShotCharacter.shot_id.in_(active_shot_ids)
            )
        )
    )
    referenced_character_ids.update(
        character_id
        for character_id in db.scalars(
            select(VoiceProfile.character_id).where(
                VoiceProfile.story_id == story_id,
                VoiceProfile.archived_at.is_(None),
                VoiceProfile.id.in_(keep_voice_ids) if keep_voice_ids else False,
                VoiceProfile.character_id.is_not(None),
            )
        )
        if character_id is not None
    )

    conflicts: list[str] = []
    for voice in omitted_voices:
        if voice.approval_state == "approved":
            conflicts.append(f"approved voice {voice.id}")
        elif voice.id in referenced_voice_ids:
            conflicts.append(f"referenced voice {voice.id}")
    for character in omitted_characters:
        if character.approval_state == "approved":
            conflicts.append(f"approved character {character.id}")
        elif character.id in referenced_character_ids:
            conflicts.append(f"referenced character {character.id}")
    if conflicts:
        raise MutationError(
            "Cannot omit protected identities from full-plan replacement: "
            + ", ".join(conflicts)
        )

    now = _now()
    for voice in omitted_voices:
        voice.archived_at = now
        voice.updated_at = now
    for character in omitted_characters:
        character.archived_at = now
        character.updated_at = now


def upsert_hierarchy(
    db: Session,
    story_id: UUID,
    proposed_chapters: list[dict[str, Any]],
    characters_by_client: dict[str, Character],
    voices_by_client: dict[str, VoiceProfile],
    *,
    replace_identities: bool = False,
) -> dict[str, Shot]:
    """Upsert chapters/scenes/shots and nested narration/prompt/recommendation rows."""
    existing_chapters = {
        str(row.id): row for row in db.scalars(select(Chapter).where(Chapter.story_id == story_id))
    }
    shots_by_client: dict[str, Shot] = {}
    keep_chapter_ids: set[UUID] = set()

    # First pass: create/update chapters, scenes, shots (continuity resolved in second pass).
    for chapter_item in proposed_chapters:
        chapter_existing = chapter_item.get("existing_id")
        chapter = existing_chapters.get(str(chapter_existing)) if chapter_existing else None
        if chapter is None:
            chapter = Chapter(
                id=uuid4(),
                story_id=story_id,
                order_index=chapter_item["order_index"],
                title=chapter_item["title"],
            )
            db.add(chapter)
        else:
            chapter.order_index = chapter_item["order_index"]
            chapter.title = chapter_item["title"]
            chapter.summary = chapter_item.get("summary")
            chapter.archived_at = None
        chapter.updated_at = _now()
        keep_chapter_ids.add(chapter.id)
        db.flush()

        existing_scenes = {
            str(row.id): row for row in db.scalars(select(Scene).where(Scene.chapter_id == chapter.id))
        }
        keep_scene_ids: set[UUID] = set()
        for scene_item in chapter_item.get("scenes") or []:
            scene_existing = scene_item.get("existing_id")
            scene = existing_scenes.get(str(scene_existing)) if scene_existing else None
            if scene is None:
                scene = Scene(
                    id=uuid4(),
                    chapter_id=chapter.id,
                    order_index=scene_item["order_index"],
                    title=scene_item["title"],
                )
                db.add(scene)
            else:
                scene.order_index = scene_item["order_index"]
                scene.title = scene_item["title"]
                scene.summary = scene_item.get("summary")
                scene.narrative_purpose = scene_item.get("narrative_purpose")
                scene.location = scene_item.get("location")
                scene.conflict_or_beat = scene_item.get("conflict_or_beat")
                scene.archived_at = None
            scene.updated_at = _now()
            keep_scene_ids.add(scene.id)
            db.flush()

            existing_shots = {
                str(row.id): row for row in db.scalars(select(Shot).where(Shot.scene_id == scene.id))
            }
            retained_existing_shot_ids = {
                UUID(str(item["existing_id"]))
                for item in (scene_item.get("shots") or [])
                if item.get("existing_id")
                and str(item["existing_id"]) in existing_shots
            }

            # Full-plan replacement semantics apply within retained scenes too:
            # shots omitted from the proposal are soft-archived. Move all
            # existing rows to temporary negative positions before assigning
            # the proposed order so SQLite/PostgreSQL's non-partial sibling
            # uniqueness constraint cannot make a valid replacement collide
            # with an omitted or reordered row.
            existing_shot_rows = list(existing_shots.values())
            temporary_order = min(
                [int(row.order_index) for row in existing_shot_rows] + [0]
            ) - len(existing_shot_rows) - 1
            now = _now()
            for existing_shot in existing_shot_rows:
                existing_shot.order_index = temporary_order
                temporary_order -= 1
                if existing_shot.id in retained_existing_shot_ids:
                    existing_shot.archived_at = None
                else:
                    existing_shot.archived_at = now
                existing_shot.updated_at = now
            db.flush()

            for shot_item in scene_item.get("shots") or []:
                shot_existing = shot_item.get("existing_id")
                shot = existing_shots.get(str(shot_existing)) if shot_existing else None
                if shot is None:
                    shot = Shot(
                        id=uuid4(),
                        scene_id=scene.id,
                        order_index=shot_item["order_index"],
                        title=shot_item["title"],
                        duration_sec=shot_item["duration_sec"],
                    )
                    db.add(shot)
                shot.order_index = shot_item["order_index"]
                shot.title = shot_item["title"]
                shot.duration_sec = shot_item["duration_sec"]
                shot.duration_override_reason = shot_item.get("duration_override_reason")
                shot.story_purpose = shot_item.get("story_purpose")
                shot.visual_description = shot_item.get("visual_description")
                shot.location = shot_item.get("location")
                shot.continuity_source_type = shot_item.get("continuity_source_type") or "none"
                shot.starting_image_required = bool(shot_item.get("starting_image_required") or False)
                shot.starting_image_asset_id = _optional_uuid(
                    shot_item.get("starting_image_asset_id")
                )
                shot.archived_at = None
                shot.updated_at = _now()
                db.flush()
                shots_by_client[shot_item["client_id"]] = shot

                _upsert_shot_characters(db, shot, shot_item.get("characters") or [], characters_by_client)
                _upsert_narration(db, shot, shot_item.get("narration"), voices_by_client)
                _upsert_prompt_package(db, shot, shot_item.get("prompt_package"))
                _upsert_model_recommendations(db, shot, shot_item.get("model_recommendations") or [])

            # Archive scenes removed from proposal (soft via archived_at).
            for scene_id, scene_row in existing_scenes.items():
                if scene_row.id not in keep_scene_ids and scene_row.archived_at is None:
                    scene_row.archived_at = _now()
                    scene_row.updated_at = _now()

    _archive_missing_chapters(db, story_id, keep_chapter_ids)
    db.flush()

    # Second pass: resolve continuity source shot IDs from client IDs.
    for chapter_item in proposed_chapters:
        for scene_item in chapter_item.get("scenes") or []:
            for shot_item in scene_item.get("shots") or []:
                shot = shots_by_client[shot_item["client_id"]]
                source_client = shot_item.get("continuity_source_shot_client_id")
                if source_client:
                    source = shots_by_client.get(source_client)
                    if source is None:
                        raise MutationError(
                            f"Continuity source client_id '{source_client}' not found for shot {shot_item['client_id']}"
                        )
                    if source.id == shot.id:
                        raise MutationError("A shot cannot use itself as continuity source")
                    shot.continuity_source_shot_id = source.id
                else:
                    shot.continuity_source_shot_id = None
                shot.updated_at = _now()
    if replace_identities:
        _archive_omitted_identities(
            db,
            story_id,
            {row.id for row in characters_by_client.values()},
            {row.id for row in voices_by_client.values()},
        )
    db.flush()
    return shots_by_client


def _upsert_shot_characters(
    db: Session,
    shot: Shot,
    links: list[dict[str, Any]],
    characters_by_client: dict[str, Character],
) -> None:
    existing = list(db.scalars(select(ShotCharacter).where(ShotCharacter.shot_id == shot.id)))
    for row in existing:
        db.delete(row)
    db.flush()
    for link in links:
        character = characters_by_client.get(link["character_client_id"])
        if character is None:
            raise MutationError(f"Unknown character client_id '{link['character_client_id']}'")
        db.add(
            ShotCharacter(
                shot_id=shot.id,
                character_id=character.id,
                role_in_shot=link.get("role_in_shot"),
                order_index=int(link.get("order_index") or 0),
                continuity_notes=link.get("continuity_notes"),
            )
        )
    db.flush()


def _upsert_narration(
    db: Session,
    shot: Shot,
    narration: dict[str, Any] | None,
    voices_by_client: dict[str, VoiceProfile],
) -> None:
    if not narration:
        return
    row = db.scalar(select(ShotNarration).where(ShotNarration.shot_id == shot.id))
    if row is None:
        row = ShotNarration(id=uuid4(), shot_id=shot.id)
        db.add(row)
    row.narration_text = narration.get("narration_text")
    row.start_offset_sec = narration.get("start_offset_sec") or 0
    row.expected_duration_sec = narration.get("expected_duration_sec")
    row.narration_exception_reason = narration.get("narration_exception_reason")
    voice_client = narration.get("voice_client_id")
    if voice_client:
        voice = voices_by_client.get(voice_client)
        if voice is None:
            raise MutationError(f"Unknown voice client_id '{voice_client}' for narration")
        row.voice_profile_id = voice.id
    else:
        row.voice_profile_id = None
    row.updated_at = _now()
    db.flush()


def _upsert_prompt_package(db: Session, shot: Shot, package: dict[str, Any] | None) -> None:
    if not package:
        return
    current = db.scalar(
        select(ShotPromptPackage)
        .where(ShotPromptPackage.shot_id == shot.id)
        .order_by(ShotPromptPackage.version.desc())
        .limit(1)
    )
    next_version = (current.version + 1) if current else 1
    row = ShotPromptPackage(
        id=uuid4(),
        shot_id=shot.id,
        version=next_version,
        image_prompt=package.get("image_prompt"),
        video_prompt=package.get("video_prompt"),
        negative_prompt=package.get("negative_prompt"),
        continuity_instructions=package.get("continuity_instructions"),
        style_lock_prompt=package.get("style_lock_prompt"),
        provider_profile_id=_optional_uuid(package.get("provider_profile_id")),
        provider_model_id=package.get("provider_model_id"),
        approval_state="draft",
    )
    db.add(row)
    db.flush()


def _upsert_model_recommendations(
    db: Session,
    shot: Shot,
    recommendations: list[dict[str, Any]],
) -> None:
    existing = list(
        db.scalars(select(ShotModelRecommendation).where(ShotModelRecommendation.shot_id == shot.id))
    )
    for row in existing:
        db.delete(row)
    db.flush()
    for item in recommendations:
        db.add(
            ShotModelRecommendation(
                id=uuid4(),
                shot_id=shot.id,
                recommendation_type=item.get("recommendation_type") or "primary",
                generation_model_variant_id=_optional_uuid(
                    item.get("generation_model_variant_id")
                ),
                workflow_template_id=_optional_uuid(item.get("workflow_template_id")),
                rationale=item.get("rationale"),
                availability_status=item.get("availability_status") or "unknown",
                benchmark_status=item.get("benchmark_status") or "unknown",
                risk_status=item.get("risk_status"),
                approval_state="draft",
            )
        )
    db.flush()


def build_snapshot(
    story: Story,
    voices_by_client: dict[str, VoiceProfile],
    characters_by_client: dict[str, Character],
    shots_by_client: dict[str, Shot],
    proposed_payload: dict[str, Any],
) -> dict[str, Any]:
    """Immutable snapshot JSON for the new storyboard version."""
    return {
        "schema_name": proposed_payload.get("schema_name") or "storyboard_proposal_v1",
        "project_id": str(story.project_id),
        "story": {
            "id": str(story.id),
            "title": story.title,
            "base_story": story.base_story,
            "target_duration_sec": float(story.target_duration_sec),
            "approval_state": story.approval_state,
            "client_id": (proposed_payload.get("story") or {}).get("client_id"),
        },
        "characters": [
            {
                "id": str(characters_by_client[c["client_id"]].id),
                "client_id": c["client_id"],
                "name": c.get("name"),
                "role": c.get("role"),
                "assigned_voice_client_id": c.get("assigned_voice_client_id"),
                "approval_state": characters_by_client[c["client_id"]].approval_state,
            }
            for c in (proposed_payload.get("story") or {}).get("characters") or []
            if c["client_id"] in characters_by_client
        ],
        "voices": [
            {
                "id": str(voices_by_client[v["client_id"]].id),
                "client_id": v["client_id"],
                "name": v.get("name"),
                "source_type": voices_by_client[v["client_id"]].source_type,
                "setup_mode": voices_by_client[v["client_id"]].setup_mode,
                "approval_state": voices_by_client[v["client_id"]].approval_state,
                "provider": voices_by_client[v["client_id"]].provider,
                "provider_voice_reference": voices_by_client[v["client_id"]].provider_voice_reference,
            }
            for v in (proposed_payload.get("story") or {}).get("voices") or []
            if v["client_id"] in voices_by_client
        ],
        "chapters": (proposed_payload.get("story") or {}).get("chapters") or [],
        "shot_id_map": {client_id: str(shot.id) for client_id, shot in shots_by_client.items()},
        "applied_from_proposal": True,
    }
