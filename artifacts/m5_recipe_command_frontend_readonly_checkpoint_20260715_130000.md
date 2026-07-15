# M5 Checkpoint: Read-only Recipe Command Manifest Frontend

## Scope
- Added frontend API typing and a GET-only client helper for existing generic FFmpeg recipe command manifests from `GET /local-post-production/recipe-commands`.
- Integrated recipe command manifest display into the existing read-only post-production page.
- Displayed stored manifest fields and structured argv as inert text only.

## Safety boundaries
- No POST/create/update/delete/execute frontend helper was added for recipe commands.
- No command input, copy, run, download, submit, form, or execution button was added.
- No FFmpeg, ComfyUI/GPU, render, or benchmark process was executed by this checkpoint.
- Backend execution semantics and public generation gates were not changed.

## Validation
- `cd frontend && npm run lint` passed.
- `cd frontend && npm run build` passed.
- `git grep -n "recipe-commands.*method: 'POST'\|method: 'POST'.*recipe-commands\|recipe-commands.*/execute\|copy.*recipe-commands\|run.*recipe-commands" -- frontend/src` returned no matches.
- `git grep -n "local-post-production.*method: 'POST'\|method: 'POST'.*local-post-production\|local-post-production.*/execute" -- frontend/src/api/client.ts frontend/src/studio/pages/PostProductionPlansPage.tsx` returned no matches.
- Focused backend route contract check: `.venv/Scripts/python.exe -m pytest backend/tests/test_local_post_production.py backend/tests/test_phase1_app_routing.py` passed: 10 passed, 2 warnings.

## Files changed
- `frontend/src/api/client.ts`
- `frontend/src/studio/pages/PostProductionPlansPage.tsx`
- `artifacts/m5_recipe_command_frontend_readonly_checkpoint_20260715_130000.md`

## Residual risks
- Stored manifests may contain long argv/path text; the UI renders it in scrollable inert text panels.
- If the backend GET route returns validation errors for corrupted stored JSON, the page reports an error and does not offer repair or retry controls.
