"""Persistence helpers for orchestration runs, steps, events, invocations, proposals."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    AIProposalRecord,
    Character,
    OrchestrationEvent,
    OrchestrationRun,
    OrchestrationStep,
    ProviderInvocation,
    Story,
)
from backend.app.schemas.orchestration import (
    ActorType,
    EventType,
    FailureCategory,
    RunStatus,
    StepStatus,
)
from backend.app.services.planning.errors import PlanningError, PlanningErrorCode, sanitize_details, sanitize_message
from backend.app.services.planning.state_machine import assert_run_transition, assert_step_transition, utcnow


class PlanningRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Story / context
    # ------------------------------------------------------------------

    def get_story(self, story_id: UUID) -> Story:
        story = self.db.get(Story, story_id)
        if story is None:
            raise PlanningError(PlanningErrorCode.STORY_NOT_FOUND, f"Story not found: {story_id}")
        return story

    def list_characters(self, story_id: UUID) -> list[Character]:
        return list(self.db.scalars(select(Character).where(Character.story_id == story_id)))

    def find_active_run(self, story_id: UUID) -> OrchestrationRun | None:
        return self.db.scalar(
            select(OrchestrationRun).where(
                OrchestrationRun.story_id == story_id,
                OrchestrationRun.status.in_([RunStatus.pending.value, RunStatus.running.value]),
            )
        )

    def get_run(self, run_id: UUID) -> OrchestrationRun:
        run = self.db.get(OrchestrationRun, run_id)
        if run is None:
            raise PlanningError(PlanningErrorCode.RUN_NOT_FOUND, f"Orchestration run not found: {run_id}")
        return run

    def find_run_by_idempotency(self, story_id: UUID, idempotency_key: str) -> OrchestrationRun | None:
        # Idempotency key is stored in routing_snapshot_json.client_idempotency_key
        runs = list(
            self.db.scalars(
                select(OrchestrationRun)
                .where(OrchestrationRun.story_id == story_id)
                .order_by(OrchestrationRun.created_at.desc())
            )
        )
        for run in runs:
            snap = run.routing_snapshot_json or {}
            if snap.get("client_idempotency_key") == idempotency_key:
                return run
        return None

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(
        self,
        *,
        story_id: UUID,
        base_storyboard_version_id: UUID | None,
        requested_by: str | None,
        routing_snapshot: dict[str, Any],
        default_provider_snapshot: dict[str, Any],
        target_duration_sec_snapshot: float | None,
        input_hash: str,
        max_steps: int,
        repair_budget: int,
    ) -> OrchestrationRun:
        run = OrchestrationRun(
            story_id=story_id,
            base_storyboard_version_id=base_storyboard_version_id,
            status=RunStatus.pending.value,
            requested_by=requested_by,
            routing_snapshot_json=routing_snapshot,
            default_provider_snapshot_json=default_provider_snapshot,
            target_duration_sec_snapshot=target_duration_sec_snapshot,
            input_hash=input_hash,
            current_step=0,
            max_steps=max_steps,
            repair_budget=repair_budget,
            repair_used=0,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def transition_run(
        self,
        run: OrchestrationRun,
        target: RunStatus,
        *,
        failure_category: str | None = None,
        failure_message: str | None = None,
    ) -> OrchestrationRun:
        assert_run_transition(run.status, target)
        now = utcnow()
        run.status = target.value
        if target == RunStatus.running:
            run.started_at = run.started_at or now
        elif target == RunStatus.completed:
            run.completed_at = now
        elif target == RunStatus.failed:
            run.failed_at = now
            run.failure_category = failure_category
            run.failure_message = sanitize_message(failure_message or "run failed")
        elif target == RunStatus.canceled:
            run.canceled_at = now
            run.failure_category = failure_category or FailureCategory.canceled.value
            run.failure_message = sanitize_message(failure_message or "run canceled")
        self.db.add(run)
        self.db.flush()
        return run

    def bump_repair_used(self, run: OrchestrationRun) -> OrchestrationRun:
        if run.repair_used >= run.repair_budget:
            raise PlanningError(
                PlanningErrorCode.BUDGET_EXHAUSTED,
                "Repair budget exhausted",
                details={"repair_budget": run.repair_budget, "repair_used": run.repair_used},
            )
        run.repair_used += 1
        self.db.add(run)
        self.db.flush()
        return run

    def set_current_step(self, run: OrchestrationRun, sequence_index: int) -> None:
        run.current_step = sequence_index
        self.db.add(run)
        self.db.flush()

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def create_step(
        self,
        *,
        run_id: UUID,
        sequence_index: int,
        task_type: str,
        provider_identifier: str | None,
        logical_model: str | None,
        resolved_model: str | None,
        attempt_number: int,
        input_hash: str | None,
        metadata_json: dict[str, Any] | None = None,
    ) -> OrchestrationStep:
        step = OrchestrationStep(
            run_id=run_id,
            sequence_index=sequence_index,
            task_type=task_type,
            status=StepStatus.pending.value,
            provider_identifier=provider_identifier,
            logical_model=logical_model,
            resolved_model=resolved_model,
            attempt_number=attempt_number,
            input_hash=input_hash,
            metadata_json=metadata_json or {},
        )
        self.db.add(step)
        self.db.flush()
        return step

    def get_steps(self, run_id: UUID) -> list[OrchestrationStep]:
        return list(
            self.db.scalars(
                select(OrchestrationStep)
                .where(OrchestrationStep.run_id == run_id)
                .order_by(OrchestrationStep.sequence_index, OrchestrationStep.attempt_number)
            )
        )

    def transition_step(
        self,
        step: OrchestrationStep,
        target: StepStatus,
        *,
        output_hash: str | None = None,
        proposal_id: UUID | None = None,
        error_category: str | None = None,
        error_message: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> OrchestrationStep:
        assert_step_transition(step.status, target)
        now = utcnow()
        step.status = target.value
        if target == StepStatus.running:
            step.started_at = step.started_at or now
        elif target in {StepStatus.completed, StepStatus.failed, StepStatus.skipped, StepStatus.canceled}:
            step.completed_at = now
        if output_hash is not None:
            step.output_hash = output_hash
        if proposal_id is not None:
            step.proposal_id = proposal_id
        if error_category is not None:
            step.error_category = error_category
        if error_message is not None:
            step.error_message = sanitize_message(error_message)
        if metadata_patch:
            meta = dict(step.metadata_json or {})
            meta.update(sanitize_details(metadata_patch))
            step.metadata_json = meta
        self.db.add(step)
        self.db.flush()
        return step

    # ------------------------------------------------------------------
    # Events / invocations / proposals
    # ------------------------------------------------------------------

    def add_event(
        self,
        *,
        run_id: UUID,
        event_type: EventType | str,
        actor_type: ActorType | str,
        step_id: UUID | None = None,
        actor_reference: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> OrchestrationEvent:
        event = OrchestrationEvent(
            run_id=run_id,
            step_id=step_id,
            event_type=event_type.value if isinstance(event_type, EventType) else str(event_type),
            actor_type=actor_type.value if isinstance(actor_type, ActorType) else str(actor_type),
            actor_reference=actor_reference,
            details_json=sanitize_details(details or {}),
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_events(self, run_id: UUID) -> list[OrchestrationEvent]:
        return list(
            self.db.scalars(
                select(OrchestrationEvent)
                .where(OrchestrationEvent.run_id == run_id)
                .order_by(OrchestrationEvent.created_at)
            )
        )

    def find_invocation_by_key(self, idempotency_key: str) -> ProviderInvocation | None:
        return self.db.scalar(
            select(ProviderInvocation).where(ProviderInvocation.idempotency_key == idempotency_key)
        )

    def create_invocation(
        self,
        *,
        run_id: UUID,
        step_id: UUID | None,
        provider_identifier: str,
        model: str | None,
        idempotency_key: str,
        request_hash: str | None,
    ) -> ProviderInvocation:
        existing = self.find_invocation_by_key(idempotency_key)
        if existing is not None:
            return existing
        inv = ProviderInvocation(
            run_id=run_id,
            step_id=step_id,
            provider_identifier=provider_identifier,
            model=model,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="pending",
            usage_json={},
        )
        self.db.add(inv)
        self.db.flush()
        return inv

    def complete_invocation(
        self,
        inv: ProviderInvocation,
        *,
        status: str,
        response_hash: str | None = None,
        latency_ms: int | None = None,
        usage_json: dict[str, Any] | None = None,
        provider_request_id: str | None = None,
        finish_category: str | None = None,
        error_category: str | None = None,
        error_message: str | None = None,
    ) -> ProviderInvocation:
        inv.status = status
        inv.response_hash = response_hash
        inv.latency_ms = latency_ms
        inv.usage_json = sanitize_details(usage_json or {})
        inv.provider_request_id = provider_request_id
        inv.finish_category = finish_category
        inv.error_category = error_category
        inv.error_message = sanitize_message(error_message) if error_message else None
        inv.completed_at = utcnow()
        self.db.add(inv)
        self.db.flush()
        return inv

    def get_invocations(self, run_id: UUID) -> list[ProviderInvocation]:
        return list(
            self.db.scalars(
                select(ProviderInvocation)
                .where(ProviderInvocation.run_id == run_id)
                .order_by(ProviderInvocation.created_at)
            )
        )

    def create_proposal(
        self,
        *,
        proposal_type: str,
        payload: dict[str, Any],
        story_id: UUID,
        orchestration_run_id: UUID,
        base_storyboard_version_id: UUID | None,
        schema_name: str,
        content_hash: str,
        validation_status: str,
        validation_report_json: dict[str, Any] | None = None,
        warnings_json: list[Any] | None = None,
    ) -> AIProposalRecord:
        record = AIProposalRecord(
            proposal_type=proposal_type,
            payload=payload,
            status="pending_review",
            validation_errors=[],
            story_id=story_id,
            orchestration_run_id=orchestration_run_id,
            base_storyboard_version_id=base_storyboard_version_id,
            schema_name=schema_name,
            content_hash=content_hash,
            validation_status=validation_status,
            validation_report_json=validation_report_json or {},
            warnings_json=warnings_json or [],
        )
        self.db.add(record)
        self.db.flush()
        return record

    def get_proposals_for_run(self, run_id: UUID) -> list[AIProposalRecord]:
        return list(
            self.db.scalars(
                select(AIProposalRecord).where(AIProposalRecord.orchestration_run_id == run_id)
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def flush(self) -> None:
        self.db.flush()

    def refresh(self, obj: Any) -> None:
        self.db.refresh(obj)
