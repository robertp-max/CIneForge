# Checkpoint: frontend raw live-probe fetch guard

Date: 2026-07-16

## Implemented

- Added static safe-boundary detection for raw frontend `fetch('/runtime/status')`, `fetch('/health/comfy')`, `fetch('/health/gpu')`, and `fetch('/health/ffmpeg')` callsites outside the API client.
- The guard targets fetch calls, so descriptive UI text mentioning live probes remains allowed.
- Added regression coverage for a raw frontend `/health/gpu` fetch.

## Validation

- Focused static validator tests: `4 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `157 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
