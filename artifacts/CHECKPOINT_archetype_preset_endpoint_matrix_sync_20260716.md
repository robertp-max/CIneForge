# Checkpoint: archetype/preset endpoint matrix sync

Date: 2026-07-16

## Implemented

- Expanded `backend/tests/test_safe_local_endpoint_docs.py` required endpoint coverage so the safe endpoint matrix must stay synchronized for:
  - `/local-archetypes/catalog`, `/local-archetypes`, `/local-archetypes/{archetype_id}`, and readiness variants,
  - `/local-presets/catalog`, `/local-presets`, `/local-presets/{preset_id}`, and readiness variants.

## Validation

- Focused safe endpoint docs tests: `4 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `159 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
