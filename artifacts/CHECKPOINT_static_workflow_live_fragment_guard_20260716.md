# Checkpoint: static workflow live-fragment guard

Date: 2026-07-16

## Implemented

- Extended `scripts/validate_safe_local_boundary.py` to scan `.github/workflows/*.yml` and `.yaml` files for live/runtime/media fragments.
- Added regression coverage for unsafe workflow fragments such as `/health/gpu`.
- This makes CI live-probe drift fail in the static file-only boundary validator, not only in runner unit tests.

## Validation

- Focused static validator tests: `3 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `153 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
