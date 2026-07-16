# Checkpoint: archetype/preset route read-only guards

Date: 2026-07-16

## Implemented

- Added method guards for archetype catalog/list/item routes so POST is rejected.
- Added method guards for preset catalog/list/item routes so POST is rejected.
- Asserted representative archetype and preset item responses remain disabled and not `ready`.

## Validation

- Focused archetype/preset route tests: `10 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `166 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
