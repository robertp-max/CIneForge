# Checkpoint: non-approval phrase hardening

Date: 2026-07-16

## Implemented

- Added `f`, abusive language, and threats/coercion to operator approval-template non-approval examples.
- Updated live-boundary, checkpoint-watchdog, and safe-endpoint docs to call those out explicitly.
- Added tests ensuring templates and docs include the current non-approval phrase set.
- Updated validation-count docs to `150 passed, 71 warnings`.

## Validation

- Focused operator/docs tests: `14 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `150 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
