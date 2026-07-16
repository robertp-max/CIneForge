# M5 Checkpoint: Recipe Command Probe Provenance UI

## Scope
- Updated frontend API typing for `GET /local-post-production/recipe-commands` to include persisted `input_probe_count` and `input_probe_jsons`.
- Extended the existing read-only post-production page to display recipe command input probe provenance.
- Rendered only inert text: count fields and a bounded safe summary of probe JSON records (top-level/key counts, stream count, codec type/name tokens, and format keys), without dumping raw JSON.

## Safety boundaries
- No POST/create/update/delete/execute recipe-command helper was added.
- No buttons, forms, inputs, selects, copy, run, download, or execute controls were added.
- No FFmpeg/ffprobe, ComfyUI/GPU, render, or benchmark command was executed.
- Backend routes and persistence were not changed in this checkpoint.

## Validation
- `cd frontend && npm run lint` passed.
- `cd frontend && npm run build` passed.
- Static safety grep for controls/copy/download handlers in `frontend/src/studio/pages/PostProductionPlansPage.tsx` returned no matches.
- Static safety grep for recipe-command/local-post-production POST/execute helpers in `frontend/src` returned no matches.
- Static safety grep for raw `JSON.stringify` of probe provenance in `frontend/src` returned no matches.
- Focused backend route tests were not run because backend files/routes were not touched.

## Files changed
- `frontend/src/api/client.ts`
- `frontend/src/studio/pages/PostProductionPlansPage.tsx`
- `artifacts/CHECKPOINT_m5_recipe_command_probe_provenance_ui_20260715_151458.md`

## Residual risks
- Existing persisted probe JSON may contain unusual keys; the UI summarizes key names and bounded codec tokens only, not raw values or full JSON.
- If the backend returns malformed probe provenance, the page falls back to zero summarized JSON records or shows the existing load error path.
