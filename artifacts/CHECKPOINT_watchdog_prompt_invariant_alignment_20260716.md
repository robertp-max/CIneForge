# Checkpoint: watchdog prompt invariant alignment

Date: 2026-07-16

## Implemented

- Updated the checkpoint watchdog invariant to name both public raw `/prompt` and `/api/prompt` routes.
- Updated `docs/CHECKPOINT_WATCHDOG.md` and watchdog tests to match the script invariant.

## Validation

- Focused watchdog tests: `7 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `154 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed the aligned invariant

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
