# Checkpoint Refresh — CineForge Local Runtime / ComfyUI Boundary

Generated: 2026-07-14 22:20 local
Working directory: `C:/AI/Git/CIneForge`
Branch: `master...origin/master`

## Model-instance handoff note

The current assistant session cannot force-switch itself to a different GPT-5.5 model instance from inside the repo. To continue with a different instance, start a new pi/model session if the launcher/UI supports it and point it at this checkpoint file.

Suggested first prompt for the new instance:

> Read `artifacts/CHECKPOINT_refresh_20260714_222030.md`, inspect `git status --short --branch`, then continue the CineForge local-runtime/ComfyUI controlled-submission work without enabling public generation or direct ComfyUI prompt submission.

## Current repo state

`git status --short --branch` shows 27 modified tracked files and many untracked files.

Tracked modified highlights:

- Docs/planning: `README.md`, `Architecture/ARCHITECTURE_BLUEPRINT.md`, `MVP/MVP_ARCHITECTURE.md`, `Benchmarks/BENCHMARK_PROTOCOL.md`, `Models/MODEL_FEASIBILITY_MATRIX.md`, `Quantization/QUANTIZATION_MATRIX.md`, `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`, `Sources/SOURCE_REGISTER.md`, `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`, `docs/PRODUCT_VISION.md`, `docs/READINESS_GATES.md`, `docs/ROADMAP.md`, `docs/WORKFLOW_TEMPLATE_MANIFEST.md`
- Backend routing/config/runtime: `backend/app/api/router.py`, `backend/app/api/routes/health.py`, `backend/app/core/config.py`, `backend/app/services/comfy/submission.py`, `backend/app/services/ffmpeg/service.py`, `backend/app/services/workflows/template_service.py`, `backend/app/utils/path_safety.py`
- Backend tests: `backend/tests/test_health.py`, `backend/tests/test_path_safety.py`, `backend/tests/test_phase1_app_routing.py`, `backend/tests/test_workflow_manifest_validation.py`
- Frontend: `frontend/src/api/client.ts`, `frontend/src/pages/Jobs.tsx`, `frontend/src/pages/Runtime.tsx`

Important untracked additions:

- Backend routes: `backend/app/api/routes/local_archetypes.py`, `local_jobs.py`, `local_presets.py`, `local_runtime.py`
- Backend schemas: `backend/app/schemas/local_*.py`, `backend/app/schemas/production.py`
- Backend services: `backend/app/services/local_*.py`, `output_collector.py`, `post_production.py`, `production_gates.py`, `production_planner.py`, `workflows/admission.py`, `workflows/compiler.py`, `workflows/registry.py`, `workflows/ui_template_service.py`
- Backend tests: `backend/tests/test_cf_vid01_api_workflow_template.py`, `test_local_archetypes.py`, `test_local_jobs.py`, `test_local_presets.py`, `test_local_runtime.py`, `test_local_runtime_evidence.py`, `test_ui_workflow_template_service.py`
- Storage/catalog/templates: `storage/archetypes/`, `storage/local_jobs/`, `storage/presets/`, `storage/projects/`, `storage/runtime/`, `storage/workflow_templates/cf_vid_01_ltx23_single_stage/` through `cf_vid_04_ltx23_lipdub_two_stage/`
- Docs/artifacts: `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md`, `docs/CFVID01_RUNTIME_SMOKE.md`, `docs/RUNTIME_INVENTORY.md`, `artifacts/`, `.pi-subagents/`
- Imported external UI artifact: `CineForge-Storyboard-Studio-v2.zip` and `CineForge-Storyboard-Studio-v2/`

## Current implementation direction

The repo is being moved toward a local, DB-free, gated ComfyUI runtime boundary:

- Local runtime catalog identifies the selected LTX 2.3 22B distilled FP8 artifact and secondary candidates.
- Output policy is one project folder under ComfyUI output root, with filename prefixes shaped as `<project-folder>/<run-stem>`.
- Public/user prompt submission remains disabled.
- Local job creation prepares manifests, output folders, and workflow snapshots only; it does **not** submit prompts to ComfyUI.
- Runtime readiness/evidence is exposed read-only.
- Workflow template manifests and compiler/registry code enforce admitted templates and production gates.

## Key backend endpoints added/changed

- `/health` now exposes local/file-backed runtime metadata and states database as not required for this local slice.
- `/runtime/status` reports ComfyUI, `object_info`, GPU, FFmpeg, queue flags, disabled actions, and output policy.
- `/local-runtime/catalog` — selected local model/artifact catalog.
- `/local-runtime/output-policy` — ComfyUI output root and prefix shape.
- `/local-runtime/evidence` and `/local-runtime/evidence/cf-vid-01-smoke` — local evidence records.
- `/local-presets` and `/local-presets/catalog` — file-backed preset catalog.
- `/local-archetypes` and `/local-archetypes/catalog` — file-backed archetype catalog.
- `/local-jobs` — create/list/get file-backed local job manifests.

## Key backend behavior

- `backend/app/services/local_runtime.py`
  - Hardcodes/checks the selected FP8 LTX2.3 artifact path and expected SHA256.
  - Provides output policy and project output-prefix preparation.
- `backend/app/services/local_jobs.py`
  - Validates preset/archetype/model/profile contract.
  - Sanitizes `project_key` and `run_stem`.
  - Creates manifest JSON under `storage/local_jobs` and appends `events.jsonl`.
  - For `CF-VID-01`, snapshots a patched workflow using `WorkflowTemplateService`.
  - Leaves `generation_submitted = false`.
- `backend/app/services/workflows/compiler.py`
  - Validates dimensions/frame count, registry admission, dependencies, semantic bindings, and forbids smoke templates for production.
- `backend/app/services/workflows/registry.py`
  - Requires canonical archetypes and checks live UI/API graph/dependency evidence.

## Key frontend behavior

- `frontend/src/api/client.ts`
  - Adds TypeScript types and API functions for local runtime catalog/evidence, presets, archetypes, and local jobs.
- `frontend/src/pages/Runtime.tsx`
  - Displays runtime status, selected FP8 artifact, local catalog counts, output policy, runtime evidence, and disabled actions.
- `frontend/src/pages/Jobs.tsx`
  - Adds a “Prepare Local Manifest” form.
  - Lists local file-backed manifests separately from DB jobs.
  - UI copy clearly states no ComfyUI prompt is submitted.

## Safety / invariants to preserve

- Do not expose direct/public `/prompt` submission.
- Do not enable generation from the UI by default.
- Do not submit to ComfyUI when creating local job manifests.
- Preserve `generation_submitted: false` unless a future controlled worker intentionally flips it after validation.
- Keep path sanitization strict: no absolute output prefixes, traversal, backslashes, or nested trees beyond `<project-folder>/<run-stem>`.
- Treat benchmark/evidence gates as required before production rendering.

## Validation status

No tests were run during this checkpoint refresh.

Recommended next validation commands:

```bash
pytest backend/tests -q
cd frontend && npm run build
```

If failures occur, prioritize:

1. Backend route imports/schema mismatches.
2. Local catalog fixture/storage path expectations.
3. Workflow template manifest hash or semantic-binding drift.
4. Frontend TypeScript type drift in `client.ts`, `Runtime.tsx`, and `Jobs.tsx`.

## Likely next work

1. Run backend tests and fix regressions.
2. Run frontend build and fix type errors.
3. Review untracked files and decide what belongs in git vs local artifacts.
4. Confirm storage JSON fixtures/templates are complete and deterministic.
5. Keep production/render submission disabled until explicit operator approval and readiness gates are satisfied.
