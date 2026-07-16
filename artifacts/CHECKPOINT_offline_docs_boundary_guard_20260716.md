# Checkpoint: offline docs boundary guard

Date: 2026-07-16

## Implemented

- Added `backend/tests/test_offline_docs_boundary.py`.
- Added the docs boundary guard to `scripts/run_offline_safe_validation.py`.
- The guard verifies API/UI/smoke docs mark live probes as approval-required and do not reintroduce stale live-probe wording.

## Validation

- Focused docs boundary test: `2 passed`
- `./.venv/Scripts/python.exe -B scripts/run_offline_safe_validation.py`
  - Static safe/local boundary validation: passed
  - Curated backend tests: `140 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
