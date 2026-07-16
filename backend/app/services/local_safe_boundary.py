"""Read-only static safe/local boundary report service."""

from __future__ import annotations

from pathlib import Path

from backend.app.schemas.local_safe_boundary import LocalSafeBoundaryFinding, LocalSafeBoundaryReport
from scripts.validate_safe_local_boundary import validate_boundary


class LocalSafeBoundaryService:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[3]).resolve()

    def report(self) -> LocalSafeBoundaryReport:
        raw_findings = validate_boundary(self.repo_root)
        findings = [
            LocalSafeBoundaryFinding(
                code=finding.code,
                path=self._safe_relative_path(finding.path),
                detail=finding.detail,
            )
            for finding in raw_findings
        ]
        return LocalSafeBoundaryReport(
            passed=not findings,
            finding_count=len(findings),
            findings=findings,
        )

    def _safe_relative_path(self, path: str) -> str:
        candidate = Path(path)
        try:
            return candidate.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return candidate.name
