"""Metadata and invariant tests for Storyboard Phase 1 persistence."""

import warnings

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, inspect as sa_inspect
from sqlalchemy.exc import SAWarning

from backend.app.db.base import (
    NATIVE_VOICE_CAPABILITIES,
    VOICE_SETUP_MODES,
    AIProposalRecord,
    Base,
    GpuResourceLease,
    ModelVariant,
    OrchestrationEvent,
    OrchestrationRun,
    OrchestrationStep,
    PlanningMediaAsset,
    ProjectStoryboardSettings,
    ProviderInvocation,
    ProviderProfile,
    ShotPromptPackage,
    Story,
    StoryboardVersion,
    VoicePreview,
    VoiceProfile,
    VoiceRecipe,
)


PHASE1_TABLES = {
    "project_storyboard_settings",
    "orchestration_runs",
    "orchestration_steps",
    "orchestration_events",
    "provider_invocations",
    "voice_recipes",
    "voice_previews",
    "gpu_resource_leases",
}

FORBIDDEN_COLUMN_FRAGMENTS = (
    "raw_prompt",
    "raw_response",
    "raw_payload",
    "request_body",
    "response_body",
    "prompt_payload",
    "completion_text",
    "api_key",
    "apikey",
    "secret",
    "credential",
    "password",
    "token_value",
    "hidden_reasoning",
    "reasoning_content",
    "chain_of_thought",
    "audio_bytes",
    "audio_base64",
    "base64_audio",
    "binary_audio",
    "wav_bytes",
    "mp3_bytes",
    "voice_clone",
    "clone_sample",
    "comfy_queue",
    "ffmpeg_queue",
    "media_queue",
    "model_download_queue",
    "download_queue",
    "render_queue",
)


def _table(name: str):
    return Base.metadata.tables[name]


def _column_names(table_name: str) -> set[str]:
    return set(_table(table_name).columns.keys())


def _check_names(table_name: str) -> set[str]:
    return {
        c.name
        for c in _table(table_name).constraints
        if isinstance(c, CheckConstraint) and c.name
    }


def _unique_names(table_name: str) -> set[str]:
    return {
        c.name
        for c in _table(table_name).constraints
        if isinstance(c, UniqueConstraint) and c.name
    }


def _index_names(table_name: str) -> set[str]:
    return {idx.name for idx in _table(table_name).indexes if idx.name}


def _fk_target_columns(table_name: str, column_name: str) -> set[str]:
    column = _table(table_name).c[column_name]
    targets = set()
    for fk in column.foreign_keys:
        targets.add(f"{fk.column.table.name}.{fk.column.name}")
    return targets


def test_phase1_tables_registered_in_metadata():
    assert PHASE1_TABLES.issubset(set(Base.metadata.tables))


def test_metadata_dependency_graph_has_no_unresolved_cycles():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", SAWarning)
        sorted_tables = list(Base.metadata.sorted_tables)

    assert len(sorted_tables) == len(Base.metadata.tables)
    assert not [
        warning
        for warning in caught
        if issubclass(warning.category, SAWarning)
        and "unresolvable cycles" in str(warning.message)
    ]


def test_exact_voice_setup_modes():
    assert VOICE_SETUP_MODES == (
        "placeholder",
        "manual",
        "existing_provider_voice",
        "qwen_voice_design",
        "qwen_custom_voice",
        "elevenlabs_voice_design",
        "parler_local_voice_design",
        "user_provided_consented",
    )
    assert "ck_voice_profiles_setup_mode" in _check_names("voice_profiles")
    setup_col = VoiceProfile.__table__.c.setup_mode
    assert setup_col.nullable is False


def test_native_voice_capability_tri_state():
    assert NATIVE_VOICE_CAPABILITIES == ("supported", "unsupported", "unknown")
    assert "ck_model_variants_native_voice_capability" in _check_names("model_variants")
    col = ModelVariant.__table__.c.native_voice_capability
    assert col.nullable is False
    # Default keeps unknown distinguishable from unsupported.
    assert col.default is not None
    assert col.default.arg == "unknown"


def test_project_storyboard_settings_shape_and_checks():
    columns = _column_names("project_storyboard_settings")
    required = {
        "project_id",
        "shot_duration_min_sec",
        "shot_duration_max_sec",
        "continuity_policy_json",
        "prompting_policy_json",
        "voice_policy_json",
        "approval_policy_json",
        "speaking_rate",
        "aspect_ratio",
        "preview_width",
        "preview_height",
        "final_width",
        "final_height",
        "fps",
        "captions_enabled",
        "audio_enabled",
        "prefer_hosted_providers",
        "prefer_local_providers",
        "allow_model_download",
        "allow_rendering",
        "require_voice_consent",
        "require_production_plan_approval",
        "settings_version",
        "created_at",
        "updated_at",
    }
    assert required.issubset(columns)
    # Story target duration remains authoritative — not duplicated here.
    assert "target_duration_sec" not in columns
    assert "uq_project_storyboard_settings_project_id" in _unique_names("project_storyboard_settings") or any(
        list(c.columns) == [ProjectStoryboardSettings.__table__.c.project_id]
        for c in ProjectStoryboardSettings.__table__.constraints
        if isinstance(c, UniqueConstraint)
    )
    checks = _check_names("project_storyboard_settings")
    assert "ck_pss_shot_duration_min_le_max" in checks
    assert "ck_pss_speaking_rate_positive" in checks
    assert "ck_pss_fps_positive" in checks
    assert _fk_target_columns("project_storyboard_settings", "project_id") == {"projects.id"}


