"""Provider-neutral planning provider interface and deterministic mock."""

from __future__ import annotations

import hashlib
import re
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

    @staticmethod
    def _pacing_beats(story: Any) -> list[dict[str, Any]]:
        """Extract explicit ``M:SS-M:SS — beat`` ranges from the source brief.

        The deterministic fallback should honor pacing the user actually wrote
        instead of inventing generic numbered chapters.  This is deliberately
        a transparent parser, not a claim that an AI provider ran.
        """

        pattern = re.compile(
            r"(?:^|\s+-\s+)(\d+):(\d{2})\s*[\u2013\u2014-]\s*(\d+):(\d{2})"
            r"\s*[\u2013\u2014-]\s*(.+?)"
            r"(?=\s+-\s+\d+:\d{2}\s*[\u2013\u2014-]\s*\d+:\d{2}\s*[\u2013\u2014-]"
            r"|\s+Do not\s+|\Z)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        beats: list[dict[str, Any]] = []
        for match in pattern.finditer(story.base_story or ""):
            start = int(match.group(1)) * 60 + int(match.group(2))
            end = int(match.group(3)) * 60 + int(match.group(4))
            if end <= start:
                continue
            description = " ".join(match.group(5).strip(" -\r\n\t").split())
            title_source = re.split(r"[,;]", description, maxsplit=1)[0].strip()
            title = title_source[:1].upper() + title_source[1:] if title_source else "Story beat"
            beats.append(
                {
                    "start_sec": start,
                    "end_sec": end,
                    "duration_sec": end - start,
                    "title": title[:300],
                    "summary": description[:2000],
                }
            )
        target = round(float(story.target_duration_sec), 3)
        if beats and round(sum(float(row["duration_sec"]) for row in beats), 3) == target:
            return beats
        return []

    @staticmethod
    def _infer_location(summary: str, visual_style: str | None) -> str:
        text = summary.casefold()
        if any(token in text for token in ("pig", "famine", "collapse")):
            return "Famine-stricken fields and a worked pig enclosure"
        if any(token in text for token in ("distant country", "departure", "travel")):
            return "Roads and an inhabited distant-country settlement"
        if any(token in text for token in ("journey home", "father running", "embrace")):
            return "Road approaching the family estate"
        if any(token in text for token in ("feast", "older brother", "older son")):
            return "Estate courtyard, feast hall, and open threshold"
        if any(token in text for token in ("estate", "inheritance", "family")):
            return "Worked family estate and limestone courtyard"
        return visual_style or "Location to be confirmed during human review"

    @staticmethod
    def _shot_stage(index: int) -> str:
        stages = (
            "establishing geography",
            "principal action",
            "restrained reaction",
            "tactile detail",
            "relationship beat",
            "consequence and transition",
        )
        return stages[index % len(stages)]

    @staticmethod
    def _characters_for_beat(
        summary: str,
        characters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return explicit character links for a source-grounded pacing beat."""

        text = summary.casefold()
        if any(token in text for token in ("distant country", "collapse", "famine", "pig")):
            wanted = ("younger",)
        elif any(token in text for token in ("journey home", "father running", "embrace")):
            wanted = ("father", "younger")
        else:
            # Estate/inheritance and feast/older-brother beats need the full
            # family relationship represented in the planning coverage.
            wanted = ("father", "younger", "older")

        links: list[dict[str, Any]] = []
        for character in characters:
            name = str(character.get("name") or "").strip()
            role = str(character.get("role") or "").strip()
            haystack = f"{name} {role}".casefold()
            matched = next((token for token in wanted if token in haystack), None)
            if matched is None:
                continue
            links.append(
                {
                    # The character-profile task intentionally emits stable
                    # names rather than database IDs.  Names are also mapped
                    # by the strict proposal adapter, so they remain resolvable
                    # after all task outputs are merged.
                    "character_id": name,
                    "role_in_shot": "lead" if matched in {"younger", "father"} else "supporting",
                    "continuity_notes": (
                        f"Preserve the approved {name} identity, wardrobe color language, age, and emotional state."
                    ),
                }
            )
        return links

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
            pacing_beats = self._pacing_beats(story)
            if pacing_beats:
                return {
                    "summary": f"{len(pacing_beats)} source-grounded pacing chapters",
                    "chapters": [
                        {
                            "order_index": i,
                            "title": beat["title"],
                            "summary": beat["summary"],
                            "start_sec": beat["start_sec"],
                            "end_sec": beat["end_sec"],
                            "duration_sec": beat["duration_sec"],
                        }
                        for i, beat in enumerate(pacing_beats)
                    ],
                }
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
            pacing_beats = self._pacing_beats(story)
            if pacing_beats:
                return {
                    "summary": f"{len(pacing_beats)} source-grounded scenes",
                    "scenes": [
                        {
                            "order_index": 0,
                            "chapter_order_index": i,
                            "title": beat["title"],
                            "summary": beat["summary"],
                            "narrative_purpose": (
                                f"Deliver the {beat['start_sec'] // 60}:{beat['start_sec'] % 60:02d}"
                                f"-{beat['end_sec'] // 60}:{beat['end_sec'] % 60:02d} pacing beat"
                            ),
                            "conflict_or_beat": beat["summary"],
                            "location": self._infer_location(beat["summary"], story.visual_style),
                            "duration_sec": beat["duration_sec"],
                        }
                        for i, beat in enumerate(pacing_beats)
                    ],
                }
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
            previous = request.previous_output or {}
            scene_rows = [row for row in (previous.get("scenes") or []) if isinstance(row, dict)]
            if scene_rows:
                shots: list[dict[str, Any]] = []
                default_scene_duration = duration / len(scene_rows)
                for scene_index, scene in enumerate(scene_rows):
                    try:
                        scene_duration = float(scene.get("duration_sec") or default_scene_duration)
                    except (TypeError, ValueError):
                        scene_duration = default_scene_duration
                    scene_duration = max(1.0, scene_duration)
                    scene_shot_count = max(1, round(scene_duration / 7.5))
                    per_shot = scene_duration / scene_shot_count
                    scene_title = str(scene.get("title") or f"Scene {scene_index + 1}")
                    summary = str(scene.get("summary") or scene.get("conflict_or_beat") or scene_title)
                    location = str(
                        scene.get("location") or self._infer_location(summary, story.visual_style)
                    )
                    character_links = self._characters_for_beat(summary, story.characters)
                    for beat_index in range(scene_shot_count):
                        stage = self._shot_stage(beat_index)
                        rounded_per_shot = round(per_shot, 3)
                        shot_duration = (
                            round(scene_duration - rounded_per_shot * (scene_shot_count - 1), 3)
                            if beat_index == scene_shot_count - 1
                            else rounded_per_shot
                        )
                        shots.append(
                            {
                                "order_index": len(shots),
                                "scene_order_index": scene_index,
                                "title": f"{scene_title} — {stage.title()} {beat_index + 1}",
                                "duration_sec": shot_duration,
                                "story_purpose": summary,
                                "visual_description": (
                                    f"{stage.capitalize()} for: {summary}. Location: {location}. "
                                    f"Maintain {story.visual_style or 'grounded cinematic realism'} "
                                    "with readable human action and natural material detail."
                                ),
                                "location": location,
                                "characters": character_links,
                                "starting_image_required": True,
                                "continuity_source_type": (
                                    "none" if not shots else "previous_shot"
                                ),
                            }
                        )
                return {"summary": f"{len(shots)} source-grounded shots", "shots": shots}
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
            previous = request.previous_output or {}
            shot_rows = [row for row in (previous.get("shots") or []) if isinstance(row, dict)]
            if shot_rows:
                first_by_scene: dict[int, tuple[int, dict[str, Any]]] = {}
                for shot_index, shot in enumerate(shot_rows):
                    try:
                        scene_index = int(shot.get("scene_order_index") or 0)
                    except (TypeError, ValueError):
                        scene_index = 0
                    first_by_scene.setdefault(scene_index, (shot_index, shot))
                return {
                    "summary": "Sparse narration plan anchored to scene openings",
                    "narrations": [
                        {
                            "shot_order_index": shot_index,
                            "narration_text": str(shot.get("story_purpose") or story.logline or "")[:500],
                            "start_offset_sec": 0,
                            "expected_duration_sec": min(
                                8.0, float(shot.get("duration_sec") or 8.0)
                            ),
                        }
                        for shot_index, shot in first_by_scene.values()
                    ],
                }
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
            previous = request.previous_output or {}
            shot_rows = [row for row in (previous.get("shots") or []) if isinstance(row, dict)]
            if shot_rows:
                return {
                    "summary": f"{len(shot_rows)} reviewable prompt packages",
                    "prompt_packages": [
                        {
                            "shot_order_index": i,
                            "image_prompt": (
                                f"{shot.get('visual_description') or shot.get('title')}. "
                                f"{story.visual_style or 'Grounded cinematic realism'}; natural light; "
                                "tactile skin, fabric, architecture, and practical environment detail."
                            ),
                            "video_prompt": (
                                f"Planning-only motion direction for {shot.get('title')}: restrained, "
                                "physically plausible performance and camera movement."
                            ),
                            "negative_prompt": (
                                "text overlay, watermark, plastic skin, illustration, fantasy costume, "
                                "modern props, artificial glamour"
                            ),
                            "continuity_instructions": (
                                "Preserve identity, wardrobe, screen direction, light, weather, and location "
                                "from the preceding approved shot."
                            ),
                            "style_lock_prompt": story.visual_style or "consistent cinematic grade",
                        }
                        for i, shot in enumerate(shot_rows)
                    ],
                }
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
            previous = request.previous_output or {}
            shot_rows = [row for row in (previous.get("shots") or []) if isinstance(row, dict)]
            if len(shot_rows) > 1:
                return {
                    "summary": f"{len(shot_rows) - 1} adjacent-shot continuity links",
                    "continuity": [
                        {
                            "from_shot_order_index": i - 1,
                            "to_shot_order_index": i,
                            "method": "last_frame",
                            "notes": (
                                "Carry forward identity, wardrobe, position, light, location, and emotional state."
                            ),
                        }
                        for i in range(1, len(shot_rows))
                    ],
                }
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
            previous = request.previous_output or {}
            shot_rows = [row for row in (previous.get("shots") or []) if isinstance(row, dict)]
            if shot_rows:
                return {
                    "summary": "Planning-only model review placeholders",
                    "recommendations": [
                        {
                            "shot_order_index": i,
                            "recommendation_type": "manual_review",
                            "rationale": (
                                "No factual generation runtime is available; select a validated workflow "
                                "and model during human review."
                            ),
                            "availability_status": "unknown",
                            "benchmark_status": "unknown",
                            "native_voice_capability": "unknown",
                        }
                        for i, _shot in enumerate(shot_rows)
                    ],
                }
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
            existing = story.existing_structure or {}
            return {
                "summary": f"Production proposal for {story.title}",
                "chapters": prev.get("chapters") or [{"order_index": 0, "title": "Chapter 1", "summary": story.logline or story.title}],
                "characters": prev.get("characters") or [{"name": "Protagonist", "role": "lead"}],
                "voices": prev.get("voices")
                or existing.get("voices")
                or [{"name": "Narrator", "source_type": "placeholder"}],
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
