"""complete storyboard phase 1 persistence

Revision ID: e1a2b3c4d5e6
Revises: d9e8c7b6a5f4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e1a2b3c4d5e6"
down_revision = "d9e8c7b6a5f4"
branch_labels = None
depends_on = None


def _uuid():
    return postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _created_at_only():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Additive columns on existing tables (preserve all Phase A rows)
    # ------------------------------------------------------------------
    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE model_variants ADD COLUMN native_voice_capability "
                "VARCHAR(16) NOT NULL DEFAULT 'unknown' "
                "CONSTRAINT ck_model_variants_native_voice_capability "
                "CHECK (native_voice_capability IN ('supported', 'unsupported', 'unknown'))"
            )
        )
    else:
        op.add_column(
            "model_variants",
            sa.Column(
                "native_voice_capability",
                sa.String(16),
                nullable=False,
                server_default="unknown",
            ),
        )
    op.add_column("model_variants", sa.Column("native_voice_capability_source", sa.Text()))
    op.add_column(
        "model_variants",
        sa.Column(
            "native_voice_capability_metadata_json",
            _json(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "model_variants",
        sa.Column("native_voice_capability_checked_at", sa.DateTime(timezone=True)),
    )

    op.add_column("provider_profiles", sa.Column("capabilities_checked_at", sa.DateTime(timezone=True)))
    op.add_column("provider_profiles", sa.Column("health_checked_at", sa.DateTime(timezone=True)))
    op.add_column("provider_profiles", sa.Column("capability_source", sa.Text()))

    op.add_column("planning_media_assets", sa.Column("original_filename", sa.Text()))
    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE planning_media_assets ADD COLUMN size_bytes INTEGER "
                "CONSTRAINT ck_planning_media_assets_size_bytes "
                "CHECK (size_bytes IS NULL OR size_bytes >= 0)"
            )
        )
    else:
        op.add_column("planning_media_assets", sa.Column("size_bytes", sa.Integer()))
    op.add_column("planning_media_assets", sa.Column("archived_at", sa.DateTime(timezone=True)))

    for column in (
        sa.Column("narrative_objectives_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("pacing_plan_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("duration_strategy_json", _json(), nullable=False, server_default=sa.text("'{}'")),
    ):
        op.add_column("stories", column)

    op.add_column("chapters", sa.Column("narrative_purpose", sa.Text()))
    op.add_column("chapters", sa.Column("target_duration_sec", sa.Numeric()))
    op.add_column("chapters", sa.Column("dramatic_progression", sa.Text()))
    op.add_column("scenes", sa.Column("target_duration_sec", sa.Numeric()))
    op.add_column("shots", sa.Column("camera_direction", sa.Text()))
    op.add_column("shots", sa.Column("motion_direction", sa.Text()))
    op.add_column("shots", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column("characters", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column("shot_narrations", sa.Column("pacing_notes", sa.Text()))
    op.add_column("shot_narrations", sa.Column("pronunciation_notes", sa.Text()))
    op.add_column("shot_narrations", sa.Column("narration_fit_status", sa.String(32)))
    op.add_column("shot_narrations", sa.Column("narration_fit_wpm", sa.Numeric()))
    op.add_column("shot_prompt_packages", sa.Column("prompt_rationale", sa.Text()))
    op.add_column(
        "shot_prompt_packages",
        sa.Column("provider_metadata_json", _json(), nullable=False, server_default=sa.text("'{}'")),
    )

    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE storyboard_versions ADD COLUMN base_version_id VARCHAR(36) "
                "CONSTRAINT fk_storyboard_versions_base_version "
                "REFERENCES storyboard_versions(id) ON DELETE SET NULL"
            )
        )
    else:
        op.add_column(
            "storyboard_versions",
            sa.Column("base_version_id", _uuid()),
        )
    op.add_column("storyboard_versions", sa.Column("content_hash", sa.String(64)))

    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE voice_profiles ADD COLUMN setup_mode VARCHAR(48) "
                "NOT NULL DEFAULT 'manual' CONSTRAINT ck_voice_profiles_setup_mode CHECK ("
                "setup_mode IN ('placeholder', 'manual', 'existing_provider_voice', "
                "'qwen_voice_design', 'qwen_custom_voice', 'elevenlabs_voice_design', "
                "'parler_local_voice_design', 'user_provided_consented'))"
            )
        )
    else:
        op.add_column(
            "voice_profiles",
            sa.Column("setup_mode", sa.String(48), nullable=False, server_default="manual"),
        )
    op.add_column("voice_profiles", sa.Column("provider_model_id", sa.Text()))
    op.add_column("voice_profiles", sa.Column("recipe_name", sa.Text()))
    op.add_column("voice_profiles", sa.Column("recipe_description", sa.Text()))
    op.add_column("voice_profiles", sa.Column("design_description", sa.Text()))
    op.add_column(
        "voice_profiles",
        sa.Column("design_metadata_json", _json(), nullable=False, server_default=sa.text("'{}'")),
    )
    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE voice_profiles ADD COLUMN selected_preview_asset_id VARCHAR(36) "
                "CONSTRAINT fk_voice_profiles_selected_preview_asset "
                "REFERENCES planning_media_assets(id) ON DELETE SET NULL"
            )
        )
    else:
        op.add_column(
            "voice_profiles",
            sa.Column(
                "selected_preview_asset_id",
                _uuid(),
            ),
        )
    op.add_column("voice_profiles", sa.Column("preview_text", sa.Text()))
    op.add_column("voice_profiles", sa.Column("gender_presentation", sa.Text()))
    op.add_column("voice_profiles", sa.Column("pitch", sa.Text()))
    op.add_column("voice_profiles", sa.Column("style", sa.Text()))
    op.add_column(
        "voice_profiles",
        sa.Column(
            "provider_configuration_status",
            sa.String(32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("voice_profiles", sa.Column("provider_identifier", sa.String(80)))
    op.add_column("voice_profiles", sa.Column("provider_voice_id", sa.Text()))
    if not _is_sqlite():
        op.add_column("voice_profiles", sa.Column("voice_recipe_id", _uuid()))
    op.add_column(
        "voice_profiles",
        sa.Column("voice_recipe_json", _json(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column("voice_profiles", sa.Column("voice_recipe_hash", sa.String(64)))
    op.add_column("voice_profiles", sa.Column("voice_description", sa.Text()))
    op.add_column("voice_profiles", sa.Column("design_model_id", sa.Text()))
    if not _is_sqlite():
        op.add_column("voice_profiles", sa.Column("selected_preview_id", _uuid()))
    op.add_column("voice_profiles", sa.Column("archived_at", sa.DateTime(timezone=True)))

    # Conservative setup_mode backfill — never infer Qwen/Parler from generic data.
    op.execute(
        sa.text(
            """
            UPDATE voice_profiles
            SET setup_mode = CASE
                WHEN source_type = 'placeholder' THEN 'placeholder'
                WHEN source_type = 'user_provided_consented' OR consent_confirmed = true
                    THEN 'user_provided_consented'
                WHEN provider_voice_reference IS NOT NULL AND TRIM(provider_voice_reference) != ''
                    THEN 'existing_provider_voice'
                ELSE 'manual'
            END
            """
        )
    )

    # ------------------------------------------------------------------
    # New Phase 1 tables
    # ------------------------------------------------------------------
    op.create_table(
        "project_storyboard_settings",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("project_id", _uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_duration_min_sec", sa.Numeric(), nullable=False),
        sa.Column("shot_duration_max_sec", sa.Numeric(), nullable=False),
        sa.Column("continuity_policy_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("prompting_policy_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("voice_policy_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("approval_policy_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("speaking_rate", sa.Numeric(), nullable=False, server_default="1"),
        sa.Column("aspect_ratio", sa.String(32), nullable=False, server_default="16:9"),
        sa.Column("preview_width", sa.Integer(), nullable=False),
        sa.Column("preview_height", sa.Integer(), nullable=False),
        sa.Column("final_width", sa.Integer(), nullable=False),
        sa.Column("final_height", sa.Integer(), nullable=False),
        sa.Column("fps", sa.Numeric(), nullable=False),
        sa.Column("captions_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("audio_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("prefer_hosted_providers", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("prefer_local_providers", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_model_download", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_rendering", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("require_voice_consent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_production_plan_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("settings_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.UniqueConstraint("project_id", name="uq_project_storyboard_settings_project_id"),
        sa.CheckConstraint("shot_duration_min_sec > 0", name="ck_pss_shot_duration_min_positive"),
        sa.CheckConstraint("shot_duration_max_sec > 0", name="ck_pss_shot_duration_max_positive"),
        sa.CheckConstraint(
            "shot_duration_min_sec <= shot_duration_max_sec",
            name="ck_pss_shot_duration_min_le_max",
        ),
        sa.CheckConstraint("speaking_rate > 0", name="ck_pss_speaking_rate_positive"),
        sa.CheckConstraint("preview_width > 0", name="ck_pss_preview_width_positive"),
        sa.CheckConstraint("preview_height > 0", name="ck_pss_preview_height_positive"),
        sa.CheckConstraint("final_width > 0", name="ck_pss_final_width_positive"),
        sa.CheckConstraint("final_height > 0", name="ck_pss_final_height_positive"),
        sa.CheckConstraint("fps > 0", name="ck_pss_fps_positive"),
        sa.CheckConstraint("settings_version > 0", name="ck_pss_settings_version_positive"),
    )
    op.create_index("ix_project_storyboard_settings_project_id", "project_storyboard_settings", ["project_id"])

    op.create_table(
        "orchestration_runs",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("story_id", _uuid(), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("retry_of_run_id", _uuid(), sa.ForeignKey("orchestration_runs.id", ondelete="SET NULL")),
        sa.Column(
            "base_storyboard_version_id",
            _uuid(),
            sa.ForeignKey("storyboard_versions.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.Text()),
        sa.Column("routing_snapshot_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("default_provider_snapshot_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("target_duration_sec_snapshot", sa.Numeric()),
        sa.Column("input_hash", sa.String(64)),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("repair_budget", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repair_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_owner_id", sa.String(128)),
        sa.Column("execution_claim_token", sa.String(64)),
        sa.Column("execution_lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("execution_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("execution_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("canceled_at", sa.DateTime(timezone=True)),
        sa.Column("failure_category", sa.String(64)),
        sa.Column("failure_message", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'canceled')",
            name="ck_orchestration_runs_status",
        ),
        sa.CheckConstraint("current_step >= 0", name="ck_orchestration_runs_current_step"),
        sa.CheckConstraint("max_steps > 0", name="ck_orchestration_runs_max_steps"),
        sa.CheckConstraint("repair_budget >= 0", name="ck_orchestration_runs_repair_budget"),
        sa.CheckConstraint("repair_used >= 0", name="ck_orchestration_runs_repair_used"),
        sa.CheckConstraint("execution_attempt >= 0", name="ck_orchestration_runs_execution_attempt"),
        sa.CheckConstraint(
            "repair_used <= repair_budget",
            name="ck_orchestration_runs_repair_used_le_budget",
        ),
        sa.CheckConstraint(
            "(execution_claim_token IS NULL AND execution_owner_id IS NULL "
            "AND execution_lease_expires_at IS NULL AND execution_heartbeat_at IS NULL) OR "
            "(execution_claim_token IS NOT NULL AND execution_owner_id IS NOT NULL "
            "AND execution_lease_expires_at IS NOT NULL AND execution_heartbeat_at IS NOT NULL)",
            name="ck_orchestration_runs_execution_lease_complete",
        ),
        sa.CheckConstraint(
            "target_duration_sec_snapshot IS NULL OR target_duration_sec_snapshot > 0",
            name="ck_orchestration_runs_target_duration",
        ),
    )
    op.create_index("ix_orchestration_runs_story_id", "orchestration_runs", ["story_id"])
    op.create_index("ix_orchestration_runs_story_status", "orchestration_runs", ["story_id", "status"])
    op.create_index(
        "ix_orchestration_runs_execution_lease",
        "orchestration_runs",
        ["status", "execution_lease_expires_at"],
    )
    op.create_index(
        "uq_orchestration_runs_one_active_per_story",
        "orchestration_runs",
        ["story_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
        sqlite_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "orchestration_steps",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("run_id", _uuid(), sa.ForeignKey("orchestration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("provider_identifier", sa.String(80)),
        sa.Column("logical_model", sa.Text()),
        sa.Column("resolved_model", sa.Text()),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_hash", sa.String(64)),
        sa.Column("output_hash", sa.String(64)),
        sa.Column("proposal_id", _uuid(), sa.ForeignKey("ai_proposal_records.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_category", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamps(),
        sa.UniqueConstraint("run_id", "sequence_index", "attempt_number", name="uq_orchestration_step_attempt"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'skipped', 'canceled')",
            name="ck_orchestration_steps_status",
        ),
        sa.CheckConstraint("sequence_index >= 0", name="ck_orchestration_steps_sequence_index"),
        sa.CheckConstraint("attempt_number > 0", name="ck_orchestration_steps_attempt_number"),
    )
    op.create_index("ix_orchestration_steps_run_id", "orchestration_steps", ["run_id"])
    op.create_index("ix_orchestration_steps_run_sequence", "orchestration_steps", ["run_id", "sequence_index"])

    op.create_table(
        "orchestration_events",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("run_id", _uuid(), sa.ForeignKey("orchestration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", _uuid(), sa.ForeignKey("orchestration_steps.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_type", sa.String(64), nullable=False),
        sa.Column("actor_reference", sa.Text()),
        sa.Column("details_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        *_created_at_only(),
    )
    op.create_index("ix_orchestration_events_run_id", "orchestration_events", ["run_id"])
    op.create_index("ix_orchestration_events_step_id", "orchestration_events", ["step_id"])
    op.create_index("ix_orchestration_events_run_created", "orchestration_events", ["run_id", "created_at"])
    op.create_index("ix_orchestration_events_step_created", "orchestration_events", ["step_id", "created_at"])

    op.create_table(
        "provider_invocations",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("run_id", _uuid(), sa.ForeignKey("orchestration_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", _uuid(), sa.ForeignKey("orchestration_steps.id", ondelete="SET NULL")),
        sa.Column("provider_identifier", sa.String(80), nullable=False),
        sa.Column("model", sa.Text()),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("response_hash", sa.String(64)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("usage_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("provider_request_id", sa.Text()),
        sa.Column("finish_category", sa.String(64)),
        sa.Column("error_category", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_created_at_only(),
        sa.UniqueConstraint("idempotency_key", name="uq_provider_invocations_idempotency_key"),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'canceled')",
            name="ck_provider_invocations_status",
        ),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_provider_invocations_latency"),
    )
    op.create_index("ix_provider_invocations_run_id", "provider_invocations", ["run_id"])
    op.create_index("ix_provider_invocations_step_id", "provider_invocations", ["step_id"])
    op.create_index("ix_provider_invocations_run_created", "provider_invocations", ["run_id", "created_at"])

    op.create_table(
        "voice_recipes",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "voice_profile_id",
            _uuid(),
            sa.ForeignKey("voice_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.Text()),
        sa.Column("recipe_name", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("seed", sa.Integer()),
        sa.Column("design_metadata_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamps(),
    )
    op.create_index("ix_voice_recipes_voice_profile_id", "voice_recipes", ["voice_profile_id"])

    op.create_table(
        "voice_previews",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "voice_profile_id",
            _uuid(),
            sa.ForeignKey("voice_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("voice_recipe_id", _uuid(), sa.ForeignKey("voice_recipes.id", ondelete="SET NULL")),
        sa.Column(
            "planning_media_asset_id",
            _uuid(),
            sa.ForeignKey("planning_media_assets.id", ondelete="SET NULL"),
        ),
        sa.Column("provider", sa.String(80)),
        sa.Column("model", sa.Text()),
        sa.Column("preview_text", sa.Text()),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rejected", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.CheckConstraint(
            "NOT (selected AND rejected)",
            name="ck_voice_previews_not_selected_and_rejected",
        ),
    )
    op.create_index("ix_voice_previews_voice_profile_id", "voice_previews", ["voice_profile_id"])
    op.create_index(
        "uq_voice_previews_one_selected_per_profile",
        "voice_previews",
        ["voice_profile_id"],
        unique=True,
        postgresql_where=sa.text("selected IS true"),
        sqlite_where=sa.text("selected = 1"),
    )

    # SQLite can add a nullable FK column without rebuilding when the
    # REFERENCES clause is part of the same ALTER TABLE statement.  These two
    # targets must exist first, hence the deferred additions here.
    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE voice_profiles ADD COLUMN voice_recipe_id VARCHAR(36) "
                "CONSTRAINT fk_voice_profiles_voice_recipe "
                "REFERENCES voice_recipes(id) ON DELETE SET NULL"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE voice_profiles ADD COLUMN selected_preview_id VARCHAR(36) "
                "CONSTRAINT fk_voice_profiles_selected_preview "
                "REFERENCES voice_previews(id) ON DELETE SET NULL"
            )
        )

    op.create_table(
        "gpu_resource_leases",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("resource_key", sa.String(128), nullable=False),
        sa.Column("exclusive_group", sa.String(128)),
        sa.Column("workload_type", sa.String(64), nullable=False),
        sa.Column("workload_id", sa.String(128)),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("worker_id", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", _json(), nullable=False, server_default=sa.text("'{}'")),
        *_created_at_only(),
        sa.CheckConstraint(
            "status IN ('active', 'released', 'expired')",
            name="ck_gpu_resource_leases_status",
        ),
    )
    op.create_index("ix_gpu_resource_leases_resource_key", "gpu_resource_leases", ["resource_key"])
    op.create_index(
        "ix_gpu_resource_leases_status_expires",
        "gpu_resource_leases",
        ["status", "expires_at"],
    )
    op.create_index(
        "uq_gpu_resource_leases_one_active_per_resource",
        "gpu_resource_leases",
        ["resource_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_gpu_resource_leases_one_active_per_group",
        "gpu_resource_leases",
        ["exclusive_group"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND exclusive_group IS NOT NULL"),
        sqlite_where=sa.text("status = 'active' AND exclusive_group IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # ai_proposal_records Phase 1 linkage (SET NULL for audit durability)
    # ------------------------------------------------------------------
    if _is_sqlite():
        for statement in (
            "ALTER TABLE ai_proposal_records ADD COLUMN story_id VARCHAR(36) "
            "CONSTRAINT fk_ai_proposal_records_story "
            "REFERENCES stories(id) ON DELETE SET NULL",
            "ALTER TABLE ai_proposal_records ADD COLUMN orchestration_run_id VARCHAR(36) "
            "CONSTRAINT fk_ai_proposal_records_orchestration_run "
            "REFERENCES orchestration_runs(id) ON DELETE SET NULL",
            "ALTER TABLE ai_proposal_records ADD COLUMN base_storyboard_version_id VARCHAR(36) "
            "CONSTRAINT fk_ai_proposal_records_base_storyboard_version "
            "REFERENCES storyboard_versions(id) ON DELETE SET NULL",
        ):
            op.execute(sa.text(statement))
    else:
        op.add_column(
            "ai_proposal_records",
            sa.Column("story_id", _uuid()),
        )
        op.add_column(
            "ai_proposal_records",
            sa.Column(
                "orchestration_run_id",
                _uuid(),
            ),
        )
        op.add_column(
            "ai_proposal_records",
            sa.Column(
                "base_storyboard_version_id",
                _uuid(),
            ),
        )
    op.add_column("ai_proposal_records", sa.Column("schema_name", sa.String(128)))
    op.add_column("ai_proposal_records", sa.Column("schema_version", sa.Integer()))
    op.add_column("ai_proposal_records", sa.Column("content_hash", sa.String(64)))
    op.add_column("ai_proposal_records", sa.Column("input_context_hash", sa.String(64)))
    op.add_column("ai_proposal_records", sa.Column("payload_hash", sa.String(64)))
    op.add_column("ai_proposal_records", sa.Column("base_content_hash", sa.String(64)))
    op.add_column("ai_proposal_records", sa.Column("validation_status", sa.String(32)))
    op.add_column(
        "ai_proposal_records",
        sa.Column("validation_report_json", _json(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "ai_proposal_records",
        sa.Column("warnings_json", _json(), nullable=False, server_default=sa.text("'[]'")),
    )
    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE ai_proposal_records ADD COLUMN superseded_by_id VARCHAR(36) "
                "CONSTRAINT fk_ai_proposal_records_superseded_by "
                "REFERENCES ai_proposal_records(id) ON DELETE SET NULL"
            )
        )
    else:
        op.add_column(
            "ai_proposal_records",
            sa.Column(
                "superseded_by_id",
                _uuid(),
            ),
        )
    op.add_column("ai_proposal_records", sa.Column("reviewed_by", sa.Text()))
    op.add_column("ai_proposal_records", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("ai_proposal_records", sa.Column("applied_at", sa.DateTime(timezone=True)))
    if _is_sqlite():
        op.execute(
            sa.text(
                "ALTER TABLE ai_proposal_records ADD COLUMN applied_storyboard_version_id VARCHAR(36) "
                "CONSTRAINT fk_ai_proposal_records_applied_storyboard_version "
                "REFERENCES storyboard_versions(id) ON DELETE SET NULL"
            )
        )
    else:
        op.add_column("ai_proposal_records", sa.Column("applied_storyboard_version_id", _uuid()))
    op.add_column("ai_proposal_records", sa.Column("rejected_at", sa.DateTime(timezone=True)))
    op.add_column("ai_proposal_records", sa.Column("rejection_reason", sa.Text()))
    op.create_index("ix_ai_proposal_records_story_id", "ai_proposal_records", ["story_id"])
    op.create_index(
        "ix_ai_proposal_records_orchestration_run_id",
        "ai_proposal_records",
        ["orchestration_run_id"],
    )

    # A digest may validly serve different planning roles. Deduplicate only
    # within a project and asset kind while still allowing null hashes.
    op.create_index(
        "uq_planning_media_assets_project_kind_sha256",
        "planning_media_assets",
        ["project_id", "kind", "sha256"],
        unique=True,
        postgresql_where=sa.text("sha256 IS NOT NULL"),
        sqlite_where=sa.text("sha256 IS NOT NULL"),
    )

    # Phase A intentionally left four circular/bare UUID references without
    # SQLite constraints.  Batch mode recreates only those tables, copies every
    # row, and restores their indexes/constraints before the migration returns.
    if _is_sqlite():
        with op.batch_alter_table("characters", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                "fk_characters_assigned_voice",
                "voice_profiles",
                ["assigned_voice_profile_id"],
                ["id"],
                ondelete="SET NULL",
            )
        with op.batch_alter_table("stories", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                "fk_stories_active_storyboard_version",
                "storyboard_versions",
                ["active_storyboard_version_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_foreign_key(
                "fk_stories_default_provider_profile",
                "provider_profiles",
                ["default_provider_profile_id"],
                ["id"],
                ondelete="SET NULL",
            )
        with op.batch_alter_table("shot_prompt_packages", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                "fk_shot_prompt_packages_provider_profile",
                "provider_profiles",
                ["provider_profile_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # PostgreSQL can add the same constraints without table recreation.
    if _is_postgres():
        op.create_foreign_key(
            "fk_storyboard_versions_base_version",
            "storyboard_versions",
            "storyboard_versions",
            ["base_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_voice_profiles_selected_preview_asset",
            "voice_profiles",
            "planning_media_assets",
            ["selected_preview_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_voice_profiles_voice_recipe",
            "voice_profiles",
            "voice_recipes",
            ["voice_recipe_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_voice_profiles_selected_preview",
            "voice_profiles",
            "voice_previews",
            ["selected_preview_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_ai_proposal_records_story",
            "ai_proposal_records",
            "stories",
            ["story_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_ai_proposal_records_orchestration_run",
            "ai_proposal_records",
            "orchestration_runs",
            ["orchestration_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_ai_proposal_records_base_storyboard_version",
            "ai_proposal_records",
            "storyboard_versions",
            ["base_storyboard_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_ai_proposal_records_superseded_by",
            "ai_proposal_records",
            "ai_proposal_records",
            ["superseded_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_ai_proposal_records_applied_storyboard_version",
            "ai_proposal_records",
            "storyboard_versions",
            ["applied_storyboard_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_check_constraint(
            "ck_model_variants_native_voice_capability",
            "model_variants",
            "native_voice_capability IN ('supported', 'unsupported', 'unknown')",
        )
        op.create_check_constraint(
            "ck_voice_profiles_setup_mode",
            "voice_profiles",
            "setup_mode IN ("
            "'placeholder', 'manual', 'existing_provider_voice', "
            "'qwen_voice_design', 'qwen_custom_voice', "
            "'elevenlabs_voice_design', 'parler_local_voice_design', "
            "'user_provided_consented')",
        )
        op.create_check_constraint(
            "ck_planning_media_assets_size_bytes",
            "planning_media_assets",
            "size_bytes IS NULL OR size_bytes >= 0",
        )
        # Bare UUID FK completion for Phase A columns (avoid SQLite rebuilds)
        op.create_foreign_key(
            "fk_stories_active_storyboard_version",
            "stories",
            "storyboard_versions",
            ["active_storyboard_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_stories_default_provider_profile",
            "stories",
            "provider_profiles",
            ["default_provider_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_shot_prompt_packages_provider_profile",
            "shot_prompt_packages",
            "provider_profiles",
            ["provider_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Remove Phase 1 additions while preserving every Phase A table and row."""
    if _is_sqlite():
        with op.batch_alter_table("shot_prompt_packages", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "fk_shot_prompt_packages_provider_profile",
                type_="foreignkey",
            )
        with op.batch_alter_table("stories", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "fk_stories_default_provider_profile",
                type_="foreignkey",
            )
            batch_op.drop_constraint(
                "fk_stories_active_storyboard_version",
                type_="foreignkey",
            )
        with op.batch_alter_table("characters", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "fk_characters_assigned_voice",
                type_="foreignkey",
            )

    if _is_postgres():
        op.drop_constraint(
            "fk_ai_proposal_records_applied_storyboard_version",
            "ai_proposal_records",
            type_="foreignkey",
        )
        op.drop_constraint("fk_ai_proposal_records_superseded_by", "ai_proposal_records", type_="foreignkey")
        op.drop_constraint(
            "fk_ai_proposal_records_base_storyboard_version", "ai_proposal_records", type_="foreignkey"
        )
        op.drop_constraint(
            "fk_ai_proposal_records_orchestration_run", "ai_proposal_records", type_="foreignkey"
        )
        op.drop_constraint("fk_ai_proposal_records_story", "ai_proposal_records", type_="foreignkey")
        op.drop_constraint(
            "fk_voice_profiles_selected_preview_asset", "voice_profiles", type_="foreignkey"
        )
        op.drop_constraint("fk_voice_profiles_selected_preview", "voice_profiles", type_="foreignkey")
        op.drop_constraint("fk_voice_profiles_voice_recipe", "voice_profiles", type_="foreignkey")
        op.drop_constraint("fk_storyboard_versions_base_version", "storyboard_versions", type_="foreignkey")
        op.drop_constraint("fk_shot_prompt_packages_provider_profile", "shot_prompt_packages", type_="foreignkey")
        op.drop_constraint("fk_stories_default_provider_profile", "stories", type_="foreignkey")
        op.drop_constraint("fk_stories_active_storyboard_version", "stories", type_="foreignkey")
        op.drop_constraint("ck_planning_media_assets_size_bytes", "planning_media_assets", type_="check")
        op.drop_constraint("ck_voice_profiles_setup_mode", "voice_profiles", type_="check")
        op.drop_constraint("ck_model_variants_native_voice_capability", "model_variants", type_="check")

    op.drop_index(
        "uq_planning_media_assets_project_kind_sha256",
        table_name="planning_media_assets",
    )

    op.drop_index("ix_ai_proposal_records_orchestration_run_id", table_name="ai_proposal_records")
    op.drop_index("ix_ai_proposal_records_story_id", table_name="ai_proposal_records")
    for col in [
        "rejection_reason",
        "rejected_at",
        "applied_storyboard_version_id",
        "applied_at",
        "reviewed_at",
        "reviewed_by",
        "superseded_by_id",
        "warnings_json",
        "validation_report_json",
        "validation_status",
        "content_hash",
        "base_content_hash",
        "payload_hash",
        "input_context_hash",
        "schema_version",
        "schema_name",
        "base_storyboard_version_id",
        "orchestration_run_id",
        "story_id",
    ]:
        op.drop_column("ai_proposal_records", col)

    op.drop_index("uq_gpu_resource_leases_one_active_per_group", table_name="gpu_resource_leases")
    op.drop_index("uq_gpu_resource_leases_one_active_per_resource", table_name="gpu_resource_leases")
    op.drop_index("ix_gpu_resource_leases_status_expires", table_name="gpu_resource_leases")
    op.drop_index("ix_gpu_resource_leases_resource_key", table_name="gpu_resource_leases")
    op.drop_table("gpu_resource_leases")

    # Remove child pointers before their referenced Phase 1 tables.
    op.drop_column("voice_profiles", "selected_preview_id")
    op.drop_column("voice_profiles", "voice_recipe_id")

    op.drop_index("uq_voice_previews_one_selected_per_profile", table_name="voice_previews")
    op.drop_index("ix_voice_previews_voice_profile_id", table_name="voice_previews")
    op.drop_table("voice_previews")

    op.drop_index("ix_voice_recipes_voice_profile_id", table_name="voice_recipes")
    op.drop_table("voice_recipes")

    op.drop_index("ix_provider_invocations_run_created", table_name="provider_invocations")
    op.drop_index("ix_provider_invocations_step_id", table_name="provider_invocations")
    op.drop_index("ix_provider_invocations_run_id", table_name="provider_invocations")
    op.drop_table("provider_invocations")

    op.drop_index("ix_orchestration_events_step_created", table_name="orchestration_events")
    op.drop_index("ix_orchestration_events_run_created", table_name="orchestration_events")
    op.drop_index("ix_orchestration_events_step_id", table_name="orchestration_events")
    op.drop_index("ix_orchestration_events_run_id", table_name="orchestration_events")
    op.drop_table("orchestration_events")

    op.drop_index("ix_orchestration_steps_run_sequence", table_name="orchestration_steps")
    op.drop_index("ix_orchestration_steps_run_id", table_name="orchestration_steps")
    op.drop_table("orchestration_steps")

    op.drop_index("uq_orchestration_runs_one_active_per_story", table_name="orchestration_runs")
    op.drop_index("ix_orchestration_runs_execution_lease", table_name="orchestration_runs")
    op.drop_index("ix_orchestration_runs_story_status", table_name="orchestration_runs")
    op.drop_index("ix_orchestration_runs_story_id", table_name="orchestration_runs")
    op.drop_table("orchestration_runs")

    op.drop_index("ix_project_storyboard_settings_project_id", table_name="project_storyboard_settings")
    op.drop_table("project_storyboard_settings")

    for col in [
        "archived_at",
        "design_model_id",
        "voice_description",
        "voice_recipe_hash",
        "voice_recipe_json",
        "provider_voice_id",
        "provider_identifier",
        "provider_configuration_status",
        "style",
        "pitch",
        "gender_presentation",
        "preview_text",
        "selected_preview_asset_id",
        "design_metadata_json",
        "design_description",
        "recipe_description",
        "recipe_name",
        "provider_model_id",
        "setup_mode",
    ]:
        op.drop_column("voice_profiles", col)

    op.drop_column("storyboard_versions", "content_hash")
    op.drop_column("storyboard_versions", "base_version_id")

    op.drop_column("shot_prompt_packages", "provider_metadata_json")
    op.drop_column("shot_prompt_packages", "prompt_rationale")
    op.drop_column("shot_narrations", "narration_fit_wpm")
    op.drop_column("shot_narrations", "narration_fit_status")
    op.drop_column("shot_narrations", "pronunciation_notes")
    op.drop_column("shot_narrations", "pacing_notes")
    op.drop_column("characters", "archived_at")
    op.drop_column("shots", "archived_at")
    op.drop_column("shots", "motion_direction")
    op.drop_column("shots", "camera_direction")
    op.drop_column("scenes", "target_duration_sec")
    op.drop_column("chapters", "dramatic_progression")
    op.drop_column("chapters", "target_duration_sec")
    op.drop_column("chapters", "narrative_purpose")
    op.drop_column("stories", "duration_strategy_json")
    op.drop_column("stories", "pacing_plan_json")
    op.drop_column("stories", "narrative_objectives_json")

    op.drop_column("planning_media_assets", "archived_at")
    op.drop_column("planning_media_assets", "size_bytes")
    op.drop_column("planning_media_assets", "original_filename")

    op.drop_column("provider_profiles", "capability_source")
    op.drop_column("provider_profiles", "health_checked_at")
    op.drop_column("provider_profiles", "capabilities_checked_at")

    op.drop_column("model_variants", "native_voice_capability_checked_at")
    op.drop_column("model_variants", "native_voice_capability_metadata_json")
    op.drop_column("model_variants", "native_voice_capability_source")
    op.drop_column("model_variants", "native_voice_capability")
