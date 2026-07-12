from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass


RESULT_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "summary", "patches", "findings", "tests", "blockers"],
    "properties": {
        "status": {"type": "string", "enum": ["completed", "blocked", "failed"]},
        "summary": {"type": "string", "maxLength": 12000},
        "patches": {
            "type": "array",
            "maxItems": 128,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "action", "expected_sha256", "content"],
                "properties": {
                    "path": {"type": "string", "maxLength": 512},
                    "action": {"type": "string", "enum": ["create", "replace"]},
                    "expected_sha256": {"type": ["string", "null"], "maxLength": 64},
                    "content": {"type": "string", "maxLength": 4000000},
                },
            },
        },
        "findings": {"type": "array", "maxItems": 256, "items": {"type": "string", "maxLength": 4000}},
        "tests": {"type": "array", "maxItems": 64, "items": {"type": "string", "maxLength": 256}},
        "blockers": {"type": "array", "maxItems": 64, "items": {"type": "string", "maxLength": 4000}},
    },
}

RESULT_SCHEMA_JSON = json.dumps(RESULT_SCHEMA, separators=(",", ":"), sort_keys=True)
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True, slots=True)
class FilePatch:
    path: str
    action: str
    expected_sha256: str | None
    content: str


@dataclass(frozen=True, slots=True)
class ImplementationResult:
    status: str
    summary: str
    patches: tuple[FilePatch, ...]
    findings: tuple[str, ...]
    tests: tuple[str, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "patches": [
                {
                    "path": patch.path,
                    "action": patch.action,
                    "expected_sha256": patch.expected_sha256,
                    "content": patch.content,
                }
                for patch in self.patches
            ],
            "findings": list(self.findings),
            "tests": list(self.tests),
            "blockers": list(self.blockers),
        }

    def as_artifact_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "patches": [
                {
                    "path": patch.path,
                    "action": patch.action,
                    "expected_sha256": patch.expected_sha256,
                    "content_sha256": hashlib.sha256(patch.content.encode("utf-8")).hexdigest(),
                    "content_bytes": len(patch.content.encode("utf-8")),
                }
                for patch in self.patches
            ],
            "findings": list(self.findings),
            "tests": list(self.tests),
            "blockers": list(self.blockers),
        }


def _string_list(value: object, field: str, maximum: int, item_maximum: int) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or not all(isinstance(item, str) and len(item) <= item_maximum for item in value)
    ):
        raise ValueError(f"invalid {field}")
    return tuple(value)


def parse_implementation_result(envelope: object, expected_session_id: str) -> ImplementationResult:
    if not isinstance(envelope, dict):
        raise ValueError("Grok envelope must be an object")
    allowed = {
        "text",
        "stopReason",
        "sessionId",
        "requestId",
        "thought",
        "structuredOutput",
        "structuredOutputError",
    }
    required = {"text", "stopReason", "sessionId", "requestId"}
    unknown = sorted(set(envelope) - allowed)
    missing = sorted(required - set(envelope))
    if unknown or missing:
        raise ValueError(f"Grok envelope fields are invalid; unknown={unknown}; missing={missing}")
    if envelope["sessionId"] != expected_session_id:
        raise ValueError("Grok envelope session ID mismatch")
    if envelope["stopReason"] != "EndTurn":
        raise ValueError("Grok did not finish with EndTurn")
    try:
        uuid.UUID(str(envelope["requestId"]))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("Grok envelope request ID is invalid") from error
    if not isinstance(envelope["text"], str):
        raise ValueError("Grok envelope text must be a string")
    if "structuredOutput" in envelope:
        payload = envelope["structuredOutput"]
    elif "structuredOutputError" in envelope:
        try:
            payload = json.loads(envelope["text"])
        except json.JSONDecodeError as error:
            raise ValueError("Grok structured-output fallback text is not valid JSON") from error
    else:
        raise ValueError("Grok envelope has no structured result")
    if not isinstance(payload, dict):
        raise ValueError("Grok result must be an object")
    expected_fields = {"status", "summary", "patches", "findings", "tests", "blockers"}
    if set(payload) != expected_fields:
        raise ValueError("Grok result has missing or unknown fields")
    status = payload["status"]
    summary = payload["summary"]
    if (
        status not in {"completed", "blocked", "failed"}
        or not isinstance(summary, str)
        or len(summary) > 12000
    ):
        raise ValueError("Grok result status or summary is invalid")
    raw_patches = payload["patches"]
    if not isinstance(raw_patches, list) or len(raw_patches) > 128:
        raise ValueError("Grok result patches are invalid")
    patches: list[FilePatch] = []
    for raw in raw_patches:
        if not isinstance(raw, dict) or set(raw) != {"path", "action", "expected_sha256", "content"}:
            raise ValueError("Grok patch has missing or unknown fields")
        path, action, expected, content = raw["path"], raw["action"], raw["expected_sha256"], raw["content"]
        if not isinstance(path, str) or not path or len(path) > 512:
            raise ValueError("Grok patch path is invalid")
        if (
            action not in {"create", "replace"}
            or not isinstance(content, str)
            or len(content) > 4000000
            or "\0" in content
        ):
            raise ValueError("Grok patch action or content is invalid")
        if expected is not None and (not isinstance(expected, str) or not _SHA256.fullmatch(expected)):
            raise ValueError("Grok patch expected SHA-256 is invalid")
        if action == "create" and expected is not None:
            raise ValueError("create patches cannot declare an expected SHA-256")
        if action == "replace" and expected is None:
            raise ValueError("replace patches require an expected SHA-256")
        patches.append(FilePatch(path=path, action=action, expected_sha256=expected, content=content))
    return ImplementationResult(
        status=status,
        summary=summary,
        patches=tuple(patches),
        findings=_string_list(payload["findings"], "findings", 256, 4000),
        tests=_string_list(payload["tests"], "tests", 64, 256),
        blockers=_string_list(payload["blockers"], "blockers", 64, 4000),
    )
