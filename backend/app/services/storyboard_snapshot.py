"""Deterministic Phase A storyboard snapshots and content hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    Chapter,
    Character,
    Scene,
    Shot,
    ShotCharacter,
    ShotNarration,
    ShotPromptPackage,
    Story,
    VoiceProfile,
)
from backend.app.services import storyboard_settings as settings_service

SNAPSHOT_SCHEMA = "cineforge.storyboard.phase_a.v1"


def canonical_json_dumps(value: Any) -> str:
    """Stable JSON encoding for content hashing."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def sha256_hex(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json_dumps(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _uuid_str(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _load_story_graph(db: Session, story_id: UUID) -> tuple[
    Story,
    list[Chapter],
    list[Scene],
    list[Shot],
    dict[UUID, ShotNarration],
    list[Character],
    list[VoiceProfile],
    list[ShotCharacter],
    dict[UUID, list[ShotPromptPackage]],
]:
    story = db.get(Story, story_id)
    if story is None:
        raise ValueError("Story not found.")

    chapters = list(
        db.scalars(
            select(Chapter)
            .where(Chapter.story_id == story_id, Chapter.archived_at.is_(None))
            .order_by(Chapter.order_index, Chapter.id)
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
            .order_by(Scene.order_index, Scene.id)
        )
    )
    scene_ids = [scene.id for scene in scenes]
    shots = list(
        db.scalars(
            select(Shot)
            .where(Shot.scene_id.in_(scene_ids) if scene_ids else False)
            .order_by(Shot.order_index, Shot.id)
        )
    )
    shot_ids = [shot.id for shot in shots]
    narrations = {
        item.shot_id: item
        for item in db.scalars(
            select(ShotNarration).where(
                ShotNarration.shot_id.in_(shot_ids) if shot_ids else False
            )
        )
    }
    characters = list(
        db.scalars(
            select(Character)
            .where(Character.story_id == story_id)
            .order_by(Character.name, Character.id)
        )
    )
    voices = list(
        db.scalars(
            select(VoiceProfile)
            .where(VoiceProfile.story_id == story_id)
            .order_by(VoiceProfile.name, VoiceProfile.id)
        )
    )
    shot_characters = list(
        db.scalars(
            select(ShotCharacter)
            .where(ShotCharacter.shot_id.in_(shot_ids) if shot_ids else False)
            .order_by(ShotCharacter.shot_id, ShotCharacter.order_index, ShotCharacter.character_id)
        )
    )
    prompt_packages: dict[UUID, list[ShotPromptPackage]] = {shot_id: [] for shot_id in shot_ids}
    for package in db.scalars(
        select(ShotPromptPackage)
        .where(ShotPromptPackage.shot_id.in_(shot_ids) if shot_ids else False)
        .order_by(ShotPromptPackage.shot_id, ShotPromptPackage.version, ShotPromptPackage.id)
    ):
        prompt_packages.setdefault(package.shot_id, []).append(package)

    return (
        story,
        chapters,
        scenes,
        shots,
        narrations,
        characters,
        voices,
        shot_characters,
        prompt_packages,
    )


