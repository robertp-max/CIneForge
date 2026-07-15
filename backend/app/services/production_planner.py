"""Deterministic local production planning for CineForge.

The planner treats the requested duration as the final assembled runtime, not as
one diffusion-generation duration. It decomposes a brief into model-safe LTX
shots, calculates legal frame counts, creates character/reference requirements,
and records storyboard/start-frame requirements without rendering.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from typing import Iterable

from backend.app.core.errors import ValidationError
from backend.app.schemas.production import (
    AspectRatio,
    CharacterPackage,
    CharacterReferenceRequest,
    ContinuityDependency,
    GeometryProfile,
    LtxFramePlan,
    OutputProfile,
    ProductionBriefRequest,
    ProductionPlan,
    ScenePlan,
    ShotPlan,
    StoryboardFrame,
    TimelinePlan,
)


ASPECT_RATIO_VALUES: dict[AspectRatio, tuple[int, int]] = {
    AspectRatio.widescreen_16_9: (16, 9),
    AspectRatio.vertical_9_16: (9, 16),
    AspectRatio.square_1_1: (1, 1),
    AspectRatio.classic_4_3: (4, 3),
    AspectRatio.scope_239_1: (239, 100),
}

_LONG_EDGE_BY_PROFILE = {
    OutputProfile.draft: 640,
    OutputProfile.review: 768,
    OutputProfile.final_candidate: 960,
    OutputProfile.controlled: 768,
    OutputProfile.lipdub: 768,
}

_UPSCALE_BY_PROFILE = {
    OutputProfile.draft: 1,
    OutputProfile.review: 1,
    OutputProfile.final_candidate: 2,
    OutputProfile.controlled: 1,
    OutputProfile.lipdub: 1,
}

_STOPWORDS = {
    "A", "An", "And", "As", "At", "Before", "Brief", "By", "For", "From", "He", "His", "In", "Into", "It",
    "On", "Scene", "Shot", "The", "Then", "They", "This", "To", "With", "Without", "CineForge",
}

_BIBLICAL_CHARACTER_HINTS = {"Jesus", "Peter", "James", "John", "Moses", "Elijah"}


@dataclass(frozen=True)
class ModelDurationConfig:
    fps: int
    min_clip_duration_sec: float
    max_clip_duration_sec: float
    transition_sec: float


def calculate_geometry(aspect_ratio: AspectRatio, quality_profile: OutputProfile, *, divisibility: int = 32) -> GeometryProfile:
    """Return model-safe generation and delivery dimensions for a profile."""

    if aspect_ratio not in ASPECT_RATIO_VALUES:
        raise ValidationError(f"Unsupported aspect ratio profile: {aspect_ratio}")
    rw, rh = ASPECT_RATIO_VALUES[aspect_ratio]
    long_edge = _LONG_EDGE_BY_PROFILE[quality_profile]
    if rw >= rh:
        width = long_edge
        height = long_edge * rh / rw
    else:
        height = long_edge
        width = long_edge * rw / rh

    generation_width = _floor_to_divisible(width, divisibility)
    generation_height = _floor_to_divisible(height, divisibility)
    if generation_width < 64 or generation_height < 64:
        raise ValidationError("Calculated generation geometry is below minimum model size")

    upscale = _UPSCALE_BY_PROFILE[quality_profile]
    return GeometryProfile(
        aspect_ratio=aspect_ratio,
        quality_profile=quality_profile,
        generation_width=generation_width,
        generation_height=generation_height,
        preview_width=generation_width,
        preview_height=generation_height,
        delivery_width=generation_width * upscale,
        delivery_height=generation_height * upscale,
        upscale_factor=upscale,
        divisibility=divisibility,
    )


def calculate_ltx_frame_plan(requested_duration_sec: float, fps: int) -> LtxFramePlan:
    """Choose the smallest legal 8n+1 LTX frame count covering duration."""

    if requested_duration_sec <= 0:
        raise ValidationError("Shot duration must be positive")
    raw_frames = max(9, math.ceil(requested_duration_sec * fps) + 1)
    frame_count = raw_frames
    remainder = (frame_count - 1) % 8
    if remainder:
        frame_count += 8 - remainder
    realizable = (frame_count - 1) / fps
    return LtxFramePlan(
        requested_duration_sec=round(requested_duration_sec, 6),
        fps=fps,
        frame_count=frame_count,
        realizable_duration_sec=round(realizable, 6),
    )


def validate_ltx_dimensions(width: int, height: int, *, divisibility: int = 32) -> None:
    if width < 64 or height < 64:
        raise ValidationError("LTX dimensions must be at least 64x64")
    if width % divisibility != 0 or height % divisibility != 0:
        raise ValidationError(f"LTX dimensions must be divisible by {divisibility}")


def validate_ltx_frame_count(frame_count: int) -> None:
    if (frame_count - 1) % 8 != 0:
        raise ValidationError("LTX frame count must satisfy 8n+1")


class ProductionPlanner:
    def plan(self, request: ProductionBriefRequest) -> ProductionPlan:
        geometry = calculate_geometry(request.aspect_ratio, request.quality_profile)
        validate_ltx_dimensions(geometry.generation_width, geometry.generation_height, divisibility=geometry.divisibility)
        characters = self._build_character_packages(request)
        durations = self._shot_durations(
            request.target_duration_sec,
            ModelDurationConfig(
                fps=request.fps,
                min_clip_duration_sec=request.min_model_clip_duration_sec,
                max_clip_duration_sec=request.max_model_clip_duration_sec,
                transition_sec=request.transition_sec,
            ),
        )
        scenes = self._build_scenes(request, geometry, durations, characters)
        transition_total = max(0.0, request.transition_sec) * max(0, len(durations) - 1)
        timeline = TimelinePlan(
            requested_final_duration_sec=round(request.target_duration_sec, 6),
            calculated_final_duration_sec=round(sum(durations), 6),
            total_source_duration_sec=round(sum(durations) + transition_total, 6),
            transition_overlap_sec=round(transition_total, 6),
            exact_duration_preserved=abs(sum(durations) - request.target_duration_sec) < 0.001,
        )
        if not timeline.exact_duration_preserved:
            raise ValidationError("Planner failed to preserve exact requested final duration")
        return ProductionPlan(
            project_key=request.project_key,
            title=request.title,
            brief=request.brief,
            target_duration_sec=request.target_duration_sec,
            aspect_ratio=request.aspect_ratio,
            quality_profile=request.quality_profile,
            fps=request.fps,
            geometry=geometry,
            scenes=scenes,
            characters=characters,
            timeline=timeline,
            narration_required=request.narration_required,
            no_narration_reason=request.no_narration_reason,
        )

    def _shot_durations(self, target_duration_sec: float, config: ModelDurationConfig) -> list[float]:
        if target_duration_sec < config.min_clip_duration_sec:
            raise ValidationError("Requested duration is too short for configured model-safe clip duration")
        max_clip = config.max_clip_duration_sec
        count = max(1, math.ceil(target_duration_sec / max_clip))
        # Avoid a tiny final shot by increasing count only when necessary then evenly distributing.
        while target_duration_sec / count > max_clip:
            count += 1
        avg = target_duration_sec / count
        if avg < config.min_clip_duration_sec and count > 1:
            count = max(1, math.floor(target_duration_sec / config.min_clip_duration_sec))
            avg = target_duration_sec / count
        if avg < config.min_clip_duration_sec or avg > max_clip:
            raise ValidationError("Cannot create model-safe shots for requested duration")
        durations = [round(avg, 6) for _ in range(count)]
        drift = round(target_duration_sec - sum(durations), 6)
        durations[-1] = round(durations[-1] + drift, 6)
        return durations

    def _build_scenes(
        self,
        request: ProductionBriefRequest,
        geometry: GeometryProfile,
        durations: list[float],
        characters: list[CharacterPackage],
    ) -> list[ScenePlan]:
        shot_count = len(durations)
        scene_count = max(1, min(8, math.ceil(shot_count / 3)))
        shots_per_scene = _partition_counts(shot_count, scene_count)
        character_ids = [character.character_id for character in characters]
        scenes: list[ScenePlan] = []
        shot_cursor = 0
        current_start = 0.0
        beats = self._derive_beats(request.brief, scene_count)
        for scene_index, count in enumerate(shots_per_scene):
            scene_id = f"scene-{scene_index + 1:02d}"
            scene_start = current_start
            scene_shots: list[ShotPlan] = []
            for local_index in range(count):
                duration = durations[shot_cursor]
                shot_id = f"shot-{shot_cursor + 1:03d}"
                frame_plan = calculate_ltx_frame_plan(duration, request.fps)
                previous_shot_id = f"shot-{shot_cursor:03d}" if shot_cursor > 0 else None
                continuity = ContinuityDependency(
                    shot_id=shot_id,
                    depends_on_shot_id=previous_shot_id,
                    kind="previous_end_frame" if previous_shot_id else "none",
                    resolved=False if previous_shot_id else True,
                    workflow_archetype_id="CF-VID-05" if previous_shot_id else None,
                )
                storyboard = StoryboardFrame(
                    storyboard_frame_id=f"frame-{shot_id}-first",
                    shot_id=shot_id,
                    approval_state="missing",
                    first_frame_asset_id=None,
                )
                scene_shots.append(
                    ShotPlan(
                        shot_id=shot_id,
                        scene_id=scene_id,
                        order_index=shot_cursor,
                        title=f"{beats[scene_index]} · shot {local_index + 1}",
                        prompt=self._shot_prompt(request.brief, beats[scene_index], local_index + 1, character_ids),
                        negative_prompt="identity drift, inconsistent wardrobe, temporal artifacts, text, watermark, low quality",
                        start_sec=round(current_start, 6),
                        duration_sec=duration,
                        source_handle_start_sec=0.0,
                        source_handle_end_sec=request.transition_sec if shot_cursor < shot_count - 1 else 0.0,
                        transition_in_sec=request.transition_sec if shot_cursor > 0 else 0.0,
                        transition_out_sec=request.transition_sec if shot_cursor < shot_count - 1 else 0.0,
                        frame_plan=frame_plan,
                        geometry=geometry,
                        character_ids=character_ids,
                        camera_intent="cinematic coverage with clear blocking and edit-safe motion",
                        lens_intent="natural lens; avoid extreme distortion unless brief requires it",
                        blocking="stage named characters and key environment references for a short model-safe clip",
                        location_environment=self._location_hint(request.brief),
                        storyboard=storyboard,
                        continuity=continuity,
                        video_archetype_id=self._video_archetype_for_profile(request.quality_profile),
                        generation_mode="i2v",
                    )
                )
                current_start = round(current_start + duration, 6)
                shot_cursor += 1
            scenes.append(
                ScenePlan(
                    scene_id=scene_id,
                    order_index=scene_index,
                    title=beats[scene_index],
                    start_sec=round(scene_start, 6),
                    duration_sec=round(sum(shot.duration_sec for shot in scene_shots), 6),
                    narrative_beat=beats[scene_index],
                    shots=scene_shots,
                )
            )
        return scenes

    def _build_character_packages(self, request: ProductionBriefRequest) -> list[CharacterPackage]:
        names = request.character_names or extract_character_names(request.brief)
        packages: list[CharacterPackage] = []
        for index, name in enumerate(names):
            seed_base = stable_seed(f"{request.project_key}:{name}")
            reference_requests = [
                self._reference_request("portrait", name, request.brief, seed_base + 1),
                self._reference_request("headshot", name, request.brief, seed_base + 2),
                self._reference_request("full_body", name, request.brief, seed_base + 3),
                self._reference_request("front", name, request.brief, seed_base + 4),
                self._reference_request("profile", name, request.brief, seed_base + 5),
                self._reference_request("three_quarter", name, request.brief, seed_base + 6),
                self._reference_request("wardrobe", name, request.brief, seed_base + 7),
                self._reference_request("expression", name, request.brief, seed_base + 8),
            ]
            packages.append(
                CharacterPackage(
                    character_id=f"char-{index + 1:02d}-{slugify(name)}",
                    name=name,
                    canonical_description=f"Canonical production identity for {name}, extracted from the brief and locked before video rendering.",
                    character_generation_prompt=f"Production character reference sheet for {name}; consistent face, wardrobe, silhouette, and era-appropriate styling. Brief context: {request.brief[:600]}",
                    negative_prompt="identity drift, duplicate faces, inconsistent age, inconsistent wardrobe, extra limbs, text, watermark",
                    reference_requests=reference_requests,
                    identity_adapter="redux_or_pulid_required_when_admitted",
                    redux_or_pulid_config={"preferred_archetypes": ["CF-IMG-02", "CF-IMG-03"]},
                    workflow_provenance={"planner": "ProductionPlanner", "rendered": False},
                )
            )
        return packages

    @staticmethod
    def _reference_request(kind: str, name: str, brief: str, seed: int) -> CharacterReferenceRequest:
        return CharacterReferenceRequest(
            kind=kind,  # type: ignore[arg-type]
            prompt=f"{kind.replace('_', ' ')} reference image for {name}; production identity asset; consistent face and wardrobe. Context: {brief[:400]}",
            negative_prompt="identity drift, inconsistent costume, text, watermark, low quality",
            seed=seed,
        )

    @staticmethod
    def _derive_beats(brief: str, count: int) -> list[str]:
        clauses = [part.strip(" .;:\n\t") for part in re.split(r"[.!?;\n]+", brief) if part.strip()]
        if not clauses:
            clauses = ["Establish", "Develop", "Resolve"]
        beats = []
        for index in range(count):
            source = clauses[min(index, len(clauses) - 1)]
            if len(source) > 72:
                source = source[:69].rstrip() + "..."
            beats.append(source or f"Narrative beat {index + 1}")
        return beats

    @staticmethod
    def _shot_prompt(brief: str, beat: str, local_shot: int, character_ids: Iterable[str]) -> str:
        chars = ", ".join(character_ids) or "environment and action"
        return (
            f"{beat}; shot {local_shot}. Use storyboard first-frame composition, production lighting, "
            f"and model-safe short motion. Characters/assets: {chars}. Brief: {brief[:800]}"
        )

    @staticmethod
    def _location_hint(brief: str) -> str:
        lowered = brief.lower()
        if "mountain" in lowered:
            return "mountain summit and ascent environment reference required"
        if "city" in lowered:
            return "urban location/environment reference required"
        if "interior" in lowered or "room" in lowered:
            return "interior environment reference required"
        return "environment reference derived from production brief"

    @staticmethod
    def _video_archetype_for_profile(profile: OutputProfile) -> str:
        if profile == OutputProfile.final_candidate:
            return "CF-VID-02"
        if profile == OutputProfile.controlled:
            return "CF-VID-03"
        if profile == OutputProfile.lipdub:
            return "CF-VID-04"
        return "CF-VID-01"


def extract_character_names(brief: str) -> list[str]:
    hinted = [name for name in sorted(_BIBLICAL_CHARACTER_HINTS) if re.search(rf"\b{re.escape(name)}\b", brief)]
    names = list(hinted)
    for match in re.finditer(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b", brief):
        name = match.group(1).strip()
        if name in _STOPWORDS or name in names:
            continue
        if len(names) >= 12:
            break
        names.append(name)
    return names


def stable_seed(value: str) -> int:
    return uuid.uuid5(uuid.NAMESPACE_URL, value).int % (2**31 - 1)


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "character"


def _floor_to_divisible(value: float, divisor: int) -> int:
    return max(divisor, int(value // divisor) * divisor)


def _partition_counts(total: int, buckets: int) -> list[int]:
    base = total // buckets
    remainder = total % buckets
    return [base + (1 if index < remainder else 0) for index in range(buckets)]
