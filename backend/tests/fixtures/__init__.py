"""Explicit, test-only acceptance fixtures.

Nothing in this package is imported by application startup.
"""

from backend.tests.fixtures.phase1_acceptance import (
    CHAPTER_DURATION_ROLLUPS,
    PHASE1_PLANNING_TASKS,
    SCENE_DURATION_ROLLUPS,
    TARGET_DURATION_SEC,
    SeededPhase1Acceptance,
    build_phase1_acceptance_payload,
    seed_phase1_acceptance_fixture,
)

__all__ = [
    "CHAPTER_DURATION_ROLLUPS",
    "PHASE1_PLANNING_TASKS",
    "SCENE_DURATION_ROLLUPS",
    "TARGET_DURATION_SEC",
    "SeededPhase1Acceptance",
    "build_phase1_acceptance_payload",
    "seed_phase1_acceptance_fixture",
]
