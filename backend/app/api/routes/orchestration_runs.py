"""HTTP routes for Storyboard Phase 1 orchestration runs.

Mount this router from the application factory when wiring is authorized.
This module does not register itself and does not touch render/media systems.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.orchestration import (
    CancelOrchestrationRunRequest,
    CreateOrchestrationRunRequest,
    CreateOrchestrationRunResponse,
    OrchestrationEventRead,
    OrchestrationRunDetailRead,
    OrchestrationRunRead,
    OrchestrationStepRead,
    ProposalSummaryRead,
    ProviderInvocationRead,
    RunActionResponse,
)
from backend.app.services.planning.engine import PlanningEngine
from backend.app.services.planning.errors import PlanningError, PlanningErrorCode


router = APIRouter(prefix="/orchestration", tags=["orchestration"])


def _http_error(error: PlanningError) -> HTTPException:
    code_map = {
        PlanningErrorCode.STORY_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        PlanningErrorCode.RUN_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        PlanningErrorCode.ACTIVE_RUN_EXISTS: status.HTTP_409_CONFLICT,
        PlanningErrorCode.ALREADY_TERMINAL: status.HTTP_409_CONFLICT,
        PlanningErrorCode.INVALID_TRANSITION: status.HTTP_409_CONFLICT,
        PlanningErrorCode.IDEMPOTENCY_CONFLICT: status.HTTP_409_CONFLICT,
        PlanningErrorCode.BUDGET_EXHAUSTED: status.HTTP_409_CONFLICT,
        PlanningErrorCode.TIME_BUDGET_EXCEEDED: status.HTTP_409_CONFLICT,
        PlanningErrorCode.CANCELED: status.HTTP_409_CONFLICT,
        PlanningErrorCode.VALIDATION_FAILED: status.HTTP_422_UNPROCESSABLE_ENTITY,
        PlanningErrorCode.CONTRACT_VIOLATION: status.HTTP_422_UNPROCESSABLE_ENTITY,
        PlanningErrorCode.ROUTING_FAILED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    status_code = code_map.get(error.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(
        status_code=status_code,
        detail={
            "code": error.code.value,
            "category": error.category.value,
            "message": error.message,
            "retryable": error.retryable,
            "details": error.details,
        },
    )


def _engine(db: Session) -> PlanningEngine:
    return PlanningEngine(db)


def _run_read(run) -> OrchestrationRunRead:
    return OrchestrationRunRead.model_validate(run)


@router.post(
    "/runs",
    response_model=CreateOrchestrationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_orchestration_run(
    payload: CreateOrchestrationRunRequest,
    db: Session = Depends(get_db),
) -> CreateOrchestrationRunResponse:
    engine = _engine(db)
    try:
        run, created = engine.create_run(payload)
    except PlanningError as error:
        raise _http_error(error) from error
    return CreateOrchestrationRunResponse(
        run=_run_read(run),
        created=created,
        idempotent_replay=not created,
    )


@router.get("/runs/{run_id}", response_model=OrchestrationRunDetailRead)
def get_orchestration_run(run_id: UUID, db: Session = Depends(get_db)) -> OrchestrationRunDetailRead:
    engine = _engine(db)
    try:
        detail = engine.get_run_detail(run_id)
    except PlanningError as error:
        raise _http_error(error) from error

    run = detail["run"]
    base = OrchestrationRunRead.model_validate(run)
    return OrchestrationRunDetailRead(
        **base.model_dump(),
        steps=[OrchestrationStepRead.model_validate(s) for s in detail["steps"]],
        events=[OrchestrationEventRead.model_validate(e) for e in detail["events"]],
        invocations=[ProviderInvocationRead.model_validate(i) for i in detail["invocations"]],
        proposals=[ProposalSummaryRead.model_validate(p) for p in detail["proposals"]],
    )


@router.get("/stories/{story_id}/runs", response_model=list[OrchestrationRunRead])
def list_story_runs(story_id: UUID, db: Session = Depends(get_db)) -> list[OrchestrationRunRead]:
    engine = _engine(db)
    runs = engine.list_runs_for_story(story_id)
    return [_run_read(run) for run in runs]


@router.post("/runs/{run_id}/start", response_model=RunActionResponse)
def start_orchestration_run(run_id: UUID, db: Session = Depends(get_db)) -> RunActionResponse:
    engine = _engine(db)
    try:
        run = engine.start_run(run_id)
    except PlanningError as error:
        raise _http_error(error) from error

    message = {
        "completed": "Planning completed; immutable proposal awaiting review",
        "failed": run.failure_message or "Planning failed",
        "canceled": run.failure_message or "Planning canceled",
        "running": "Planning still running",
        "pending": "Planning pending",
    }.get(run.status, f"Run status={run.status}")
    return RunActionResponse(run=_run_read(run), message=message)


@router.post("/runs/{run_id}/cancel", response_model=RunActionResponse)
def cancel_orchestration_run(
    run_id: UUID,
    payload: CancelOrchestrationRunRequest | None = None,
    db: Session = Depends(get_db),
) -> RunActionResponse:
    engine = _engine(db)
    body = payload or CancelOrchestrationRunRequest()
    try:
        run = engine.cancel_run(
            run_id,
            reason=body.reason,
            requested_by=body.requested_by,
        )
    except PlanningError as error:
        raise _http_error(error) from error
    return RunActionResponse(run=_run_read(run), message="Run canceled")


@router.get("/runs/{run_id}/events", response_model=list[OrchestrationEventRead])
def list_run_events(run_id: UUID, db: Session = Depends(get_db)) -> list[OrchestrationEventRead]:
    engine = _engine(db)
    try:
        detail = engine.get_run_detail(run_id)
    except PlanningError as error:
        raise _http_error(error) from error
    return [OrchestrationEventRead.model_validate(e) for e in detail["events"]]


@router.get("/runs/{run_id}/steps", response_model=list[OrchestrationStepRead])
def list_run_steps(run_id: UUID, db: Session = Depends(get_db)) -> list[OrchestrationStepRead]:
    engine = _engine(db)
    try:
        detail = engine.get_run_detail(run_id)
    except PlanningError as error:
        raise _http_error(error) from error
    return [OrchestrationStepRead.model_validate(s) for s in detail["steps"]]


@router.get("/runs/{run_id}/invocations", response_model=list[ProviderInvocationRead])
def list_run_invocations(
    run_id: UUID, db: Session = Depends(get_db)
) -> list[ProviderInvocationRead]:
    engine = _engine(db)
    try:
        detail = engine.get_run_detail(run_id)
    except PlanningError as error:
        raise _http_error(error) from error
    return [ProviderInvocationRead.model_validate(i) for i in detail["invocations"]]
