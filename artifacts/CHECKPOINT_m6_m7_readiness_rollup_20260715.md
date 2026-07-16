# CHECKPOINT: M6/M7 Readiness Rollup APIs

Date: 2026-07-15

## Scope

Added backend read-only readiness rollups for local archetypes and presets to support M6/M7 planning without live execution.

## Endpoints

- `GET /local-archetypes/readiness`
- `GET /local-archetypes/{archetype_id}/readiness`
- `GET /local-presets/readiness`
- `GET /local-presets/{preset_id}/readiness`

## Safety contract

- No FFmpeg/ffprobe execution.
- No ComfyUI contact or prompt submission.
- No GPU lease acquisition, render, benchmark, job creation, or public generation enablement.
- Responses report `public_generation_enabled=false` and endpoint-level `live_execution_performed_by_endpoint=false`.
- Non-ready records report promotion blockers such as missing benchmark evidence, missing human approval, missing implementation, missing dependency evidence, blocked catalog state, or default archetype blockers.

## Implementation notes

- Readiness records merge local catalog metadata with workflow registry evidence, admission findings, and production-ready gate criteria.
- Archetype rollups include local catalog records plus registry-only canonical archetypes; registry-only records are blocked from promotion until catalog coverage exists.
- Current catalog/registry evidence yields no ready archetypes or presets.
- `CF-VID-01` and presets that default to it remain `benchmark_required`; production readiness remains false because benchmark and human approval evidence are missing.
- Planned/unimplemented archetypes and presets defaulting to them remain `blocked`.

## Validation target

Focused backend tests:

- `backend/tests/test_local_readiness.py`
- Existing catalog route coverage in `backend/tests/test_local_archetypes.py`
- Existing preset route coverage in `backend/tests/test_local_presets.py`
