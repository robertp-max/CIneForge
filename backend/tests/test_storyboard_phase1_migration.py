"""Migration parity tests for Storyboard Phase 1 persistence."""

from datetime import datetime, timezone
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.tests.test_db_schema import PHASE1_EXTENDED_COLUMNS, STORYBOARD_PHASE1_TABLES


PHASE_A_REVISION = "d9e8c7b6a5f4"
PHASE1_REVISION = "e1a2b3c4d5e6"

PHASE_A_TABLES = {
    "stories",
    "planning_media_assets",
    "characters",
    "voice_profiles",
    "character_reference_assets",
    "chapters",
    "scenes",
    "shots",
    "shot_characters",
    "shot_narrations",
    "shot_prompt_packages",
    "shot_model_recommendations",
    "storyboard_versions",
    "provider_profiles",
    "task_provider_assignments",
}

FORBIDDEN_COLUMN_FRAGMENTS = (
    "raw_prompt",
    "raw_response",
    "request_body",
    "response_body",
    "api_key",
    "credential",
    "hidden_reasoning",
    "audio_bytes",
    "audio_base64",
    "base64_audio",
    "binary_audio",
    "voice_clone",
    "comfy_queue",
    "ffmpeg_queue",
    "media_queue",
    "model_download_queue",
    "render_queue",
)


