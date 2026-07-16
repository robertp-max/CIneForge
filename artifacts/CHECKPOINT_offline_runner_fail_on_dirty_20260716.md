# Checkpoint: offline runner fail-on-dirty passthrough

Date: 2026-07-16

## Implemented

- Added `--fail-on-dirty` to `scripts/run_offline_safe_validation.py`.
- The runner forwards the option to `scripts/checkpoint_watchdog.py --fail-on-dirty` after static checks, tests, frontend lint/build, and `git diff --check`.
- Added regression coverage in `backend/tests/test_offline_safe_validation_runner.py`.
- Documented the option in `docs/OFFLINE_SAFE_VALIDATION.md` and `docs/CHECKPOINT_WATCHDOG.md`.
- Updated validation-count docs to `155 passed, 71 warnings`.

## Validation

- Focused runner tests: `6 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `155 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
