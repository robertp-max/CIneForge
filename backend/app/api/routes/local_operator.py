"""Local operator run packet routes.

These routes prepare review packets only. They do not approve or start live
ComfyUI, GPU, FFmpeg/ffprobe, render, benchmark, or queue work.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.core.config import get_settings
from backend.app.core.errors import ValidationError
from backend.app.schemas.local_operator import (
    LocalOperatorApprovalTemplate,
    LocalOperatorRunMode,
    LocalOperatorRunPacket,
    LocalOperatorRunPacketCreate,
    LocalOperatorRunbook,
)
from backend.app.services.local_operator import (
    LocalOperatorRunPacketStore,
    get_local_operator_approval_template,
    get_local_operator_runbook,
    local_operator_approval_templates,
    local_operator_runbooks,
)


router = APIRouter(prefix="/local-operator", tags=["local-operator"])


def _store() -> LocalOperatorRunPacketStore:
    return LocalOperatorRunPacketStore(get_settings())


@router.post("/packets", response_model=LocalOperatorRunPacket)
def create_local_operator_run_packet(request: LocalOperatorRunPacketCreate) -> LocalOperatorRunPacket:
    try:
        return _store().create(request)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured local operator metadata file not found: {exc.filename}",
        ) from exc


@router.get("/packets", response_model=list[LocalOperatorRunPacket])
def list_local_operator_run_packets(limit: int = Query(default=25, ge=1, le=100)) -> list[LocalOperatorRunPacket]:
    return _store().list(limit=limit)


@router.get("/packets/{packet_id}", response_model=LocalOperatorRunPacket)
def get_local_operator_run_packet(packet_id: UUID) -> LocalOperatorRunPacket:
    return _store().get(packet_id)


@router.get("/approval-templates", response_model=list[LocalOperatorApprovalTemplate])
def list_local_operator_approval_templates() -> list[LocalOperatorApprovalTemplate]:
    return local_operator_approval_templates()


@router.get("/approval-templates/{mode}", response_model=LocalOperatorApprovalTemplate)
def get_local_operator_approval_template_route(mode: LocalOperatorRunMode) -> LocalOperatorApprovalTemplate:
    template = get_local_operator_approval_template(mode)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local operator approval template not found.")
    return template


@router.get("/runbooks", response_model=list[LocalOperatorRunbook])
def list_local_operator_runbooks() -> list[LocalOperatorRunbook]:
    return local_operator_runbooks()


@router.get("/runbooks/{mode}", response_model=LocalOperatorRunbook)
def get_local_operator_runbook_route(mode: LocalOperatorRunMode) -> LocalOperatorRunbook:
    runbook = get_local_operator_runbook(mode)
    if runbook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local operator runbook not found.")
    return runbook
