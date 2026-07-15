# Checkpoint — M5 Hash and Execute-path Hardening

Generated: 2026-07-15 08:27 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `85fe878 checkpoint: gate concat manifests on hashes and probes`
Review source: `.pi-subagents/artifacts/outputs/7017b535-fb60-4e17-a198-50df09a75a6b/.pi-subagents/artifacts/review/latest-m5-ffmpeg-review.md`

## Scope

Addressed M5 reviewer residual notes with additional offline hardening.

Changes:

- Added shared `validate_sha256_hex(...)` for 64-character hex SHA256 values.
- `PostProductionService.build_assembly_plan(...)` now validates supplied clip hashes before accepting them.
- `FFmpegService.build_stream_copy_concat_manifest(...)` now validates supplied input hashes, not just presence.
- `PostProductionService.execute_assembly(...)` now reuses the resolved safe output path for existence checks, output hash, and probe path derivation.
- Added offline tests for invalid supplied hashes and resolved output-path bookkeeping using monkeypatched subprocess/probe calls only.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_ffmpeg_service.py \
  backend/tests/test_post_production.py
# 13 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 506 passed, 9 skipped, warnings only, ~74.33s
```

## Safety notes

- No real FFmpeg command was executed; execute-path test used monkeypatches.
- No FFmpeg execution API was exposed.
- No live ComfyUI/GPU/render/benchmark action was run.
