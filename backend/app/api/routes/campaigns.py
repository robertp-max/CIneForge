from uuid import UUID

from fastapi import APIRouter

from backend.app.core.errors import not_found
from backend.app.schemas.api import CampaignCreate, CampaignRead, StubStore


router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignRead, status_code=201)
def create_campaign(payload: CampaignCreate) -> CampaignRead:
    return StubStore.create_campaign(payload)


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: UUID) -> CampaignRead:
    item = StubStore.campaigns.get(campaign_id)
    if item is None:
        raise not_found("Campaign not found. DB persistence wiring is scheduled after Sprint 1A foundation.")
    return item

