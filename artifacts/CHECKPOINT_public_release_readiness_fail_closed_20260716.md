# Checkpoint: fail-closed public-release readiness report

Date: 2026-07-16

## Implemented

- Added read-only backend public-release readiness surface:
  - `GET /local-runtime/public-readiness`
- Added schemas/service/tests:
  - `backend/app/schemas/local_public_readiness.py`
  - `backend/app/services/local_public_readiness.py`
  - `backend/tests/test_local_public_readiness.py`
- Added Runtime page consumption via `api.localPublicReadiness()` and a fail-closed public-release readiness panel.
- Updated route-contract tests and docs.

## Safety posture

The report always fails closed for this local-only MVP wave:

- `status=blocked`
- `public_release_ready=false`
- `public_generation_enabled=false`
- `public_prompt_enabled=false`
- `internet_facing_enabled=false`
- `live_execution_performed_by_endpoint=false`
- `live_execution_approved_by_endpoint=false`

It aggregates existing read-only local runtime/readiness metadata only. It does not run FFmpeg/ffprobe, contact ComfyUI, probe GPU/runtime health, submit prompts, create jobs, render media, benchmark, approve live work, or enable public generation.

## Validation

- `./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests/test_local_public_readiness.py backend/tests/test_local_mvp_readiness.py backend/tests/test_local_readiness.py backend/tests/test_phase1_app_routing.py`
  - Result: `14 passed`
- `cd frontend && npm run lint && npm run build`
  - Result: passed
- `git diff --check`
  - Result: no whitespace errors; CRLF warnings only
