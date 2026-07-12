from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from backend.app.core.errors import ForbiddenProposalError
from backend.app.services.ai_orchestration.schemas import (
    STORYBOARD_PROPOSAL_SCHEMA_NAME,
    STORYBOARD_PROPOSAL_TYPES,
    AIProposal,
    ProposalType,
    ProposalValidationResult,
)


FORBIDDEN_FIELD_NAMES = {
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
    "execute_sql",
    "drop_table",
    "credential",
    "api_key",
    "secret",
    "password",
    "private_key",
    "access_token",
}

_NON_ALNUM = re.compile(r"[^a-z0-9_]")


def normalize_key(key: str) -> str:
    """Normalize object keys for forbidden-field scanning."""
    text = str(key).strip().lower().replace("-", "_").replace(" ", "_")
    text = _NON_ALNUM.sub("", text)
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


NORMALIZED_FORBIDDEN_FIELD_NAMES = {normalize_key(name) for name in FORBIDDEN_FIELD_NAMES}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def content_hash_for(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _scan_forbidden(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            normalized = normalize_key(key_text)
            if key_text in FORBIDDEN_FIELD_NAMES or normalized in NORMALIZED_FORBIDDEN_FIELD_NAMES:
                found.append(child_path)
            found.extend(_scan_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_scan_forbidden(child, f"{path}[{index}]"))
    return found


def _is_uuid(value: Any) -> bool:
    if value is None:
        return False
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _unique_client_ids(items: list[dict[str, Any]], path: str, errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{path}[{index}] must be an object")
            continue
        client_id = item.get("client_id")
        if not isinstance(client_id, str) or not client_id.strip():
            errors.append(f"{path}[{index}].client_id is required")
            continue
        if client_id in seen:
            errors.append(f"{path}: duplicate client_id '{client_id}'")
        seen.add(client_id)
    return seen


def _check_order_indexes(items: list[dict[str, Any]], path: str, errors: list[str]) -> None:
    indexes: list[int] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        order_index = item.get("order_index")
        if not isinstance(order_index, int) or isinstance(order_index, bool):
            errors.append(f"{path}[{index}].order_index must be an integer >= 0")
            continue
        if order_index < 0:
            errors.append(f"{path}[{index}].order_index must be >= 0")
            continue
        indexes.append(order_index)
    if not indexes:
        return
    expected = list(range(len(indexes)))
    if sorted(indexes) != expected:
        errors.append(
            f"{path}: order_index values must be contiguous starting at 0; got {sorted(indexes)}"
        )


def _shot_needs_voice(shot: dict[str, Any]) -> bool:
    narration = shot.get("narration")
    if not isinstance(narration, dict):
        return False
    text = (narration.get("narration_text") or "").strip()
    exception = (narration.get("narration_exception_reason") or "").strip()
    return bool(text) and not exception


def _validate_qwen_rules(shot: dict[str, Any], path: str, errors: list[str], warnings: list[str]) -> None:
    recommendations = shot.get("model_recommendations") or []
    if not isinstance(recommendations, list):
        errors.append(f"{path}.model_recommendations must be a list")
        return

    voice_required = _shot_needs_voice(shot)
    for index, rec in enumerate(recommendations):
        if not isinstance(rec, dict):
            errors.append(f"{path}.model_recommendations[{index}] must be an object")
            continue

        recommends_qwen = bool(rec.get("recommends_qwen_voice"))
        capability = rec.get("native_voice_capability")
        recommendation_type = (rec.get("recommendation_type") or "").strip()
        is_qwen_companion = recommends_qwen or recommendation_type == "qwen_voice_companion"
        provider = (rec.get("provider_identifier") or rec.get("provider") or "").strip().lower()
        model_name = (rec.get("provider_model_id") or rec.get("model") or "").strip().lower()
        looks_like_qwen = "qwen" in provider or "qwen" in model_name or is_qwen_companion

        if capability is not None and capability not in {"supported", "unsupported", "unknown"}:
            errors.append(
                f"{path}.model_recommendations[{index}].native_voice_capability must be "
                "supported|unsupported|unknown"
            )
            continue

        # Native-speech capable models (e.g. LTX with native speech) must not pull in Qwen.
        if capability == "supported" and looks_like_qwen:
            errors.append(
                f"{path}.model_recommendations[{index}]: Qwen must not be recommended when "
                "native speech is supported (including native-speech LTX)"
            )
            continue

        if not looks_like_qwen:
            if capability == "unknown" and voice_required:
                warnings.append(
                    f"{path}.model_recommendations[{index}]: native voice capability is unknown; "
                    "requires human review and must not auto-select Qwen"
                )
            continue

        # Qwen path
        if not voice_required:
            errors.append(
                f"{path}.model_recommendations[{index}]: Qwen may only be recommended when "
                "voice/narration is required"
            )
            continue

        if capability == "unknown" or capability is None:
            errors.append(
                f"{path}.model_recommendations[{index}]: native voice capability is unknown; "
                "Qwen is forbidden — flag for review instead"
            )
            warnings.append(
                f"{path}: unknown native voice capability requires review (no Qwen auto-recommend)"
            )
            continue

        if capability != "unsupported":
            errors.append(
                f"{path}.model_recommendations[{index}]: Qwen may be recommended only when "
                "native speech is explicitly unsupported"
            )


def _validate_shot(
    shot: dict[str, Any],
    path: str,
    character_ids: set[str],
    voice_ids: set[str],
    shot_ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> float:
    duration = shot.get("duration_sec")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        errors.append(f"{path}.duration_sec must be a number > 0")
        duration_value = 0.0
    else:
        duration_value = float(duration)
        if not (6 <= duration_value <= 12) and not (shot.get("duration_override_reason") or "").strip():
            errors.append(
                f"{path}: shots outside 6–12 seconds require duration_override_reason"
            )

    continuity_type = (shot.get("continuity_source_type") or "none").strip()
    continuity_ref = shot.get("continuity_source_shot_client_id")
    if continuity_type == "none":
        if continuity_ref:
            errors.append(
                f"{path}: continuity_source_shot_client_id must be null when continuity_source_type is none"
            )
    elif continuity_type in {"previous_shot", "shot_ref", "starting_image"}:
        if continuity_type != "starting_image":
            if not continuity_ref:
                errors.append(f"{path}: continuity_source_shot_client_id is required for {continuity_type}")
            elif continuity_ref not in shot_ids:
                errors.append(
                    f"{path}: continuity_source_shot_client_id '{continuity_ref}' does not resolve"
                )
            elif continuity_ref == shot.get("client_id"):
                errors.append(f"{path}: shot cannot reference itself as continuity source")
        if continuity_type == "starting_image":
            if not shot.get("starting_image_required") and not shot.get("starting_image_asset_id"):
                errors.append(
                    f"{path}: starting_image continuity requires starting_image_required or starting_image_asset_id"
                )
    else:
        errors.append(f"{path}.continuity_source_type is not supported: {continuity_type}")

    if shot.get("starting_image_asset_id") is not None and not _is_uuid(shot.get("starting_image_asset_id")):
        errors.append(f"{path}.starting_image_asset_id must be a UUID")

    characters = shot.get("characters") or []
    if not isinstance(characters, list):
        errors.append(f"{path}.characters must be a list")
    else:
        for c_index, link in enumerate(characters):
            if not isinstance(link, dict):
                errors.append(f"{path}.characters[{c_index}] must be an object")
                continue
            char_ref = link.get("character_client_id")
            if not char_ref or char_ref not in character_ids:
                errors.append(
                    f"{path}.characters[{c_index}].character_client_id does not resolve to a story character"
                )

    narration = shot.get("narration")
    if narration is None:
        errors.append(f"{path}.narration is required (text or narration_exception_reason)")
    elif not isinstance(narration, dict):
        errors.append(f"{path}.narration must be an object")
    else:
        text = (narration.get("narration_text") or "").strip()
        exception = (narration.get("narration_exception_reason") or "").strip()
        if not text and not exception:
            errors.append(
                f"{path}.narration requires narration_text or narration_exception_reason"
            )
        voice_ref = narration.get("voice_client_id")
        if voice_ref and voice_ref not in voice_ids:
            errors.append(f"{path}.narration.voice_client_id '{voice_ref}' does not resolve")
        if text and not voice_ref and not exception:
            warnings.append(f"{path}.narration has text but no voice_client_id")

    prompt = shot.get("prompt_package")
    if prompt is None:
        errors.append(f"{path}.prompt_package is required")
    elif not isinstance(prompt, dict):
        errors.append(f"{path}.prompt_package must be an object")
    else:
        image_prompt = (prompt.get("image_prompt") or "").strip()
        video_prompt = (prompt.get("video_prompt") or "").strip()
        if not image_prompt and not video_prompt:
            errors.append(f"{path}.prompt_package requires image_prompt or video_prompt")

    recommendations = shot.get("model_recommendations") or []
    if isinstance(recommendations, list):
        for r_index, rec in enumerate(recommendations):
            if not isinstance(rec, dict):
                continue
            variant_id = rec.get("generation_model_variant_id")
            workflow_id = rec.get("workflow_template_id")
            if variant_id is not None and not _is_uuid(variant_id):
                errors.append(
                    f"{path}.model_recommendations[{r_index}].generation_model_variant_id must be a UUID"
                )
            if workflow_id is not None and not _is_uuid(workflow_id):
                errors.append(
                    f"{path}.model_recommendations[{r_index}].workflow_template_id must be a UUID"
                )

    _validate_qwen_rules(shot, path, errors, warnings)
    return duration_value


def _collect_all_shot_client_ids(story: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for chapter in story.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        for scene in chapter.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            for shot in scene.get("shots") or []:
                if isinstance(shot, dict) and isinstance(shot.get("client_id"), str):
                    ids.add(shot["client_id"])
    return ids


def _validate_continuity_order(story: dict[str, Any], errors: list[str]) -> None:
    """Ensure continuity sources precede targets in canonical chapter/scene/shot order."""
    ordered: list[str] = []
    positions: dict[str, int] = {}
    for chapter in sorted((story.get("chapters") or []), key=lambda c: c.get("order_index", -1) if isinstance(c, dict) else -1):
        if not isinstance(chapter, dict):
            continue
        for scene in sorted((chapter.get("scenes") or []), key=lambda s: s.get("order_index", -1) if isinstance(s, dict) else -1):
            if not isinstance(scene, dict):
                continue
            for shot in sorted((scene.get("shots") or []), key=lambda s: s.get("order_index", -1) if isinstance(s, dict) else -1):
                if not isinstance(shot, dict):
                    continue
                client_id = shot.get("client_id")
                if isinstance(client_id, str):
                    positions[client_id] = len(ordered)
                    ordered.append(client_id)

    for chapter in story.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        for scene in chapter.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            for shot in scene.get("shots") or []:
                if not isinstance(shot, dict):
                    continue
                src = shot.get("continuity_source_shot_client_id")
                dst = shot.get("client_id")
                if not src or not dst or src not in positions or dst not in positions:
                    continue
                if positions[src] >= positions[dst]:
                    errors.append(
                        f"shot '{dst}': continuity source '{src}' must precede the target shot"
                    )

    # Cycle detection on continuity edges.
    edges = {}
    for chapter in story.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        for scene in chapter.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            for shot in scene.get("shots") or []:
                if isinstance(shot, dict) and shot.get("client_id") and shot.get("continuity_source_shot_client_id"):
                    edges[shot["client_id"]] = shot["continuity_source_shot_client_id"]
    for start in list(edges):
        seen: set[str] = set()
        current = start
        while current in edges:
            if current in seen:
                errors.append(f"continuity cycle detected involving shot '{start}'")
                break
            seen.add(current)
            current = edges[current]


def _validate_approved_voice_preservation(
    story: dict[str, Any],
    base_snapshot: dict[str, Any] | None,
    errors: list[str],
) -> None:
    if not base_snapshot:
        return
    base_voices = {
        str(v.get("id") or v.get("existing_id") or v.get("client_id")): v
        for v in (base_snapshot.get("voices") or [])
        if isinstance(v, dict)
    }
    protected_fields = (
        "provider",
        "provider_voice_reference",
        "setup_mode",
        "source_type",
        "provider_model_id",
        "consent_confirmed",
        "consent_required",
    )
    for voice in story.get("voices") or []:
        if not isinstance(voice, dict):
            continue
        existing_id = voice.get("existing_id")
        if existing_id is None:
            continue
        base = base_voices.get(str(existing_id))
        if not base:
            # also try matching by client_id in snapshot
            base = next(
                (
                    v
                    for v in (base_snapshot.get("voices") or [])
                    if isinstance(v, dict) and str(v.get("id")) == str(existing_id)
                ),
                None,
            )
        if not base:
            continue
        if (base.get("approval_state") or "") != "approved":
            continue
        for field in protected_fields:
            if field in voice and voice.get(field) != base.get(field):
                errors.append(
                    f"voices[{voice.get('client_id')}]: cannot modify approved voice field '{field}'"
                )


def validate_storyboard_payload(
    payload: dict[str, Any],
    *,
    base_snapshot: dict[str, Any] | None = None,
    known_model_variant_ids: set[str] | None = None,
    known_workflow_template_ids: set[str] | None = None,
    known_provider_profile_ids: set[str] | None = None,
    known_asset_ids: set[str] | None = None,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    report: dict[str, Any] = {"checks": []}

    if not isinstance(payload, dict):
        return ["payload must be an object"], warnings, report

    schema_name = payload.get("schema_name") or STORYBOARD_PROPOSAL_SCHEMA_NAME
    if schema_name != STORYBOARD_PROPOSAL_SCHEMA_NAME:
        errors.append(f"schema_name must be {STORYBOARD_PROPOSAL_SCHEMA_NAME}")

    project_id = payload.get("project_id")
    if not _is_uuid(project_id):
        errors.append("project_id must be a UUID")

    story = payload.get("story")
    if not isinstance(story, dict):
        errors.append("story must be an object")
        return errors, warnings, report

    if not isinstance(story.get("client_id"), str) or not story.get("client_id", "").strip():
        errors.append("story.client_id is required")
    if not isinstance(story.get("title"), str) or not story.get("title", "").strip():
        errors.append("story.title is required")
    if not isinstance(story.get("base_story"), str) or not story.get("base_story", "").strip():
        errors.append("story.base_story is required")

    target = story.get("target_duration_sec")
    if not isinstance(target, (int, float)) or isinstance(target, bool) or float(target) <= 0:
        errors.append("story.target_duration_sec must be a number > 0")
        target_value = None
    else:
        target_value = float(target)

    characters = story.get("characters") or []
    voices = story.get("voices") or []
    chapters = story.get("chapters") or []
    if not isinstance(characters, list):
        errors.append("story.characters must be a list")
        characters = []
    if not isinstance(voices, list):
        errors.append("story.voices must be a list")
        voices = []
    if not isinstance(chapters, list):
        errors.append("story.chapters must be a list")
        chapters = []

    character_ids = _unique_client_ids(characters, "story.characters", errors)
    voice_ids = _unique_client_ids(voices, "story.voices", errors)
    _unique_client_ids(chapters, "story.chapters", errors)
    _check_order_indexes(chapters, "story.chapters", errors)

    for index, character in enumerate(characters):
        if not isinstance(character, dict):
            continue
        if not (character.get("name") or "").strip():
            errors.append(f"story.characters[{index}].name is required")
        voice_ref = character.get("assigned_voice_client_id")
        if voice_ref and voice_ref not in voice_ids:
            errors.append(
                f"story.characters[{index}].assigned_voice_client_id '{voice_ref}' does not resolve"
            )
        for a_index, asset_id in enumerate(character.get("reference_asset_ids") or []):
            if not _is_uuid(asset_id):
                errors.append(
                    f"story.characters[{index}].reference_asset_ids[{a_index}] must be a UUID"
                )
            elif known_asset_ids is not None and str(asset_id) not in known_asset_ids:
                errors.append(
                    f"story.characters[{index}].reference_asset_ids[{a_index}] is not a known planning asset"
                )

    for index, voice in enumerate(voices):
        if not isinstance(voice, dict):
            continue
        if not (voice.get("name") or "").strip():
            errors.append(f"story.voices[{index}].name is required")
        source_type = voice.get("source_type")
        if not source_type:
            errors.append(f"story.voices[{index}].source_type is required")
        if source_type == "user_provided_consented" and not voice.get("consent_confirmed"):
            errors.append(
                f"story.voices[{index}]: user_provided_consented requires consent_confirmed"
            )

    all_shot_ids = _collect_all_shot_client_ids(story)
    planned = 0.0
    shot_count = 0
    for c_index, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            errors.append(f"story.chapters[{c_index}] must be an object")
            continue
        if not (chapter.get("title") or "").strip():
            errors.append(f"story.chapters[{c_index}].title is required")
        scenes = chapter.get("scenes") or []
        if not isinstance(scenes, list):
            errors.append(f"story.chapters[{c_index}].scenes must be a list")
            continue
        _unique_client_ids(scenes, f"story.chapters[{c_index}].scenes", errors)
        _check_order_indexes(scenes, f"story.chapters[{c_index}].scenes", errors)
        for s_index, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                errors.append(f"story.chapters[{c_index}].scenes[{s_index}] must be an object")
                continue
            if not (scene.get("title") or "").strip():
                errors.append(f"story.chapters[{c_index}].scenes[{s_index}].title is required")
            shots = scene.get("shots") or []
            if not isinstance(shots, list):
                errors.append(
                    f"story.chapters[{c_index}].scenes[{s_index}].shots must be a list"
                )
                continue
            _unique_client_ids(
                shots, f"story.chapters[{c_index}].scenes[{s_index}].shots", errors
            )
            _check_order_indexes(
                shots, f"story.chapters[{c_index}].scenes[{s_index}].shots", errors
            )
            for sh_index, shot in enumerate(shots):
                if not isinstance(shot, dict):
                    errors.append(
                        f"story.chapters[{c_index}].scenes[{s_index}].shots[{sh_index}] must be an object"
                    )
                    continue
                shot_path = f"story.chapters[{c_index}].scenes[{s_index}].shots[{sh_index}]"
                planned += _validate_shot(
                    shot,
                    shot_path,
                    character_ids,
                    voice_ids,
                    all_shot_ids,
                    errors,
                    warnings,
                )
                shot_count += 1

                # Factual reference checks when catalogs are provided.
                for r_index, rec in enumerate(shot.get("model_recommendations") or []):
                    if not isinstance(rec, dict):
                        continue
                    variant_id = rec.get("generation_model_variant_id")
                    workflow_id = rec.get("workflow_template_id")
                    provider_profile_id = rec.get("provider_profile_id")
                    if (
                        known_model_variant_ids is not None
                        and variant_id is not None
                        and str(variant_id) not in known_model_variant_ids
                    ):
                        errors.append(
                            f"{shot_path}.model_recommendations[{r_index}].generation_model_variant_id "
                            "is not a factual registry reference"
                        )
                    if (
                        known_workflow_template_ids is not None
                        and workflow_id is not None
                        and str(workflow_id) not in known_workflow_template_ids
                    ):
                        errors.append(
                            f"{shot_path}.model_recommendations[{r_index}].workflow_template_id "
                            "is not a factual registry reference"
                        )
                    if (
                        known_provider_profile_ids is not None
                        and provider_profile_id is not None
                        and str(provider_profile_id) not in known_provider_profile_ids
                    ):
                        errors.append(
                            f"{shot_path}.model_recommendations[{r_index}].provider_profile_id "
                            "is not a factual registry reference"
                        )

                asset_id = shot.get("starting_image_asset_id")
                if (
                    known_asset_ids is not None
                    and asset_id is not None
                    and str(asset_id) not in known_asset_ids
                ):
                    errors.append(
                        f"{shot_path}.starting_image_asset_id is not a factual planning asset reference"
                    )

    if not chapters:
        errors.append("story.chapters must contain at least one chapter")
    if shot_count == 0:
        errors.append("story must contain at least one shot")

    if target_value is not None:
        # Exact duration: planned sum must equal target (float-safe to 4 decimal places).
        if round(planned - target_value, 4) != 0:
            errors.append(
                f"exact duration mismatch: planned {planned:g}s != target {target_value:g}s"
            )
        report["planned_duration_sec"] = planned
        report["target_duration_sec"] = target_value
        report["discrepancy_sec"] = round(planned - target_value, 4)

    _validate_continuity_order(story, errors)
    _validate_approved_voice_preservation(story, base_snapshot, errors)

    report["shot_count"] = shot_count
    report["character_count"] = len(character_ids)
    report["voice_count"] = len(voice_ids)
    report["checks"].append("structure")
    report["checks"].append("duration")
    report["checks"].append("continuity")
    report["checks"].append("references")
    report["checks"].append("qwen_policy")
    return errors, warnings, report


class ProposalValidator:
    def validate(
        self,
        proposal: AIProposal,
        *,
        base_snapshot: dict[str, Any] | None = None,
        known_model_variant_ids: set[str] | None = None,
        known_workflow_template_ids: set[str] | None = None,
        known_provider_profile_ids: set[str] | None = None,
        known_asset_ids: set[str] | None = None,
    ) -> ProposalValidationResult:
        dumped = proposal.model_dump()
        forbidden = _scan_forbidden(dumped)
        errors = [f"Forbidden proposal field: {item}" for item in forbidden]
        warnings: list[str] = []
        report: dict[str, Any] = {}

        if proposal.proposal_type in STORYBOARD_PROPOSAL_TYPES:
            schema_name = proposal.schema_name or proposal.payload.get("schema_name")
            if schema_name not in (None, STORYBOARD_PROPOSAL_SCHEMA_NAME):
                errors.append(f"schema_name must be {STORYBOARD_PROPOSAL_SCHEMA_NAME}")
            sb_errors, sb_warnings, report = validate_storyboard_payload(
                proposal.payload,
                base_snapshot=base_snapshot,
                known_model_variant_ids=known_model_variant_ids,
                known_workflow_template_ids=known_workflow_template_ids,
                known_provider_profile_ids=known_provider_profile_ids,
                known_asset_ids=known_asset_ids,
            )
            errors.extend(sb_errors)
            warnings.extend(sb_warnings)

        if errors:
            status = "invalid"
            accepted = False
        elif warnings:
            status = "needs_review"
            accepted = True
        else:
            status = "valid"
            accepted = True

        return ProposalValidationResult(
            accepted=accepted,
            errors=errors,
            warnings=warnings,
            validation_status=status,
            content_hash=content_hash_for(proposal.payload),
            report=report,
        )

    def assert_valid(self, proposal: AIProposal, **kwargs: Any) -> None:
        result = self.validate(proposal, **kwargs)
        if not result.accepted or result.errors:
            raise ForbiddenProposalError("; ".join(result.errors) or "Proposal validation failed")
