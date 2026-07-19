from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import (
    Base,
    Project,
    ProjectStoryboardSettings,
    ProjectWorkspaceCreation,
    Story,
)
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.schemas.api import ProjectWorkspaceCreate
from backend.app.services import project_workspace


def _payload(**overrides) -> dict:
    payload = {
        "idempotency_key": "project-workspace-test-key-001",
        "name": "Atomic Project",
        "description": "Created in one transaction",
        "source_mode": "story",
        "story_title": "Atomic Project",
        "base_story": "A complete source story.",
        "target_duration_sec": 315,
        "audience": "Families",
        "genre": "Drama",
        "tone": "Hopeful",
        "point_of_view": "Third person",
        "visual_style": "Naturalistic",
        "production_notes": "Planning only.",
        "aspect_ratio": "2.39:1",
        "preview_width": 1280,
        "preview_height": 536,
        "final_width": 1920,
        "final_height": 804,
        "fps": 30,
        "captions_enabled": False,
        "audio_enabled": True,
        "speaking_rate": 1.15,
        "prefer_hosted_providers": True,
        "prefer_local_providers": True,
        "allow_model_download": False,
        "allow_rendering": False,
        "require_production_plan_approval": True,
        "orchestration_mode": "Hybrid",
        "privacy_preference": "Hosted providers allowed",
        "quality_preference": "Quality weighted",
        "cost_sensitivity": "Balanced",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'workspace.db').as_posix()}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _count(db: Session, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def test_workspace_api_creates_and_reloads_all_wizard_values(client: TestClient, db_session: Session):
    response = client.post("/projects/workspace", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["idempotent_replay"] is False
    assert body["project"]["name"] == "Atomic Project"
    assert body["story"] | {
        "audience": "Families",
        "genre": "Drama",
        "tone": "Hopeful",
        "point_of_view": "Third person",
        "visual_style": "Naturalistic",
        "production_notes": "Planning only.",
    } == body["story"]
    assert body["story"]["approval_state"] == "draft"

    project_id = body["project"]["id"]
    settings = client.get(f"/projects/{project_id}/storyboard-settings").json()
    assert settings["aspect_ratio"] == "2.39:1"
    assert (settings["preview_width"], settings["preview_height"]) == (1280, 536)
    assert (settings["final_width"], settings["final_height"]) == (1920, 804)
    assert settings["fps"] == 30
    assert settings["captions_enabled"] is False
    assert settings["audio_enabled"] is True
    assert settings["speaking_rate"] == 1.15
    assert settings["prefer_hosted_providers"] is True
    assert settings["prefer_local_providers"] is True
    assert settings["allow_model_download"] is False
    assert settings["allow_rendering"] is False
    assert settings["require_production_plan_approval"] is True
    assert settings["prompting_policy_json"] | {
        "orchestration_mode": "Hybrid",
        "privacy_preference": "Hosted providers allowed",
        "quality_preference": "Quality weighted",
        "cost_sensitivity": "Balanced",
    } == settings["prompting_policy_json"]
    assert _count(db_session, Project) == 1
    assert _count(db_session, Story) == 1
    assert _count(db_session, ProjectStoryboardSettings) == 1


def test_workspace_idempotent_replay_reuses_all_rows(client: TestClient, db_session: Session):
    first = client.post("/projects/workspace", json=_payload())
    second = client.post("/projects/workspace", json=_payload())

    assert first.status_code == second.status_code == 201
    assert second.json()["idempotent_replay"] is True
    assert second.json()["project"]["id"] == first.json()["project"]["id"]
    assert second.json()["story"]["id"] == first.json()["story"]["id"]
    assert second.json()["settings"]["id"] == first.json()["settings"]["id"]
    assert _count(db_session, Project) == 1
    assert _count(db_session, Story) == 1
    assert _count(db_session, ProjectStoryboardSettings) == 1
    assert _count(db_session, ProjectWorkspaceCreation) == 1


def test_workspace_rejects_idempotency_key_reuse_for_different_request(client: TestClient):
    assert client.post("/projects/workspace", json=_payload()).status_code == 201
    conflict = client.post("/projects/workspace", json=_payload(name="Different Project"))

    assert conflict.status_code == 409
    assert "different project workspace request" in conflict.json()["detail"]


@pytest.mark.parametrize("failure_helper", ["_new_story", "_new_settings"])
def test_workspace_rolls_back_when_story_or_settings_creation_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, failure_helper: str
):
    def fail(*_args, **_kwargs):
        raise RuntimeError("forced workspace child failure")

    monkeypatch.setattr(project_workspace, failure_helper, fail)

    with pytest.raises(RuntimeError, match="forced workspace child failure"):
        project_workspace.create_project_workspace(
            db_session, ProjectWorkspaceCreate.model_validate(_payload())
        )

    assert _count(db_session, Project) == 0
    assert _count(db_session, Story) == 0
    assert _count(db_session, ProjectStoryboardSettings) == 0
    assert _count(db_session, ProjectWorkspaceCreation) == 0


def test_workspace_safe_defaults_are_persisted(client: TestClient):
    payload = _payload()
    for field in (
        "preview_width",
        "preview_height",
        "final_width",
        "final_height",
        "fps",
        "captions_enabled",
        "audio_enabled",
        "speaking_rate",
        "prefer_hosted_providers",
        "prefer_local_providers",
        "allow_model_download",
        "allow_rendering",
        "require_production_plan_approval",
    ):
        payload.pop(field)

    settings = client.post("/projects/workspace", json=payload).json()["settings"]
    assert (settings["preview_width"], settings["preview_height"]) == (1280, 720)
    assert (settings["final_width"], settings["final_height"]) == (1920, 1080)
    assert settings["fps"] == 24
    assert settings["captions_enabled"] is True
    assert settings["audio_enabled"] is True
    assert settings["speaking_rate"] == 1
    assert settings["prefer_hosted_providers"] is False
    assert settings["prefer_local_providers"] is True
    assert settings["allow_model_download"] is False
    assert settings["allow_rendering"] is False
    assert settings["require_production_plan_approval"] is True


def test_workspace_can_derive_title_from_the_single_prompt(client: TestClient):
    response = client.post(
        "/projects/workspace",
        json=_payload(
            auto_title=True,
            name="CineForge Production",
            story_title="CineForge Production",
            base_story="Create a five-minute cinematic narrative of The Northern Crossing using a grounded style.",
        ),
    )

    assert response.status_code == 201
    assert response.json()["project"]["name"] == "The Northern Crossing"
    assert response.json()["story"]["title"] == "The Northern Crossing"
