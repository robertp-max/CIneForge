# Checkpoint — M5 Read-only FFmpeg Recipe Catalog

Generated: 2026-07-15 08:18 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `5f656fc checkpoint: harden M5 post-production planning`

## Scope

Added a read-only FFmpeg command-template recipe catalog backed by the existing allowlist.

Changes:

- Added `backend/app/schemas/ffmpeg_recipes.py`.
- Added `ffmpeg_command_template_catalog()` in `backend/app/services/ffmpeg/service.py`.
- Added `GET /local-runtime/ffmpeg-recipes`.
- Added tests proving the catalog matches `APPROVED_COMMAND_TEMPLATES` and is read-only:
  - `executes_from_catalog=false`
  - `user_authored_command_allowed=false`
  - `command_shape=structured_argument_array`
  - stream-copy recipe requires probe compatibility.
- Added the route to the routing contract.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_ffmpeg_service.py \
  backend/tests/test_post_production.py \
  backend/tests/test_phase1_app_routing.py \
  backend/tests/test_local_runtime.py
# 17 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 502 passed, 9 skipped, warnings only, ~75.45s
```

## Safety notes

- Recipe endpoint is read-only.
- It exposes no FFmpeg execution API.
- No FFmpeg command was executed.
- No live ComfyUI/GPU/render/benchmark action was run.
