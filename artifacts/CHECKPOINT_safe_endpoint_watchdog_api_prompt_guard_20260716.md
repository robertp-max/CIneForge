# Checkpoint: safe endpoint watchdog/API prompt guard

Date: 2026-07-16

## Implemented

- Added `/local-runtime/checkpoint-watchdog` to the endpoint matrix sync test's required documented endpoints.
- Added `/api/prompt` to forbidden allowed-table rows so the safe endpoint matrix cannot document it as allowed.

## Validation

- Focused safe endpoint docs tests: `3 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `156 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
