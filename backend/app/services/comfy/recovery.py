"""Mockable ComfyUI runtime recovery orchestration.

This module coordinates backend state transitions around a runtime failure and a
supervisor-owned process-tree recovery. It does not itself spawn, kill, restart,
or mutate ComfyUI; production code must inject an explicit supervisor that owns
those platform-specific actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.base import QueueStatus
from backend.app.services.queue.service import QueueService


class ComfyRuntimeSupervisor(Protocol):
    def terminate_process_tree(self, reason: str) -> dict: ...

    def restart_pinned_runtime(self) -> dict: ...

    def health_check(self) -> dict: ...


@dataclass(frozen=True)
class RuntimeRecoveryResult:
    job_id: UUID
    terminal_status: str
    process_terminated: bool
    restart_attempted: bool
    health_ok: bool
    health: dict
    diagnostics: dict

    @property
    def recovered(self) -> bool:
        return self.process_terminated and self.restart_attempted and self.health_ok


class ComfyRuntimeRecoveryService:
    def __init__(self, queue_service: QueueService | None = None) -> None:
        self.queue_service = queue_service or QueueService()

    def recover_failed_runtime(
        self,
        db: Session,
        job_id: UUID,
        worker_id: str,
        supervisor: ComfyRuntimeSupervisor,
        *,
        reason: str,
        terminal_status: QueueStatus = QueueStatus.runtime_failed,
    ) -> RuntimeRecoveryResult:
        if terminal_status not in {QueueStatus.runtime_failed, QueueStatus.oom, QueueStatus.timeout, QueueStatus.interrupted}:
            raise ValueError(f"Unsupported runtime recovery terminal status: {terminal_status.value}")

        self.queue_service.mark_terminal_job(
            db,
            job_id,
            terminal_status,
            reason,
            actor="worker",
            worker_id=worker_id,
            error_message=reason,
        )
        termination = supervisor.terminate_process_tree(reason)
        restart = supervisor.restart_pinned_runtime()
        health = supervisor.health_check()
        return RuntimeRecoveryResult(
            job_id=job_id,
            terminal_status=terminal_status.value,
            process_terminated=bool(termination.get("terminated")),
            restart_attempted=bool(restart.get("started")),
            health_ok=health.get("status") == "ok",
            health=health,
            diagnostics={"termination": termination, "restart": restart},
        )
