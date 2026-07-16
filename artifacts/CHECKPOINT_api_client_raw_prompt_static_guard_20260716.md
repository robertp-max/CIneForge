# Checkpoint: API client raw prompt static guard

Date: 2026-07-16

## Implemented

- Narrowed the static validator frontend API-client exemption so only live health/status wrapper callsite checks are skipped for `frontend/src/api/client.ts`.
- Raw `/prompt` and `/api/prompt` strings and forbidden local child routes are now scanned in the API client too.
- Added regression coverage proving an API-client raw `/prompt` method is flagged.

## Validation

- Focused static validator tests: `3 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `154 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
