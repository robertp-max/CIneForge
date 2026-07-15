# Checkpoint — M5 Additional Structured FFmpeg Recipe Builders

Generated: 2026-07-15 10:14 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `661591e checkpoint: persist post-production outcomes`

## Scope

Added more non-executing structured command-array builders for allowlisted CF-POST-01 FFmpeg recipes.

Changes:

- Added `FFmpegService.build_normalize_delivery_h264_command(...)`.
- Added `FFmpegService.build_normalize_mezzanine_prores_command(...)`.
- Added `FFmpegService.build_captions_srt_mux_command(...)`.
- Added `FFmpegService.build_audio_loudness_normalize_command(...)`.
- Updated decode-validation recipe metadata to reflect hash-gated builder behavior.
- Builders validate SHA256 strings, resolve inputs/outputs inside the configured storage root, and return `RecipeCommandBuildResult` structured argument arrays only.
- Added focused tests for happy paths plus invalid hashes, non-SRT caption rejection, and unsafe paths.

## Independent review

Fresh read-only reviewer run: `6c2f8c1d`.

Result summary:

- Blockers: none.
- Major findings: none.
- Recommendation: pass for committing.
- Minor note about additional invalid hash/path test coverage was addressed before this checkpoint.
- Reviewer noted that builders validate supplied SHA256 strings but do not compute/compare file contents; that remains intentional for command-builder scope and must not be treated as proof of content integrity by downstream code.

Artifact path:

- `.pi-subagents/artifacts/6c2f8c1d_reviewer_0_output.md`

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_ffmpeg_service.py \
  backend/tests/test_post_production.py
# 20 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 516 passed, 9 skipped, warnings only, ~74.42s
```

## Safety notes

- No FFmpeg command was executed.
- No FFmpeg execution/submission endpoint was added.
- No live ComfyUI/GPU/render/benchmark action was run.
