# Checkpoint: safe endpoint docs sync

Date: 2026-07-16

## Implemented

- Expanded `docs/SAFE_LOCAL_ENDPOINTS.md` to list exact local archetype/preset catalog and readiness routes.
- Added `backend/tests/test_safe_local_endpoint_docs.py` to keep the endpoint matrix synchronized with FastAPI route paths and to prevent live execution routes from being documented as allowed table rows.
- Added the docs sync test to `scripts/run_offline_safe_validation.py`.

## Validation

- `./.venv/Scripts/python.exe -B scripts/run_offline_safe_validation.py`
  - Static safe/local boundary validation: passed
  - Curated backend tests: `136 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