def test_orchestration_run_step_event_invariants():
    run_cols = _column_names("orchestration_runs")
    assert {
        "story_id",
        "base_storyboard_version_id",
        "status",
        "requested_by",
        "routing_snapshot_json",
        "default_provider_snapshot_json",
        "target_duration_sec_snapshot",
        "input_hash",
        "current_step",
        "max_steps",
        "repair_budget",
        "repair_used",
        "failure_category",
        "failure_message",
    }.issubset(run_cols)
    assert "uq_orchestration_step_attempt" in _unique_names("orchestration_steps")
    assert "ck_orchestration_runs_repair_used_le_budget" in _check_names("orchestration_runs")
    assert "uq_orchestration_runs_one_active_per_story" in _index_names("orchestration_runs")
    assert "ix_orchestration_events_run_created" in _index_names("orchestration_events")
    assert "ix_orchestration_events_step_created" in _index_names("orchestration_events")
    assert _fk_target_columns("orchestration_steps", "run_id") == {"orchestration_runs.id"}
    assert _fk_target_columns("orchestration_events", "run_id") == {"orchestration_runs.id"}


def test_provider_invocations_are_hash_only_audit_trail():
    cols = _column_names("provider_invocations")
    assert {
        "run_id",
        "step_id",
        "provider_identifier",
        "model",
        "idempotency_key",
        "request_hash",
        "response_hash",
        "latency_ms",
        "usage_json",
        "status",
        "provider_request_id",
        "finish_category",
        "error_category",
        "error_message",
    }.issubset(cols)
    assert "uq_provider_invocations_idempotency_key" in _unique_names("provider_invocations")
    lowered = {c.lower() for c in cols}
    for fragment in (
        "raw_prompt",
        "raw_response",
        "request_body",
        "response_body",
        "api_key",
        "credential",
        "hidden_reasoning",
    ):
        assert not any(fragment in name for name in lowered)


def test_voice_recipe_and_preview_metadata_only():
    recipe_cols = _column_names("voice_recipes")
    preview_cols = _column_names("voice_previews")
    assert {
        "voice_profile_id",
        "provider",
        "model",
        "recipe_name",
        "description",
        "seed",
        "design_metadata_json",
    }.issubset(recipe_cols)
    assert {
        "voice_profile_id",
        "voice_recipe_id",
        "planning_media_asset_id",
        "selected",
        "rejected",
        "preview_text",
    }.issubset(preview_cols)
    assert "ck_voice_previews_not_selected_and_rejected" in _check_names("voice_previews")
    assert "uq_voice_previews_one_selected_per_profile" in _index_names("voice_previews")
    for cols in (recipe_cols, preview_cols):
        lowered = {c.lower() for c in cols}
        for fragment in ("audio_bytes", "audio_base64", "base64_audio", "binary_audio", "wav_bytes"):
            assert not any(fragment in name for name in lowered)


def test_gpu_resource_lease_is_lease_boundary_not_queue():
    cols = _column_names("gpu_resource_leases")
    assert {
        "resource_key",
        "exclusive_group",
        "workload_type",
        "workload_id",
        "owner",
        "worker_id",
        "status",
        "acquired_at",
        "heartbeat_at",
        "expires_at",
        "released_at",
        "metadata_json",
    }.issubset(cols)
    assert "uq_gpu_resource_leases_one_active_per_resource" in _index_names("gpu_resource_leases")
    assert "uq_gpu_resource_leases_one_active_per_group" in _index_names("gpu_resource_leases")
    assert "ck_gpu_resource_leases_status" in _check_names("gpu_resource_leases")
    lowered = {c.lower() for c in cols}
    for fragment in ("comfy", "ffmpeg", "render_queue", "media_queue", "model_download"):
        assert not any(fragment in name for name in lowered)


