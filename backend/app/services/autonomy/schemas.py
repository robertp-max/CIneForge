from enum import StrEnum

from pydantic import BaseModel, Field


class AutonomyRunState(StrEnum):
    planning = "planning"
    awaiting_policy_validation = "awaiting_policy_validation"
    awaiting_human_approval = "awaiting_human_approval"
    scaffold_only = "scaffold_only"
    failed = "failed"


class AutonomyRun(BaseModel):
    state: AutonomyRunState = AutonomyRunState.scaffold_only
    policy_snapshot: dict = Field(default_factory=dict)


def execute_autonomy_run(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("Autonomous production execution is not implemented in Sprint 1A")

