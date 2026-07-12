"""API routes for remaining Storyboard Phase 1 planning CRUD."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.storyboard_crud import (
    ProposalCreateExtended,
    ProposalReadExtended,
    ProposalUpdate,
    ProviderProfileCreate,
    ProviderProfileRead,
    ProviderProfileUpdate,
    ShotModelRecommendationCreate,
    ShotModelRecommendationRead,
    ShotModelRecommendationUpdate,
    ShotNarrationCreate,
    ShotNarrationRead,
    ShotNarrationUpdate,
    ShotPromptPackageCreate,
    ShotPromptPackageRead,
    ShotPromptPackageUpdate,
    StoryboardVersionDetail,
    StoryboardVersionListItem,
    TaskProviderAssignmentCreate,
    TaskProviderAssignmentRead,
    TaskProviderAssignmentUpdate,
)
from backend.app.services import storyboard_crud as service


router = APIRouter(prefix="/storyboard-crud", tags=["storyboard-crud"])


def _http_for(error: Exception) -> HTTPException:
    if isinstance(error, service.StoryboardCrudNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, service.StoryboardCrudConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, service.StoryboardCrudError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        )
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


# ---------------------------------------------------------------------------
# Narrations
# ---------------------------------------------------------------------------


@router.get("/shots/{shot_id}/narration", response_model=ShotNarrationRead)
def get_narration(shot_id: UUID, db: Session = Depends(get_db)) -> ShotNarrationRead:
    try:
        row = service.get_narration(db, shot_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    if row is None:
        raise HTTPException(status_code=404, detail="Narration not found.")
    return ShotNarrationRead.model_validate(row)


@router.put("/shots/{shot_id}/narration", response_model=ShotNarrationRead)
def put_narration(
    shot_id: UUID,
    payload: ShotNarrationCreate,
    db: Session = Depends(get_db),
) -> ShotNarrationRead:
    try:
        row = service.upsert_narration(db, shot_id, payload, partial=False)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
        service.StoryboardCrudConflictError,
    ) as error:
        raise _http_for(error) from error
    return ShotNarrationRead.model_validate(row)


@router.patch("/shots/{shot_id}/narration", response_model=ShotNarrationRead)
def patch_narration(
    shot_id: UUID,
    payload: ShotNarrationUpdate,
    db: Session = Depends(get_db),
) -> ShotNarrationRead:
    try:
        existing = service.get_narration(db, shot_id)
        if existing is None:
            # Patch on missing requires enough fields to satisfy create validator.
            create_payload = ShotNarrationCreate(**payload.model_dump(exclude_unset=True))
            row = service.upsert_narration(db, shot_id, create_payload, partial=False)
        else:
            row = service.upsert_narration(db, shot_id, payload, partial=True)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
        service.StoryboardCrudConflictError,
        ValueError,
    ) as error:
        if isinstance(error, ValueError) and not isinstance(error, service.StoryboardCrudError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        raise _http_for(error) from error
    return ShotNarrationRead.model_validate(row)


@router.delete("/shots/{shot_id}/narration", status_code=status.HTTP_204_NO_CONTENT)
def delete_narration(shot_id: UUID, db: Session = Depends(get_db)) -> Response:
    try:
        service.delete_narration(db, shot_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Prompt packages
# ---------------------------------------------------------------------------


@router.get("/shots/{shot_id}/prompt-packages", response_model=list[ShotPromptPackageRead])
def list_prompt_packages(
    shot_id: UUID, db: Session = Depends(get_db)
) -> list[ShotPromptPackageRead]:
    try:
        rows = service.list_prompt_packages(db, shot_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return [ShotPromptPackageRead.model_validate(row) for row in rows]


@router.post(
    "/shots/{shot_id}/prompt-packages",
    response_model=ShotPromptPackageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_package(
    shot_id: UUID,
    payload: ShotPromptPackageCreate,
    db: Session = Depends(get_db),
) -> ShotPromptPackageRead:
    try:
        row = service.create_prompt_package(db, shot_id, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
        service.StoryboardCrudConflictError,
    ) as error:
        raise _http_for(error) from error
    return ShotPromptPackageRead.model_validate(row)


@router.get(
    "/shots/{shot_id}/prompt-packages/versions/{version}",
    response_model=ShotPromptPackageRead,
)
def get_prompt_package_version(
    shot_id: UUID,
    version: int,
    db: Session = Depends(get_db),
) -> ShotPromptPackageRead:
    try:
        row = service.get_prompt_package_version(db, shot_id, version)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return ShotPromptPackageRead.model_validate(row)


@router.get("/prompt-packages/{package_id}", response_model=ShotPromptPackageRead)
def get_prompt_package(
    package_id: UUID, db: Session = Depends(get_db)
) -> ShotPromptPackageRead:
    try:
        row = service.get_prompt_package(db, package_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return ShotPromptPackageRead.model_validate(row)


@router.patch("/prompt-packages/{package_id}", response_model=ShotPromptPackageRead)
def update_prompt_package(
    package_id: UUID,
    payload: ShotPromptPackageUpdate,
    db: Session = Depends(get_db),
) -> ShotPromptPackageRead:
    try:
        row = service.update_prompt_package(db, package_id, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
    ) as error:
        raise _http_for(error) from error
    return ShotPromptPackageRead.model_validate(row)


# ---------------------------------------------------------------------------
# Model / workflow recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/shots/{shot_id}/recommendations",
    response_model=list[ShotModelRecommendationRead],
)
def list_recommendations(
    shot_id: UUID, db: Session = Depends(get_db)
) -> list[ShotModelRecommendationRead]:
    try:
        rows = service.list_recommendations(db, shot_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return [ShotModelRecommendationRead.model_validate(row) for row in rows]


@router.post(
    "/shots/{shot_id}/recommendations",
    response_model=ShotModelRecommendationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_recommendation(
    shot_id: UUID,
    payload: ShotModelRecommendationCreate,
    db: Session = Depends(get_db),
) -> ShotModelRecommendationRead:
    try:
        row = service.create_recommendation(db, shot_id, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
    ) as error:
        raise _http_for(error) from error
    return ShotModelRecommendationRead.model_validate(row)


@router.get(
    "/recommendations/{recommendation_id}",
    response_model=ShotModelRecommendationRead,
)
def get_recommendation(
    recommendation_id: UUID, db: Session = Depends(get_db)
) -> ShotModelRecommendationRead:
    try:
        row = service.get_recommendation(db, recommendation_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return ShotModelRecommendationRead.model_validate(row)


@router.patch(
    "/recommendations/{recommendation_id}",
    response_model=ShotModelRecommendationRead,
)
def update_recommendation(
    recommendation_id: UUID,
    payload: ShotModelRecommendationUpdate,
    db: Session = Depends(get_db),
) -> ShotModelRecommendationRead:
    try:
        row = service.update_recommendation(db, recommendation_id, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
    ) as error:
        raise _http_for(error) from error
    return ShotModelRecommendationRead.model_validate(row)


@router.delete(
    "/recommendations/{recommendation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_recommendation(
    recommendation_id: UUID, db: Session = Depends(get_db)
) -> Response:
    try:
        service.delete_recommendation(db, recommendation_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Provider profiles
# ---------------------------------------------------------------------------


@router.get("/provider-profiles", response_model=list[ProviderProfileRead])
def list_provider_profiles(db: Session = Depends(get_db)) -> list[ProviderProfileRead]:
    rows = service.list_provider_profiles(db)
    return [ProviderProfileRead.model_validate(row) for row in rows]


@router.post(
    "/provider-profiles",
    response_model=ProviderProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_provider_profile(
    payload: ProviderProfileCreate, db: Session = Depends(get_db)
) -> ProviderProfileRead:
    try:
        row = service.create_provider_profile(db, payload)
    except service.StoryboardCrudError as error:
        raise _http_for(error) from error
    return ProviderProfileRead.model_validate(row)


@router.get("/provider-profiles/{profile_id}", response_model=ProviderProfileRead)
def get_provider_profile(
    profile_id: UUID, db: Session = Depends(get_db)
) -> ProviderProfileRead:
    try:
        row = service.get_provider_profile(db, profile_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return ProviderProfileRead.model_validate(row)


@router.patch("/provider-profiles/{profile_id}", response_model=ProviderProfileRead)
def update_provider_profile(
    profile_id: UUID,
    payload: ProviderProfileUpdate,
    db: Session = Depends(get_db),
) -> ProviderProfileRead:
    try:
        row = service.update_provider_profile(db, profile_id, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
    ) as error:
        raise _http_for(error) from error
    return ProviderProfileRead.model_validate(row)


@router.delete(
    "/provider-profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_provider_profile(profile_id: UUID, db: Session = Depends(get_db)) -> Response:
    try:
        service.delete_provider_profile(db, profile_id)
    except (
        service.StoryboardCrudNotFoundError,
        service.StoryboardCrudConflictError,
    ) as error:
        raise _http_for(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Task provider assignments
# ---------------------------------------------------------------------------


@router.get(
    "/stories/{story_id}/task-assignments",
    response_model=list[TaskProviderAssignmentRead],
)
def list_task_assignments(
    story_id: UUID, db: Session = Depends(get_db)
) -> list[TaskProviderAssignmentRead]:
    try:
        rows = service.list_task_assignments(db, story_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return [TaskProviderAssignmentRead.model_validate(row) for row in rows]


@router.post(
    "/stories/{story_id}/task-assignments",
    response_model=TaskProviderAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_task_assignment(
    story_id: UUID,
    payload: TaskProviderAssignmentCreate,
    db: Session = Depends(get_db),
) -> TaskProviderAssignmentRead:
    try:
        row = service.create_task_assignment(db, story_id, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
        service.StoryboardCrudConflictError,
    ) as error:
        raise _http_for(error) from error
    return TaskProviderAssignmentRead.model_validate(row)


@router.get(
    "/task-assignments/{assignment_id}",
    response_model=TaskProviderAssignmentRead,
)
def get_task_assignment(
    assignment_id: UUID, db: Session = Depends(get_db)
) -> TaskProviderAssignmentRead:
    try:
        row = service.get_task_assignment(db, assignment_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return TaskProviderAssignmentRead.model_validate(row)


@router.patch(
    "/task-assignments/{assignment_id}",
    response_model=TaskProviderAssignmentRead,
)
def update_task_assignment(
    assignment_id: UUID,
    payload: TaskProviderAssignmentUpdate,
    db: Session = Depends(get_db),
) -> TaskProviderAssignmentRead:
    try:
        row = service.update_task_assignment(db, assignment_id, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
    ) as error:
        raise _http_for(error) from error
    return TaskProviderAssignmentRead.model_validate(row)


@router.delete(
    "/task-assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task_assignment(
    assignment_id: UUID, db: Session = Depends(get_db)
) -> Response:
    try:
        service.delete_task_assignment(db, assignment_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


@router.post(
    "/proposals",
    response_model=ProposalReadExtended,
    status_code=status.HTTP_201_CREATED,
)
def create_proposal(
    payload: ProposalCreateExtended, db: Session = Depends(get_db)
) -> ProposalReadExtended:
    try:
        row = service.create_proposal(db, payload)
    except (
        service.StoryboardCrudError,
        service.StoryboardCrudNotFoundError,
    ) as error:
        raise _http_for(error) from error
    return ProposalReadExtended.model_validate(row)


@router.get("/proposals", response_model=list[ProposalReadExtended])
def list_proposals(
    story_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[ProposalReadExtended]:
    rows = service.list_proposals(db, story_id=story_id, status_filter=status_filter)
    return [ProposalReadExtended.model_validate(row) for row in rows]


@router.get("/proposals/{proposal_id}", response_model=ProposalReadExtended)
def get_proposal(
    proposal_id: UUID, db: Session = Depends(get_db)
) -> ProposalReadExtended:
    try:
        row = service.get_proposal(db, proposal_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return ProposalReadExtended.model_validate(row)


@router.patch("/proposals/{proposal_id}", response_model=ProposalReadExtended)
def update_proposal(
    proposal_id: UUID,
    payload: ProposalUpdate,
    db: Session = Depends(get_db),
) -> ProposalReadExtended:
    try:
        row = service.update_proposal(db, proposal_id, payload)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return ProposalReadExtended.model_validate(row)


# ---------------------------------------------------------------------------
# Storyboard versions (list / get)
# ---------------------------------------------------------------------------


@router.get(
    "/stories/{story_id}/versions",
    response_model=list[StoryboardVersionListItem],
)
def list_storyboard_versions(
    story_id: UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[StoryboardVersionListItem]:
    try:
        rows = service.list_storyboard_versions(db, story_id, status_filter=status_filter)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return [StoryboardVersionListItem.model_validate(row) for row in rows]


@router.get(
    "/stories/{story_id}/versions/{version_id}",
    response_model=StoryboardVersionDetail,
)
def get_storyboard_version(
    story_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
) -> StoryboardVersionDetail:
    try:
        row = service.get_storyboard_version_for_story(db, story_id, version_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return StoryboardVersionDetail.model_validate(row)


@router.get("/versions/{version_id}", response_model=StoryboardVersionDetail)
def get_storyboard_version_by_id(
    version_id: UUID, db: Session = Depends(get_db)
) -> StoryboardVersionDetail:
    try:
        row = service.get_storyboard_version(db, version_id)
    except service.StoryboardCrudNotFoundError as error:
        raise _http_for(error) from error
    return StoryboardVersionDetail.model_validate(row)
