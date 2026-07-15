# Checkpoint — M5 Offline Post-production Plan Manifest

Generated: 2026-07-15 08:30 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `bb8f961 checkpoint: harden M5 hashes and output path`

## Scope

Added file-backed offline post-production plan manifests to persist deterministic FFmpeg assembly intent without executing FFmpeg.

Changes:

- Added `backend/app/schemas/post_production.py` with `PostProductionPlanManifest`.
- Added `backend/app/services/post_production_manifest.py` with `PostProductionPlanStore`.
- `PostProductionPlanStore.create_from_plan(...)` validates/builds the structured command array through `PostProductionService.build_command(...)`, then writes a manifest and JSONL audit event.
- Manifest records command template ID, command array, input paths, input hashes, probe count, output path, timeline duration fields, and embedded `FFmpegAssemblyPlan`.
- Manifest defaults keep execution state explicitly offline:
  - `state=planned_offline`
  - `execution_submitted=false`
  - `ffmpeg_job_id=null`
  - `output_sha256=null`
  - `final_probe_json=null`
- Added tests proving manifest creation does not execute FFmpeg and round-trips through get/list.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_post_production.py \
  backend/tests/test_ffmpeg_service.py
# 14 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 507 passed, 9 skipped, warnings only, ~75.48s
```

## Safety notes

- No FFmpeg command was executed.
- No FFmpeg execution API was exposed.
- No live ComfyUI/GPU/render/benchmark action was run.
