# Checkpoint: offline-safe CI fail-on-dirty enforcement

Date: 2026-07-16

## Implemented

- Updated GitHub Actions to run `python scripts/run_offline_safe_validation.py --watchdog-json artifacts/watchdog/ci.json --fail-on-dirty`.
- Updated runner workflow regression test to require the CI `--fail-on-dirty` option.
- Updated offline validation docs to record CI clean-tree enforcement.

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
