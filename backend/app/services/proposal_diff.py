"""Deterministic storyboard proposal diffs.

Ops are stable: sorted by path, then by op name. Values are compared via
canonical JSON so key order never affects equality.
"""

from __future__ import annotations

from typing import Any

from backend.app.services.ai_orchestration.validator import canonical_json


def _is_mapping(value: Any) -> bool:
    return isinstance(value, dict)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, list)


def _identity_key(item: Any, index: int) -> str:
    if isinstance(item, dict):
        for key in ("client_id", "id", "existing_id"):
            if item.get(key) is not None:
                return str(item[key])
    return f"#{index}"


def _sorted_dict_items(value: dict[str, Any]) -> list[tuple[str, Any]]:
    return sorted(value.items(), key=lambda pair: pair[0])


def diff_values(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    """Return deterministic replace/add/remove ops between two JSON-like values."""
    ops: list[dict[str, Any]] = []

    if _is_mapping(before) and _is_mapping(after):
        before_keys = set(before)
        after_keys = set(after)
        for key in sorted(before_keys - after_keys):
            ops.append({"op": "remove", "path": f"{path}.{key}", "before": before[key], "after": None})
        for key in sorted(after_keys - before_keys):
            ops.append({"op": "add", "path": f"{path}.{key}", "before": None, "after": after[key]})
        for key in sorted(before_keys & after_keys):
            ops.extend(diff_values(before[key], after[key], f"{path}.{key}"))
        return ops

    if _is_sequence(before) and _is_sequence(after):
        before_map = {_identity_key(item, index): item for index, item in enumerate(before)}
        after_map = {_identity_key(item, index): item for index, item in enumerate(after)}
        for key in sorted(set(before_map) - set(after_map)):
            ops.append(
                {
                    "op": "remove",
                    "path": f"{path}[{key}]",
                    "before": before_map[key],
                    "after": None,
                }
            )
        for key in sorted(set(after_map) - set(before_map)):
            ops.append(
                {
                    "op": "add",
                    "path": f"{path}[{key}]",
                    "before": None,
                    "after": after_map[key],
                }
            )
        for key in sorted(set(before_map) & set(after_map)):
            ops.extend(diff_values(before_map[key], after_map[key], f"{path}[{key}]"))
        return ops

    if canonical_json(before) != canonical_json(after):
        ops.append({"op": "replace", "path": path, "before": before, "after": after})
    return ops


def diff_storyboard_payloads(base_payload: dict[str, Any] | None, proposed_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Diff two proposal payloads; missing base is treated as empty object."""
    base = base_payload if isinstance(base_payload, dict) else {}
    proposed = proposed_payload if isinstance(proposed_payload, dict) else {}
    ops = diff_values(base, proposed, "$")
    # Final stable ordering: path, then op.
    ops.sort(key=lambda item: (item["path"], item["op"]))
    return ops


def diff_snapshot_to_proposal(
    base_snapshot: dict[str, Any] | None,
    proposed_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Diff an aggregate/version snapshot against the proposal story subtree."""
    proposed_story = proposed_payload.get("story") if isinstance(proposed_payload, dict) else {}
    base_story = None
    if isinstance(base_snapshot, dict):
        # Snapshots from aggregate() nest under "story" plus sibling collections.
        if "story" in base_snapshot or "chapters" in base_snapshot:
            base_story = {
                **(base_snapshot.get("story") or {}),
                "characters": base_snapshot.get("characters") or [],
                "voices": base_snapshot.get("voices") or [],
                "chapters": base_snapshot.get("chapters") or [],
            }
        else:
            base_story = base_snapshot
    return diff_values(base_story or {}, proposed_story or {}, "$.story")
