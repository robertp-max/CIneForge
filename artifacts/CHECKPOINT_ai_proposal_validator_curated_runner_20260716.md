# Checkpoint: AI proposal validator in curated runner

Date: 2026-07-16

## Implemented

- Added advisory AI proposal validator tests (`backend/tests/test_ai_proposal_validator.py`) to the curated offline validation runner.
- The tests assert proposals containing raw FFmpeg commands, direct workflow node IDs, or queue mutations are rejected.
- Extended runner membership guard so advisory-boundary coverage remains in `BACKEND_TESTS`.
- Updated README/offline validation docs and current validation-count docs to warning-free `235 passed`.

## Validation

- Focused AI proposal validator + offline runner tests: `10 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `235 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after count updates before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
