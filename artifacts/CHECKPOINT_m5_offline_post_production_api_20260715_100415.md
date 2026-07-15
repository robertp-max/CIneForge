# Checkpoint — M5 Offline Post-production Plan API

Generated: 2026-07-15 10:04 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `4bfb40c checkpoint: add structured FFmpeg recipe builders`

## Scope

Added a non-executing local API for file-backed CF-POST-01 post-production plan manifests.

Changes:

- Added `PostProductionAssemblyPlanCreate` request schema.
- Added `PostProductionPlanStore.create_from_request(...)` to build and persist offline manifests from request payloads.
- Added `backend/app/api/routes/local_post_production.py`:
  - `POST /local-post-production/plans`
  - `GET /local-post-production/plans`
  - `GET /local-post-production/plans/{plan_id}`
- Mounted the new router and updated app route-contract tests.
- Added tests proving:
  - plans are persisted as `planned_offline`;
  - `execution_submitted=false` and output/final probe/error fields remain null;
  - invalid SHA256 and unsafe paths are rejected;
  - no execution endpoint is exposed;
  - manifest list/get round-trip works.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_local_post_production.py \
  backend/tests/test_post_production.py \
  backend/tests/test_phase1_app_routing.py
# 15 passed, 2 warnings

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 512 passed, 9 skipped, warnings only, ~71.51s
```

## Safety notes

- The new API creates/list/gets offline manifests only.
- No FFmpeg command was executed.
- No FFmpeg execution/submission endpoint was added.
- No live ComfyUI/GPU/render/benchmark action was run.
