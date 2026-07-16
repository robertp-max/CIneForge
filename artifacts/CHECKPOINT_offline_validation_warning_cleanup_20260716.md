# Checkpoint: offline validation warning cleanup

Date: 2026-07-16

## Implemented

- Replaced SQLAlchemy timestamp defaults in `backend/app/db/base.py` with a timezone-aware UTC helper.
- Replaced Storyboard service `datetime.utcnow()` calls with a non-deprecated naive-UTC helper to preserve existing comparisons.
- Replaced deprecated `HTTP_422_UNPROCESSABLE_ENTITY` constants in curated local-only routes with `HTTP_422_UNPROCESSABLE_CONTENT`.
- Updated current validation-count docs from warning-bearing results to `157 passed`.

## Validation

- Focused warning-producing local route tests: `34 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `157 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after updating count docs before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
