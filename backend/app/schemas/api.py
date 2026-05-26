from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    persistence: str = "stub"


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

