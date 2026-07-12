"""Planning-provider discovery, bounded connection tests, and route preflight."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.schemas.providers import (
    ProviderCapabilitiesResponse,
    ProviderCatalogEntry,
    ProviderCatalogResponse,
    ProviderConnectionTestRequest,
    ProviderConnectionTestResponse,
    ProviderProfileCapabilitiesResponse,
    RoutingPreflightRequest,
    RoutingPreflightResponse,
)
from backend.app.services.planning.provider_contract import (
    ProviderConnectionTester,
    ProviderContractNotFoundError,
    provider_capabilities,
    provider_catalog,
    provider_descriptor,
    provider_profile_capabilities,
    validate_story_routing,
)


router = APIRouter(tags=["providers"])


def get_provider_connection_tester() -> ProviderConnectionTester:
    """Dependency boundary that tests can replace with a mock HTTP transport."""

    return ProviderConnectionTester(get_settings())


def _not_found(error: ProviderContractNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


@router.get("/providers", response_model=ProviderCatalogResponse)
def list_planning_providers() -> ProviderCatalogResponse:
    return provider_catalog()


@router.get("/providers/{provider_identifier}", response_model=ProviderCatalogEntry)
def get_planning_provider(provider_identifier: str) -> ProviderCatalogEntry:
    try:
        return provider_descriptor(provider_identifier)
    except ProviderContractNotFoundError as error:
        raise _not_found(error) from error


@router.get(
    "/providers/{provider_identifier}/capabilities",
    response_model=ProviderCapabilitiesResponse,
)
def get_planning_provider_capabilities(
    provider_identifier: str,
) -> ProviderCapabilitiesResponse:
    try:
        return provider_capabilities(provider_identifier)
    except ProviderContractNotFoundError as error:
        raise _not_found(error) from error


@router.get(
    "/storyboard-crud/provider-profiles/{profile_id}/capabilities",
    response_model=ProviderProfileCapabilitiesResponse,
)
def get_provider_profile_capabilities(
    profile_id: UUID,
    db: Session = Depends(get_db),
) -> ProviderProfileCapabilitiesResponse:
    try:
        return provider_profile_capabilities(db, profile_id)
    except ProviderContractNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/providers/{provider_identifier}/connection-test",
    response_model=ProviderConnectionTestResponse,
)
def test_planning_provider_connection(
    provider_identifier: str,
    payload: ProviderConnectionTestRequest,
    tester: ProviderConnectionTester = Depends(get_provider_connection_tester),
) -> ProviderConnectionTestResponse:
    try:
        return tester.test(provider_identifier, timeout_sec=payload.timeout_sec)
    except ProviderContractNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/stories/{story_id}/routing/validate",
    response_model=RoutingPreflightResponse,
)
def validate_routing_preflight(
    story_id: UUID,
    payload: RoutingPreflightRequest,
    db: Session = Depends(get_db),
) -> RoutingPreflightResponse:
    try:
        return validate_story_routing(db, story_id, payload)
    except ProviderContractNotFoundError as error:
        raise _not_found(error) from error
