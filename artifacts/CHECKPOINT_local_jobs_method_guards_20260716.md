# Checkpoint: local jobs method guards

Date: 2026-07-16

## Implemented

- Added route method guards for `/local-jobs` to reject PUT/PATCH/DELETE.
- Added route method guards for `/local-jobs/{job_id}` to reject POST/PUT/DELETE.
- Preserved the manifest-only POST `/local-jobs` and read-only GET/list behavior.

## Validation

- Focused local jobs tests: `7 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `166 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
