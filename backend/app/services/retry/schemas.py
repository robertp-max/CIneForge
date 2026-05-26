from pydantic import BaseModel


class RetryAttempt(BaseModel):
    attempt_index: int
    reason: str
    result: str | None = None

