"""API routes for managed Storyboard Phase 1 reference / planning media assets."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.assets import (
    AssetArchiveRequest,
    AssetDeleteRequest,
    AssetKind,
    AssetListResponse,
    AssetUploadResponse,
    CharacterReferenceLinkCreate,
    CharacterReferenceLinkRead,
    PlanningMediaAssetRead,
)
from backend.app.services import reference_assets as service


router = APIRouter(prefix="/assets", tags=["assets"])


def _http_for(error: Exception) -> HTTPException:
    if isinstance(error, service.ReferenceAssetNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, service.ReferenceAssetConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, service.ReferenceAssetError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        )
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


def _to_read(asset, *, is_duplicate: bool = False) -> PlanningMediaAssetRead:
    return PlanningMediaAssetRead.model_validate(
        service.to_public_dict(asset, is_duplicate=is_duplicate)
    )


@router.post(
    "/projects/{project_id}/upload",
    response_model=AssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_planning_asset(
    project_id: UUID,
    kind: AssetKind = Form(...),
    file: UploadFile = File(...),
    consent_confirmed: bool = Form(False),
    source_type: str = Form("user_upload"),
    db: Session = Depends(get_db),
) -> AssetUploadResponse:
    """Managed upload. Returns asset ID metadata only — never filesystem paths."""
    try:
        asset, created = service.upload_asset_from_fileobj(
            db,
            project_id=project_id,
            kind=kind.value,
            fileobj=file.file,
            original_filename=file.filename,
            content_type=file.content_type,
            source_type=source_type,
            consent_confirmed=consent_confirmed if kind == AssetKind.voice_source else None,
        )
    except (service.ReferenceAssetError, service.ReferenceAssetNotFoundError) as error:
        raise _http_for(error) from error

    # Duplicate reuse is still a successful response; created=false signals no clone.
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    response = AssetUploadResponse(
        asset=_to_read(asset, is_duplicate=not created),
        created=created,
        duplicate_of_existing=not created,
    )
    # FastAPI uses decorator status_code for non-Response returns; duplicates stay 201
    # with created=false, which is acceptable and explicit in the body.
    _ = status_code
    return response


@router.get(
    "/projects/{project_id}",
    response_model=AssetListResponse,
)
def list_planning_assets(
    project_id: UUID,
    kind: AssetKind | None = None,
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
) -> AssetListResponse:
    try:
        rows = service.list_assets(
            db,
            project_id,
            kind=kind.value if kind else None,
            include_archived=include_archived,
        )
    except (service.ReferenceAssetError, service.ReferenceAssetNotFoundError) as error:
        raise _http_for(error) from error
    items = [_to_read(row) for row in rows]
    return AssetListResponse(items=items, total=len(items))


@router.get(
    "/{asset_id}",
    response_model=PlanningMediaAssetRead,
)
def get_planning_asset(
    asset_id: UUID,
    include_archived: bool = Query(True),
    db: Session = Depends(get_db),
) -> PlanningMediaAssetRead:
    try:
        asset = service.get_asset(db, asset_id, include_archived=include_archived)
    except service.ReferenceAssetNotFoundError as error:
        raise _http_for(error) from error
    return _to_read(asset)


@router.get("/{asset_id}/content")
def stream_planning_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Controlled stream by asset ID. Clients never supply filesystem paths."""
    try:
        asset, path = service.open_asset_for_stream(db, asset_id)
    except (service.ReferenceAssetError, service.ReferenceAssetNotFoundError) as error:
        raise _http_for(error) from error

    filename = asset.original_filename or path.name
    return FileResponse(
        path=path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=filename,
        content_disposition_type="inline",
    )


@router.post(
    "/{asset_id}/archive",
    response_model=PlanningMediaAssetRead,
)
def archive_planning_asset(
    asset_id: UUID,
    payload: AssetArchiveRequest | None = None,
    db: Session = Depends(get_db),
) -> PlanningMediaAssetRead:
    try:
        asset = service.archive_asset(
            db,
            asset_id,
            reason=(payload.reason if payload else None),
        )
    except (service.ReferenceAssetError, service.ReferenceAssetNotFoundError) as error:
        raise _http_for(error) from error
    return _to_read(asset)


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_planning_asset(
    asset_id: UUID,
    force: bool = Query(False),
    reason: str | None = Query(None),
    db: Session = Depends(get_db),
) -> None:
    try:
        service.delete_asset(db, asset_id, reason=reason, force=force)
    except (service.ReferenceAssetError, service.ReferenceAssetNotFoundError) as error:
        raise _http_for(error) from error


@router.post(
    "/characters/{character_id}/references",
    response_model=CharacterReferenceLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def link_character_reference(
    character_id: UUID,
    payload: CharacterReferenceLinkCreate,
    db: Session = Depends(get_db),
) -> CharacterReferenceLinkRead:
    try:
        link = service.link_character_reference(
            db,
            character_id=character_id,
            asset_id=payload.asset_id,
            reference_role=payload.reference_role.value,
            approved=payload.approved,
            order_index=payload.order_index,
        )
        asset = service.get_asset(db, link.asset_id)
    except (
        service.ReferenceAssetError,
        service.ReferenceAssetNotFoundError,
        service.ReferenceAssetConflictError,
    ) as error:
        raise _http_for(error) from error
    return CharacterReferenceLinkRead(
        id=link.id,
        character_id=link.character_id,
        asset_id=link.asset_id,
        reference_role=link.reference_role,
        approved=link.approved,
        order_index=link.order_index,
        created_at=link.created_at,
        updated_at=link.updated_at,
        asset=_to_read(asset),
    )


@router.get(
    "/characters/{character_id}/references",
    response_model=list[CharacterReferenceLinkRead],
)
def list_character_references(
    character_id: UUID,
    db: Session = Depends(get_db),
) -> list[CharacterReferenceLinkRead]:
    try:
        links = service.list_character_references(db, character_id)
    except service.ReferenceAssetNotFoundError as error:
        raise _http_for(error) from error
    results: list[CharacterReferenceLinkRead] = []
    for link in links:
        try:
            asset = service.get_asset(db, link.asset_id, include_archived=True)
            asset_read = _to_read(asset)
        except service.ReferenceAssetNotFoundError:
            asset_read = None
        results.append(
            CharacterReferenceLinkRead(
                id=link.id,
                character_id=link.character_id,
                asset_id=link.asset_id,
                reference_role=link.reference_role,
                approved=link.approved,
                order_index=link.order_index,
                created_at=link.created_at,
                updated_at=link.updated_at,
                asset=asset_read,
            )
        )
    return results


@router.delete(
    "/character-references/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_character_reference(
    link_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        service.unlink_character_reference(db, link_id)
    except service.ReferenceAssetNotFoundError as error:
        raise _http_for(error) from error


# Silence unused import warning for AssetDeleteRequest (reserved for body-form deletes).
_ = AssetDeleteRequest
