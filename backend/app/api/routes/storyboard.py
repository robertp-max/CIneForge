from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import Chapter, Character, Scene, Shot, Story, VoiceProfile
from backend.app.db.session import get_db
from backend.app.schemas.storyboard import (
    ApprovalRequest,
    ChapterCreate,
    ChapterRead,
    CharacterCreate,
    CharacterRead,
    PhaseASnapshot,
    ProposalCreate,
    ProposalRead,
    ReorderRequest,
    SceneCreate,
    SceneRead,
    ShotCreate,
    ShotRead,
    StoryCreate,
    StoryRead,
    StoryUpdate,
    StoryboardReadiness,
    StoryboardVersionRead,
    VoiceProfileCreate,
    VoiceProfileRead,
)
from backend.app.services import storyboard as service


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
    return list(db.scalars(select(Character).where(Character.story_id == story_id)))


@router.post("/stories/{story_id}/voices", response_model=VoiceProfileRead, status_code=201)
def create_voice(story_id: UUID, payload: VoiceProfileCreate, db: Session = Depends(get_db)) -> VoiceProfile:
    try:
        return service.create_voice_profile(db, story_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.get("/stories/{story_id}/voices", response_model=list[VoiceProfileRead])
def list_voices(story_id: UUID, db: Session = Depends(get_db)) -> list[VoiceProfile]:
    return list(db.scalars(select(VoiceProfile).where(VoiceProfile.story_id == story_id)))


@router.post("/stories/{story_id}/chapters", response_model=ChapterRead, status_code=201)
def create_chapter(story_id: UUID, payload: ChapterCreate, db: Session = Depends(get_db)) -> Chapter:
    try:
        return service.create_chapter(db, story_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


@router.post("/chapters/{chapter_id}/scenes", response_model=SceneRead, status_code=201)
def create_scene(chapter_id: UUID, payload: SceneCreate, db: Session = Depends(get_db)) -> Scene:
    try:
        return service.create_scene(db, chapter_id, payload)
    except service.StoryboardDomainError as error:
        raise _domain_error(error) from error


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
        return service.approve(db, story_id, payload.approved_by)
    except service.StoryboardConflictError as error:
        raise _conflict_error(error) from error
    except service.StoryboardDomainError as error:
        raise _domain_error(error, conflict=True) from error


@router.post("/proposals", response_model=ProposalRead, status_code=201)
def store_proposal(payload: ProposalCreate, db: Session = Depends(get_db)):
    return service.create_proposal(db, payload)


@router.get("/stories/{story_id}/export.json")
def export_json(story_id: UUID, db: Session = Depends(get_db)) -> dict:
    return service.aggregate(db, story_id)


@router.get("/stories/{story_id}/shot-list.csv")
def export_shot_csv(story_id: UUID, db: Session = Depends(get_db)) -> Response:
    return Response(
        content=service.export_csv(db, story_id),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=shot-list.csv"},
    )