def _alembic_config(db_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _insert_phase_a_seed(connection) -> dict:
    """Insert representative Phase A rows used to verify upgrade/backfill safety."""
    project_id = str(uuid4())
    story_id = str(uuid4())
    character_id = str(uuid4())
    now = _now().isoformat()

    connection.execute(
        text(
            "INSERT INTO projects (id, name, description, created_at) "
            "VALUES (:id, :name, :description, :created_at)"
        ),
        {
            "id": project_id,
            "name": "Phase1 Migration Project",
            "description": "seed",
            "created_at": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO stories ("
            "id, project_id, title, base_story, target_duration_sec, approval_state, "
            "created_at, updated_at"
            ") VALUES ("
            ":id, :project_id, :title, :base_story, :target_duration_sec, :approval_state, "
            ":created_at, :updated_at"
            ")"
        ),
        {
            "id": story_id,
            "project_id": project_id,
            "title": "Seed Story",
            "base_story": "Once upon a time",
            "target_duration_sec": 90,
            "approval_state": "draft",
            "created_at": now,
            "updated_at": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO characters ("
            "id, story_id, name, approval_state, created_at, updated_at"
            ") VALUES ("
            ":id, :story_id, :name, :approval_state, :created_at, :updated_at"
            ")"
        ),
        {
            "id": character_id,
            "story_id": story_id,
            "name": "Narrator",
            "approval_state": "draft",
            "created_at": now,
            "updated_at": now,
        },
    )

    voice_rows = [
        {
            "id": str(uuid4()),
            "key": "placeholder",
            "source_type": "placeholder",
            "provider": None,
            "provider_voice_reference": None,
            "consent_confirmed": False,
        },
        {
            "id": str(uuid4()),
            "key": "consented",
            "source_type": "user_provided_consented",
            "provider": None,
            "provider_voice_reference": None,
            "consent_confirmed": True,
        },
        {
            "id": str(uuid4()),
            "key": "provider_ref",
            "source_type": "synthetic",
            "provider": "elevenlabs",
            "provider_voice_reference": "voice_abc123",
            "consent_confirmed": False,
        },
        {
            "id": str(uuid4()),
            "key": "manual_fallback",
            "source_type": "synthetic",
            "provider": "qwen",
            "provider_voice_reference": None,
            "consent_confirmed": False,
        },
        {
            "id": str(uuid4()),
            "key": "consent_flag_only",
            "source_type": "uploaded",
            "provider": None,
            "provider_voice_reference": None,
            "consent_confirmed": True,
        },
    ]

    for row in voice_rows:
        connection.execute(
            text(
                "INSERT INTO voice_profiles ("
                "id, story_id, character_id, name, source_type, provider, "
                "provider_voice_reference, consent_required, consent_confirmed, "
                "approval_state, created_at, updated_at"
                ") VALUES ("
                ":id, :story_id, :character_id, :name, :source_type, :provider, "
                ":provider_voice_reference, :consent_required, :consent_confirmed, "
                ":approval_state, :created_at, :updated_at"
                ")"
            ),
            {
                "id": row["id"],
                "story_id": story_id,
                "character_id": character_id,
                "name": f"Voice {row['key']}",
                "source_type": row["source_type"],
                "provider": row["provider"],
                "provider_voice_reference": row["provider_voice_reference"],
                "consent_required": bool(row["consent_confirmed"]),
                "consent_confirmed": row["consent_confirmed"],
                "approval_state": "draft",
                "created_at": now,
                "updated_at": now,
            },
        )

    connection.execute(
        text(
            "INSERT INTO models (id, family, name, evidence_level) "
            "VALUES (:id, :family, :name, :evidence_level)"
        ),
        {
            "id": str(uuid4()),
            "family": "test-family",
            "name": "test-model",
            "evidence_level": "unknown",
        },
    )
    model_id = connection.execute(text("SELECT id FROM models LIMIT 1")).scalar_one()
    variant_id = str(uuid4())
    connection.execute(
        text(
            "INSERT INTO model_variants ("
            "id, model_id, variant_name, compatible_24gb_status"
            ") VALUES ("
            ":id, :model_id, :variant_name, :compatible_24gb_status"
            ")"
        ),
        {
            "id": variant_id,
            "model_id": model_id,
            "variant_name": "base",
            "compatible_24gb_status": "unknown",
        },
    )

    proposal_id = str(uuid4())
    connection.execute(
        text(
            "INSERT INTO ai_proposal_records ("
            "id, proposal_type, payload, status, validation_errors, created_at"
            ") VALUES ("
            ":id, :proposal_type, :payload, :status, :validation_errors, :created_at"
            ")"
        ),
        {
            "id": proposal_id,
            "proposal_type": "storyboard_outline",
            "payload": "{}",
            "status": "pending_review",
            "validation_errors": "[]",
            "created_at": now,
        },
    )

    return {
        "project_id": project_id,
        "story_id": story_id,
        "voice_rows": voice_rows,
        "variant_id": variant_id,
        "proposal_id": proposal_id,
    }


def test_upgrade_from_phase_a_preserves_rows_and_backfills(tmp_path):
    db_path = tmp_path / "phase1_upgrade_from_a.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    config = _alembic_config(db_url)

    command.upgrade(config, PHASE_A_REVISION)

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            seed = _insert_phase_a_seed(conn)
            story_title = conn.execute(
                text("SELECT title FROM stories WHERE id = :id"),
                {"id": seed["story_id"]},
            ).scalar_one()
            assert story_title == "Seed Story"

        command.upgrade(config, "head")

        with engine.begin() as conn:
            tables = set(inspect(conn).get_table_names())
            assert PHASE_A_TABLES.issubset(tables)
            assert STORYBOARD_PHASE1_TABLES.issubset(tables)

            # Phase A row preserved
            preserved = conn.execute(
                text("SELECT title, target_duration_sec FROM stories WHERE id = :id"),
                {"id": seed["story_id"]},
            ).mappings().one()
            assert preserved["title"] == "Seed Story"
            assert float(preserved["target_duration_sec"]) == 90.0

            # Extended columns present
            inspector = inspect(conn)
            for table_name, expected_columns in PHASE1_EXTENDED_COLUMNS.items():
                columns = {c["name"] for c in inspector.get_columns(table_name)}
                assert expected_columns.issubset(columns), table_name

            modes = {
                row["name"].removeprefix("Voice "): row["setup_mode"]
                for row in conn.execute(
                    text(
                        "SELECT name, setup_mode FROM voice_profiles WHERE story_id = :story_id"
                    ),
                    {"story_id": seed["story_id"]},
                ).mappings()
            }
            assert modes["placeholder"] == "placeholder"
            assert modes["consented"] == "user_provided_consented"
            assert modes["consent_flag_only"] == "user_provided_consented"
            assert modes["provider_ref"] == "existing_provider_voice"
            # Generic synthetic + provider name must NOT become qwen_* / parler_*.
            assert modes["manual_fallback"] == "manual"

            capability = conn.execute(
                text(
                    "SELECT native_voice_capability FROM model_variants WHERE id = :id"
                ),
                {"id": seed["variant_id"]},
            ).scalar_one()
            assert capability == "unknown"

            proposal = conn.execute(
                text(
                    "SELECT story_id, orchestration_run_id, validation_report_json, warnings_json "
                    "FROM ai_proposal_records WHERE id = :id"
                ),
                {"id": seed["proposal_id"]},
            ).mappings().one()
            assert proposal["story_id"] is None
            assert proposal["orchestration_run_id"] is None

            # Forbidden column names absent after upgrade
            for table_name in list(STORYBOARD_PHASE1_TABLES) + [
                "voice_profiles",
                "ai_proposal_records",
                "model_variants",
            ]:
                for column in inspector.get_columns(table_name):
                    lowered = column["name"].lower()
                    for fragment in FORBIDDEN_COLUMN_FRAGMENTS:
                        assert fragment not in lowered, f"{table_name}.{column['name']}"
    finally:
        engine.dispose()


def test_downgrade_removes_phase1_only_and_upgrade_is_rerunnable(tmp_path):
    db_path = tmp_path / "phase1_downgrade_upgrade.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    config = _alembic_config(db_url)

    command.upgrade(config, PHASE_A_REVISION)
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            seed = _insert_phase_a_seed(conn)

        command.upgrade(config, PHASE1_REVISION)

        with engine.begin() as conn:
            # Insert a Phase 1 settings row to ensure new tables are live.
            conn.execute(
                text(
                    "INSERT INTO project_storyboard_settings ("
                    "id, project_id, shot_duration_min_sec, shot_duration_max_sec, "
                    "continuity_policy_json, prompting_policy_json, voice_policy_json, "
                    "approval_policy_json, speaking_rate, aspect_ratio, preview_width, "
                    "preview_height, final_width, final_height, fps, captions_enabled, "
                    "audio_enabled, prefer_hosted_providers, prefer_local_providers, "
                    "allow_model_download, allow_rendering, require_voice_consent, "
                    "require_production_plan_approval, settings_version, created_at, updated_at"
                    ") VALUES ("
                    ":id, :project_id, 2, 8, '{}', '{}', '{}', '{}', 1.0, '16:9', "
                    "1280, 720, 1920, 1080, 24, 1, 1, 0, 1, 0, 0, 1, 1, 1, "
                    ":created_at, :updated_at"
                    ")"
                ),
                {
                    "id": str(uuid4()),
                    "project_id": seed["project_id"],
                    "created_at": _now().isoformat(),
                    "updated_at": _now().isoformat(),
                },
            )

        command.downgrade(config, PHASE_A_REVISION)

        with engine.begin() as conn:
            tables = set(inspect(conn).get_table_names())
            # Phase A tables remain
            assert PHASE_A_TABLES.issubset(tables)
            # Phase 1 tables removed
            assert STORYBOARD_PHASE1_TABLES.isdisjoint(tables)

            # Phase A data still present
            count = conn.execute(
                text("SELECT COUNT(*) FROM stories WHERE id = :id"),
                {"id": seed["story_id"]},
            ).scalar_one()
            assert count == 1
            voice_count = conn.execute(
                text("SELECT COUNT(*) FROM voice_profiles WHERE story_id = :id"),
                {"id": seed["story_id"]},
            ).scalar_one()
            assert voice_count == 5

            # Phase 1 columns removed from extended tables
            inspector = inspect(conn)
            voice_cols = {c["name"] for c in inspector.get_columns("voice_profiles")}
            assert "setup_mode" not in voice_cols
            variant_cols = {c["name"] for c in inspector.get_columns("model_variants")}
            assert "native_voice_capability" not in variant_cols
            proposal_cols = {c["name"] for c in inspector.get_columns("ai_proposal_records")}
            assert "orchestration_run_id" not in proposal_cols

        # Re-upgrade is safe and re-applies Phase 1
        command.upgrade(config, "head")
        with engine.begin() as conn:
            tables = set(inspect(conn).get_table_names())
            assert STORYBOARD_PHASE1_TABLES.issubset(tables)
            modes = {
                row["name"].removeprefix("Voice "): row["setup_mode"]
                for row in conn.execute(
                    text(
                        "SELECT name, setup_mode FROM voice_profiles WHERE story_id = :story_id"
                    ),
                    {"story_id": seed["story_id"]},
                ).mappings()
            }
            assert modes["placeholder"] == "placeholder"
            assert modes["provider_ref"] == "existing_provider_voice"
            assert modes["manual_fallback"] == "manual"
    finally:
        engine.dispose()


def test_phase1_revision_is_successor_of_phase_a():
    from backend.alembic.versions import e1a2b3c4d5e6_complete_storyboard_phase_1 as phase1

    assert phase1.revision == PHASE1_REVISION
    assert phase1.down_revision == PHASE_A_REVISION


def test_head_upgrade_creates_phase1_indexes(tmp_path):
    db_path = tmp_path / "phase1_indexes.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    config = _alembic_config(db_url)
    command.upgrade(config, "head")

    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        index_names = set()
        for table_name in STORYBOARD_PHASE1_TABLES | {
            "planning_media_assets",
            "ai_proposal_records",
        }:
            for idx in inspector.get_indexes(table_name):
                if idx.get("name"):
                    index_names.add(idx["name"])

        expected = {
            "uq_orchestration_runs_one_active_per_story",
            "uq_orchestration_step_attempt",
            "uq_provider_invocations_idempotency_key",
            "uq_voice_previews_one_selected_per_profile",
            "uq_gpu_resource_leases_one_active_per_resource",
            "uq_planning_media_assets_project_sha256",
            "ix_orchestration_events_run_created",
            "ix_orchestration_events_step_created",
        }
        # UniqueConstraints may appear as indexes or as unique constraints depending on dialect.
        unique_names = set()
        for table_name in STORYBOARD_PHASE1_TABLES:
            for uc in inspector.get_unique_constraints(table_name):
                if uc.get("name"):
                    unique_names.add(uc["name"])

        present = index_names | unique_names
        missing = expected - present
        assert not missing, f"missing indexes/uniques: {missing}"
    finally:
        engine.dispose()
