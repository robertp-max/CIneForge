"""API-level tests for orchestration_runs router (mounted locally in-test)."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.routes.orchestration_runs import router
from backend.app.db.base import Base, Project, Story
from backend.app.db.session import get_db


@pytest.fixture()
def client_and_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        Base.metadata.tables["projects"],
        Base.metadata.tables["stories"],
        Base.metadata.tables["characters"],
        Base.metadata.tables["orchestration_runs"],
        Base.metadata.tables["orchestration_steps"],
        Base.metadata.tables["orchestration_events"],
        Base.metadata.tables["provider_invocations"],
        Base.metadata.tables["ai_proposal_records"],
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _override_db

    db = SessionLocal()
    project = Project(id=uuid.uuid4(), name="API Project", description=None, created_at=datetime.utcnow())
    db.add(project)
    db.flush()
    story = Story(
        id=uuid.uuid4(),
        project_id=project.id,
        title="API Story",
        base_story="A short story for API tests.",
        target_duration_sec=24.0,
        approval_state="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(story)
    db.commit()
    story_id = story.id
    db.close()

    with TestClient(app) as client:
        yield client, story_id

    engine.dispose()


def test_create_start_get_flow(client_and_db):
    client, story_id = client_and_db
    create = client.post(
        "/orchestration/runs",
        json={
            "story_id": str(story_id),
            "requested_by": "api-tester",
            "routing_mode": "automatic",
            "max_steps": 4,
            "repair_budget": 2,
            "time_budget_sec": 120,
            "task_types": ["shot_list", "production_proposal"],
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["created"] is True
    run_id = body["run"]["id"]
    assert body["run"]["status"] == "pending"

    start = client.post(f"/orchestration/runs/{run_id}/start")
    assert start.status_code == 200, start.text
    assert start.json()["run"]["status"] == "completed"
    assert "awaiting review" in start.json()["message"].lower()

    detail = client.get(f"/orchestration/runs/{run_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "completed"
    assert data["steps"]
    assert data["events"]
    assert data["proposals"]
    assert data["proposals"][0]["status"] == "pending_review"

    events = client.get(f"/orchestration/runs/{run_id}/events")
    assert events.status_code == 200
    assert any(e["event_type"] == "proposal_created" for e in events.json())


def test_idempotent_create_via_api(client_and_db):
    client, story_id = client_and_db
    payload = {
        "story_id": str(story_id),
        "idempotency_key": "api-idem-key-abcdefgh",
        "task_types": ["production_proposal"],
        "max_steps": 2,
    }
    r1 = client.post("/orchestration/runs", json=payload)
    r2 = client.post("/orchestration/runs", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["run"]["id"] == r2.json()["run"]["id"]
    assert r2.json()["idempotent_replay"] is True


def test_cancel_via_api(client_and_db):
    client, story_id = client_and_db
    created = client.post(
        "/orchestration/runs",
        json={
            "story_id": str(story_id),
            "task_types": ["shot_list", "production_proposal"],
            "max_steps": 3,
        },
    )
    run_id = created.json()["run"]["id"]
    canceled = client.post(
        f"/orchestration/runs/{run_id}/cancel",
        json={"reason": "stop", "requested_by": "api-tester"},
    )
    assert canceled.status_code == 200
    assert canceled.json()["run"]["status"] == "canceled"


def test_list_story_runs(client_and_db):
    client, story_id = client_and_db
    client.post(
        "/orchestration/runs",
        json={
            "story_id": str(story_id),
            "task_types": ["production_proposal"],
            "max_steps": 2,
        },
    )
    listed = client.get(f"/orchestration/stories/{story_id}/runs")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


def test_unknown_run_404(client_and_db):
    client, _story_id = client_and_db
    resp = client.get(f"/orchestration/runs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "run_not_found"
