from pydantic import BaseModel, Field


class QAReport(BaseModel):
    subject_id: str
    findings: list[str] = Field(default_factory=list)
    passed: bool = False

