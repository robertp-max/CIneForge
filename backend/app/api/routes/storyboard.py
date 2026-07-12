from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import Chapter, Character, Scene, Shot, Story
from backend.app.db.session import get_db
from backend.app.schemas.storyboard import (
    ApprovalRequest,
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
    PhaseASnapshot,
    ReorderRequest,
    SceneCreate,
    SceneRead,
    SceneUpdate,
    ShotCreate,
    ShotCharacterLinkCreate,
    ShotCharacterLinkRead,
    ShotCharacterReplaceRequest,
    ShotRead,
    ShotUpdate,
    StoryCreate,
    StoryRead,
    StoryUpdate,
    StoryboardReadiness,
    StoryboardVersionRead,
)
from backend.app.services import storyboard as service
from backend.app.services import storyboard_snapshot


router = APIRouter(prefix="/storyboard", tags=["storyboard"])


def _domain_error(error: service.StoryboardDomainError, conflict: bool = False) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT if conflict else status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(error),
    )


def _conflict_error(error: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.post("/stories", response_model=StoryRead, status_code=201)
def create_story(payload: StoryCreate, db: Session = Depends(get_db)) -> Story:
    try:
        return service.create_story(db, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.get("/stories", response_model=list[StoryRead])
def list_stories(project_id: UUID | None = None, db: Session = Depends(get_db)) -> list[Story]:
    query = select(Story).order_by(Story.created_at.desc())
    if project_id:
        query = query.where(Story.project_id == project_id)
    return list(db.scalars(query))


@router.get("/stories/{story_id}", response_model=StoryRead)
def get_story(story_id: UUID, db: Session = Depends(get_db)) -> Story:
    try:
        return service._story_or_error(db, story_id)
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/stories/{story_id}", response_model=StoryRead)
def patch_story(story_id: UUID, payload: StoryUpdate, db: Session = Depends(get_db)) -> Story:
    try:
        return service.update_story(db, story_id, payload)
    except service.StoryboardConflictError as error:
        raise _conflict_error(error) from error
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/stories/{story_id}/characters", response_model=CharacterRead, status_code=201)
def create_character(story_id: UUID, payload: CharacterCreate, db: Session = Depends(get_db)) -> Character:
    try:
        return service.create_character(db, story_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.get("/stories/{story_id}/characters", response_model=list[CharacterRead])
def list_characters(story_id: UUID, db: Session = Depends(get_db)) -> list[Character]:
    return list(
        db.scalars(
            select(Character).where(
                Character.story_id == story_id, Character.archived_at.is_(None)
            )
        )
    )


@router.patch("/characters/{character_id}", response_model=CharacterRead)
def patch_character(
    character_id: UUID, payload: CharacterUpdate, db: Session = Depends(get_db)
) -> Character:
    try:
        return service.update_character(db, character_id, payload)
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_character(
    character_id: UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
) -> Response:
    try:
        service.archive_character(db, character_id, reason=reason)
    except service.StoryboardConflictError as error:
        raise _conflict_error(error) from error
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/stories/{story_id}/chapters", response_model=ChapterRead, status_code=201)
def create_chapter(story_id: UUID, payload: ChapterCreate, db: Session = Depends(get_db)) -> Chapter:
    try:
        return service.create_chapter(db, story_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def patch_chapter(
    chapter_id: UUID, payload: ChapterUpdate, db: Session = Depends(get_db)
) -> Chapter:
    try:
        return service.update_chapter(db, chapter_id, payload)
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_chapter(
    chapter_id: UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
) -> Response:
    try:
        service.archive_chapter(db, chapter_id, reason=reason)
    except service.StoryboardConflictError as error:
        raise _conflict_error(error) from error
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chapters/{chapter_id}/scenes", response_model=SceneRead, status_code=201)
def create_scene(chapter_id: UUID, payload: SceneCreate, db: Session = Depends(get_db)) -> Scene:
    try:
        return service.create_scene(db, chapter_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.patch("/scenes/{scene_id}", response_model=SceneRead)
def patch_scene(
    scene_id: UUID, payload: SceneUpdate, db: Session = Depends(get_db)
) -> Scene:
    try:
        return service.update_scene(db, scene_id, payload)
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_scene(
    scene_id: UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
) -> Response:
    try:
        service.archive_scene(db, scene_id, reason=reason)
    except service.StoryboardConflictError as error:
        raise _conflict_error(error) from error
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/scenes/{scene_id}/shots", response_model=ShotRead, status_code=201)
def create_shot(scene_id: UUID, payload: ShotCreate, db: Session = Depends(get_db)) -> Shot:
    try:
        return service.create_shot(db, scene_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.put("/shots/{shot_id}", response_model=ShotRead)
def update_shot(shot_id: UUID, payload: ShotCreate, db: Session = Depends(get_db)) -> Shot:
    try:
        return service.update_shot(db, shot_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.patch("/shots/{shot_id}", response_model=ShotRead)
def patch_shot(shot_id: UUID, payload: ShotUpdate, db: Session = Depends(get_db)) -> Shot:
    try:
        return service.patch_shot(db, shot_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.delete("/shots/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_shot(
    shot_id: UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
) -> Response:
    try:
        service.archive_shot(db, shot_id, reason=reason)
    except service.StoryboardConflictError as error:
        raise _conflict_error(error) from error
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/shots/{shot_id}/characters", response_model=list[ShotCharacterLinkRead])
def list_shot_characters(shot_id: UUID, db: Session = Depends(get_db)):
    try:
        return service.list_shot_characters(db, shot_id)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.put("/shots/{shot_id}/characters", response_model=list[ShotCharacterLinkRead])
def replace_shot_characters(
    shot_id: UUID,
    payload: ShotCharacterReplaceRequest,
    db: Session = Depends(get_db),
):
    try:
        return service.replace_shot_characters(db, shot_id, payload.characters)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.post(
    "/shots/{shot_id}/characters",
    response_model=ShotCharacterLinkRead,
    status_code=201,
)
def create_shot_character_link(
    shot_id: UUID,
    payload: ShotCharacterLinkCreate,
    db: Session = Depends(get_db),
):
    try:
        return service.create_shot_character_link(db, shot_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.delete("/shots/{shot_id}/characters/{character_id}", status_code=204)
def delete_shot_character_link(
    shot_id: UUID, character_id: UUID, db: Session = Depends(get_db)
) -> Response:
    try:
        service.delete_shot_character_link(db, shot_id, character_id)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error
    return Response(status_code=204)


@router.post("/stories/{story_id}/chapters/reorder", status_code=204)
def reorder_chapters(story_id: UUID, payload: ReorderRequest, db: Session = Depends(get_db)) -> Response:
    try:
        service.reorder(db, Chapter, "story_id", story_id, payload.ordered_ids)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error
    return Response(status_code=204)


@router.post("/chapters/{chapter_id}/scenes/reorder", status_code=204)
def reorder_scenes(chapter_id: UUID, payload: ReorderRequest, db: Session = Depends(get_db)) -> Response:
    try:
        service.reorder(db, Scene, "chapter_id", chapter_id, payload.ordered_ids)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error
    return Response(status_code=204)


@router.post("/scenes/{scene_id}/shots/reorder", status_code=204)
def reorder_shots(scene_id: UUID, payload: ReorderRequest, db: Session = Depends(get_db)) -> Response:
    try:
        service.reorder(db, Shot, "scene_id", scene_id, payload.ordered_ids)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error
    return Response(status_code=204)


@router.get("/stories/{story_id}/aggregate")
def get_aggregate(story_id: UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return service.aggregate(db, story_id)
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/stories/{story_id}/phase-a", response_model=PhaseASnapshot)
def get_phase_a_snapshot(story_id: UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return service.phase_a_snapshot(db, story_id)
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/stories/{story_id}/readiness", response_model=StoryboardReadiness)
def get_readiness(story_id: UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return service.readiness(db, story_id)
    except service.StoryboardDomainError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/stories/{story_id}/approve", response_model=StoryboardVersionRead)
def approve(story_id: UUID, payload: ApprovalRequest, db: Session = Depends(get_db)):
    try:
        return service.approve(
            db,
            story_id,
            payload.approved_by,
            payload.expected_revision,
        )
    except service.StoryboardConflictError as error:
        raise _conflict_error(error) from error
    except service.StoryboardDomainError as error:
        raise _domain_error(error, conflict=True) from error


@router.get("/stories/{story_id}/export.json")
def export_json(story_id: UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return storyboard_snapshot.build_canonical_snapshot(db, story_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/stories/{story_id}/shot-list.csv")
def export_shot_csv(story_id: UUID, db: Session = Depends(get_db)) -> Response:
    return Response(
        content=service.export_csv(db, story_id),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=shot-list.csv"},
    )
