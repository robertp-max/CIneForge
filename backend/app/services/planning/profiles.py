"""Logical Sol / Terra / Luna profiles and resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.schemas.orchestration import LogicalModelProfile, PlanningTaskType


# Escalation ladder: start cheap/fast, escalate quality on semantic failure.
ESCALATION_ORDER: tuple[LogicalModelProfile, ...] = (
    LogicalModelProfile.luna,
    LogicalModelProfile.terra,
    LogicalModelProfile.sol,
)


@dataclass(frozen=True, slots=True)
class LogicalProfileSpec:
    profile: LogicalModelProfile
    display_name: str
    quality_rank: int
    default_resolved_model: str
    description: str


PROFILE_SPECS: dict[LogicalModelProfile, LogicalProfileSpec] = {
    LogicalModelProfile.luna: LogicalProfileSpec(
        profile=LogicalModelProfile.luna,
        display_name="Luna",
        quality_rank=1,
        default_resolved_model="logical/luna",
        description="Fast drafting profile for structured first passes.",
    ),
    LogicalModelProfile.terra: LogicalProfileSpec(
        profile=LogicalModelProfile.terra,
        display_name="Terra",
        quality_rank=2,
        default_resolved_model="logical/terra",
        description="Balanced profile for repairs and mid-complexity planning.",
    ),
    LogicalModelProfile.sol: LogicalProfileSpec(
        profile=LogicalModelProfile.sol,
        display_name="Sol",
        quality_rank=3,
        default_resolved_model="logical/sol",
        description="Highest-capability profile for final proposal synthesis.",
    ),
}


# Default starting profile per task. Production proposal always prefers Sol.
DEFAULT_TASK_PROFILE: dict[PlanningTaskType, LogicalModelProfile] = {
    PlanningTaskType.story_structure: LogicalModelProfile.sol,
    PlanningTaskType.character_bible: LogicalModelProfile.terra,
    PlanningTaskType.chapter_outline: LogicalModelProfile.terra,
    PlanningTaskType.scene_breakdown: LogicalModelProfile.terra,
    PlanningTaskType.shot_list: LogicalModelProfile.luna,
    PlanningTaskType.narration_plan: LogicalModelProfile.terra,
    PlanningTaskType.prompt_package: LogicalModelProfile.luna,
    PlanningTaskType.continuity_plan: LogicalModelProfile.terra,
    PlanningTaskType.model_recommendation: LogicalModelProfile.terra,
    PlanningTaskType.production_proposal: LogicalModelProfile.sol,
}


def profile_spec(profile: LogicalModelProfile) -> LogicalProfileSpec:
    return PROFILE_SPECS[profile]


def next_escalation(current: LogicalModelProfile) -> LogicalModelProfile | None:
    try:
        idx = ESCALATION_ORDER.index(current)
    except ValueError:
        return LogicalModelProfile.terra
    if idx + 1 >= len(ESCALATION_ORDER):
        return None
    return ESCALATION_ORDER[idx + 1]


def resolve_model_name(
    profile: LogicalModelProfile,
    *,
    provider_identifier: str,
    explicit: str | None = None,
) -> str:
    if explicit:
        return explicit
    # Provider-neutral logical name; concrete adapters may remap later.
    base = PROFILE_SPECS[profile].default_resolved_model
    return f"{provider_identifier}:{base}"


def default_profile_for_task(task_type: PlanningTaskType) -> LogicalModelProfile:
    return DEFAULT_TASK_PROFILE.get(task_type, LogicalModelProfile.luna)