def test_extended_existing_tables_phase1_columns():
    voice_cols = _column_names("voice_profiles")
    assert {
        "setup_mode",
        "provider_model_id",
        "recipe_name",
        "recipe_description",
        "design_description",
        "design_metadata_json",
        "selected_preview_asset_id",
        "preview_text",
        "gender_presentation",
        "pitch",
        "style",
        "provider_configuration_status",
        # legacy retained
        "source_type",
        "provider",
        "provider_voice_reference",
        "consent_required",
        "consent_confirmed",
    }.issubset(voice_cols)

    proposal_cols = _column_names("ai_proposal_records")
    assert {
        "story_id",
        "orchestration_run_id",
        "base_storyboard_version_id",
        "schema_name",
        "content_hash",
        "validation_status",
        "validation_report_json",
        "warnings_json",
        "superseded_by_id",
        "reviewed_by",
        "reviewed_at",
        "applied_at",
        "rejected_at",
        "rejection_reason",
    }.issubset(proposal_cols)

    assert {"base_version_id", "content_hash"}.issubset(_column_names("storyboard_versions"))
    assert {
        "native_voice_capability",
        "native_voice_capability_source",
        "native_voice_capability_metadata_json",
        "native_voice_capability_checked_at",
    }.issubset(_column_names("model_variants"))
    assert {
        "capabilities_checked_at",
        "health_checked_at",
        "capability_source",
    }.issubset(_column_names("provider_profiles"))
    assert {
        "original_filename",
        "size_bytes",
        "archived_at",
    }.issubset(_column_names("planning_media_assets"))
    assert "uq_planning_media_assets_project_kind_sha256" in _index_names(
        "planning_media_assets"
    )
    hash_index = next(
        index
        for index in _table("planning_media_assets").indexes
        if index.name == "uq_planning_media_assets_project_kind_sha256"
    )
    assert [column.name for column in hash_index.columns] == [
        "project_id",
        "kind",
        "sha256",
    ]


def test_story_and_shot_prompt_fk_targets_in_metadata():
    assert _fk_target_columns("stories", "active_storyboard_version_id") == {
        "storyboard_versions.id"
    }
    assert _fk_target_columns("stories", "default_provider_profile_id") == {
        "provider_profiles.id"
    }
    assert _fk_target_columns("shot_prompt_packages", "provider_profile_id") == {
        "provider_profiles.id"
    }


def test_ai_proposal_set_null_relationships():
    for column_name, target in (
        ("story_id", "stories.id"),
        ("orchestration_run_id", "orchestration_runs.id"),
        ("base_storyboard_version_id", "storyboard_versions.id"),
        ("superseded_by_id", "ai_proposal_records.id"),
        ("applied_storyboard_version_id", "storyboard_versions.id"),
    ):
        fks = list(AIProposalRecord.__table__.c[column_name].foreign_keys)
        assert fks, column_name
        assert f"{fks[0].column.table.name}.{fks[0].column.name}" == target
        assert fks[0].ondelete == "SET NULL"


def test_no_forbidden_payload_or_queue_columns_on_phase1_tables():
    tables = list(PHASE1_TABLES) + [
        "voice_profiles",
        "ai_proposal_records",
        "model_variants",
        "provider_profiles",
        "planning_media_assets",
        "storyboard_versions",
    ]
    for table_name in tables:
        for column_name in _column_names(table_name):
            lowered = column_name.lower()
            for fragment in FORBIDDEN_COLUMN_FRAGMENTS:
                assert fragment not in lowered, f"{table_name}.{column_name}"


def test_model_classes_exportable_attributes():
    assert ProjectStoryboardSettings.__tablename__ == "project_storyboard_settings"
    assert OrchestrationRun.__tablename__ == "orchestration_runs"
    assert OrchestrationStep.__tablename__ == "orchestration_steps"
    assert OrchestrationEvent.__tablename__ == "orchestration_events"
    assert ProviderInvocation.__tablename__ == "provider_invocations"
    assert VoiceRecipe.__tablename__ == "voice_recipes"
    assert VoicePreview.__tablename__ == "voice_previews"
    assert GpuResourceLease.__tablename__ == "gpu_resource_leases"
    assert Story.__tablename__ == "stories"
    assert StoryboardVersion.__tablename__ == "storyboard_versions"
    assert ProviderProfile.__tablename__ == "provider_profiles"
    assert PlanningMediaAsset.__tablename__ == "planning_media_assets"
    assert ShotPromptPackage.__tablename__ == "shot_prompt_packages"


def test_partial_unique_indexes_marked_unique():
    for table_name, index_name in (
        ("orchestration_runs", "uq_orchestration_runs_one_active_per_story"),
        ("voice_previews", "uq_voice_previews_one_selected_per_profile"),
        ("gpu_resource_leases", "uq_gpu_resource_leases_one_active_per_resource"),
        ("gpu_resource_leases", "uq_gpu_resource_leases_one_active_per_group"),
        ("planning_media_assets", "uq_planning_media_assets_project_kind_sha256"),
    ):
        matches = [idx for idx in _table(table_name).indexes if idx.name == index_name]
        assert len(matches) == 1, index_name
        assert matches[0].unique is True
