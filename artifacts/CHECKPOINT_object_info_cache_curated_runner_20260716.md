# Checkpoint: object-info cache in curated runner

Date: 2026-07-16

## Implemented

- Added offline object-info cache tests (`backend/tests/test_object_info_cache.py`) to the curated offline validation runner.
- These tests use local fixtures and an explicit offline client stub; they do not contact ComfyUI.
- Extended runner membership guard so object-info cache compatibility remains in `BACKEND_TESTS`.
- Updated offline validation docs and current validation-count docs to `189 passed`.

## Validation

- Focused object-info cache + offline runner tests: `12 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `189 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after count updates before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
