"""Evidence helpers for factual runtime discovery (no model loading)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EvidenceRecord:
    provider: str
    capability: str
    status: str
    evidence_level: str
    evidence_source: str | None = None
    available: bool = False
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def evidence(
    *,
    provider: str,
    capability: str,
    status: str,
    evidence_level: str,
    available: bool,
    evidence_source: str | None = None,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        provider=provider,
        capability=capability,
        status=status,
        evidence_level=evidence_level,
        evidence_source=evidence_source,
        available=available,
        message=message,
        details=dict(details or {}),
        checked_at=datetime.now(timezone.utc),
    )
