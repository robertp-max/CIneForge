# M5 Offline Recipe Command Manifest Checkpoint

Backend-only checkpoint for persisting generic FFmpeg recipe command plans built from `RecipeCommandBuildResult` values.

## Scope

- Persists structured command arrays and approved `command_template_id` values only.
- Records `input_paths`, validated `input_hashes`, optional `output_path`, `created_at`, `state=planned_offline`, and `execution_submitted=false`.
- Revalidates persisted recipe `input_paths` and optional `output_path` against the configured FFmpeg storage root before writing manifests.
- Includes optional future result fields (`output_sha256`, `final_probe_json`, `error`) in the manifest schema.
- Adds no execution endpoint and does not run FFmpeg, ComfyUI, GPU rendering, rendering, or benchmarking.

## Subagent Evidence

- Worker run `bde5661b` implemented the initial backend-only generic offline recipe command manifest schema/store support, focused persistence and validation coverage, and this checkpoint artifact. Recorded focused validation: `.venv/Scripts/python -m pytest backend/tests/test_post_production.py backend/tests/test_ffmpeg_service.py` returned `22 passed` at that point.
- Worker/reviewer follow-up run `ba2260b7` hardened `PostProductionPlanStore.create_from_recipe_command` path validation for recipe input/output paths, added unsafe path rejection coverage, and refreshed this checkpoint. Recorded focused validation: `.venv/Scripts/python -m pytest backend/tests/test_post_production.py backend/tests/test_ffmpeg_service.py` returned `23 tests` passed.
- Reviewer evidence for the current uncommitted checkpoint: the backend-only manifest path remained non-executing, did not add endpoints/routes, and retained the planned-offline manifest state with structured argv persistence.

## Validation Evidence

- Focused backend validation for the current checkpoint: `backend/tests/test_post_production.py backend/tests/test_ffmpeg_service.py` = `23 passed`.
- Full backend pytest validation for the current checkpoint: `519 passed, 9 skipped`.
- No FFmpeg execution was performed.
- No ComfyUI execution was performed.
- No GPU job, render, or benchmark execution was performed.
- No endpoints or routes were added for this checkpoint.

## Safety Notes

- The persisted command remains a structured argument array from approved recipe command builders, not a user-authored raw command string.
- Manifest creation records offline planning metadata only; it does not submit execution work and leaves `execution_submitted=false`.
- Path validation is performed before manifest persistence so recipe input and output paths remain constrained to the configured FFmpeg storage root.
- Result fields remain optional placeholders for future ingest and are not evidence of execution in this checkpoint.

## Residual Risks

- Validation evidence is recorded from the current uncommitted checkpoint runs; this artifact update did not re-run FFmpeg, ComfyUI, GPU, render, benchmark, or backend test execution.
- Existing uncommitted source/test changes remain outside this artifact-only update.
