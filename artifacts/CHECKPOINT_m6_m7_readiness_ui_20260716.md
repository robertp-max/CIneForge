# CHECKPOINT: M6/M7 Readiness Rollup Frontend Consumption

Date: 2026-07-16

## Scope

Implemented frontend read-only consumption for the M6/M7 local readiness rollup endpoints.

## Endpoints consumed

- `GET /local-archetypes/readiness`
- `GET /local-archetypes/{archetype_id}/readiness`
- `GET /local-presets/readiness`
- `GET /local-presets/{preset_id}/readiness`

## UI behavior

- Runtime page now loads archetype and preset readiness rollups through API-client GET helpers only.
- Displays bounded M6/M7 planning summaries:
  - counts by `blocked`, `benchmark_required`, and `ready`
  - top blocker/promotion reasons, capped at three
  - `public_generation_enabled` endpoint and summary flags
  - `live_execution_required_for_promotion` counts and sample-record flags
  - evidence gate count showing records remain gated unless backend evidence reports ready/admitted/production-ready
- Sample records are capped at four per rollup.
- UI remains inert: no runtime status, ComfyUI health, GPU health, FFmpeg health, prompt submission, execution, approval, benchmark, or render controls were added.

## Validation

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `if rg "api\\.(runtimeStatus|comfyHealth|gpuHealth|ffmpegHealth)" frontend/src --glob '!api/client.ts'; then echo "Unexpected live probe helper usage found"; exit 1; else echo "No api.runtimeStatus/comfyHealth/gpuHealth/ffmpegHealth UI calls outside frontend/src/api/client.ts"; fi`
- `git diff --check`

## Notes

- `git diff --check` passed with existing line-ending warnings only.
- The new single-record API helpers are available for future detail surfaces but the Runtime page uses the aggregate read-only rollups for bounded summaries.
