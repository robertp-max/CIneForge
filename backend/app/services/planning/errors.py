"""Sanitized planning errors — no stack traces, secrets, or hidden reasoning."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from backend.app.schemas.orchestration import FailureCategory, SanitizedError


class PlanningErrorCode(StrEnum):
    STORY_NOT_FOUND = "story_not_found"
    ACTIVE_RUN_EXISTS = "active_run_exists"
    RUN_NOT_FOUND = "run_not_found"
    INVALID_TRANSITION = "invalid_transition"
    ALREADY_TERMINAL = "already_terminal"
    ROUTING_FAILED = "routing_failed"
    CONTRACT_VIOLATION = "contract_violation"
    VALIDATION_FAILED = "validation_failed"
    PROVIDER_FAILED = "provider_failed"
    TRANSPORT_FAILED = "transport_failed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIME_BUDGET_EXCEEDED = "time_budget_exceeded"
    CANCELED = "canceled"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    INTERNAL = "internal"


_CODE_TO_CATEGORY: dict[PlanningErrorCode, FailureCategory] = {
    PlanningErrorCode.STORY_NOT_FOUND: FailureCategory.validation,
    PlanningErrorCode.ACTIVE_RUN_EXISTS: FailureCategory.validation,
    PlanningErrorCode.RUN_NOT_FOUND: FailureCategory.validation,
    PlanningErrorCode.INVALID_TRANSITION: FailureCategory.validation,
    PlanningErrorCode.ALREADY_TERMINAL: FailureCategory.validation,
    PlanningErrorCode.ROUTING_FAILED: FailureCategory.routing,
    PlanningErrorCode.CONTRACT_VIOLATION: FailureCategory.contract,
    PlanningErrorCode.VALIDATION_FAILED: FailureCategory.validation,
    PlanningErrorCode.PROVIDER_FAILED: FailureCategory.provider,
    PlanningErrorCode.TRANSPORT_FAILED: FailureCategory.transport,
    PlanningErrorCode.BUDGET_EXHAUSTED: FailureCategory.budget,
    PlanningErrorCode.TIME_BUDGET_EXCEEDED: FailureCategory.timeout,
    PlanningErrorCode.CANCELED: FailureCategory.canceled,
    PlanningErrorCode.IDEMPOTENCY_CONFLICT: FailureCategory.validation,
    PlanningErrorCode.INTERNAL: FailureCategory.internal,
}


# Substrings that must never appear in persisted/user-facing messages.
_REDACT_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "password",
    "secret",
    "chain_of_thought",
    "hidden_reasoning",
    "traceback",
    "file://",
    "sk-",
    "xai-",
)


def sanitize_message(message: str, *, max_length: int = 500) -> str:
    text = " ".join(str(message or "unknown error").split())
    lower = text.lower()
    for marker in _REDACT_MARKERS:
        if marker in lower:
            text = "An internal error occurred; sensitive details were redacted."
            break
    return text[:max_length] if text else "unknown error"


def sanitize_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if not details:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in details.items():
        key_text = str(key)
        if key_text.lower() in {
            "raw_prompt",
            "raw_response",
            "reasoning",
            "chain_of_thought",
            "credentials",
            "api_key",
            "authorization",
            "traceback",
            "stack",
            "exception",
        }:
            continue
        if isinstance(value, str):
            cleaned[key_text] = sanitize_message(value, max_length=300)
        elif isinstance(value, (int, float, bool)) or value is None:
            cleaned[key_text] = value
        elif isinstance(value, list):
            cleaned[key_text] = [
                sanitize_message(str(item), max_length=200) if isinstance(item, str) else item
                for item in value[:20]
            ]
        elif isinstance(value, dict):
            cleaned[key_text] = sanitize_details(value)
        else:
            cleaned[key_text] = sanitize_message(str(value), max_length=200)
    return cleaned


class PlanningError(Exception):
    """Domain error for the planning engine. Safe to surface after sanitization."""

    def __init__(
        self,
        code: PlanningErrorCode,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.category = _CODE_TO_CATEGORY.get(code, FailureCategory.internal)
        self.message = sanitize_message(message)
        self.retryable = retryable
        self.details = sanitize_details(details)
        super().__init__(self.message)

    def to_sanitized(self) -> SanitizedError:
        return SanitizedError(
            category=self.category,
            message=self.message,
            retryable=self.retryable,
            details={**self.details, "code": self.code.value},
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_sanitized().model_dump(mode="json")
