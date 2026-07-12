"""Proposal lifecycle service: validate, store, review, reject, load, diff.

Does not apply proposals (see proposal_apply) and never performs external calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    AIProposalRecord,
    AuditLog,
    ModelVariant,
    OrchestrationRun,
    PlanningMediaAsset,
    ProviderProfile,
    Story,
    StoryboardVersion,
    WorkflowTemplate,
)
from backend.app.schemas.proposals import (
    ProposalCreateRequest,
    ProposalDiffResponse,
    ProposalRejectRequest,
    ProposalReviewRequest,
    ProposalValidationResponse,
    StoryboardProposalPayload,
    ValidationStatus,
)
from backend.app.services.ai_orchestration.schemas import (
    STORYBOARD_PROPOSAL_SCHEMA_NAME,
    STORYBOARD_PROPOSAL_TYPES,
    AIProposal,
    ProposalType,
)
from backend.app.services.ai_orchestration.validator import ProposalValidator, content_hash_for
from backend.app.services.proposal_diff import diff_snapshot_to_proposal, diff_storyboard_payloads
from backend.app.services import storyboard_snapshot


class ProposalServiceError(ValueError):
    pass


class ProposalNotFoundError(ProposalServiceError):
    pass


class ProposalStateError(ProposalServiceError):
    pass


def _now() -> datetime:
    return datetime.utcnow()


def _load_reference_catalogs(db: Session, project_id: UUID | None) -> dict[str, set[str]]:
    model_ids = {str(row) for row in db.scalars(select(ModelVariant.id))}
    workflow_ids = {str(row) for row in db.scalars(select(WorkflowTemplate.id))}
    provider_ids = {str(row) for row in db.scalars(select(ProviderProfile.id))}
    asset_ids: set[str] = set()
    if project_id is not None:
        asset_ids = {
            str(row)
            for row in db.scalars(
                select(PlanningMediaAsset.id).where(PlanningMediaAsset.project_id == project_id)
            )
        }
    else:
        asset_ids = {str(row) for row in db.scalars(select(PlanningMediaAsset.id))}
    return {
        "model_variant_ids": model_ids,
        "workflow_template_ids": workflow_ids,
        "provider_profile_ids": provider_ids,
        "asset_ids": asset_ids,
    }


def _base_snapshot(db: Session, version_id: UUID | None) -> dict[str, Any] | None:
    if version_id is None:
        return None
    version = db.get(StoryboardVersion, version_id)
    if version is None:
        return None
    return version.snapshot_json


def validate_storyboard_proposal_ownership(
    db: Session,
    *,
    payload: dict[str, Any],
    story_id: UUID | None,
    base_storyboard_version_id: UUID | None,
    orchestration_run_id: UUID | None,
) -> tuple[Story, StoryboardProposalPayload]:
    """Bind a storyboard proposal to exactly one persisted story graph.

    This is intentionally stricter than foreign-key existence checks.  The
    public request/record, payload identity, project, optional base version,
    and optional orchestration run must all describe the same Story.  The
    check is repeated before diff/apply so a legacy or corrupted row cannot
    cross project boundaries.
    """

    try:
        parsed = StoryboardProposalPayload.model_validate(payload)
    except Exception as exc:
        raise ProposalServiceError(f"Storyboard proposal schema is invalid: {exc}") from exc

    payload_story_id = parsed.story.existing_id
    if story_id is None:
        story_id = payload_story_id
    if story_id is None or payload_story_id is None:
        raise ProposalServiceError(
            "Storyboard proposals must identify an existing story in both the record and payload."
        )
    if payload_story_id != story_id:
        raise ProposalServiceError(
            "Proposal payload story does not match the proposal story."
        )

    story = db.get(Story, story_id)
    if story is None:
        raise ProposalServiceError("Story not found.")
    if parsed.project_id != story.project_id:
        raise ProposalServiceError(
            "Proposal payload project does not own the proposal story."
        )

    payload_base_id = parsed.base_storyboard_version_id
    if payload_base_id != base_storyboard_version_id:
        raise ProposalServiceError(
            "Proposal payload base version does not match the proposal record."
        )
    if base_storyboard_version_id is not None:
        version = db.get(StoryboardVersion, base_storyboard_version_id)
        if version is None:
            raise ProposalServiceError("Base storyboard version not found.")
        if version.story_id != story.id:
            raise ProposalServiceError(
                "Base storyboard version does not belong to the proposal story."
            )

    if orchestration_run_id is not None:
        run = db.get(OrchestrationRun, orchestration_run_id)
        if run is None:
            raise ProposalServiceError("Orchestration run not found.")
        if run.story_id != story.id:
            raise ProposalServiceError(
                "Orchestration run does not belong to the proposal story."
            )
        if run.base_storyboard_version_id != base_storyboard_version_id:
            raise ProposalServiceError(
                "Orchestration run base version does not match the proposal base version."
            )

    return story, parsed


def validate_create_request(
    db: Session,
    request: ProposalCreateRequest,
) -> ProposalValidationResponse:
    try:
        proposal_type = ProposalType(request.proposal_type)
    except ValueError as exc:
        raise ProposalServiceError(f"Unknown proposal_type: {request.proposal_type}") from exc

    payload = request.payload
    base_snapshot = None
    catalogs: dict[str, set[str]] = {
        "model_variant_ids": None,  # type: ignore[dict-item]
        "workflow_template_ids": None,  # type: ignore[dict-item]
        "provider_profile_ids": None,  # type: ignore[dict-item]
        "asset_ids": None,  # type: ignore[dict-item]
    }

    if proposal_type in STORYBOARD_PROPOSAL_TYPES:
        # Structural pydantic contract (extra forbid) before semantic validator.
        try:
            parsed = StoryboardProposalPayload.model_validate(payload)
            payload = parsed.model_dump(mode="json")
        except Exception as exc:
            return ProposalValidationResponse(
                accepted=False,
                validation_status=ValidationStatus.invalid,
                errors=[f"schema: {exc}"],
                warnings=[],
                content_hash=content_hash_for(request.payload),
                report={},
            )

        resolved_story_id = request.story_id or parsed.story.existing_id
        resolved_base_id = (
            request.base_storyboard_version_id
            if request.base_storyboard_version_id is not None
            else parsed.base_storyboard_version_id
        )
        try:
            story, _ = validate_storyboard_proposal_ownership(
                db,
                payload=payload,
                story_id=resolved_story_id,
                base_storyboard_version_id=resolved_base_id,
                orchestration_run_id=request.orchestration_run_id,
            )
        except ProposalServiceError as exc:
            return ProposalValidationResponse(
                accepted=False,
                validation_status=ValidationStatus.invalid,
                errors=[f"ownership: {exc}"],
                warnings=[],
                content_hash=content_hash_for(payload),
                report={},
            )
        base_snapshot = _base_snapshot(db, resolved_base_id)
        catalogs = _load_reference_catalogs(db, story.project_id)

    ai_proposal = AIProposal(
        proposal_type=proposal_type,
        summary=request.summary,
        payload=payload,
        schema_name=request.schema_name or payload.get("schema_name"),
        story_id=str(request.story_id) if request.story_id else None,
        base_storyboard_version_id=(
            str(request.base_storyboard_version_id) if request.base_storyboard_version_id else None
        ),
        base_content_hash=payload.get("base_content_hash"),
    )
    result = ProposalValidator().validate(
        ai_proposal,
        base_snapshot=base_snapshot,
        known_model_variant_ids=catalogs.get("model_variant_ids"),
        known_workflow_template_ids=catalogs.get("workflow_template_ids"),
        known_provider_profile_ids=catalogs.get("provider_profile_ids"),
        known_asset_ids=catalogs.get("asset_ids"),
    )
    return ProposalValidationResponse(
        accepted=result.accepted and not result.errors,
        validation_status=ValidationStatus(result.validation_status),
        errors=result.errors,
        warnings=result.warnings,
        content_hash=result.content_hash,
        report=result.report,
    )


def create_proposal(db: Session, request: ProposalCreateRequest) -> AIProposalRecord:
    validation = validate_create_request(db, request)
    try:
        proposal_type = ProposalType(request.proposal_type)
    except ValueError as exc:
        raise ProposalServiceError(f"Unknown proposal_type: {request.proposal_type}") from exc

    payload = request.payload
    story_id = request.story_id
    base_version_id = request.base_storyboard_version_id
    if proposal_type in STORYBOARD_PROPOSAL_TYPES:
        try:
            parsed = StoryboardProposalPayload.model_validate(request.payload)
        except Exception:
            parsed = None
        if parsed is not None:
            story_id = story_id or parsed.story.existing_id
            base_version_id = (
                base_version_id
                if base_version_id is not None
                else parsed.base_storyboard_version_id
            )
            story, parsed = validate_storyboard_proposal_ownership(
                db,
                payload=request.payload,
                story_id=story_id,
                base_storyboard_version_id=base_version_id,
                orchestration_run_id=request.orchestration_run_id,
            )
            story_id = story.id
            if validation.accepted:
                payload = parsed.model_dump(mode="json")
        else:
            if story_id is not None and db.get(Story, story_id) is None:
                raise ProposalServiceError("Story not found.")
            if (
                base_version_id is not None
                and db.get(StoryboardVersion, base_version_id) is None
            ):
                raise ProposalServiceError("Base storyboard version not found.")
    else:
        if story_id is not None and db.get(Story, story_id) is None:
            raise ProposalServiceError("Story not found.")
        if base_version_id is not None and db.get(StoryboardVersion, base_version_id) is None:
            raise ProposalServiceError("Base storyboard version not found.")

    status = "pending_review"
    if not validation.accepted:
        status = "pending_review"
    elif validation.validation_status == ValidationStatus.needs_review:
        status = "needs_review"
    elif validation.validation_status == ValidationStatus.valid:
        status = "validated"

    record = AIProposalRecord(
        proposal_type=str(proposal_type),
        payload=payload,
        status=status,
        validation_errors=list(validation.errors),
        story_id=story_id,
        orchestration_run_id=request.orchestration_run_id,
        base_storyboard_version_id=base_version_id,
        schema_name=request.schema_name or payload.get("schema_name") or STORYBOARD_PROPOSAL_SCHEMA_NAME,
        schema_version=int(payload.get("schema_version") or 1),
        content_hash=validation.content_hash,
        payload_hash=content_hash_for(payload),
        input_context_hash=payload.get("input_context_hash"),
        base_content_hash=payload.get("base_content_hash"),
        validation_status=str(validation.validation_status),
        validation_report_json=validation.report or {},
        warnings_json=list(validation.warnings),
    )
    db.add(record)
    db.add(
        AuditLog(
            entity_type="ai_proposal_record",
            entity_id=None,
            action="proposal_created",
            details={
                "proposal_type": str(proposal_type),
                "validation_status": str(validation.validation_status),
                "story_id": str(story_id) if story_id else None,
            },
        )
    )
    db.commit()
    db.refresh(record)
    # Backfill entity_id on audit after id assignment is not required for Phase 1.
    return record


def get_proposal(db: Session, proposal_id: UUID) -> AIProposalRecord:
    record = db.get(AIProposalRecord, proposal_id)
    if record is None:
        raise ProposalNotFoundError("Proposal not found.")
    return record


def list_proposals_for_story(db: Session, story_id: UUID) -> list[AIProposalRecord]:
    return list(
        db.scalars(
            select(AIProposalRecord)
            .where(AIProposalRecord.story_id == story_id)
            .order_by(AIProposalRecord.created_at.desc())
        )
    )


def review_proposal(db: Session, proposal_id: UUID, request: ProposalReviewRequest) -> AIProposalRecord:
    record = get_proposal(db, proposal_id)
    if record.status in {"applied", "rejected", "superseded"}:
        raise ProposalStateError(f"Cannot review proposal in status '{record.status}'.")
    if record.validation_status == "invalid" or record.validation_errors:
        raise ProposalStateError("Cannot mark invalid proposal as reviewed.")

    record.reviewed_by = request.reviewed_by
    record.reviewed_at = _now()
    if record.status == "needs_review":
        record.status = "validated"
        record.validation_status = "valid"
    elif record.status == "pending_review":
        record.status = "validated"
    db.add(
        AuditLog(
            entity_type="ai_proposal_record",
            entity_id=record.id,
            action="proposal_reviewed",
            details={"reviewed_by": request.reviewed_by, "notes": request.notes},
        )
    )
    db.commit()
    db.refresh(record)
    return record


def reject_proposal(db: Session, proposal_id: UUID, request: ProposalRejectRequest) -> AIProposalRecord:
    record = get_proposal(db, proposal_id)
    if record.status in {"applied", "rejected", "superseded"}:
        raise ProposalStateError(f"Cannot reject proposal in status '{record.status}'.")

    record.status = "rejected"
    record.rejected_at = _now()
    record.rejection_reason = request.reason
    record.reviewed_by = request.rejected_by
    record.reviewed_at = record.rejected_at
    db.add(
        AuditLog(
            entity_type="ai_proposal_record",
            entity_id=record.id,
            action="proposal_rejected",
            details={"rejected_by": request.rejected_by, "reason": request.reason},
        )
    )
    db.commit()
    db.refresh(record)
    return record


def build_diff(db: Session, proposal_id: UUID) -> ProposalDiffResponse:
    record = get_proposal(db, proposal_id)
    try:
        proposal_type = ProposalType(record.proposal_type)
    except ValueError as exc:
        raise ProposalServiceError(f"Unknown proposal_type: {record.proposal_type}") from exc
    if proposal_type in STORYBOARD_PROPOSAL_TYPES:
        validate_storyboard_proposal_ownership(
            db,
            payload=record.payload if isinstance(record.payload, dict) else {},
            story_id=record.story_id,
            base_storyboard_version_id=record.base_storyboard_version_id,
            orchestration_run_id=record.orchestration_run_id,
        )
    base_snapshot = _base_snapshot(db, record.base_storyboard_version_id)
    base_hash = None
    if record.base_storyboard_version_id:
        version = db.get(StoryboardVersion, record.base_storyboard_version_id)
        if version is not None:
            base_hash = version.content_hash
    elif record.story_id is not None:
        expected_live_hash = record.base_content_hash or (
            record.payload.get("base_content_hash")
            if isinstance(record.payload, dict)
            else None
        )
        if expected_live_hash:
            live_snapshot, live_hash = storyboard_snapshot.build_snapshot_with_hash(
                db,
                record.story_id,
            )
            if live_hash != expected_live_hash:
                raise ProposalStateError(
                    "Stale proposal: live storyboard content changed before diff review."
                )
            base_snapshot = live_snapshot
            base_hash = live_hash

    if base_snapshot is not None:
        ops = diff_snapshot_to_proposal(base_snapshot, record.payload)
    else:
        ops = diff_storyboard_payloads({}, record.payload)

    return ProposalDiffResponse(
        proposal_id=record.id,
        base_storyboard_version_id=record.base_storyboard_version_id,
        base_content_hash=base_hash,
        proposed_content_hash=record.content_hash or content_hash_for(record.payload),
        ops=ops,
    )
