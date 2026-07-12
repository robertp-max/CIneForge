"""OpenAI planning provider adapter (Storyboard Phase 1).

Uses existing HTTP dependencies only (httpx). Never persists credentials,
never logs full request/response payloads, never emits chain-of-thought,
and never accepts shell commands or executable paths.

Transient transport failures raise TransportError (eligible for bounded
retry). Schema, semantic, and policy rejections return a failed
ProviderResponseContract with retryable=False and are never retried here.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable
from uuid import UUID

import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.orchestration import (
    FailureCategory,
    LogicalModelProfile,
    PlanningTaskType,
    ProviderRequestContract,
    ProviderResponseContract,
    SanitizedError,
)
from backend.app.services.planning.contracts import (
    FORBIDDEN_PAYLOAD_KEYS,
    REQUIRED_KEYS,
    validate_provider_response,
)
from backend.app.services.planning.errors import sanitize_message
from backend.app.services.planning.hashes import request_hash, response_hash
from backend.app.services.planning.provider import PlanningProvider, TransportError

logger = logging.getLogger(__name__)

# Transient HTTP statuses eligible for bounded transport retry.
_TRANSIENT_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

_SYSTEM_RULES = (
    "You are a CineForge storyboard planning assistant. "
    "Return ONLY a single JSON object matching the requested task schema. "
    "Do not include chain-of-thought, reasoning, scratchpad, thinking, "
    "hidden_reasoning, credentials, api keys, shell commands, ffmpeg, "
    "ComfyUI payloads, installers, model downloads, or executable paths. "
    "Do not invent execution side effects. Planning output only."
)


def _json_schema_for_task(task: PlanningTaskType) -> dict[str, Any]:
    """Minimal JSON Schema fragments for structured-output requests."""
    base_props: dict[str, Any]
    required: list[str]

    if task == PlanningTaskType.story_structure:
        base_props = {
            "summary": {"type": "string"},
            "acts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "target_pct": {"type": "number"},
                    },
                    "required": ["name", "target_pct"],
                    "additionalProperties": True,
                },
            },
            "target_duration_sec": {"type": "number"},
        }
        required = ["summary", "acts", "target_duration_sec"]
    elif task == PlanningTaskType.character_bible:
        base_props = {
            "summary": {"type": "string"},
            "characters": {"type": "array", "items": {"type": "object"}},
        }
        required = ["summary", "characters"]
    elif task == PlanningTaskType.chapter_outline:
        base_props = {
            "summary": {"type": "string"},
            "chapters": {"type": "array", "items": {"type": "object"}},
        }
        required = ["summary", "chapters"]
    elif task == PlanningTaskType.scene_breakdown:
        base_props = {
            "summary": {"type": "string"},
            "scenes": {"type": "array", "items": {"type": "object"}},
        }
        required = ["summary", "scenes"]
    elif task == PlanningTaskType.shot_list:
        base_props = {
            "summary": {"type": "string"},
            "shots": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "order_index": {"type": "integer"},
                        "title": {"type": "string"},
                        "duration_sec": {"type": "number"},
                        "visual_description": {"type": "string"},
                    },
                    "required": ["order_index", "duration_sec"],
                    "additionalProperties": True,
                },
            },
        }
        required = ["summary", "shots"]
    elif task == PlanningTaskType.narration_plan:
        base_props = {
            "summary": {"type": "string"},
            "narrations": {"type": "array", "items": {"type": "object"}},
        }
        required = ["summary", "narrations"]
    elif task == PlanningTaskType.prompt_package:
        base_props = {
            "summary": {"type": "string"},
            "prompt_packages": {"type": "array", "items": {"type": "object"}},
        }
        required = ["summary", "prompt_packages"]
    elif task == PlanningTaskType.continuity_plan:
        base_props = {
            "summary": {"type": "string"},
            "continuity": {"type": "array", "items": {"type": "object"}},
        }
        required = ["summary", "continuity"]
    elif task == PlanningTaskType.model_recommendation:
        base_props = {
            "summary": {"type": "string"},
            "recommendations": {"type": "array", "items": {"type": "object"}},
        }
        required = ["summary", "recommendations"]
    elif task == PlanningTaskType.production_proposal:
        base_props = {
            "summary": {"type": "string"},
            "shots": {"type": "array", "items": {"type": "object"}},
            "target_duration_sec": {"type": "number"},
            "chapters": {"type": "array", "items": {"type": "object"}},
            "characters": {"type": "array", "items": {"type": "object"}},
            "voices": {"type": "array", "items": {"type": "object"}},
            "narrations": {"type": "array", "items": {"type": "object"}},
            "prompt_packages": {"type": "array", "items": {"type": "object"}},
            "continuity": {"type": "array", "items": {"type": "object"}},
            "model_recommendations": {"type": "array", "items": {"type": "object"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
        }
        required = ["summary", "shots", "target_duration_sec"]
    else:
        base_props = {"summary": {"type": "string"}}
        required = ["summary"]

    return {
        "type": "object",
        "properties": base_props,
        "required": required,
        "additionalProperties": True,
    }


def _context_brief(request: ProviderRequestContract) -> dict[str, Any]:
    """Bounded context for the model — no secrets."""
    ctx = request.context
    return {
        "story_id": str(ctx.story_id),
        "title": ctx.title,
        "base_story": ctx.base_story[:4000],
        "target_duration_sec": ctx.target_duration_sec,
        "logline": (ctx.logline or "")[:500] or None,
        "synopsis": (ctx.synopsis or "")[:1500] or None,
        "audience": ctx.audience,
        "tone": ctx.tone,
        "genre": ctx.genre,
        "visual_style": ctx.visual_style,
        "point_of_view": ctx.point_of_view,
        "production_notes": (ctx.production_notes or "")[:1000] or None,
        "characters": (ctx.characters or [])[:24],
    }


def _failed(
    request: ProviderRequestContract,
    *,
    category: FailureCategory,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
    finish_category: str | None = None,
) -> ProviderResponseContract:
    return ProviderResponseContract(
        task_type=request.task_type,
        status="failed",
        payload={},
        error=SanitizedError(
            category=category,
            message=sanitize_message(message)[:500],
            retryable=retryable,
            details=details or {},
        ),
        usage=usage or {},
        finish_category=finish_category or category.value,
    )


class OpenAIPlanningProvider(PlanningProvider):
    """Hosted OpenAI chat-completions adapter for planning tasks only."""

    identifier = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_sec: float = 60.0,
        wall_time_sec: float = 120.0,
        transport_retries: int = 2,
        max_response_bytes: int = 524_288,
        repair_instruction_limit: int = 12,
        model_luna: str = "gpt-4o-mini",
        model_terra: str = "gpt-4o",
        model_sol: str = "gpt-4.1",
        http_client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ValueError("OpenAI API key is required when constructing OpenAIPlanningProvider")
        if any(ch in key for ch in ("\n", "\r", "\x00")):
            raise ValueError("OpenAI API key contains invalid characters")

        self._api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = float(timeout_sec)
        self.wall_time_sec = float(wall_time_sec)
        self.transport_retries = max(0, int(transport_retries))
        self.max_response_bytes = int(max_response_bytes)
        self.repair_instruction_limit = max(0, int(repair_instruction_limit))
        self.model_luna = model_luna
        self.model_terra = model_terra
        self.model_sol = model_sol
        self._http_client_factory = http_client_factory
        # In-process idempotency cache for identical keys within this instance.
        self._idempotency_cache: dict[str, ProviderResponseContract] = {}

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> OpenAIPlanningProvider:
        cfg = settings or get_settings()
        if not cfg.openai_configured:
            raise ValueError("OpenAI planning provider is not configured")
        assert cfg.openai_api_key is not None
        return cls(
            api_key=cfg.openai_api_key.get_secret_value(),
            base_url=cfg.openai_base_url,
            timeout_sec=cfg.openai_timeout_sec,
            wall_time_sec=cfg.openai_wall_time_sec,
            transport_retries=cfg.openai_transport_retries,
            max_response_bytes=cfg.openai_max_response_bytes,
            repair_instruction_limit=cfg.openai_repair_instruction_limit,
            model_luna=cfg.openai_logical_model_luna,
            model_terra=cfg.openai_logical_model_terra,
            model_sol=cfg.openai_logical_model_sol,
        )

    def resolve_logical_model(self, profile: LogicalModelProfile) -> str:
        mapping = {
            LogicalModelProfile.luna: self.model_luna,
            LogicalModelProfile.terra: self.model_terra,
            LogicalModelProfile.sol: self.model_sol,
        }
        return mapping[profile]

    def invoke(self, request: ProviderRequestContract) -> ProviderResponseContract:
        if request.provider_identifier not in {self.identifier, "openai"}:
            return _failed(
                request,
                category=FailureCategory.routing,
                message=f"OpenAI provider cannot serve provider_identifier={request.provider_identifier}",
            )

        cached = self._idempotency_cache.get(request.idempotency_key)
        if cached is not None:
            # Idempotent replay — return prior contract without re-calling the network.
            usage = dict(cached.usage or {})
            usage["idempotent_replay"] = True
            return cached.model_copy(update={"usage": usage})

        req_dump = request.model_dump(mode="json")
        # Strip nothing sensitive beyond contract; never log the dump.
        req_hash = request_hash(req_dump)
        resolved_model = self.resolve_logical_model(request.logical_model)

        body = self._build_request_body(request, resolved_model=resolved_model)
        deadline = time.monotonic() + self.wall_time_sec
        last_transport: str | None = None

        for attempt in range(self.transport_retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError("OpenAI planning wall-time budget exceeded")

            timeout = min(self.timeout_sec, max(0.1, remaining))
            try:
                raw_bytes, status_code, headers = self._post_chat_completions(
                    body=body,
                    idempotency_key=request.idempotency_key,
                    timeout=timeout,
                )
            except TransportError as te:
                last_transport = te.message
                if attempt < self.transport_retries:
                    logger.info(
                        "openai_planning_transport_retry attempt=%s limit=%s request_hash=%s message=%s",
                        attempt + 1,
                        self.transport_retries,
                        req_hash,
                        te.message,
                    )
                    continue
                raise

            # Byte bound before JSON parse.
            if len(raw_bytes) > self.max_response_bytes:
                return _failed(
                    request,
                    category=FailureCategory.provider,
                    message=(
                        f"OpenAI response exceeded max_response_bytes "
                        f"({len(raw_bytes)} > {self.max_response_bytes})"
                    ),
                    usage={
                        "request_hash": req_hash,
                        "logical_model": request.logical_model.value,
                        "resolved_model": resolved_model,
                        "response_bytes": len(raw_bytes),
                    },
                    finish_category="response_too_large",
                )

            if status_code in _TRANSIENT_STATUS:
                last_transport = f"OpenAI transient HTTP {status_code}"
                if attempt < self.transport_retries:
                    logger.info(
                        "openai_planning_transport_retry attempt=%s limit=%s request_hash=%s status=%s",
                        attempt + 1,
                        self.transport_retries,
                        req_hash,
                        status_code,
                    )
                    continue
                raise TransportError(last_transport)

            # Non-retryable HTTP failures (auth, policy, bad request, etc.).
            if status_code == 401 or status_code == 403:
                return _failed(
                    request,
                    category=FailureCategory.provider,
                    message=f"OpenAI authentication/authorization failed (HTTP {status_code})",
                    usage={
                        "request_hash": req_hash,
                        "logical_model": request.logical_model.value,
                        "resolved_model": resolved_model,
                    },
                    finish_category="auth_failed",
                )

            if status_code == 400:
                # Schema / request rejection — never retry.
                return _failed(
                    request,
                    category=FailureCategory.validation,
                    message="OpenAI rejected the planning request (HTTP 400 schema/policy)",
                    details={"http_status": 400},
                    usage={
                        "request_hash": req_hash,
                        "logical_model": request.logical_model.value,
                        "resolved_model": resolved_model,
                    },
                    finish_category="schema_rejected",
                )

            if status_code != 200:
                return _failed(
                    request,
                    category=FailureCategory.provider,
                    message=f"OpenAI provider error (HTTP {status_code})",
                    details={"http_status": status_code},
                    usage={
                        "request_hash": req_hash,
                        "logical_model": request.logical_model.value,
                        "resolved_model": resolved_model,
                    },
                    finish_category="http_error",
                )

            return self._parse_success(
                request=request,
                raw_bytes=raw_bytes,
                req_hash=req_hash,
                resolved_model=resolved_model,
                headers=headers,
            )

        raise TransportError(last_transport or "OpenAI transport failed after retries")

    def _build_request_body(
        self,
        request: ProviderRequestContract,
        *,
        resolved_model: str,
    ) -> dict[str, Any]:
        required = sorted(REQUIRED_KEYS.get(request.task_type, {"summary"}))
        repair = [
            str(item)[:300]
            for item in (request.repair_instructions or [])[: self.repair_instruction_limit]
            if item and str(item).strip()
        ]
        user_payload = {
            "task_type": request.task_type.value,
            "logical_model": request.logical_model.value,
            "required_keys": required,
            "forbidden_keys": sorted(FORBIDDEN_PAYLOAD_KEYS),
            "context": _context_brief(request),
            "constraints": {
                k: v
                for k, v in (request.constraints or {}).items()
                if str(k).lower()
                not in {
                    "api_key",
                    "credentials",
                    "shell_command",
                    "cli_command",
                    "executable",
                    "command",
                }
            },
            "previous_output": request.previous_output,
            "repair_instructions": repair,
            "attempt_number": request.attempt_number,
            "instructions": (
                f"Produce the JSON payload for task_type={request.task_type.value}. "
                f"Required top-level keys: {', '.join(required)}. "
                "Do not include any forbidden keys."
            ),
        }

        schema = _json_schema_for_task(request.task_type)
        return {
            "model": resolved_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _SYSTEM_RULES},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":")),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"planning_{request.task_type.value}",
                    "strict": False,
                    "schema": schema,
                },
            },
        }

    def _post_chat_completions(
        self,
        *,
        body: dict[str, Any],
        idempotency_key: str,
        timeout: float,
    ) -> tuple[bytes, int, dict[str, str]]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key[:128],
        }
        url = f"{self.base_url}/chat/completions"

        client: httpx.Client | None = None
        owns_client = False
        try:
            if self._http_client_factory is not None:
                client = self._http_client_factory()
            else:
                client = httpx.Client(timeout=timeout)
                owns_client = True

            try:
                response = client.post(url, headers=headers, json=body, timeout=timeout)
            except httpx.TimeoutException as exc:
                raise TransportError(f"OpenAI request timed out: {exc.__class__.__name__}") from exc
            except httpx.TransportError as exc:
                raise TransportError(f"OpenAI transport error: {exc.__class__.__name__}") from exc
            except httpx.HTTPError as exc:
                raise TransportError(f"OpenAI HTTP error: {exc.__class__.__name__}") from exc

            # Read with hard byte cap (+1 to detect overflow).
            content = response.content
            header_map = {k.lower(): v for k, v in response.headers.items()}
            # Never log body or Authorization.
            logger.info(
                "openai_planning_http status=%s bytes=%s request_id=%s",
                response.status_code,
                len(content),
                header_map.get("x-request-id") or header_map.get("openai-request-id") or "-",
            )
            return content, int(response.status_code), header_map
        finally:
            if owns_client and client is not None:
                client.close()

    def _parse_success(
        self,
        *,
        request: ProviderRequestContract,
        raw_bytes: bytes,
        req_hash: str,
        resolved_model: str,
        headers: dict[str, str],
    ) -> ProviderResponseContract:
        try:
            envelope = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _failed(
                request,
                category=FailureCategory.validation,
                message="OpenAI response was not valid JSON",
                usage={
                    "request_hash": req_hash,
                    "logical_model": request.logical_model.value,
                    "resolved_model": resolved_model,
                    "response_bytes": len(raw_bytes),
                },
                finish_category="invalid_json",
            )

        if not isinstance(envelope, dict):
            return _failed(
                request,
                category=FailureCategory.validation,
                message="OpenAI response envelope must be an object",
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
            )

        # Policy / safety refusals — never retry.
        if envelope.get("error"):
            err = envelope["error"]
            err_type = ""
            err_msg = "provider error"
            if isinstance(err, dict):
                err_type = str(err.get("type") or err.get("code") or "")
                err_msg = str(err.get("message") or err_msg)[:200]
            category = FailureCategory.provider
            if "content" in err_type.lower() or "policy" in err_type.lower() or "safety" in err_msg.lower():
                category = FailureCategory.provider
            return _failed(
                request,
                category=category,
                message=sanitize_message(f"OpenAI error: {err_msg}"),
                details={"error_type": err_type[:80]} if err_type else {},
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
                finish_category="provider_error",
            )

        choices = envelope.get("choices")
        if not isinstance(choices, list) or not choices:
            return _failed(
                request,
                category=FailureCategory.provider,
                message="OpenAI response missing choices",
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
            )

        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        refusal = message.get("refusal")
        if refusal:
            return _failed(
                request,
                category=FailureCategory.provider,
                message="OpenAI refused the planning request (policy)",
                details={"finish_reason": str(first.get("finish_reason") or "refusal")[:80]},
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
                finish_category="policy_refusal",
            )

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return _failed(
                request,
                category=FailureCategory.validation,
                message="OpenAI response content was empty",
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
                finish_category="empty_content",
            )

        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return _failed(
                request,
                category=FailureCategory.validation,
                message="OpenAI message content was not valid JSON",
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
                finish_category="invalid_content_json",
            )

        if not isinstance(payload, dict):
            return _failed(
                request,
                category=FailureCategory.validation,
                message="Planning payload must be a JSON object",
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
            )

        usage_raw = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
        usage: dict[str, Any] = {
            "input_tokens": usage_raw.get("prompt_tokens"),
            "output_tokens": usage_raw.get("completion_tokens"),
            "total_tokens": usage_raw.get("total_tokens"),
            "logical_model": request.logical_model.value,
            "resolved_model": resolved_model,
            "request_hash": req_hash,
            "provider_request_id": headers.get("x-request-id") or headers.get("openai-request-id"),
        }

        try:
            response = ProviderResponseContract(
                task_type=request.task_type,
                status="succeeded",
                payload=payload,
                warnings=[],
                usage=usage,
                finish_category=str(first.get("finish_reason") or "stop"),
            )
        except Exception as exc:  # pydantic / forbidden-field validation
            return _failed(
                request,
                category=FailureCategory.validation,
                message=f"Response contract validation failed: {exc}",
                usage={"request_hash": req_hash, "resolved_model": resolved_model},
                finish_category="contract_violation",
            )

        # Strict post-parse validation (required keys, shot durations, etc.).
        # Failures here are semantic/schema — never retried at transport layer.
        errors = validate_provider_response(response, expected_task=request.task_type)
        if errors:
            return _failed(
                request,
                category=FailureCategory.validation,
                message="; ".join(errors)[:500],
                details={"validation_errors": errors[:10]},
                usage={
                    "request_hash": req_hash,
                    "resolved_model": resolved_model,
                    "logical_model": request.logical_model.value,
                },
                finish_category="validation_failed",
            )

        resp_hash = response_hash(response.model_dump(mode="json"))
        usage["response_hash"] = resp_hash
        response = response.model_copy(update={"usage": usage})

        # Cache successful idempotent result only.
        self._idempotency_cache[request.idempotency_key] = response
        return response


def build_openai_provider_from_settings(settings: Settings | None = None) -> OpenAIPlanningProvider | None:
    """Return an OpenAI provider when configured; otherwise None (mock remains default)."""
    cfg = settings or get_settings()
    if not cfg.openai_configured:
        return None
    return OpenAIPlanningProvider.from_settings(cfg)


# Silence unused UUID import risk if re-exports change — keep story id typing free.
_ = UUID
