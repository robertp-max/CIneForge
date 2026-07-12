"""Strict validation and localized semantic repair helpers."""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from backend.app.schemas.orchestration import (
    PlanningContext,
    PlanningTaskType,
    ProviderResponseContract,
)
from backend.app.schemas.proposals import StoryboardProposalPayload, VoiceSetupMode
from backend.app.services.planning.errors import PlanningError, PlanningErrorCode


FORBIDDEN_PAYLOAD_KEYS = {
    "raw_ffmpeg_command",
    "ffmpeg_command",
    "workflow_node_id",
    "node_id",
    "direct_db_insert",
    "direct_db_update",
    "direct_db_delete",
    "queue_state",
    "queue_mutation",
    "asset_overwrite_path",
    "direct_comfy_prompt_payload",
    "prompt_payload",
    "registry_mutation",
    "shell_command",
    "comfyui",
    "ffmpeg",
    "model_download",
    "installer",
    "cli_command",
    "reasoning",
    "chain_of_thought",
    "hidden_reasoning",
    "scratchpad",
    "thinking",
    "raw_prompt",
    "raw_response",
    "api_key",
    "credentials",
}


REQUIRED_KEYS: dict[PlanningTaskType, set[str]] = {
    PlanningTaskType.story_structure: {"summary", "acts", "target_duration_sec"},
    PlanningTaskType.character_bible: {"summary", "characters"},
    PlanningTaskType.chapter_outline: {"summary", "chapters"},
    PlanningTaskType.scene_breakdown: {"summary", "scenes"},
    PlanningTaskType.shot_list: {"summary", "shots"},
    PlanningTaskType.narration_plan: {"summary", "narrations"},
    PlanningTaskType.prompt_package: {"summary", "prompt_packages"},
    PlanningTaskType.continuity_plan: {"summary", "continuity"},
    PlanningTaskType.model_recommendation: {"summary", "recommendations"},
    PlanningTaskType.production_proposal: {"summary", "shots", "target_duration_sec"},
}


