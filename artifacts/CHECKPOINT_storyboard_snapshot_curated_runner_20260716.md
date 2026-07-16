# Checkpoint: storyboard snapshot in curated runner

Date: 2026-07-16

## Implemented

- Added SQLite-only storyboard snapshot/content-hash tests (`backend/tests/test_storyboard_snapshot.py`) to the curated offline validation runner.
- Cleaned service-level `datetime.utcnow()` warnings in `backend/app/services/storyboard_mutations.py` by using an explicit UTC timestamp converted to the existing naive DB convention.
- Extended runner membership guard so storyboard snapshot immutability coverage remains in `BACKEND_TESTS`.
- Updated README/offline validation docs and current validation-count docs to warning-free `225 passed`.

## Validation

- Focused storyboard snapshot + offline runner tests: `19 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `225 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after count updates before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
