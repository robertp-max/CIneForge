# Checkpoint: watchdog source-scoped untracked visibility

Date: 2026-07-16

## Implemented

- Added `untracked_source_files` to `CheckpointWatchdogReport` for source/docs/test/config-like untracked files.
- Kept ignored local watchdog JSON artifacts out of the untracked-source list.
- Updated text and JSON watchdog output, `--fail-on-dirty`, read-only API schema/service, frontend API type, and Runtime UI panel to surface source-scoped untracked files.
- Updated watchdog/offline validation docs and current validation-count docs to `164 passed`.

## Validation

- Focused watchdog/API/docs tests: `16 passed`
- Frontend lint/build: passed
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `164 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed with source-scoped untracked count

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
