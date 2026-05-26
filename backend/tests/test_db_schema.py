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


def test_required_schema_tables_exist():
    assert REQUIRED_TABLES.issubset(set(Base.metadata.tables))


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
