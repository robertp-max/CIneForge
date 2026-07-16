# Checkpoint: workflow manifest validation in curated runner

Date: 2026-07-16

## Implemented

- Added offline workflow manifest validation tests (`backend/tests/test_workflow_manifest_validation.py`) to the curated offline validation runner.
- Extended runner membership guard so workflow manifest validation remains in `BACKEND_TESTS` alongside path/output, runtime catalog, and CF-VID-01 coverage.
- Updated offline validation docs and current validation-count docs to `184 passed`.

## Validation

- Focused workflow manifest + offline runner tests: `13 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `184 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after count updates before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
