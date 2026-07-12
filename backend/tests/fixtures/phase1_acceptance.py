"""Canonical Storyboard Phase-1 development/test acceptance fixture.

This module is deliberately test-only.  It seeds planning records, never render
records, and never invokes a provider, model runtime, startup hook, or network
service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy.orm import Session

from backend.app.db.base import (
    Model,
    ModelVariant,
    Project,
    ProjectStoryboardSettings,
    ProviderProfile,
    Story,
    TaskProviderAssignment,
)
from backend.app.schemas.orchestration import PlanningTaskType
from backend.app.services.storyboard_settings import default_settings_values


FIXTURE_NAMESPACE = UUID("d4ec5b67-8d32-4ad5-bd5b-9976df0d8ec5")
PROJECT_ID = uuid5(FIXTURE_NAMESPACE, "project:a-new-journey")
STORY_ID = uuid5(FIXTURE_NAMESPACE, "story:a-new-journey")
PLANNING_PROVIDER_PROFILE_ID = uuid5(FIXTURE_NAMESPACE, "provider:mock-planning")
GENERATION_PROVIDER_PROFILE_ID = uuid5(FIXTURE_NAMESPACE, "provider:ltx-native")
GENERATION_MODEL_ID = uuid5(FIXTURE_NAMESPACE, "model:ltx-eros")
GENERATION_MODEL_VARIANT_ID = uuid5(FIXTURE_NAMESPACE, "variant:ltx-eros-native")
SETTINGS_ID = uuid5(FIXTURE_NAMESPACE, "settings:a-new-journey")

TARGET_DURATION_SEC = 225.0
SCENE_DURATION_ROLLUPS = (38.0, 37.0, 39.0, 38.0, 40.0, 33.0)
CHAPTER_DURATION_ROLLUPS = (75.0, 77.0, 73.0)

PHASE1_PLANNING_TASKS = tuple(PlanningTaskType)

_CHARACTERS = (
    {
        "client_id": "character-alex",
        "name": "Alex Reyes",
        "role": "Lead · New team member",
        "age_range": "Late 20s–mid 30s",
        "physical_description": "Warm, observant presence; short dark textured hair; grounded posture.",
        "personality": "Curious, conscientious, quietly confident",
        "speaking_style": "Thoughtful, direct, receptive",
        "wardrobe": "Soft blue button-up, charcoal trousers, canvas tote",
        "consistency_prompt": "Preserve Alex's facial structure, hair, posture, and understated professional wardrobe.",
        "assigned_voice_client_id": "voice-alex",
    },
    {
        "client_id": "character-dana",
        "name": "Dana Whitfield",
        "role": "Supervisor",
        "age_range": "40s–50s",
        "physical_description": "Calm, composed supervisor with silver-streaked dark hair.",
        "personality": "Reassuring, exact, generous",
        "speaking_style": "Confident and measured",
        "wardrobe": "Navy blazer, neutral blouse, practical shoes",
        "consistency_prompt": "Keep Dana's silver-streaked hair, calm expression, and navy professional wardrobe consistent.",
        "assigned_voice_client_id": "voice-dana",
    },
    {
        "client_id": "character-maya",
        "name": "Dr. Maya Chen",
        "role": "Clinical mentor",
        "age_range": "30s–40s",
        "physical_description": "Precise, approachable clinician with shoulder-length black hair.",
        "personality": "Attentive, practical, unflappable",
        "speaking_style": "Precise and approachable",
        "wardrobe": "Teal clinical jacket over neutral workwear",
        "consistency_prompt": "Preserve Maya's facial identity, shoulder-length hair, and teal clinical layers.",
        "assigned_voice_client_id": "voice-maya",
    },
    {
        "client_id": "character-jordan",
        "name": "Jordan Blake",
        "role": "Supporting colleague",
        "age_range": "Late 20s–40s",
        "physical_description": "Friendly colleague with close-cropped hair and relaxed posture.",
        "personality": "Observant, candid, collaborative",
        "speaking_style": "Conversational and practical",
        "wardrobe": "Field-ready overshirt and dark work trousers",
        "consistency_prompt": "Keep Jordan's close-cropped hair, relaxed posture, and field-ready wardrobe consistent.",
        "assigned_voice_client_id": "voice-jordan",
    },
)

_VOICES = (
    ("voice-alex", "Alex · Placeholder 03", "Curious, grounded"),
    ("voice-dana", "Dana · Studio 07", "Confident, reassuring"),
    ("voice-maya", "Maya · Clinical Clear", "Precise, approachable"),
    ("voice-jordan", "Jordan · Field Note", "Conversational, practical"),
)

_CHAPTERS = (
    (
        "chapter-first-door",
        "The First Door",
        "Alex arrives, meets Dana, and learns what the first week will ask.",
        (
            (
                "scene-arrival",
                "Arrival at Care Indeed",
                "Alex enters a new workplace and opens the welcome message.",
                "Care Indeed exterior and reception",
                ("Morning exterior", "The welcome email", "Responsibility", "The path ahead", "Step inside"),
                (8.0, 7.0, 8.0, 7.0, 8.0),
            ),
            (
                "scene-welcome",
                "The Welcome Conversation",
                "Dana frames the agency promise and Alex's first week.",
                "Care Indeed orientation room",
                ("Meet Dana", "A calm welcome", "The agency promise", "Your role in the team", "First-week map"),
                (7.0, 8.0, 7.0, 7.0, 8.0),
            ),
        ),
    ),
    (
        "chapter-standards",
        "Standards in Action",
        "Policies become practical choices through preparation and clinical mentorship.",
        (
            (
                "scene-policy",
                "Policy into Practice",
                "Standards become a usable guide for real home-care decisions.",
                "Training room",
                ("The policy guide", "Why standards matter", "A home is different", "Prepare before entry", "Pause and verify"),
                (8.0, 8.0, 8.0, 7.0, 8.0),
            ),
            (
                "scene-mentor",
                "The Mentor Check",
                "Dr. Chen turns uncertainty into a safe escalation and documentation routine.",
                "Clinical huddle room",
                ("Dr. Chen's huddle", "Ask before acting", "Escalate concerns", "Document clearly", "Protect the patient"),
                (8.0, 7.0, 8.0, 7.0, 8.0),
            ),
        ),
    ),
    (
        "chapter-ready",
        "Ready to Begin",
        "A field scenario tests the team, then Alex reflects and steps forward.",
        (
            (
                "scene-field",
                "In the Field",
                "Jordan demonstrates how preparation, handoff, and follow-through earn trust.",
                "Home-care field scenario",
                ("Jordan's field notes", "Team handoff", "Safe choices", "Trust through follow-through"),
                (10.0, 10.0, 10.0, 10.0),
            ),
            (
                "scene-reflection",
                "Reflection and Next Step",
                "Alex connects the week's lessons and chooses a prepared way forward.",
                "Care Indeed quiet meeting space",
                ("Reflection", "Ready for tomorrow", "A new journey"),
                (11.0, 11.0, 11.0),
            ),
        ),
    ),
)

_SILENT_SHOT_ORDINALS = frozenset({5, 10, 15, 20, 25})


@dataclass(frozen=True)
class SeededPhase1Acceptance:
    project_id: UUID
    story_id: UUID
    planning_provider_profile_id: UUID
    generation_provider_profile_id: UUID
    generation_model_variant_id: UUID
    payload: dict[str, Any]
    scene_duration_rollups: tuple[float, ...]
    chapter_duration_rollups: tuple[float, ...]
    planning_task_types: tuple[PlanningTaskType, ...]


def _fixture_id(name: str) -> UUID:
    return uuid5(FIXTURE_NAMESPACE, name)


def _shot_characters(scene_index: int, local_index: int) -> list[str]:
    supporting_by_scene = (
        None,
        "character-dana",
        "character-maya",
        "character-maya",
        "character-jordan",
        ("character-dana", "character-maya", "character-jordan")[local_index % 3],
    )
    supporting = supporting_by_scene[scene_index]
    return ["character-alex"] if supporting is None else ["character-alex", supporting]


def build_phase1_acceptance_payload() -> dict[str, Any]:
    """Return a fresh JSON-compatible proposal payload with deterministic IDs."""

    chapter_payloads: list[dict[str, Any]] = []
    global_ordinal = 0
    previous_shot_client_id: str | None = None
    scene_index = 0

    for chapter_order, (chapter_id, title, summary, scenes) in enumerate(_CHAPTERS):
        scene_payloads: list[dict[str, Any]] = []
        for scene_order, (scene_id, scene_title, scene_summary, location, titles, durations) in enumerate(scenes):
            shot_payloads: list[dict[str, Any]] = []
            for shot_order, (shot_title, duration) in enumerate(zip(titles, durations, strict=True)):
                global_ordinal += 1
                shot_client_id = f"shot-{global_ordinal:02d}"
                character_ids = _shot_characters(scene_index, shot_order)
                if global_ordinal in _SILENT_SHOT_ORDINALS:
                    narration = {
                        "client_id": f"narration-{global_ordinal:02d}",
                        "narration_text": None,
                        "voice_client_id": None,
                        "start_offset_sec": 0.0,
                        "expected_duration_sec": duration,
                        "narration_exception_reason": "Intentional silent visual beat approved for planning.",
                    }
                else:
                    narration = {
                        "client_id": f"narration-{global_ordinal:02d}",
                        "narration_text": f"{shot_title} reveals the next responsibility in Alex's journey.",
                        "voice_client_id": "voice-alex",
                        "start_offset_sec": 0.0,
                        "expected_duration_sec": duration,
                        "narration_exception_reason": None,
                    }

                continuity: dict[str, Any]
                if previous_shot_client_id is None:
                    continuity = {
                        "continuity_source_type": "none",
                        "continuity_source_shot_client_id": None,
                    }
                else:
                    continuity = {
                        "continuity_source_type": "shot_ref",
                        "continuity_source_shot_client_id": previous_shot_client_id,
                    }

                shot_payloads.append(
                    {
                        "client_id": shot_client_id,
                        "order_index": shot_order,
                        "title": shot_title,
                        "duration_sec": duration,
                        "duration_override_reason": None,
                        "story_purpose": f"Advance acceptance beat {global_ordinal} while preserving the learning arc.",
                        "visual_description": (
                            f"Cinematic, grounded frame for {shot_title.lower()} in {location}; "
                            "natural light, restrained teal-and-amber palette, clear visual storytelling."
                        ),
                        "location": location,
                        **continuity,
                        "starting_image_required": False,
                        "starting_image_asset_id": None,
                        "characters": [
                            {
                                "character_client_id": character_id,
                                "role_in_shot": "lead" if order == 0 else "supporting",
                                "order_index": order,
                                "continuity_notes": "Preserve approved identity and wardrobe.",
                            }
                            for order, character_id in enumerate(character_ids)
                        ],
                        "narration": narration,
                        "prompt_package": {
                            "image_prompt": f"Cinematic 16:9 frame for {shot_title}; {location}; coherent identities.",
                            "video_prompt": f"Grounded camera movement for {shot_title}; preserve eyeline and screen direction.",
                            "negative_prompt": "identity drift, warped hands, text artifacts, flicker, jitter",
                            "continuity_instructions": "Use the immediately preceding approved planning shot as continuity source.",
                            "style_lock_prompt": "Premium grounded workplace drama; natural light; restrained teal-and-amber palette.",
                            "provider_profile_id": str(GENERATION_PROVIDER_PROFILE_ID),
                            "provider_model_id": "ltx-eros-native-speech",
                        },
                        "model_recommendations": [
                            {
                                "recommendation_type": "primary",
                                "generation_model_variant_id": str(GENERATION_MODEL_VARIANT_ID),
                                "workflow_template_id": None,
                                "provider_profile_id": str(GENERATION_PROVIDER_PROFILE_ID),
                                "provider_identifier": "ltx",
                                "provider_model_id": "ltx-eros-native-speech",
                                "rationale": "Approved fixture model supports native speech; Qwen is unnecessary.",
                                "availability_status": "available",
                                "benchmark_status": "fixture_verified",
                                "risk_status": "low",
                                "recommends_qwen_voice": False,
                                "native_voice_capability": "supported",
                            }
                        ],
                    }
                )
                previous_shot_client_id = shot_client_id

            scene_payloads.append(
                {
                    "client_id": scene_id,
                    "order_index": scene_order,
                    "title": scene_title,
                    "summary": scene_summary,
                    "narrative_purpose": scene_summary,
                    "location": location,
                    "conflict_or_beat": "Translate safe-care standards into a human decision.",
                    "shots": shot_payloads,
                }
            )
            scene_index += 1

        chapter_payloads.append(
            {
                "client_id": chapter_id,
                "order_index": chapter_order,
                "title": title,
                "summary": summary,
                "scenes": scene_payloads,
            }
        )

    return {
        "schema_name": "storyboard_proposal_v1",
        "project_id": str(PROJECT_ID),
        "story": {
            "client_id": "story-a-new-journey",
            "existing_id": str(STORY_ID),
            "title": "A New Journey",
            "base_story": (
                "Alex Reyes joins Care Indeed and meets supervisor Dana Whitfield, clinical mentor "
                "Dr. Maya Chen, and colleague Jordan Blake. Across orientation, practical scenarios, "
                "and reflection, Alex learns how preparation, documentation, escalation, and teamwork "
                "protect patients and earn trust."
            ),
            "target_duration_sec": TARGET_DURATION_SEC,
            "logline": (
                "On a first day filled with new standards and human stakes, Alex learns that safe care "
                "begins long before entering a patient's home."
            ),
            "synopsis": (
                "Alex's first week becomes a guided journey through the responsibilities, relationships, "
                "and decisions behind safe home health care."
            ),
            "audience": "New Care Indeed team members",
            "tone": "Warm, confident, human",
            "genre": "Workplace learning drama",
            "visual_style": "Cinematic realism with calm natural light",
            "point_of_view": "Second person alongside Alex",
            "production_notes": "Keep compliance concepts human and visual; avoid clinical spectacle.",
            "characters": [
                {
                    **character,
                    "reference_asset_ids": [],
                    "approval_state": "draft",
                }
                for character in _CHARACTERS
            ],
            "voices": [
                {
                    "client_id": client_id,
                    "name": name,
                    "source_type": "placeholder",
                    "character_client_id": character["client_id"],
                    "provider": None,
                    "provider_voice_reference": None,
                    "language": "English",
                    "accent": "Neutral US",
                    "presentation": "Warm and grounded",
                    "tone": tone,
                    "speaking_directions": "Sound thoughtful and human; never promotional.",
                    "pacing": "145 wpm",
                    "energy": "calm-medium",
                    "consent_required": False,
                    "consent_confirmed": False,
                    "setup_mode": "placeholder",
                    "approval_state": "draft",
                }
                for (client_id, name, tone), character in zip(_VOICES, _CHARACTERS, strict=True)
            ],
            "chapters": chapter_payloads,
        },
    }


def seed_phase1_acceptance_fixture(db: Session) -> SeededPhase1Acceptance:
    """Seed the explicit planning context and return its strict proposal payload."""

    project = Project(
        id=PROJECT_ID,
        name="A New Journey",
        description="Storyboard Phase-1 development/test acceptance project.",
    )
    planning_provider = ProviderProfile(
        id=PLANNING_PROVIDER_PROFILE_ID,
        provider_identifier="mock",
        display_name="Deterministic Mock Planning",
        provider_model_id="fixture-deterministic-v1",
        execution_mode="local",
        availability_status="available",
        privacy_classification="local-test-only",
        capabilities_json={"planning": True, "external_calls": False},
        configuration_reference="test-only:MockPlanningProvider",
        capability_source="explicit acceptance fixture",
    )
    generation_provider = ProviderProfile(
        id=GENERATION_PROVIDER_PROFILE_ID,
        provider_identifier="ltx",
        display_name="LTX Native Speech Fixture Route",
        provider_model_id="ltx-eros-native-speech",
        execution_mode="planning_only",
        availability_status="available",
        privacy_classification="local-test-only",
        capabilities_json={"video_generation": True, "native_voice": True, "enqueue": False},
        configuration_reference="test-only:factual-reference",
        capability_source="explicit acceptance fixture",
    )
    model = Model(
        id=GENERATION_MODEL_ID,
        family="LTX",
        name="LTX Eros",
        source_url=None,
        license="fixture metadata only",
        evidence_level="acceptance_fixture",
        notes="Factual planning reference; no model files or runtime are installed.",
    )
    variant = ModelVariant(
        id=GENERATION_MODEL_VARIANT_ID,
        model_id=GENERATION_MODEL_ID,
        variant_name="LTX Eros Native Speech",
        compatible_24gb_status="fixture_verified",
        native_voice_capability="supported",
        native_voice_capability_source="explicit acceptance fixture",
        native_voice_capability_metadata_json={"requires_qwen_tts": False},
        notes="Planning metadata only; no weights are present or downloaded.",
    )
    story = Story(
        id=STORY_ID,
        project_id=PROJECT_ID,
        title="A New Journey",
        base_story="Acceptance fixture awaiting a reviewed production-plan proposal.",
        target_duration_sec=TARGET_DURATION_SEC,
        logline="A new team member learns that safe care begins with preparation.",
        synopsis="A structured first-week learning journey.",
        audience="New Care Indeed team members",
        tone="Warm, confident, human",
        genre="Workplace learning drama",
        visual_style="Cinematic realism with calm natural light",
        point_of_view="Second person alongside Alex",
        production_notes="Planning only; never enqueue rendering.",
        default_provider_profile_id=PLANNING_PROVIDER_PROFILE_ID,
    )
    settings = ProjectStoryboardSettings(
        id=SETTINGS_ID,
        project_id=PROJECT_ID,
        **default_settings_values(),
    )

    db.add_all([project, planning_provider, generation_provider, model])
    db.flush()
    db.add_all([variant, story, settings])
    db.flush()
    db.add_all(
        [
            TaskProviderAssignment(
                id=_fixture_id(f"task-route:{task.value}"),
                story_id=STORY_ID,
                task_type=task.value,
                provider_profile_id=PLANNING_PROVIDER_PROFILE_ID,
                assignment_mode="automatic",
                rationale="Explicit offline deterministic acceptance route.",
                priority=0,
                enabled=True,
            )
            for task in PHASE1_PLANNING_TASKS
        ]
    )
    db.commit()

    return SeededPhase1Acceptance(
        project_id=PROJECT_ID,
        story_id=STORY_ID,
        planning_provider_profile_id=PLANNING_PROVIDER_PROFILE_ID,
        generation_provider_profile_id=GENERATION_PROVIDER_PROFILE_ID,
        generation_model_variant_id=GENERATION_MODEL_VARIANT_ID,
        payload=build_phase1_acceptance_payload(),
        scene_duration_rollups=SCENE_DURATION_ROLLUPS,
        chapter_duration_rollups=CHAPTER_DURATION_ROLLUPS,
        planning_task_types=PHASE1_PLANNING_TASKS,
    )
