# M5 Checkpoint: Read-only Recipe Command Manifest API

## Scope
- Added backend-only GET routes for already-persisted generic FFmpeg recipe command manifests:
  - `GET /local-post-production/recipe-commands`
  - `GET /local-post-production/recipe-commands/{plan_id}`
- Routes read from `PostProductionPlanStore.list_recipe_commands()` and `get_recipe_command()` only.
- Updated app route contract coverage for the new mounted GET routes.
- Added route tests using a temp file-backed store with pre-persisted recipe command manifests.

## Validation
- `.venv/Scripts/python.exe -m pytest backend/tests/test_local_post_production.py backend/tests/test_post_production.py backend/tests/test_phase1_app_routing.py` passed: 25 tests.
- Tests cover list/get response behavior, invalid UUID handling, missing manifest 404 behavior, and absence of recipe-command create/execute endpoints.

## Safety Notes
- This checkpoint does not add POST, PUT, PATCH, DELETE, execute, submission, or raw command input endpoints for recipe commands.
- The new routes are read-only over already-persisted manifests; they do not invoke FFmpeg, ComfyUI, GPU rendering, benchmarks, or workers.
- Existing persisted command arrays remain provenance returned from stored manifests, not user-submitted command input.
