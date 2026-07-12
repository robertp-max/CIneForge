"""Strict validation and localized semantic repair helpers."""

from __future__ import annotations

from typing import Any

from backend.app.schemas.orchestration import (
    PlanningTaskType,
    ProposalPayloadContract,
    ProviderResponseContract,
)
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
    story_id: Any,
    run_id: Any,
    base_storyboard_version_id: Any,
    target_duration_sec: float,
    title: str,
    merged: dict[str, Any],
    production_payload: dict[str, Any] | None,
) -> ProposalPayloadContract:
    src = dict(production_payload or {})
    # Prefer explicit production payload fields; fall back to merged task outputs.
    chapters = src.get("chapters") or merged.get("chapters") or []
    characters = src.get("characters") or merged.get("characters") or []
    voices = src.get("voices") or merged.get("voices") or []
    shots = src.get("shots") or merged.get("shots") or []
    narrations = src.get("narrations") or merged.get("narrations") or []
    prompt_packages = src.get("prompt_packages") or merged.get("prompt_packages") or []
    continuity = src.get("continuity") or merged.get("continuity") or []
    model_recs = (
        src.get("model_recommendations")
        or src.get("recommendations")
        or merged.get("model_recommendations")
        or merged.get("recommendations")
        or []
    )
    warnings = list(src.get("warnings") or []) + list(merged.get("warnings") or [])
    summary = str(src.get("summary") or f"Planning proposal for {title}").strip()

    try:
        return ProposalPayloadContract(
            summary=summary[:1000],
            story_id=story_id,
            orchestration_run_id=run_id,
            base_storyboard_version_id=base_storyboard_version_id,
            target_duration_sec=float(src.get("target_duration_sec") or target_duration_sec),
            chapters=list(chapters),
            characters=list(characters),
            voices=list(voices),
            shots=list(shots),
            narrations=list(narrations),
            prompt_packages=list(prompt_packages),
            continuity=list(continuity),
            model_recommendations=list(model_recs),
            warnings=[str(w)[:300] for w in warnings][:50],
            metadata={
                "awaiting_review": True,
                "auto_applied": False,
                "immutable": True,
            },
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
