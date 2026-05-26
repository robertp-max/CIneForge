from backend.app.db.base import Base


def test_required_schema_tables_exist():
    required = {
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
    assert required.issubset(set(Base.metadata.tables))

