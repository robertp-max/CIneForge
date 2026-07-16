# Checkpoint: watchdog staged-file visibility

Date: 2026-07-16

## Implemented

- Added `staged_files` to `scripts/checkpoint_watchdog.py` reports and JSON output.
- Banner now prints staged-file count.
- `GET /local-runtime/checkpoint-watchdog` now includes staged-file names.
- Runtime UI now shows staged-file summary in the Checkpoint Watchdog panel.
- Updated backend tests and docs for staged-file reporting.

## Validation

- Focused watchdog/backend tests and frontend lint/build passed:
  - `10 passed`
  - frontend lint/build passed
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `150 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed with staged-file count

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
