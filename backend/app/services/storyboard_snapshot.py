"""Deterministic Phase A storyboard snapshots and content hashing."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    Chapter,
    Character,
    CharacterReferenceAsset,
    Model,
    ModelVariant,
    PlanningMediaAsset,
    ProviderProfile,
    Scene,
    Shot,
    ShotCharacter,
    ShotModelRecommendation,
    ShotNarration,
    ShotPromptPackage,
    Story,
    TaskProviderAssignment,
    VoicePreview,
    VoiceProfile,
    VoiceRecipe,
    WorkflowTemplate,
)
from backend.app.services import storyboard_settings as settings_service

SNAPSHOT_SCHEMA = "cineforge.storyboard.phase1.v1"


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
            .where(
                Shot.scene_id.in_(scene_ids) if scene_ids else False,
                Shot.archived_at.is_(None),
            )
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
            .where(Character.story_id == story_id, Character.archived_at.is_(None))
            .order_by(Character.name, Character.id)
        )
    )
    voices = list(
        db.scalars(
            select(VoiceProfile)
            .where(VoiceProfile.story_id == story_id, VoiceProfile.archived_at.is_(None))
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

    settings_row = settings_service.get_settings(db, story.project_id)
    character_ids = [character.id for character in characters]
    character_references: dict[UUID, list[CharacterReferenceAsset]] = {
        character_id: [] for character_id in character_ids
    }
    for reference in db.scalars(
        select(CharacterReferenceAsset)
        .where(
            CharacterReferenceAsset.character_id.in_(character_ids)
            if character_ids
            else False
        )
        .order_by(
            CharacterReferenceAsset.character_id,
            CharacterReferenceAsset.order_index,
            CharacterReferenceAsset.id,
        )
    ):
        character_references.setdefault(reference.character_id, []).append(reference)

    voice_ids = [voice.id for voice in voices]
    recipes_by_voice: dict[UUID, list[VoiceRecipe]] = {voice_id: [] for voice_id in voice_ids}
    for recipe in db.scalars(
        select(VoiceRecipe)
        .where(VoiceRecipe.voice_profile_id.in_(voice_ids) if voice_ids else False)
        .order_by(VoiceRecipe.voice_profile_id, VoiceRecipe.created_at, VoiceRecipe.id)
    ):
        recipes_by_voice.setdefault(recipe.voice_profile_id, []).append(recipe)

    selected_preview_ids = [
        voice.selected_preview_id for voice in voices if voice.selected_preview_id is not None
    ]
    selected_previews = {
        preview.id: preview
        for preview in db.scalars(
            select(VoicePreview).where(
                VoicePreview.id.in_(selected_preview_ids) if selected_preview_ids else False
            )
        )
    }

    shot_ids = [shot.id for shot in shots]
    recommendations_by_shot: dict[UUID, list[ShotModelRecommendation]] = {
        shot_id: [] for shot_id in shot_ids
    }
    recommendations = list(
        db.scalars(
            select(ShotModelRecommendation)
            .where(
                ShotModelRecommendation.shot_id.in_(shot_ids) if shot_ids else False
            )
            .order_by(
                ShotModelRecommendation.shot_id,
                ShotModelRecommendation.recommendation_type,
                ShotModelRecommendation.id,
            )
        )
    )
    for recommendation in recommendations:
        recommendations_by_shot.setdefault(recommendation.shot_id, []).append(recommendation)

    task_assignments = list(
        db.scalars(
            select(TaskProviderAssignment)
            .where(TaskProviderAssignment.story_id == story_id)
            .order_by(TaskProviderAssignment.task_type, TaskProviderAssignment.priority, TaskProviderAssignment.id)
        )
    )

    provider_ids = {
        assignment.provider_profile_id for assignment in task_assignments
    }
    if story.default_provider_profile_id is not None:
        provider_ids.add(story.default_provider_profile_id)
    for packages in prompt_packages.values():
        provider_ids.update(
            package.provider_profile_id
            for package in packages
            if package.provider_profile_id is not None
        )
    provider_profiles = list(
        db.scalars(
            select(ProviderProfile)
            .where(ProviderProfile.id.in_(provider_ids) if provider_ids else False)
            .order_by(ProviderProfile.provider_identifier, ProviderProfile.id)
        )
    )

    model_variant_ids = {
        item.generation_model_variant_id
        for item in recommendations
        if item.generation_model_variant_id is not None
    }
    model_variants = list(
        db.scalars(
            select(ModelVariant)
            .where(ModelVariant.id.in_(model_variant_ids) if model_variant_ids else False)
            .order_by(ModelVariant.id)
        )
    )
    model_ids = {variant.model_id for variant in model_variants}
    models = {row.id: row for row in db.scalars(select(Model).where(Model.id.in_(model_ids) if model_ids else False))}

    workflow_ids = {
        item.workflow_template_id
        for item in recommendations
        if item.workflow_template_id is not None
    }
    workflows = list(
        db.scalars(
            select(WorkflowTemplate)
            .where(WorkflowTemplate.id.in_(workflow_ids) if workflow_ids else False)
            .order_by(WorkflowTemplate.id)
        )
    )

    art_direction_assets = list(
        db.scalars(
            select(PlanningMediaAsset)
            .where(
                PlanningMediaAsset.project_id == story.project_id,
                PlanningMediaAsset.kind == "art_direction_reference",
                PlanningMediaAsset.archived_at.is_(None),
            )
            .order_by(PlanningMediaAsset.id)
        )
    )
    art_assets_by_scene_id: dict[str, list[PlanningMediaAsset]] = {}
    art_assets_by_scene_number: dict[int, list[PlanningMediaAsset]] = {}
    for asset in art_direction_assets:
        client_metadata = (asset.metadata_json or {}).get("client", {})
        scene_id = client_metadata.get("scene_id")
        scene_number = client_metadata.get("scene_number")
        if scene_id:
            art_assets_by_scene_id.setdefault(str(scene_id), []).append(asset)
        if scene_number is not None:
            art_assets_by_scene_number.setdefault(int(scene_number), []).append(asset)

    asset_ids: set[UUID] = set()
    asset_ids.update(
        reference.asset_id
        for references in character_references.values()
        for reference in references
    )
    asset_ids.update(
        shot.starting_image_asset_id
        for shot in shots
        if shot.starting_image_asset_id is not None
    )
    asset_ids.update(
        voice.source_asset_id for voice in voices if voice.source_asset_id is not None
    )
    asset_ids.update(
        preview.planning_media_asset_id
        for preview in selected_previews.values()
        if preview.planning_media_asset_id is not None
    )
    asset_ids.update(asset.id for asset in art_direction_assets)
    planning_assets = list(
        db.scalars(
            select(PlanningMediaAsset)
            .where(PlanningMediaAsset.id.in_(asset_ids) if asset_ids else False)
            .order_by(PlanningMediaAsset.id)
        )
    )
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

    scene_sequence_number = 0
    for chapter in chapters:
        chapter_duration = 0.0
        scenes_payload: list[dict] = []
        for scene in scenes_by_chapter.get(chapter.id, []):
            scene_sequence_number += 1
            art_references = art_assets_by_scene_id.get(str(scene.id))
            if art_references is None:
                art_references = art_assets_by_scene_number.get(scene_sequence_number, [])
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
                        "camera_direction": shot.camera_direction,
                        "motion_direction": shot.motion_direction,
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
                            "pacing_notes": narration.pacing_notes,
                            "pronunciation_notes": narration.pronunciation_notes,
                            "narration_fit_status": narration.narration_fit_status,
                            "narration_fit_wpm": _float_or_none(narration.narration_fit_wpm),
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
                                "prompt_rationale": package.prompt_rationale,
                                "provider_metadata_json": dict(package.provider_metadata_json or {}),
                                "proposal_id": _uuid_str(package.proposal_id),
                                "approval_state": package.approval_state,
                            }
                            for package in prompt_packages.get(shot.id, [])
                        ],
                        "recommendations": [
                            {
                                "id": str(recommendation.id),
                                "recommendation_type": recommendation.recommendation_type,
                                "generation_model_variant_id": _uuid_str(
                                    recommendation.generation_model_variant_id
                                ),
                                "workflow_template_id": _uuid_str(
                                    recommendation.workflow_template_id
                                ),
                                "rationale": recommendation.rationale,
                                "availability_status": recommendation.availability_status,
                                "benchmark_status": recommendation.benchmark_status,
                                "risk_status": recommendation.risk_status,
                                "acknowledged_at": recommendation.acknowledged_at,
                                "approval_state": recommendation.approval_state,
                            }
                            for recommendation in recommendations_by_shot.get(shot.id, [])
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
                    "target_duration_sec": _float_or_none(scene.target_duration_sec),
                    "approval_state": scene.approval_state,
                    "art_direction_reference_asset_ids": [
                        str(asset.id) for asset in art_references
                    ],
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
                "narrative_purpose": chapter.narrative_purpose,
                "target_duration_sec": _float_or_none(chapter.target_duration_sec),
                "dramatic_progression": chapter.dramatic_progression,
                "approval_state": chapter.approval_state,
                "duration_sec": chapter_duration,
                "scenes": scenes_payload,
            }
        )

    snapshot = {
        "schema": SNAPSHOT_SCHEMA,
        "schema_name": SNAPSHOT_SCHEMA,
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
            "narrative_objectives_json": dict(story.narrative_objectives_json or {}),
            "pacing_plan_json": dict(story.pacing_plan_json or {}),
            "duration_strategy_json": dict(story.duration_strategy_json or {}),
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
                "reference_assets": [
                    {
                        "id": str(reference.id),
                        "asset_id": str(reference.asset_id),
                        "reference_role": reference.reference_role,
                        "approved": bool(reference.approved),
                        "order_index": int(reference.order_index),
                    }
                    for reference in character_references.get(character.id, [])
                ],
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
                "provider_identifier": voice.provider_identifier,
                "provider_voice_id": voice.provider_voice_id,
                "provider_model_id": voice.provider_model_id,
                "voice_recipe_id": _uuid_str(voice.voice_recipe_id),
                "voice_recipe_json": dict(voice.voice_recipe_json or {}),
                "voice_recipe_hash": voice.voice_recipe_hash,
                "voice_description": voice.voice_description,
                "design_model_id": voice.design_model_id,
                "selected_preview_id": _uuid_str(voice.selected_preview_id),
                "recipes": [
                    {
                        "id": str(recipe.id),
                        "provider": recipe.provider,
                        "model": recipe.model,
                        "recipe_name": recipe.recipe_name,
                        "description": recipe.description,
                        "seed": recipe.seed,
                        "design_metadata_json": dict(recipe.design_metadata_json or {}),
                    }
                    for recipe in recipes_by_voice.get(voice.id, [])
                ],
                "selected_preview": None
                if voice.selected_preview_id not in selected_previews
                else {
                    "id": str(selected_previews[voice.selected_preview_id].id),
                    "voice_recipe_id": _uuid_str(
                        selected_previews[voice.selected_preview_id].voice_recipe_id
                    ),
                    "planning_media_asset_id": _uuid_str(
                        selected_previews[voice.selected_preview_id].planning_media_asset_id
                    ),
                    "provider": selected_previews[voice.selected_preview_id].provider,
                    "model": selected_previews[voice.selected_preview_id].model,
                    "preview_text": selected_previews[voice.selected_preview_id].preview_text,
                },
            }
            for voice in voices
        ],
        "planning_assets": [
            {
                "id": str(asset.id),
                "kind": asset.kind,
                "source_type": asset.source_type,
                "managed_uri": asset.managed_uri,
                "sha256": asset.sha256,
                "mime_type": asset.mime_type,
                "width": asset.width,
                "height": asset.height,
                "duration_sec": _float_or_none(asset.duration_sec),
                "size_bytes": asset.size_bytes,
                "approval_state": asset.approval_state,
            }
            for asset in planning_assets
        ],
        "provider_profiles": [
            {
                "id": str(profile.id),
                "provider_identifier": profile.provider_identifier,
                "display_name": profile.display_name,
                "provider_model_id": profile.provider_model_id,
                "execution_mode": profile.execution_mode,
                "privacy_classification": profile.privacy_classification,
                "capabilities_json": dict(profile.capabilities_json or {}),
                "capability_source": profile.capability_source,
            }
            for profile in provider_profiles
        ],
        "task_provider_assignments": [
            {
                "id": str(assignment.id),
                "task_type": assignment.task_type,
                "provider_profile_id": str(assignment.provider_profile_id),
                "assignment_mode": assignment.assignment_mode,
                "rationale": assignment.rationale,
                "priority": int(assignment.priority),
                "enabled": bool(assignment.enabled),
            }
            for assignment in task_assignments
        ],
        "model_variants": [
            {
                "id": str(variant.id),
                "model_id": str(variant.model_id),
                "model_family": models.get(variant.model_id).family
                if models.get(variant.model_id)
                else None,
                "model_name": models.get(variant.model_id).name
                if models.get(variant.model_id)
                else None,
                "variant_name": variant.variant_name,
                "sha256": variant.sha256,
                "native_voice_capability": variant.native_voice_capability,
                "native_voice_capability_source": variant.native_voice_capability_source,
                "native_voice_capability_metadata_json": dict(
                    variant.native_voice_capability_metadata_json or {}
                ),
            }
            for variant in model_variants
        ],
        "workflow_templates": [
            {
                "id": str(workflow.id),
                "name": workflow.name,
                "version": workflow.version,
                "sha256": workflow.sha256,
                "manifest_json": dict(workflow.manifest_json or {}),
            }
            for workflow in workflows
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
    # Approval lifecycle fields point at the immutable version produced from
    # this content.  Including them would make the content hash change merely
    # because approval succeeded, defeating idempotent re-approval.
    content = copy.deepcopy(snapshot)
    story = content.get("story")
    if isinstance(story, dict):
        story.pop("active_storyboard_version_id", None)
        story.pop("approval_state", None)
    return sha256_hex(content)


def build_snapshot_with_hash(db: Session, story_id: UUID) -> tuple[dict, str]:
    snapshot = build_canonical_snapshot(db, story_id)
    return snapshot, content_hash_for_snapshot(snapshot)


def current_revision(db: Session, story_id: UUID) -> str:
    """Revision token for optimistic concurrency on the live Phase A plan."""
    _, digest = build_snapshot_with_hash(db, story_id)
    return digest