def build_canonical_snapshot(db: Session, story_id: UUID) -> dict:
    """Build a complete, deterministic production-plan snapshot for hashing and approval."""
    (
        story,
        chapters,
        scenes,
        shots,
        narrations,
        characters,
        voices,
        shot_characters,
        prompt_packages,
    ) = _load_story_graph(db, story_id)

    settings_row = settings_service.get_settings_row(db, story.project_id)
    scenes_by_chapter: dict[UUID, list[Scene]] = {chapter.id: [] for chapter in chapters}
    for scene in scenes:
        scenes_by_chapter.setdefault(scene.chapter_id, []).append(scene)

    shots_by_scene: dict[UUID, list[Shot]] = {scene.id: [] for scene in scenes}
    for shot in shots:
        shots_by_scene.setdefault(shot.scene_id, []).append(shot)

    shot_chars_by_shot: dict[UUID, list[ShotCharacter]] = {shot.id: [] for shot in shots}
    for link in shot_characters:
        shot_chars_by_shot.setdefault(link.shot_id, []).append(link)

    chapters_payload: list[dict] = []
    planned_duration = 0.0

    for chapter in chapters:
        chapter_duration = 0.0
        scenes_payload: list[dict] = []
        for scene in scenes_by_chapter.get(chapter.id, []):
            scene_duration = 0.0
            shots_payload: list[dict] = []
            for shot in shots_by_scene.get(scene.id, []):
                duration = float(shot.duration_sec)
                planned_duration += duration
                scene_duration += duration
                narration = narrations.get(shot.id)
                shots_payload.append(
                    {
                        "id": str(shot.id),
                        "order_index": int(shot.order_index),
                        "title": shot.title,
                        "duration_sec": duration,
                        "duration_override_reason": shot.duration_override_reason,
                        "story_purpose": shot.story_purpose,
                        "visual_description": shot.visual_description,
                        "location": shot.location,
                        "continuity_source_type": shot.continuity_source_type,
                        "continuity_source_shot_id": _uuid_str(shot.continuity_source_shot_id),
                        "starting_image_required": bool(shot.starting_image_required),
                        "starting_image_asset_id": _uuid_str(shot.starting_image_asset_id),
                        "approval_state": shot.approval_state,
                        "production_status": shot.production_status,
                        "blocked_reason": shot.blocked_reason,
                        "characters": [
                            {
                                "character_id": str(link.character_id),
                                "role_in_shot": link.role_in_shot,
                                "order_index": int(link.order_index),
                                "continuity_notes": link.continuity_notes,
                            }
                            for link in shot_chars_by_shot.get(shot.id, [])
                        ],
                        "narration": None
                        if narration is None
                        else {
                            "id": str(narration.id),
                            "voice_profile_id": _uuid_str(narration.voice_profile_id),
                            "narration_text": narration.narration_text,
                            "start_offset_sec": float(narration.start_offset_sec or 0),
                            "expected_duration_sec": _float_or_none(narration.expected_duration_sec),
                            "narration_exception_reason": narration.narration_exception_reason,
                            "approval_state": narration.approval_state,
                        },
                        "prompt_packages": [
                            {
                                "id": str(package.id),
                                "version": int(package.version),
                                "image_prompt": package.image_prompt,
                                "video_prompt": package.video_prompt,
                                "negative_prompt": package.negative_prompt,
                                "continuity_instructions": package.continuity_instructions,
                                "style_lock_prompt": package.style_lock_prompt,
                                "provider_profile_id": _uuid_str(package.provider_profile_id),
                                "provider_model_id": package.provider_model_id,
                                "approval_state": package.approval_state,
                            }
                            for package in prompt_packages.get(shot.id, [])
                        ],
                    }
                )
            chapter_duration += scene_duration
            scenes_payload.append(
                {
                    "id": str(scene.id),
                    "order_index": int(scene.order_index),
                    "title": scene.title,
                    "summary": scene.summary,
                    "narrative_purpose": scene.narrative_purpose,
                    "location": scene.location,
                    "conflict_or_beat": scene.conflict_or_beat,
                    "approval_state": scene.approval_state,
                    "duration_sec": scene_duration,
                    "shots": shots_payload,
                }
            )
        chapters_payload.append(
            {
                "id": str(chapter.id),
                "order_index": int(chapter.order_index),
                "title": chapter.title,
                "summary": chapter.summary,
                "approval_state": chapter.approval_state,
                "duration_sec": chapter_duration,
                "scenes": scenes_payload,
            }
        )

    snapshot = {
        "schema": SNAPSHOT_SCHEMA,
        "story": {
            "id": str(story.id),
            "project_id": str(story.project_id),
            "title": story.title,
            "base_story": story.base_story,
            "logline": story.logline,
            "synopsis": story.synopsis,
            "target_duration_sec": float(story.target_duration_sec),
            "audience": story.audience,
            "tone": story.tone,
            "genre": story.genre,
            "visual_style": story.visual_style,
            "point_of_view": story.point_of_view,
            "production_notes": story.production_notes,
            "approval_state": story.approval_state,
            "default_provider_profile_id": _uuid_str(story.default_provider_profile_id),
            "active_storyboard_version_id": _uuid_str(story.active_storyboard_version_id),
        },
        "settings": settings_service.settings_snapshot_fragment(settings_row),
        "characters": [
            {
                "id": str(character.id),
                "name": character.name,
                "role": character.role,
                "age_range": character.age_range,
                "physical_description": character.physical_description,
                "personality": character.personality,
                "speaking_style": character.speaking_style,
                "wardrobe": character.wardrobe,
                "consistency_prompt": character.consistency_prompt,
                "negative_identity_prompt": character.negative_identity_prompt,
                "identity_method": character.identity_method,
                "approval_state": character.approval_state,
                "assigned_voice_profile_id": _uuid_str(character.assigned_voice_profile_id),
            }
            for character in characters
        ],
        "voice_profiles": [
            {
                "id": str(voice.id),
                "name": voice.name,
                "character_id": _uuid_str(voice.character_id),
                "source_type": voice.source_type,
                "setup_mode": voice.setup_mode,
                "provider": voice.provider,
                "provider_voice_reference": voice.provider_voice_reference,
                "language": voice.language,
                "accent": voice.accent,
                "presentation": voice.presentation,
                "tone": voice.tone,
                "speaking_directions": voice.speaking_directions,
                "pacing": voice.pacing,
                "energy": voice.energy,
                "pronunciation_notes": voice.pronunciation_notes,
                "source_asset_id": _uuid_str(voice.source_asset_id),
                "source_description": voice.source_description,
                "consent_required": bool(voice.consent_required),
                "consent_confirmed": bool(voice.consent_confirmed),
                "consent_notes": voice.consent_notes,
                "usage_notes": voice.usage_notes,
                "approval_state": voice.approval_state,
                "provider_configuration_status": voice.provider_configuration_status,
            }
            for voice in voices
        ],
        "chapters": chapters_payload,
        "totals": {
            "planned_duration_sec": planned_duration,
            "target_duration_sec": float(story.target_duration_sec),
            "chapter_count": len(chapters_payload),
            "scene_count": sum(len(chapter["scenes"]) for chapter in chapters_payload),
            "shot_count": sum(
                len(scene["shots"])
                for chapter in chapters_payload
                for scene in chapter["scenes"]
            ),
        },
    }
    return snapshot


def content_hash_for_snapshot(snapshot: dict) -> str:
    return sha256_hex(snapshot)


def build_snapshot_with_hash(db: Session, story_id: UUID) -> tuple[dict, str]:
    snapshot = build_canonical_snapshot(db, story_id)
    return snapshot, content_hash_for_snapshot(snapshot)


def current_revision(db: Session, story_id: UUID) -> str:
    """Revision token for optimistic concurrency on the live Phase A plan."""
    _, digest = build_snapshot_with_hash(db, story_id)
    return digest
