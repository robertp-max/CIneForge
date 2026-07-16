# CHECKPOINT: M6 Local Archetype Catalog Expansion

Date: 2026-07-16

## Scope

Expanded `storage/archetypes/catalog.json` so the local planning catalog includes every canonical workflow registry archetype:

- `CF-IMG-01` through `CF-IMG-05`
- `CF-VID-01` through `CF-VID-05`
- `CF-UTIL-01`
- `CF-POST-01`

## Safety contract

- Catalog expansion is planning-only metadata.
- All newly added records are `enabled=false` and `readiness=blocked`.
- `CF-VID-01` remains disabled and `benchmark_required`.
- No archetype is marked ready.
- No public generation, `/prompt` proxy, ComfyUI submission, live probe, GPU lease, queue execution, render, benchmark, FFmpeg, or ffprobe action is added or performed.

## Implementation notes

- Existing catalog entries were retained.
- Missing canonical records were added with known quality profiles from the workflow registry and known model key only for the LTX video continuation entry.
- Readiness rollups should now report `catalog_present=true` for every canonical registry archetype while keeping `summary.ready == 0`.
- Schema/test expectations now require the full canonical registry archetype set.

## Validation target

Focused backend tests:

- `backend/tests/test_local_archetypes.py`
- `backend/tests/test_local_readiness.py`
- `backend/tests/test_local_presets.py`

Also run `git diff --check`.
