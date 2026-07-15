# M5 Checkpoint: Offline recipe command input probe provenance

## Scope
- Backend-only extension for generic offline FFmpeg recipe command manifests.
- No FFmpeg/ffprobe execution, no execute/create API route changes, and no generation gate changes.

## Implementation
- Added optional `input_probe_jsons` and derived `input_probe_count` to `PostProductionRecipeCommandManifest`.
- Extended `PostProductionPlanStore.create_from_recipe_command(...)` with optional `input_probe_jsons` keyword argument.
- Rejects provided input probe lists whose count does not match recipe command `input_paths`.
- Persists probe provenance into the same offline JSON manifest read by existing GET/list recipe-command APIs.

## Validation
- `.venv/Scripts/python.exe -m pytest backend/tests/test_post_production.py backend/tests/test_local_post_production.py backend/tests/test_ffmpeg_service.py`
- Result: 42 passed, 2 existing deprecation warnings.

## Notes
- Requested context and plan files under `.pi-subagents/chain-runs/45c907cb/` were absent; implementation followed the user task scope directly.
