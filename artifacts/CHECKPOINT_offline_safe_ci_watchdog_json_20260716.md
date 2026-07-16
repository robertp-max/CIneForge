# Checkpoint: offline-safe CI writes watchdog JSON

Date: 2026-07-16

## Implemented

- Updated `.github/workflows/test.yml` to run `python scripts/run_offline_safe_validation.py --watchdog-json artifacts/watchdog/ci.json`.
- Added a regression test that verifies the CI workflow keeps the `--watchdog-json` invocation.
- Documented CI usage in `docs/OFFLINE_SAFE_VALIDATION.md`.
- Updated validation-count docs to `148 passed, 71 warnings`.

## Validation

- Focused runner tests: `4 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `148 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
