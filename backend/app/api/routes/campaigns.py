from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.errors import not_found
from backend.app.db.base import Campaign, Project
from backend.app.db.session import get_db
from backend.app.schemas.api import CampaignCreate, CampaignRead


router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def campaign_to_response(campaign: Campaign) -> CampaignRead:
    target_duration_sec = (
        float(campaign.target_duration_sec) if campaign.target_duration_sec is not None else None
    )
    return CampaignRead(
        id=campaign.id,
        project_id=campaign.project_id,
        name=campaign.name,
        target_duration_sec=target_duration_sec,
        created_at=campaign.created_at,
        persistence="db",
    )


@router.post("", response_model=CampaignRead, status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)) -> CampaignRead:
    project = db.get(Project, payload.project_id)
    if project is None:
        raise not_found("Project not found.")

    campaign = Campaign(
        project_id=payload.project_id,
        name=payload.name,
        target_duration_sec=payload.target_duration_sec,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_to_response(campaign)


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: UUID, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise not_found("Campaign not found.")
    return campaign_to_response(campaign)
