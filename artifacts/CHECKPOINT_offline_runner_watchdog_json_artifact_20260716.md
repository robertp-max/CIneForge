# Checkpoint: offline runner watchdog JSON artifact option

Date: 2026-07-16

## Implemented

- Added `--watchdog-json <path>` to `scripts/run_offline_safe_validation.py`.
- The runner still prints the checkpoint watchdog banner and can additionally write a machine-readable JSON watchdog report.
- Fixed direct script import path handling for `python scripts/run_offline_safe_validation.py`.
- Added regression coverage in `backend/tests/test_offline_safe_validation_runner.py`.
- Documented the option in `docs/OFFLINE_SAFE_VALIDATION.md` and `docs/CHECKPOINT_WATCHDOG.md`.
- Updated validation-count docs to `147 passed, 71 warnings`.

## Validation

- Focused runner tests: `3 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `147 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
