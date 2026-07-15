# Checkpoint — M5 Post-production Path and Hash Safety

Generated: 2026-07-15 08:14 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `832caf6 checkpoint: record M4 read-only gate status`

## Scope

Started M5 deterministic post-production hardening without executing FFmpeg.

Changes:

- `PostProductionService.build_assembly_plan(...)` now resolves clip inputs inside the configured FFmpeg storage root.
- Assembly planning now requires either a supplied input hash or an existing file that can be hashed.
- `build_command(...)` resolves input/output media paths inside the configured root and rejects traversal/absolute escapes unless the central settings explicitly allow absolute paths.
- `build_command(...)` now requires one input hash per clip before constructing an argument array.
- Added offline tests for safe structured command construction, missing hashes/files, unsafe input/output paths, and missing plan hashes.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_post_production.py \
  backend/tests/test_ffmpeg_service.py
# 7 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 500 passed, 9 skipped, warnings only, ~80.35s
```

## Safety notes

- No FFmpeg command was executed.
- No live ComfyUI/GPU/render/benchmark action was run.
- This checkpoint only hardens deterministic planning/command-array construction.
