# Checkpoint: watchdog fail-on-dirty mode

Date: 2026-07-16

## Implemented

- Added optional `--fail-on-dirty` mode to `scripts/checkpoint_watchdog.py`.
- Normal watchdog behavior remains unchanged; fail-on-dirty exits nonzero only when explicitly requested and tracked files are dirty.
- Added regression coverage for dirty-tree exit behavior.
- Documented the option in `docs/CHECKPOINT_WATCHDOG.md`.
- Updated validation-count docs to `151 passed, 71 warnings`.

## Validation

- Focused watchdog tests: `5 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `151 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
