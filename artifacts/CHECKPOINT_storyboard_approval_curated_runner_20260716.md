# Checkpoint: storyboard approval in curated runner

Date: 2026-07-16

## Implemented

- Added SQLite-only storyboard approval/readiness tests (`backend/tests/test_storyboard_approval.py`) to the curated offline validation runner.
- Cleaned the test's `datetime.utcnow()` warning by using an explicit UTC timestamp converted to the existing naive DB convention.
- Extended runner membership guard so storyboard approval immutability/readiness coverage remains in `BACKEND_TESTS`.
- Updated offline validation docs and current validation-count docs to warning-free `213 passed`.

## Validation

- Focused storyboard approval + offline runner tests: `25 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `213 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after count updates before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
