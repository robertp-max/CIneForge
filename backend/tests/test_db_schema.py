from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from backend.app.db.base import Base


REQUIRED_TABLES = {
    "hardware_profiles",
    "projects",
    "campaigns",
    "tracks",
    "timeline_slots",
    "prompts",
    "negative_prompts",
    "models",
    "model_variants",
    "quantizations",
    "text_encoders",
    "vaes",
    "loras",
    "lora_combinations",
    "lora_combination_items",
    "workflow_templates",
    "clips",
    "clip_iterations",
    "workflow_runs",
    "comfy_jobs",
    "generated_assets",
    "file_outputs",
    "benchmark_runs",
    "ffmpeg_jobs",
    "audit_logs",
    "error_logs",
    "ai_proposal_records",
    "autonomy_runs",
    "autonomy_run_events",
    "autonomy_policies",
    "qa_reports",
    "retry_attempts",
    "creative_review_notes",
    "candidate_scores",
}

COMFY_JOB_WORKER_COLUMNS = {
    "worker_id",
    "reserved_at",
    "heartbeat_at",
    "attempt_count",
    "last_state_change_at",
    "recovery_metadata",
}


def test_required_schema_tables_exist():
    assert REQUIRED_TABLES.issubset(set(Base.metadata.tables))


def test_queue_worker_fields_exist_in_metadata():
    comfy_job_columns = set(Base.metadata.tables["comfy_jobs"].columns.keys())

    assert COMFY_JOB_WORKER_COLUMNS.issubset(comfy_job_columns)


def test_alembic_upgrade_creates_required_tables(tmp_path):
    db_path = tmp_path / "cineforge_alembic_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(config, "head")

    engine = create_engine(db_url)
    try:
        table_names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert REQUIRED_TABLES.issubset(table_names)


def test_alembic_upgrade_includes_worker_ownership_fields(tmp_path):
    db_path = tmp_path / "cineforge_alembic_worker_fields_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(config, "head")

    engine = create_engine(db_url)
    try:
        columns = {column["name"] for column in inspect(engine).get_columns("comfy_jobs")}
    finally:
        engine.dispose()
    assert COMFY_JOB_WORKER_COLUMNS.issubset(columns)
