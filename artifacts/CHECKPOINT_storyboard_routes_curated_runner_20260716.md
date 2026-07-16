# Checkpoint: storyboard routes in curated runner

Date: 2026-07-16

## Implemented

- Added SQLite/TestClient storyboard route tests (`backend/tests/test_storyboard_routes.py`) to the curated offline validation runner.
- These tests include the route-level invariant that storyboard approval does not render or queue work.
- Cleaned deprecated FastAPI 422 constant usage in `backend/app/api/routes/storyboard.py`.
- Extended runner membership guard so storyboard route coverage remains in `BACKEND_TESTS`.
- Updated README/offline validation docs and current validation-count docs to warning-free `232 passed`.

## Validation

- Focused storyboard routes + offline runner tests: `14 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `232 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after count updates before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
