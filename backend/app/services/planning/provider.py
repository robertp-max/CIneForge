"""Provider-neutral planning provider interface and deterministic mock."""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from typing import Any

from backend.app.schemas.orchestration import (
    FailureCategory,
    PlanningTaskType,
    ProviderRequestContract,
    ProviderResponseContract,
    SanitizedError,
)
from backend.app.services.planning.errors import PlanningError, PlanningErrorCode, sanitize_message


class PlanningProvider(ABC):
    """Provider-neutral interface. Implementations must not call render/media systems."""

    identifier: str

    @abstractmethod
    def invoke(self, request: ProviderRequestContract) -> ProviderResponseContract:
        """Execute a single planning call. Must return a strict contract."""


class TransportError(Exception):
    """Transient transport failure eligible for bounded retry."""

    def __init__(self, message: str) -> None:
        self.message = sanitize_message(message)
        super().__init__(self.message)


class MockPlanningProvider(PlanningProvider):
    """Deterministic mock provider for tests and offline planning.

    Outputs are pure functions of the request contract (minus volatile fields).
    Supports simulated transport failures via constraints.simulate_transport_failures.
    """

    identifier = "mock"

    def __init__(self, *, fixed_latency_ms: int = 1) -> None:
        self.fixed_latency_ms = max(0, fixed_latency_ms)
        self._transport_fail_counts: dict[str, int] = {}

    def invoke(self, request: ProviderRequestContract) -> ProviderResponseContract:
        # Bounded simulated transport failures (per idempotency key).
        failures_wanted = int(request.constraints.get("simulate_transport_failures") or 0)
        if failures_wanted > 0:
            seen = self._transport_fail_counts.get(request.idempotency_key, 0)
            if seen < failures_wanted:
                self._transport_fail_counts[request.idempotency_key] = seen + 1
                raise TransportError(f"Simulated transport failure {seen + 1}/{failures_wanted}")

        if request.constraints.get("force_provider_error"):
            return ProviderResponseContract(
                task_type=request.task_type,
                status="failed",
                payload={},
                error=SanitizedError(
                    category=FailureCategory.provider,
                    message="Mock provider forced failure",
                    retryable=False,
                ),
            )

        # Deterministic seed from request content.
        seed_src = f"{request.task_type.value}|{request.context.story_id}|{request.attempt_number}|{request.logical_model.value}"
        seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest()[:8], 16)

        if self.fixed_latency_ms:
            time.sleep(min(self.fixed_latency_ms, 5) / 1000.0)

        payload = self._build_payload(request, seed)

        # Optional semantic defect for repair/escalation tests.
        if request.constraints.get("inject_schema_defect") and not request.repair_instructions:
            payload.pop("summary", None)

        return ProviderResponseContract(
            task_type=request.task_type,
            status="succeeded",
            payload=payload,
            warnings=[],
            usage={
                "input_tokens": 100 + (seed % 50),
                "output_tokens": 200 + (seed % 80),
                "logical_model": request.logical_model.value,
            },
            finish_category="stop",
        )

    def _build_payload(self, request: ProviderRequestContract, seed: int) -> dict[str, Any]:
        story = request.context
        duration = float(story.target_duration_sec)
        task = request.task_type

        if task == PlanningTaskType.story_structure:
            return {
                "summary": f"Structure for {story.title}",
                "acts": [
                    {"name": "Setup", "target_pct": 0.25},
                    {"name": "Confrontation", "target_pct": 0.5},
                    {"name": "Resolution", "target_pct": 0.25},
                ],
                "target_duration_sec": duration,
            }

        if task == PlanningTaskType.character_bible:
            chars = story.characters or [
                {"name": "Protagonist", "role": "lead"},
                {"name": "Narrator", "role": "voice"},
            ]
            return {
                "summary": f"Characters for {story.title}",
                "characters": [
                    {
                        "name": c.get("name", f"Character {i+1}"),
                        "role": c.get("role", "supporting"),
                        "physical_description": c.get("physical_description") or "Consistent wardrobe and silhouette",
                        "speaking_style": c.get("speaking_style") or "clear and grounded",
                        "consistency_prompt": c.get("consistency_prompt")
                        or f"Keep {c.get('name', 'character')} identity locked across shots",
                    }
                    for i, c in enumerate(chars[:12])
                ],
            }

        if task == PlanningTaskType.chapter_outline:
            chapter_count = max(1, min(4, int(duration // 60) or 1))
            return {
                "summary": f"{chapter_count} chapter outline",
                "chapters": [
                    {
                        "order_index": i,
                        "title": f"Chapter {i + 1}",
                        "summary": f"Beat cluster {i + 1} for {story.title}",
                    }
                    for i in range(chapter_count)
                ],
            }

        if task == PlanningTaskType.scene_breakdown:
            scene_count = max(2, min(8, int(duration // 20) or 2))
            return {
                "summary": f"{scene_count} scenes",
                "scenes": [
                    {
                        "order_index": i,
                        "chapter_order_index": 0,
                        "title": f"Scene {i + 1}",
                        "summary": f"Narrative beat {i + 1}",
                        "location": story.visual_style or "unspecified location",
                    }
                    for i in range(scene_count)
                ],
            }

        if task == PlanningTaskType.shot_list:
            # Prefer 6–12s shots within target duration.
            shot_dur = 8.0
            count = max(1, int(round(duration / shot_dur)))
            shots = []
            remaining = duration
            for i in range(count):
                d = min(12.0, max(6.0, remaining if i == count - 1 else shot_dur))
                if i == count - 1:
                    d = max(1.0, remaining)
                remaining = max(0.0, remaining - d)
                shots.append(
                    {
                        "order_index": i,
                        "scene_order_index": i % max(1, count // 2 or 1),
                        "title": f"Shot {i + 1}",
                        "duration_sec": round(d, 3),
                        "story_purpose": f"Advance beat {i + 1}",
                        "visual_description": f"Visual for {story.title} shot {i + 1}",
                        "continuity_source_type": "none" if i == 0 else "previous_shot",
                    }
                )
            return {"summary": f"{len(shots)} shots", "shots": shots}

        if task == PlanningTaskType.narration_plan:
            return {
                "summary": "Narration plan",
                "narrations": [
                    {
                        "shot_order_index": 0,
                        "narration_text": story.logline or story.base_story[:240],
                        "start_offset_sec": 0,
                        "expected_duration_sec": min(8.0, duration),
                    }
                ],
            }

        if task == PlanningTaskType.prompt_package:
            return {
                "summary": "Prompt packages",
                "prompt_packages": [
                    {
                        "shot_order_index": 0,
                        "image_prompt": f"{story.visual_style or 'cinematic'} establishing frame",
                        "video_prompt": f"Gentle camera move, {story.tone or 'neutral'} mood",
                        "negative_prompt": "blurry, watermark, text overlay",
                        "continuity_instructions": "Match wardrobe and lighting from prior shot",
                        "style_lock_prompt": story.visual_style or "consistent cinematic grade",
                    }
                ],
            }

        if task == PlanningTaskType.continuity_plan:
            return {
                "summary": "Continuity plan",
                "continuity": [
                    {
                        "from_shot_order_index": 0,
                        "to_shot_order_index": 1,
                        "method": "last_frame",
                        "notes": "Carry forward subject position and palette",
                    }
                ],
            }

        if task == PlanningTaskType.model_recommendation:
            return {
                "summary": "Model recommendations (planning only)",
                "recommendations": [
                    {
                        "shot_order_index": 0,
                        "recommendation_type": "primary",
                        "rationale": "Planning-phase recommendation only; not a render enqueue",
                        "availability_status": "unknown",
                        "benchmark_status": "unknown",
                    }
                ],
            }

        if task == PlanningTaskType.production_proposal:
            # Compose from previous_output when present.
            prev = request.previous_output or {}
            return {
                "summary": f"Production proposal for {story.title}",
                "chapters": prev.get("chapters") or [{"order_index": 0, "title": "Chapter 1", "summary": story.logline or story.title}],
                "characters": prev.get("characters") or [{"name": "Protagonist", "role": "lead"}],
                "voices": prev.get("voices") or [{"name": "Narrator", "source_type": "placeholder"}],
                "shots": prev.get("shots")
                or [
                    {
                        "order_index": 0,
                        "title": "Opening shot",
                        "duration_sec": min(8.0, duration),
                        "visual_description": story.base_story[:200],
                        "continuity_source_type": "none",
                    }
                ],
                "narrations": prev.get("narrations") or [],
                "prompt_packages": prev.get("prompt_packages") or [],
                "continuity": prev.get("continuity") or [],
                "model_recommendations": prev.get("recommendations") or prev.get("model_recommendations") or [],
                "warnings": list(prev.get("warnings") or []),
                "target_duration_sec": duration,
            }

        raise PlanningError(
            PlanningErrorCode.CONTRACT_VIOLATION,
            f"Unsupported task_type for mock provider: {task.value}",
        )


def get_provider(
    provider_identifier: str,
    registry: dict[str, PlanningProvider] | None = None,
) -> PlanningProvider:
    """Resolve a planning provider.

    Explicit registry entries win. When no registry is supplied (or the
    identifier is absent), fall through to the provider registry which keeps
    mock as the default and OpenAI available only when configured. Hosted
    non-OpenAI adapters and local_cli remain explicitly unavailable.
    """
    if registry is not None and provider_identifier in registry:
        return registry[provider_identifier]

    if provider_identifier == MockPlanningProvider.identifier:
        return MockPlanningProvider()

    # Lazy import avoids circular dependency with provider_registry.
    from backend.app.services.planning.provider_registry import resolve_provider

    return resolve_provider(provider_identifier, registry=registry)