def _scan_forbidden(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text.lower() in FORBIDDEN_PAYLOAD_KEYS or key_text in FORBIDDEN_PAYLOAD_KEYS:
                found.append(child_path)
            found.extend(_scan_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_scan_forbidden(child, f"{path}[{index}]"))
    return found


def validate_provider_response(
    response: ProviderResponseContract,
    *,
    expected_task: PlanningTaskType,
) -> list[str]:
    errors: list[str] = []
    if response.task_type != expected_task:
        errors.append(
            f"task_type mismatch: expected {expected_task.value}, got {response.task_type.value}"
        )
    if response.status not in {"succeeded", "failed"}:
        errors.append(f"invalid status: {response.status}")
    if response.status == "failed":
        if response.error is None:
            errors.append("failed response missing sanitized error")
        return errors

    payload = response.payload or {}
    required = REQUIRED_KEYS.get(expected_task, {"summary"})
    missing = sorted(required - set(payload.keys()))
    if missing:
        errors.append(f"missing required keys: {', '.join(missing)}")

    forbidden = _scan_forbidden(payload)
    errors.extend(f"forbidden field: {item}" for item in forbidden)

    if expected_task == PlanningTaskType.shot_list:
        shots = payload.get("shots")
        if not isinstance(shots, list) or not shots:
            errors.append("shots must be a non-empty list")
        else:
            for i, shot in enumerate(shots):
                if not isinstance(shot, dict):
                    errors.append(f"shots[{i}] must be an object")
                    continue
                dur = shot.get("duration_sec")
                if not isinstance(dur, (int, float)) or dur <= 0:
                    errors.append(f"shots[{i}].duration_sec must be > 0")

    if expected_task == PlanningTaskType.production_proposal:
        if not isinstance(payload.get("summary"), str) or not str(payload.get("summary")).strip():
            errors.append("production_proposal.summary must be non-empty")
        td = payload.get("target_duration_sec")
        if not isinstance(td, (int, float)) or td <= 0:
            errors.append("production_proposal.target_duration_sec must be > 0")

    return errors


def build_repair_instructions(errors: list[str]) -> list[str]:
    """Localized semantic repair instructions — only the failing fields."""
    instructions: list[str] = []
    for err in errors[:12]:
        if err.startswith("missing required keys:"):
            keys = err.split(":", 1)[1].strip()
            instructions.append(f"Add the missing fields only: {keys}. Do not rewrite unrelated sections.")
        elif err.startswith("forbidden field:"):
            field = err.split(":", 1)[1].strip()
            instructions.append(f"Remove forbidden field {field}. Do not add execution or media commands.")
        elif "duration_sec" in err:
            instructions.append("Fix shot duration_sec values to positive seconds within policy; leave other shots unchanged.")
        elif "task_type mismatch" in err:
            instructions.append("Return the requested task_type payload only.")
        else:
            instructions.append(f"Repair validation issue: {err}")
    if not instructions:
        instructions.append("Return a valid strict JSON payload for the requested task only.")
    return instructions


def merge_task_outputs(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Merge per-task payloads into a previous_output bag for proposal synthesis."""
    merged: dict[str, Any] = {"warnings": []}
    key_map = {
        PlanningTaskType.chapter_outline.value: "chapters",
        PlanningTaskType.character_bible.value: "characters",
        PlanningTaskType.shot_list.value: "shots",
        PlanningTaskType.narration_plan.value: "narrations",
        PlanningTaskType.prompt_package.value: "prompt_packages",
        PlanningTaskType.continuity_plan.value: "continuity",
        PlanningTaskType.model_recommendation.value: "recommendations",
        PlanningTaskType.scene_breakdown.value: "scenes",
        PlanningTaskType.story_structure.value: "structure",
    }
    for task_name, payload in outputs.items():
        if not isinstance(payload, dict):
            continue
        for warn in payload.get("warnings") or []:
            merged["warnings"].append(str(warn))
        mapped = key_map.get(task_name)
        if mapped and mapped in payload:
            merged[mapped] = payload[mapped]
        elif mapped == "characters" and "characters" in payload:
            merged["characters"] = payload["characters"]
        # Keep full task payload under namespaced key for resume.
        merged[f"task:{task_name}"] = payload
    return merged


def build_proposal_payload(
    *,
    project_id: Any,
    context: PlanningContext,
    base_storyboard_version_id: Any,
    base_content_hash: str,
    target_duration_sec: float,
    merged: dict[str, Any],
    production_payload: dict[str, Any] | None,
) -> StoryboardProposalPayload:
    """Normalize provider-neutral planning outputs into the canonical Phase-1 graph.

    Providers intentionally work with small, flat task contracts.  The review/apply
    boundary, however, accepts only the strict Project -> Story -> Chapter -> Scene
    -> Shot proposal contract.  This function is the deterministic adapter between
    those two boundaries.  Missing optional planning output becomes an explicit
    manual-review fallback; it never becomes an execution instruction.
    """

    src = dict(production_payload or {})

    def dicts(value: Any) -> list[dict[str, Any]]:
        return [dict(item) for item in (value or []) if isinstance(item, dict)]

    def optional_uuid(value: Any) -> str | None:
        if value in (None, ""):
            return None
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError):
            return None

    def optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def nonnegative_float(value: Any, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed >= 0 else default

    def positive_float(value: Any, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    def unique_client_id(
        prefix: str,
        ordinal: int,
        candidate: Any,
        used: set[str],
    ) -> str:
        base = optional_text(candidate) or f"{prefix}-{ordinal + 1:03d}"
        base = base[:128]
        result = base
        suffix = 2
        while result in used:
            tail = f"-{suffix}"
            result = f"{base[:128 - len(tail)]}{tail}"
            suffix += 1
        used.add(result)
        return result

    existing = context.existing_structure if isinstance(context.existing_structure, dict) else {}

    # ---- Characters -------------------------------------------------
    character_sources = dicts(src.get("characters") or merged.get("characters"))
    existing_characters = dicts(existing.get("characters") or context.characters)
    if not character_sources:
        character_sources = existing_characters
    existing_char_by_name = {
        str(item.get("name") or "").strip().casefold(): item
        for item in existing_characters
        if str(item.get("name") or "").strip()
    }
    character_ids: set[str] = set()
    character_ref_map: dict[str, str] = {}
    characters: list[dict[str, Any]] = []
    character_source_rows: list[dict[str, Any]] = []
    for index, item in enumerate(character_sources):
        name = optional_text(item.get("name")) or f"Character {index + 1}"
        matched = existing_char_by_name.get(name.casefold(), {})
        client_id = unique_client_id("character", index, item.get("client_id"), character_ids)
        for ref in (item.get("client_id"), item.get("id"), item.get("existing_id"), name):
            if ref not in (None, ""):
                character_ref_map[str(ref)] = client_id
        reference_asset_ids = item.get("reference_asset_ids")
        if reference_asset_ids is None and matched:
            reference_asset_ids = [
                row.get("asset_id")
                for row in dicts(matched.get("reference_assets"))
                if row.get("asset_id")
            ]
        characters.append(
            {
                "client_id": client_id,
                "existing_id": optional_uuid(
                    item.get("existing_id") or item.get("id") or matched.get("id")
                ),
                "name": name[:200],
                "role": optional_text(item.get("role") or matched.get("role")),
                "age_range": optional_text(item.get("age_range") or matched.get("age_range")),
                "physical_description": optional_text(
                    item.get("physical_description") or matched.get("physical_description")
                ),
                "personality": optional_text(item.get("personality") or matched.get("personality")),
                "speaking_style": optional_text(
                    item.get("speaking_style") or matched.get("speaking_style")
                ),
                "wardrobe": optional_text(item.get("wardrobe") or matched.get("wardrobe")),
                "consistency_prompt": optional_text(
                    item.get("consistency_prompt") or matched.get("consistency_prompt")
                ),
                "negative_identity_prompt": optional_text(
                    item.get("negative_identity_prompt") or matched.get("negative_identity_prompt")
                ),
                "identity_method": optional_text(
                    item.get("identity_method") or matched.get("identity_method")
                ),
                "assigned_voice_client_id": None,
                "reference_asset_ids": [
                    asset_id
                    for asset_id in (optional_uuid(value) for value in (reference_asset_ids or []))
                    if asset_id is not None
                ],
                "approval_state": str(item.get("approval_state") or matched.get("approval_state") or "draft")[:32],
            }
        )
        character_source_rows.append({"source": item, "matched": matched})

    # ---- Voices -----------------------------------------------------
    narration_sources = dicts(src.get("narrations") or merged.get("narrations"))
    voice_sources = dicts(src.get("voices") or merged.get("voices"))
    existing_voices = dicts(existing.get("voices") or existing.get("voice_profiles"))
    if not voice_sources and any(optional_text(row.get("narration_text")) for row in narration_sources):
        voice_sources = [{"name": "Narrator", "source_type": "placeholder"}]
    existing_voice_by_name = {
        str(item.get("name") or "").strip().casefold(): item
        for item in existing_voices
        if str(item.get("name") or "").strip()
    }
    allowed_modes = {mode.value for mode in VoiceSetupMode}
    voice_ids: set[str] = set()
    voice_ref_map: dict[str, str] = {}
    voice_existing_to_client: dict[str, str] = {}
    voices: list[dict[str, Any]] = []
    for index, item in enumerate(voice_sources):
        name = optional_text(item.get("name")) or f"Voice {index + 1}"
        matched = existing_voice_by_name.get(name.casefold(), {})
        client_id = unique_client_id("voice", index, item.get("client_id"), voice_ids)
        for ref in (
            item.get("client_id"),
            item.get("id"),
            item.get("existing_id"),
            name,
            matched.get("id"),
        ):
            if ref not in (None, ""):
                voice_ref_map[str(ref)] = client_id
        matched_id = optional_uuid(matched.get("id"))
        if matched_id:
            voice_existing_to_client[matched_id] = client_id

        source_type = str(item.get("source_type") or matched.get("source_type") or "placeholder")
        if source_type not in allowed_modes:
            source_type = "manual"
        setup_mode = str(item.get("setup_mode") or matched.get("setup_mode") or source_type)
        if setup_mode not in allowed_modes:
            setup_mode = "manual"

        # Approved voice identity fields are immutable.  When a provider row
        # matches one, copy the factual protected values into the proposal.
        approved = str(matched.get("approval_state") or "") == "approved"
        protected_source = matched if approved else item
        character_ref = item.get("character_client_id") or matched.get("character_id")
        voices.append(
            {
                "client_id": client_id,
                "existing_id": optional_uuid(
                    item.get("existing_id") or item.get("id") or matched.get("id")
                ),
                "name": name[:200],
                "source_type": str(protected_source.get("source_type") or source_type),
                "character_client_id": character_ref_map.get(str(character_ref)) if character_ref else None,
                "provider": optional_text(protected_source.get("provider")),
                "provider_voice_reference": optional_text(
                    protected_source.get("provider_voice_reference")
                ),
                "language": optional_text(item.get("language") or matched.get("language")),
                "accent": optional_text(item.get("accent") or matched.get("accent")),
                "presentation": optional_text(item.get("presentation") or matched.get("presentation")),
                "tone": optional_text(item.get("tone") or matched.get("tone")),
                "speaking_directions": optional_text(
                    item.get("speaking_directions") or matched.get("speaking_directions")
                ),
                "pacing": optional_text(item.get("pacing") or matched.get("pacing")),
                "energy": optional_text(item.get("energy") or matched.get("energy")),
                "pronunciation_notes": optional_text(
                    item.get("pronunciation_notes") or matched.get("pronunciation_notes")
                ),
                "source_asset_id": optional_uuid(item.get("source_asset_id") or matched.get("source_asset_id")),
                "source_description": optional_text(
                    item.get("source_description") or matched.get("source_description")
                ),
                "consent_required": bool(protected_source.get("consent_required") or False),
                "consent_confirmed": bool(protected_source.get("consent_confirmed") or False),
                "consent_notes": optional_text(item.get("consent_notes") or matched.get("consent_notes")),
                "usage_notes": optional_text(item.get("usage_notes") or matched.get("usage_notes")),
                "setup_mode": str(protected_source.get("setup_mode") or setup_mode),
                "provider_model_id": optional_text(protected_source.get("provider_model_id")),
                "recipe_name": optional_text(item.get("recipe_name")),
                "recipe_description": optional_text(item.get("recipe_description")),
                "design_description": optional_text(item.get("design_description")),
                "approval_state": str(item.get("approval_state") or matched.get("approval_state") or "draft")[:32],
            }
        )

    for character, row in zip(characters, character_source_rows, strict=True):
        source = row["source"]
        matched = row["matched"]
        voice_ref = source.get("assigned_voice_client_id") or matched.get("assigned_voice_profile_id")
        assigned = voice_ref_map.get(str(voice_ref)) if voice_ref else None
        if assigned is None and voice_ref:
            assigned = voice_existing_to_client.get(str(voice_ref))
        if assigned is None:
            assigned = next(
                (
                    voice["client_id"]
                    for voice in voices
                    if voice.get("character_client_id") == character["client_id"]
                ),
                None,
            )
        character["assigned_voice_client_id"] = assigned

    # ---- Chapter / scene skeleton ----------------------------------
    chapter_sources = dicts(src.get("chapters") or merged.get("chapters"))
    if not chapter_sources:
        chapter_sources = [{"title": "Production Plan", "summary": context.logline}]
    chapter_ids: set[str] = set()
    chapters: list[dict[str, Any]] = []
    for index, item in enumerate(chapter_sources):
        chapters.append(
            {
                "client_id": unique_client_id("chapter", index, item.get("client_id"), chapter_ids),
                "existing_id": optional_uuid(item.get("existing_id") or item.get("id")),
                "order_index": index,
                "title": (optional_text(item.get("title")) or f"Chapter {index + 1}")[:300],
                "summary": optional_text(item.get("summary")),
                "scenes": [],
            }
        )

    nested_scene_sources: list[dict[str, Any]] = []
    for chapter_index, chapter in enumerate(chapter_sources):
        for scene in dicts(chapter.get("scenes")):
            scene["_chapter_index"] = chapter_index
            nested_scene_sources.append(scene)
    scene_sources = nested_scene_sources or dicts(src.get("scenes") or merged.get("scenes"))
    if not scene_sources:
        scene_sources = [{"title": "Planned Sequence", "chapter_order_index": 0}]

    scene_ids: set[str] = set()
    scenes: list[dict[str, Any]] = []
    for index, item in enumerate(scene_sources):
        raw_chapter = item.get("_chapter_index", item.get("chapter_order_index", 0))
        try:
            chapter_index = int(raw_chapter)
        except (TypeError, ValueError):
            chapter_index = 0
        chapter_index = max(0, min(chapter_index, len(chapters) - 1))
        scene = {
            "client_id": unique_client_id("scene", index, item.get("client_id"), scene_ids),
            "existing_id": optional_uuid(item.get("existing_id") or item.get("id")),
            "order_index": 0,  # assigned within the containing chapter below
            "title": (optional_text(item.get("title")) or f"Scene {index + 1}")[:300],
            "summary": optional_text(item.get("summary")),
            "narrative_purpose": optional_text(item.get("narrative_purpose")),
            "location": optional_text(item.get("location")),
            "conflict_or_beat": optional_text(item.get("conflict_or_beat")),
            "shots": [],
            "_chapter_index": chapter_index,
        }
        scenes.append(scene)
        chapters[chapter_index]["scenes"].append(scene)
    for chapter in chapters:
        for scene_index, scene in enumerate(chapter["scenes"]):
            scene["order_index"] = scene_index

    # ---- Shots and embedded planning records -----------------------
    nested_shot_sources: list[dict[str, Any]] = []
    if nested_scene_sources:
        for scene_index, scene in enumerate(nested_scene_sources):
            for shot in dicts(scene.get("shots")):
                shot["_scene_index"] = scene_index
                nested_shot_sources.append(shot)
    shot_sources = nested_shot_sources or dicts(src.get("shots") or merged.get("shots"))
    if not shot_sources:
        shot_sources = [
            {
                "title": "Opening shot",
                "visual_description": context.base_story[:500],
                "story_purpose": context.logline or "Establish the story plan",
            }
        ]

    target = Decimal(str(float(target_duration_sec)))
    preferred_count = max(1, len(shot_sources))
    if target >= Decimal("6"):
        minimum_count = max(1, math.ceil(float(target / Decimal("12"))))
        maximum_count = max(1, math.floor(float(target / Decimal("6"))))
        shot_count = max(minimum_count, min(preferred_count, maximum_count))
        if preferred_count < minimum_count or preferred_count > maximum_count:
            shot_count = max(minimum_count, min(maximum_count, round(float(target) / 8)))
    else:
        shot_count = 1
    average = (target / Decimal(shot_count)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    durations = [average for _ in range(max(0, shot_count - 1))]
    durations.append(target - sum(durations, Decimal("0")))

    prompt_sources = dicts(src.get("prompt_packages") or merged.get("prompt_packages"))
    recommendation_sources = dicts(
        src.get("model_recommendations")
        or src.get("recommendations")
        or merged.get("model_recommendations")
        or merged.get("recommendations")
    )

    def indexed(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
        result: dict[int, list[dict[str, Any]]] = {}
        for position, row in enumerate(rows):
            raw = row.get("shot_order_index", position)
            try:
                key = int(raw)
            except (TypeError, ValueError):
                key = position
            result.setdefault(key, []).append(row)
        return result

    narrations_by_shot = indexed(narration_sources)
    prompts_by_shot = indexed(prompt_sources)
    recommendations_by_shot = indexed(recommendation_sources)
    shot_ids: set[str] = set()
    shot_rows: list[tuple[int, dict[str, Any]]] = []

    for index in range(shot_count):
        template = dict(shot_sources[index % len(shot_sources)])
        duration = float(durations[index])
        client_id = unique_client_id("shot", index, template.get("client_id"), shot_ids)
        raw_scene = template.get("_scene_index", template.get("scene_order_index"))
        if raw_scene is None:
            scene_index = min(len(scenes) - 1, int(index * len(scenes) / shot_count))
        else:
            try:
                scene_index = int(raw_scene) % len(scenes)
            except (TypeError, ValueError):
                scene_index = min(len(scenes) - 1, int(index * len(scenes) / shot_count))

        embedded_narration = template.get("narration")
        narration_source = (
            narrations_by_shot.get(index)
            or ([dict(embedded_narration)] if isinstance(embedded_narration, dict) else [])
            or [{}]
        )[0]
        narration_text = optional_text(narration_source.get("narration_text"))
        narration_exception = optional_text(narration_source.get("narration_exception_reason"))
        voice_ref = narration_source.get("voice_client_id") or narration_source.get("voice_profile_id")
        voice_client_id = voice_ref_map.get(str(voice_ref)) if voice_ref else None
        if narration_text and voice_client_id is None and voices:
            voice_client_id = voices[0]["client_id"]
        if not narration_text and not narration_exception:
            narration_exception = "No narration was proposed; manual review required."

        embedded_prompt = template.get("prompt_package")
        prompt_source = (
            prompts_by_shot.get(index)
            or ([dict(embedded_prompt)] if isinstance(embedded_prompt, dict) else [])
            or [{}]
        )[0]
        image_prompt = optional_text(prompt_source.get("image_prompt"))
        video_prompt = optional_text(prompt_source.get("video_prompt"))
        if not image_prompt and not video_prompt:
            image_prompt = (
                f"Manual-review planning frame for {optional_text(template.get('title')) or f'Shot {index + 1}'}: "
                f"{optional_text(template.get('visual_description')) or context.visual_style or context.base_story[:240]}"
            )[:4000]

        recommendations: list[dict[str, Any]] = []
        embedded_recommendations = dicts(template.get("model_recommendations"))
        for recommendation in (
            recommendations_by_shot.get(index) or embedded_recommendations
        ):
            capability = recommendation.get("native_voice_capability")
            if capability not in {"supported", "unsupported", "unknown"}:
                capability = "unknown"
            recommendations.append(
                {
                    "recommendation_type": str(
                        recommendation.get("recommendation_type") or "manual_review"
                    )[:64],
                    "generation_model_variant_id": optional_uuid(
                        recommendation.get("generation_model_variant_id")
                    ),
                    "workflow_template_id": optional_uuid(
                        recommendation.get("workflow_template_id")
                    ),
                    "provider_profile_id": optional_uuid(
                        recommendation.get("provider_profile_id")
                    ),
                    "provider_identifier": optional_text(
                        recommendation.get("provider_identifier") or recommendation.get("provider")
                    ),
                    "provider_model_id": optional_text(
                        recommendation.get("provider_model_id") or recommendation.get("model")
                    ),
                    "rationale": optional_text(recommendation.get("rationale")),
                    "availability_status": str(
                        recommendation.get("availability_status") or "unknown"
                    )[:32],
                    "benchmark_status": str(
                        recommendation.get("benchmark_status") or "unknown"
                    )[:32],
                    "risk_status": optional_text(recommendation.get("risk_status")),
                    "recommends_qwen_voice": bool(
                        recommendation.get("recommends_qwen_voice") or False
                    ),
                    "native_voice_capability": capability,
                }
            )
        if not recommendations:
            recommendations = [
                {
                    "recommendation_type": "manual_review",
                    "rationale": "No factual generation route was proposed; select one during review.",
                    "availability_status": "unknown",
                    "benchmark_status": "unknown",
                    "risk_status": "review",
                    "recommends_qwen_voice": False,
                    "native_voice_capability": "unknown",
                }
            ]

        character_links: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        for link_index, link in enumerate(dicts(template.get("characters"))):
            raw_ref = link.get("character_client_id") or link.get("character_id")
            resolved = character_ref_map.get(str(raw_ref)) if raw_ref else None
            if resolved and resolved not in seen_links:
                seen_links.add(resolved)
                character_links.append(
                    {
                        "character_client_id": resolved,
                        "role_in_shot": optional_text(link.get("role_in_shot")),
                        "order_index": len(character_links),
                        "continuity_notes": optional_text(link.get("continuity_notes")),
                    }
                )
        if not character_links and characters:
            character_links = [
                {
                    "character_client_id": characters[0]["client_id"],
                    "role_in_shot": "lead",
                    "order_index": 0,
                    "continuity_notes": "Preserve identity and wardrobe during review.",
                }
            ]

        shot_rows.append(
            (
                scene_index,
                {
                    "client_id": client_id,
                    "existing_id": optional_uuid(template.get("existing_id") or template.get("id")),
                    "order_index": 0,
                    "title": (optional_text(template.get("title")) or f"Shot {index + 1}")[:300],
                    "duration_sec": duration,
                    "duration_override_reason": (
                        optional_text(template.get("duration_override_reason"))
                        if 6 <= duration <= 12
                        else "Target duration requires a shot outside the preferred 6-12 second range."
                    ),
                    "story_purpose": optional_text(template.get("story_purpose")),
                    "visual_description": optional_text(template.get("visual_description")),
                    "location": optional_text(template.get("location")),
                    "continuity_source_type": "none",  # linked in canonical order below
                    "continuity_source_shot_client_id": None,
                    "starting_image_required": bool(template.get("starting_image_required") or False),
                    "starting_image_asset_id": optional_uuid(template.get("starting_image_asset_id")),
                    "characters": character_links,
                    "narration": {
                        "client_id": unique_client_id(
                            "narration",
                            index,
                            narration_source.get("client_id"),
                            set(),
                        ),
                        "narration_text": narration_text,
                        "voice_client_id": voice_client_id,
                        "start_offset_sec": nonnegative_float(
                            narration_source.get("start_offset_sec"), 0.0
                        ),
                        "expected_duration_sec": positive_float(
                            narration_source.get("expected_duration_sec"), duration
                        ),
                        "narration_exception_reason": narration_exception,
                    },
                    "prompt_package": {
                        "image_prompt": image_prompt,
                        "video_prompt": video_prompt,
                        "negative_prompt": optional_text(prompt_source.get("negative_prompt")),
                        "continuity_instructions": optional_text(
                            prompt_source.get("continuity_instructions")
                        ),
                        "style_lock_prompt": optional_text(prompt_source.get("style_lock_prompt")),
                        "provider_profile_id": optional_uuid(prompt_source.get("provider_profile_id")),
                        "provider_model_id": optional_text(prompt_source.get("provider_model_id")),
                    },
                    "model_recommendations": recommendations,
                },
            )
        )

    for scene_index, shot in shot_rows:
        scenes[scene_index]["shots"].append(shot)

    previous_shot_id: str | None = None
    for chapter in chapters:
        for scene in chapter["scenes"]:
            for shot_index, shot in enumerate(scene["shots"]):
                shot["order_index"] = shot_index
                if previous_shot_id is not None:
                    shot["continuity_source_type"] = "shot_ref"
                    shot["continuity_source_shot_client_id"] = previous_shot_id
                previous_shot_id = shot["client_id"]
            scene.pop("_chapter_index", None)

    try:
        return StoryboardProposalPayload.model_validate(
            {
                "schema_name": "storyboard_proposal_v1",
                "project_id": project_id,
                "story": {
                    "client_id": f"story-{context.story_id}",
                    "existing_id": context.story_id,
                    "title": context.title,
                    "base_story": context.base_story,
                    "target_duration_sec": float(target),
                    "logline": context.logline,
                    "synopsis": context.synopsis,
                    "audience": context.audience,
                    "tone": context.tone,
                    "genre": context.genre,
                    "visual_style": context.visual_style,
                    "point_of_view": context.point_of_view,
                    "production_notes": context.production_notes,
                    "characters": characters,
                    "voices": voices,
                    "chapters": chapters,
                },
                "base_storyboard_version_id": base_storyboard_version_id,
                "base_content_hash": base_content_hash,
            }
        )
    except Exception as exc:  # pydantic validation
        raise PlanningError(
            PlanningErrorCode.VALIDATION_FAILED,
            f"Proposal contract validation failed: {exc}",
            details={"phase": "proposal_build"},
        ) from exc


def assert_no_execution_side_effects(payload: dict[str, Any]) -> None:
    forbidden = _scan_forbidden(payload)
    if forbidden:
        raise PlanningError(
            PlanningErrorCode.CONTRACT_VIOLATION,
            "Payload contains forbidden execution fields",
            details={"fields": forbidden[:20]},
        )
