# Checkpoint: frontend backtick live/prompt literal guard

Date: 2026-07-16

## Implemented

- Extended static safe-boundary scanning to catch template-literal/backtick frontend strings for:
  - raw live-probe fetches (`/runtime/status`, `/health/comfy`, `/health/gpu`, `/health/ffmpeg`),
  - raw public prompt references (`/prompt`, `/api/prompt`), and
  - watchdog child-route matching internals.
- Updated static and safe-boundary service regressions to exercise backtick live/prompt literals.

## Validation

- Focused safe-boundary tests: `8 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `157 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
