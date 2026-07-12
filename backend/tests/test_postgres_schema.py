import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID

from backend.tests.test_db_schema import REQUIRED_TABLES, STORYBOARD_PHASE1_TABLES


POSTGRES_URL_ENV = "CINEFORGE_TEST_POSTGRES_URL"
QUEUE_CRITICAL_COLUMNS = {
    "workflow_templates": {
        "id",
        "name",
        "version",
        "workflow_api_json",
        "manifest_json",
        "sha256",
        "custom_node_snapshot",
        "created_at",
    },
    "workflow_runs": {
        "id",
        "clip_iteration_id",
        "workflow_template_id",
        "patched_workflow_json",
        "patch_payload_json",
        "status",
        "started_at",
        "ended_at",
    },
    "comfy_jobs": {
        "id",
        "workflow_run_id",
        "prompt_id",
        "client_id",
        "queue_number",
        "status",
        "worker_id",
        "reserved_at",
        "heartbeat_at",
        "attempt_count",
        "last_state_change_at",
        "recovery_metadata",
        "node_errors",
        "websocket_events",
        "error_message",
        "submitted_at",
        "completed_at",
    },
    "audit_logs": {"id", "entity_type", "entity_id", "action", "details", "created_at"},
    "error_logs": {"id", "source", "severity", "message", "details", "created_at"},
}
JSONB_COLUMNS = {
    ("workflow_templates", "workflow_api_json"),
    ("workflow_templates", "manifest_json"),
    ("workflow_templates", "custom_node_snapshot"),
    ("workflow_runs", "patched_workflow_json"),
    ("workflow_runs", "patch_payload_json"),
    ("comfy_jobs", "recovery_metadata"),
    ("comfy_jobs", "node_errors"),
    ("comfy_jobs", "websocket_events"),
    ("audit_logs", "details"),
    ("error_logs", "details"),
    ("project_storyboard_settings", "continuity_policy_json"),
    ("project_storyboard_settings", "prompting_policy_json"),
    ("project_storyboard_settings", "voice_policy_json"),
    ("project_storyboard_settings", "approval_policy_json"),
    ("orchestration_runs", "routing_snapshot_json"),
    ("orchestration_runs", "default_provider_snapshot_json"),
    ("orchestration_steps", "metadata_json"),
    ("orchestration_events", "details_json"),
    ("provider_invocations", "usage_json"),
    ("voice_recipes", "design_metadata_json"),
    ("gpu_resource_leases", "metadata_json"),
    ("ai_proposal_records", "validation_report_json"),
    ("ai_proposal_records", "warnings_json"),
    ("model_variants", "native_voice_capability_metadata_json"),
    ("voice_profiles", "design_metadata_json"),
}
UUID_COLUMNS = {
    ("workflow_templates", "id"),
    ("workflow_runs", "id"),
    ("workflow_runs", "clip_iteration_id"),
    ("workflow_runs", "workflow_template_id"),
    ("comfy_jobs", "id"),
    ("comfy_jobs", "workflow_run_id"),
    ("audit_logs", "id"),
    ("audit_logs", "entity_id"),
    ("error_logs", "id"),
    ("project_storyboard_settings", "id"),
    ("project_storyboard_settings", "project_id"),
    ("orchestration_runs", "id"),
    ("orchestration_runs", "story_id"),
    ("orchestration_steps", "id"),
    ("orchestration_steps", "run_id"),
    ("provider_invocations", "id"),
    ("voice_recipes", "id"),
    ("voice_previews", "id"),
    ("gpu_resource_leases", "id"),
}
PHASE1_POSTGRES_FK_NAMES = {
    "fk_stories_active_storyboard_version",
    "fk_stories_default_provider_profile",
    "fk_shot_prompt_packages_provider_profile",
}


def _postgres_url() -> str | None:
    return os.environ.get(POSTGRES_URL_ENV)


def _skip_without_postgres_url() -> str:
    url = _postgres_url()
    if not url:
        pytest.skip(f"{POSTGRES_URL_ENV} is not configured")
    return url


@pytest.fixture(scope="module")
def postgres_url() -> str:
    return _skip_without_postgres_url()


@pytest.fixture(scope="module")
def upgraded_postgres_engine(postgres_url: str):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")

    engine = create_engine(postgres_url)
    try:
        yield engine
    finally:
        engine.dispose()


def test_postgres_schema_check_skips_without_url():
    _skip_without_postgres_url()


def test_postgres_alembic_upgrade_head(postgres_url: str):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)

    command.upgrade(config, "head")


def test_postgres_required_tables_exist(upgraded_postgres_engine):
    table_names = set(inspect(upgraded_postgres_engine).get_table_names())

    assert REQUIRED_TABLES.issubset(table_names)
    assert STORYBOARD_PHASE1_TABLES.issubset(table_names)


def test_postgres_queue_tables_have_expected_columns(upgraded_postgres_engine):
    inspector = inspect(upgraded_postgres_engine)

    for table_name, expected_columns in QUEUE_CRITICAL_COLUMNS.items():
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert expected_columns.issubset(columns)

    for table_name, column_name in JSONB_COLUMNS:
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert isinstance(columns[column_name]["type"], JSONB)

    for table_name, column_name in UUID_COLUMNS:
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert isinstance(columns[column_name]["type"], UUID)


def test_postgres_phase1_bare_uuid_fks_exist(upgraded_postgres_engine):
    inspector = inspect(upgraded_postgres_engine)
    fk_names = set()
    for table_name in ("stories", "shot_prompt_packages"):
        for fk in inspector.get_foreign_keys(table_name):
            if fk.get("name"):
                fk_names.add(fk["name"])
    assert PHASE1_POSTGRES_FK_NAMES.issubset(fk_names)
