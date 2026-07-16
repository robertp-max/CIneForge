# Checkpoint: watchdog JSON fail-on-dirty coverage

Date: 2026-07-16

## Implemented

- Added regression coverage for `scripts/checkpoint_watchdog.py --json --fail-on-dirty`.
- Verified JSON output is still emitted while dirty tracked state returns a nonzero exit.
- Updated validation-count docs to `152 passed, 71 warnings`.

## Validation

- Focused watchdog tests: `6 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `152 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
