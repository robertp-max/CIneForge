# M5 Backend Checkpoint: FFmpeg Transition Recipe Command Builder

## Scope
- Added backend-only FFmpeg recipe command-builder `transition_crossfade_h264_v1` for the canonical M5 transitions category.
- The builder returns `RecipeCommandBuildResult` with a structured argv array only.
- No FFmpeg execution, API routes, frontend changes, public generation, raw command submission, or execution endpoints were added.

## Validation
- Focused tests added/updated in `backend/tests/test_ffmpeg_service.py` for:
  - crossfade happy path
  - invalid SHA256 input hashes
  - unsafe input/output paths
  - invalid transition duration/fps/geometry parameters
  - no subprocess execution by the builder
- Command run: `.venv/Scripts/python -m pytest backend/tests/test_ffmpeg_service.py backend/tests/test_post_production.py`
- Result: 37 passed in 1.18s.

## Safety Notes
- Template ID is allowlisted in `APPROVED_COMMAND_TEMPLATES` and catalog metadata category is `transitions`.
- Input hashes are normalized and validated as SHA256 hex before returning the recipe result.
- Input and output paths are resolved under the configured FFmpeg storage root via existing path-safety utilities.
- Duration, offset, fps, width, and height parameters must be positive and typed/finite through existing validation helpers.
- The command-builder constructs a list of arguments and does not call `subprocess.run` or invoke FFmpeg.
