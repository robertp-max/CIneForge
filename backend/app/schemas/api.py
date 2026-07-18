from datetime import datetime
from uuid import UUID, uuid4

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.storyboard import StoryRead
from backend.app.schemas.storyboard_settings import (
    DEFAULT_FINAL_HEIGHT,
    DEFAULT_FINAL_WIDTH,
    DEFAULT_FPS,
    DEFAULT_PREVIEW_HEIGHT,
    DEFAULT_PREVIEW_WIDTH,
    DEFAULT_SPEAKING_RATE,
    ProjectStoryboardSettingsRead,
)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    persistence: str = "stub"


class ProjectWorkspaceCreate(BaseModel):
    """One complete, planning-only project-creation request."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    source_mode: Literal["story", "blank", "import"]
    story_title: str = Field(min_length=1, max_length=300)
    base_story: str = ""
    target_duration_sec: float = Field(gt=0)
    audience: str | None = None
    genre: str | None = None
    tone: str | None = None
    point_of_view: str | None = None
    visual_style: str | None = None
    production_notes: str | None = None

    aspect_ratio: str = Field(default="16:9", min_length=1, max_length=32)
    preview_width: int = Field(default=DEFAULT_PREVIEW_WIDTH, gt=0)
    preview_height: int = Field(default=DEFAULT_PREVIEW_HEIGHT, gt=0)
    final_width: int = Field(default=DEFAULT_FINAL_WIDTH, gt=0)
    final_height: int = Field(default=DEFAULT_FINAL_HEIGHT, gt=0)
    fps: float = Field(default=DEFAULT_FPS, gt=0)
    captions_enabled: bool = True
    audio_enabled: bool = True
    speaking_rate: float = Field(default=DEFAULT_SPEAKING_RATE, gt=0)
    prefer_hosted_providers: bool = False
    prefer_local_providers: bool = True
    allow_model_download: Literal[False] = False
    allow_rendering: Literal[False] = False
    require_production_plan_approval: Literal[True] = True
    orchestration_mode: str = Field(min_length=1, max_length=64)
    privacy_preference: str = Field(min_length=1, max_length=100)
    quality_preference: str = Field(min_length=1, max_length=100)
    cost_sensitivity: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_source_material(self):
        if self.source_mode != "blank" and not self.base_story.strip():
            raise ValueError("base_story is required unless source_mode is blank.")
        return self


class ProjectWorkspaceRead(BaseModel):
    project: ProjectRead
    story: StoryRead
    settings: ProjectStoryboardSettingsRead
    idempotent_replay: bool


class CampaignCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    target_duration_sec: float | None = Field(default=None, gt=0)


class CampaignRead(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    target_duration_sec: float | None = None
    created_at: datetime
    persistence: str = "stub"


class JobRead(BaseModel):
    id: UUID
    status: str
    detail: str
    workflow_run_id: UUID | None = None
    comfy_prompt_id: str | None = None
    error_message: str | None = None


class StubStore:
    projects: dict[UUID, ProjectRead] = {}
    campaigns: dict[UUID, CampaignRead] = {}
    jobs: dict[UUID, JobRead] = {}

    @classmethod
    def create_project(cls, payload: ProjectCreate) -> ProjectRead:
        item = ProjectRead(id=uuid4(), name=payload.name, description=payload.description, created_at=datetime.utcnow())
        cls.projects[item.id] = item
        return item

    @classmethod
    def create_campaign(cls, payload: CampaignCreate) -> CampaignRead:
        item = CampaignRead(
            id=uuid4(),
            project_id=payload.project_id,
            name=payload.name,
            target_duration_sec=payload.target_duration_sec,
            created_at=datetime.utcnow(),
        )
        cls.campaigns[item.id] = item
        return item
