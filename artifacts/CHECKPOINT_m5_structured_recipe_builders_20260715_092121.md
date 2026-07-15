# Checkpoint — M5 Structured Recipe Command Builders

Generated: 2026-07-15 09:21 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `4e30532 checkpoint: refresh M5 implementation status`

## Scope

Added non-executing structured command-array builders for additional allowlisted FFmpeg recipes.

Changes:

- Added allowlisted `audio_mux_v1` recipe metadata.
- Added `RecipeCommandBuildResult`.
- Added `FFmpegService.build_decode_validate_command(...)`.
- Added `FFmpegService.build_audio_mux_command(...)`.
- Builders validate SHA256 inputs, resolve all media paths inside the configured storage root, and return structured argument arrays only.
- Added tests proving structured command output, lowercased hash normalization, SHA256 rejection, and unsafe-path rejection.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_ffmpeg_service.py \
  backend/tests/test_post_production.py
# 16 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 509 passed, 9 skipped, warnings only, ~75.59s
```

## Safety notes

- Builders do not execute FFmpeg.
- No FFmpeg execution API was exposed.
- No live ComfyUI/GPU/render/benchmark action was run.
