"""Deterministic hashing for planning inputs, outputs, and provider invocations."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def _normalize(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _normalize(value[k]) for k in sorted(value.keys(), key=lambda x: str(x))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        # Stable JSON float representation
        return float(f"{value:.10g}")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(_normalize(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_hex(value: Any) -> str:
    payload = value if isinstance(value, (bytes, bytearray)) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_input_hash(
    *,
    story_id: UUID,
    base_storyboard_version_id: UUID | None,
    target_duration_sec: float | None,
    routing_snapshot: dict[str, Any],
    task_types: list[str],
) -> str:
    return sha256_hex(
        {
            "story_id": str(story_id),
            "base_storyboard_version_id": str(base_storyboard_version_id) if base_storyboard_version_id else None,
            "target_duration_sec": target_duration_sec,
            "routing_snapshot": routing_snapshot,
            "task_types": list(task_types),
        }
    )


def step_input_hash(
    *,
    run_id: UUID,
    sequence_index: int,
    task_type: str,
    context_hash: str,
    attempt_number: int,
    logical_model: str | None,
    provider_identifier: str | None,
    repair_instructions: list[str] | None = None,
) -> str:
    return sha256_hex(
        {
            "run_id": str(run_id),
            "sequence_index": sequence_index,
            "task_type": task_type,
            "context_hash": context_hash,
            "attempt_number": attempt_number,
            "logical_model": logical_model,
            "provider_identifier": provider_identifier,
            "repair_instructions": repair_instructions or [],
        }
    )


def request_hash(request_payload: dict[str, Any]) -> str:
    # Exclude volatile fields that must not affect idempotency of content.
    body = dict(request_payload)
    body.pop("idempotency_key", None)
    return sha256_hex(body)


def response_hash(response_payload: dict[str, Any]) -> str:
    body = dict(response_payload)
    # usage is advisory; hash semantic payload only
    body.pop("usage", None)
    return sha256_hex(body)


def proposal_content_hash(payload: dict[str, Any]) -> str:
    return sha256_hex(payload)


def invocation_idempotency_key(
    *,
    run_id: UUID,
    step_id: UUID,
    provider_identifier: str,
    request_hash_value: str,
    attempt_number: int,
) -> str:
    raw = sha256_hex(
        {
            "run_id": str(run_id),
            "step_id": str(step_id),
            "provider_identifier": provider_identifier,
            "request_hash": request_hash_value,
            "attempt_number": attempt_number,
        }
    )
    return f"inv_{raw[:120]}"
