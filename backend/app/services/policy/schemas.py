from pydantic import BaseModel, Field


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str
    gates: list[str] = Field(default_factory=list)

