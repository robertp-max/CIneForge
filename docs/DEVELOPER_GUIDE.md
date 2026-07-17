# CineForge Developer Guide

Date: 2026-07-16

This guide explains the current CineForge codebase, local development workflow, safety boundaries, validation suite, and extension points.

## 1. Current architecture summary

CineForge is a local-first FastAPI + React/Vite application for planning and controlling AI video workflows. The current codebase emphasizes deterministic planning, safe local readiness, and file-backed manifests before exposing live generation.

Primary layers:

- Backend: FastAPI, SQLAlchemy, Pydantic schemas, service modules.
- Frontend: React + TypeScript + Vite.
- Storage: local SQLite by default plus JSON catalogs/manifests under `storage/`.
- Validation: static safe-boundary validator, curated backend tests, frontend lint/build, checkpoint watchdog.
- Runtime lane: ComfyUI/FFmpeg/GPU integration surfaces are gated and mostly read-only or manifest-only in the current UI/API.

## 2. Repository layout

Important paths:

```text
backend/app/
  api/routes/                 FastAPI route modules
  core/                       settings and core errors
  db/                         SQLAlchemy models/session
  schemas/                    Pydantic request/response schemas
  services/                   business logic and safety boundaries
  workers/                    worker skeletons

backend/tests/                pytest tests
frontend/src/                 React app source
scripts/                      validation, watchdog, DB helpers
storage/                      local catalogs, templates, evidence, manifests
docs/                         docs and runbooks
artifacts/                    committed checkpoint notes; local watchdog JSON ignored
```

## 3. Local prerequisites

Expected tools:

- Python 3.12+ compatible environment,
- Node.js/npm,
- local virtual environment at `.venv`,
- installed frontend dependencies in `frontend/node_modules`.

Install backend dev dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
```

Install frontend dependencies:

```powershell
cd frontend
npm install
```

Create local DB if needed:

```powershell
.\.venv\Scripts\python scripts\create_db.py
```

## 4. Running the app locally

Backend:

```powershell
.\.venv\Scripts\python -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

Frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173/
```

Backend root:

```text
http://127.0.0.1:8010/
```

The frontend default API base is currently `http://127.0.0.1:8010`. Override with:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8010"
$env:VITE_CINEFORGE_API_BASE_URL="http://127.0.0.1:8010"
```

## 5. Configuration

Backend settings are defined in:

```text
backend/app/core/config.py
```

Settings use the `CINEFORGE_` environment prefix.

Important settings:

- `CINEFORGE_DATABASE_URL`
- `CINEFORGE_COMFYUI_BASE_URL`
- `CINEFORGE_COMFYUI_OUTPUT_ROOT`
- `CINEFORGE_STORAGE_ROOT`
- `CINEFORGE_QUEUE_WORKER_ENABLED`
- `CINEFORGE_HARDWARE_OPERATOR_ENABLED`
- `CINEFORGE_M4_HARDWARE_PROBE_APPROVED`
- OpenAI planning provider settings under `CINEFORGE_OPENAI_*`

Current provider preference policy:

- OpenAI is the default hosted planning provider when configured.
- xAI/Grok is the secondary hosted provider switch target.
- Deterministic mock remains available for offline tests/local use.

Current implementation truth:

- OpenAI planning adapter exists.
- xAI/Grok appears in routing/catalog as a provider identity but is not yet a live adapter unless future code adds it.
- OpenAI should remain default; xAI/Grok should be secondary with a switch path through provider routing/profile configuration.

## 6. Backend route structure

Main route modules live in:

```text
backend/app/api/routes/
```

Key groups:

- `health.py`: backend and live-health endpoints; live probes are not part of offline validation.
- `projects.py`, `campaigns.py`: planning scaffold records.
- `storyboard.py`, `storyboard_crud.py`: Storyboard Phase A planning APIs.
- `providers.py`: provider discovery, capabilities, and connection-test routes.
- `local_runtime.py`: local runtime catalog/readiness/evidence/safety/watchdog surfaces.
- `local_jobs.py`: file-backed offline local job manifests.
- `local_generation.py`: offline semantic request and storyboard handoff manifests.
- `local_operator.py`: operator packets, runbooks, approval templates.
- `local_post_production.py`: offline post-production plans and stored recipe command manifests.
- `local_archetypes.py`, `local_presets.py`: DB-free local catalog/readiness records.

## 7. Safe local endpoint policy

Safe local endpoints are documented in:

```text
docs/SAFE_LOCAL_ENDPOINTS.md
```

All listed `/local-*` surfaces must remain:

- non-live,
- non-approving,
- non-generation-starting,
- non-media-tool-executing.

Do not add local child routes with exact segments such as execute, submit, run, approve, or prompt unless the safety design and static guards are intentionally updated.

Current static guard coverage checks that no safe endpoint matrix row says `/local-*` routes execute live tools, record approval, or start generation/media work.

## 8. Live/runtime boundary

See:

```text
docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md
```

Live/runtime work includes:

- contacting ComfyUI,
- GPU/runtime health probes,
- prompt submission,
- queue execution,
- rendering,
- benchmarking,
- FFmpeg/ffprobe execution,
- public/autonomous generation.

The offline validation suite must not perform any of those actions.

## 9. Validation commands

Full curated offline-safe validation:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py --fail-on-dirty
```

Static boundary only:

```powershell
.\.venv\Scripts\python scripts\validate_safe_local_boundary.py
```

Checkpoint watchdog:

```powershell
.\.venv\Scripts\python -B scripts\checkpoint_watchdog.py --fail-on-dirty
```

Frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

Current checkpoint truth:

- curated backend tests: `243 passed`,
- static safe/local boundary: passed,
- frontend lint/build: passed,
- `git diff --check`: passed,
- checkpoint watchdog: clean.

## 10. Curated offline-safe runner

The curated runner is:

```text
scripts/run_offline_safe_validation.py
```

It runs:

1. static safe-boundary validation,
2. curated backend pytest files,
3. frontend lint,
4. frontend build,
5. `git diff --check`,
6. checkpoint watchdog.

When adding a test file to `BACKEND_TESTS`, ensure the test is offline-safe and deterministic. Tests must not contact ComfyUI, external providers, GPU hardware, FFmpeg/ffprobe, or runtime-health endpoints unless explicitly scoped for a separate live test lane.

## 11. Static safe-boundary validator

The validator is:

```text
scripts/validate_safe_local_boundary.py
```

It scans source/docs/config/test surfaces for safety regressions, including:

- enabled/ready local archetypes or presets,
- frontend raw live-probe fetches outside API client definitions,
- raw prompt/public prompt route exposure,
- GitHub workflow live/media fragments,
- package script live/media fragments,
- assistant debug/analysis text leaks,
- unsafe local child route shapes,
- safe endpoint docs claiming live/approval/start capability.

Add new static checks here when a class of regression can be caught without executing the app.

## 12. Checkpoint watchdog

The watchdog is:

```text
scripts/checkpoint_watchdog.py
backend/app/services/local_checkpoint_watchdog.py
backend/app/api/routes/local_runtime.py
```

It reports:

- restart directive,
- last commit,
- tracked worktree cleanliness,
- staged file count/names,
- source-scoped untracked files,
- no-live invariants.

The local watchdog JSON artifact path is ignored:

```text
artifacts/watchdog/*.json
```

## 13. Database and storage

Default DB:

```text
sqlite:///./storage/cineforge_local.db
```

Important storage paths:

```text
storage/archetypes/catalog.json
storage/presets/catalog.json
storage/workflow_registry/catalog.json
storage/workflow_templates/
storage/runtime/
storage/local_jobs/
storage/projects/
storage/assets/
storage/outputs/
```

Many generated/local runtime files are intentionally ignored. Keep committed storage files limited to canonical fixtures, catalogs, templates, and evidence that should be versioned.

## 14. Storyboard Phase A development

Storyboard Phase A ends at planning approval. It must not start generation.

Core files:

```text
backend/app/api/routes/storyboard.py
backend/app/api/routes/storyboard_crud.py
backend/app/services/storyboard.py
backend/app/services/storyboard_crud.py
backend/app/services/storyboard_snapshot.py
backend/app/services/storyboard_mutations.py
backend/app/schemas/storyboard.py
backend/app/schemas/storyboard_crud.py
```

Important invariants:

- approvals are immutable snapshots,
- stale revision updates conflict,
- readiness is backend-derived,
- approved snapshots do not mutate when live planning graph changes,
- route-level approval does not render or queue work,
- identities/assets/voices remain planning records until separately acted on.

Relevant curated tests:

- `backend/tests/test_storyboard_routes.py`
- `backend/tests/test_storyboard_approval.py`
- `backend/tests/test_storyboard_snapshot.py`

## 15. Provider/planning engine development

Current provider modules:

```text
backend/app/services/planning/provider.py
backend/app/services/planning/openai_provider.py
backend/app/services/planning/provider_registry.py
backend/app/services/planning/provider_contract.py
backend/app/services/planning/routing.py
```

OpenAI adapter tests:

```text
backend/tests/services/planning/test_openai_provider.py
```

Provider contract tests:

```text
backend/tests/test_provider_contract.py
```

Development rules:

- Never persist API keys in database records.
- Never return secrets in API responses.
- Keep connection tests explicit and bounded.
- Use mocked transports in tests.
- Keep provider routing preflight non-mutating.
- Distinguish declared user capabilities from verified runtime capabilities.
- Keep OpenAI default and xAI/Grok secondary/switchable unless product direction changes.

### Adding xAI/Grok as a real secondary adapter

Recommended implementation path:

1. Add xAI settings to `backend/app/core/config.py`, using safe URL/model validators equivalent to OpenAI.
2. Add `backend/app/services/planning/xai_provider.py`.
3. Use the same strict request/response contract as OpenAI.
4. Add mocked unit tests; do not perform live xAI calls in the offline runner.
5. Update `provider_registry.py` so xAI is available only when configured.
6. Update `provider_contract.py` connection-test support only if a bounded, explicit, mocked-testable connection test exists.
7. Update frontend provider labels only after backend facts are available.
8. Keep OpenAI default; route xAI only when selected by provider profile/routing policy.

## 16. Local runtime development

Core local runtime files:

```text
backend/app/services/local_runtime.py
backend/app/services/local_runtime_m4.py
backend/app/services/local_runtime_evidence.py
backend/app/services/local_mvp_readiness.py
backend/app/services/local_public_readiness.py
backend/app/services/local_safe_boundary.py
backend/app/services/local_checkpoint_watchdog.py
```

Current runtime APIs are read-only and evidence-based. Do not add live probes to page-load paths or default validation.

## 17. Local jobs and generation manifests

Core files:

```text
backend/app/services/local_jobs.py
backend/app/services/local_generation.py
backend/app/api/routes/local_jobs.py
backend/app/api/routes/local_generation.py
```

Current local jobs and semantic requests are file-backed offline manifests. They do not submit prompts or queue work.

If adding a real live generation runner later, keep it separate from manifest creation and require explicit routing/gating/evidence capture.

## 18. Workflow template development

Core files:

```text
backend/app/services/workflows/template_service.py
backend/app/services/workflows/registry.py
backend/app/services/workflows/compiler.py
backend/app/services/workflows/admission.py
```

Canonical workflow files live under:

```text
storage/workflow_templates/
storage/workflow_registry/catalog.json
```

Rules:

- validate graph hash,
- validate node class/input bindings,
- sanitize output prefixes,
- write immutable snapshots,
- do not submit templates directly to ComfyUI from validation code,
- keep workflow admission separate from execution.

## 19. FFmpeg/post-production development

Core files:

```text
backend/app/services/ffmpeg/service.py
backend/app/services/post_production.py
backend/app/services/post_production_manifest.py
backend/app/services/local_post_production.py
```

Rules:

- no raw user-authored command strings,
- use allowlisted structured recipes,
- require safe paths and hashes,
- keep manifests separate from execution,
- never run FFmpeg/ffprobe from offline validation.

## 20. Frontend development

Frontend source:

```text
frontend/src/
```

Important files:

```text
frontend/src/api/client.ts
frontend/src/App.tsx
frontend/src/pages/Runtime.tsx
frontend/src/studio/
```

Frontend rules:

- API calls should go through `frontend/src/api/client.ts`.
- Do not add direct raw live-probe fetches in UI components.
- Do not add public generation buttons unless backend gates and product policy are changed.
- Keep Runtime page explicit about read-only/manifest-only status.
- Keep planning UI copy honest: planning approval does not render.

Run:

```powershell
cd frontend
npm run lint
npm run build
```

## 21. Adding new endpoints

For any new endpoint:

1. Add schema models in `backend/app/schemas/`.
2. Add service logic in `backend/app/services/`.
3. Add route in `backend/app/api/routes/`.
4. Mount route in the app router if needed.
5. Add route-contract tests.
6. Update `docs/API_CONTRACT.md` or local endpoint docs if public/local-safe.
7. If it is a `/local-*` endpoint, update `docs/SAFE_LOCAL_ENDPOINTS.md` and safe endpoint tests.
8. Run offline-safe validation.

If the endpoint can execute live tools or start work, do not add it to the safe local endpoint matrix.

## 22. Adding new tests to the curated runner

Before adding a test to `scripts/run_offline_safe_validation.py`, confirm it:

- is deterministic,
- uses temp directories or fixtures,
- does not require PostgreSQL unless explicitly intended,
- does not call ComfyUI,
- does not call live provider APIs,
- does not run FFmpeg/ffprobe,
- does not probe GPU/runtime health,
- does not enqueue live jobs,
- does not submit prompts,
- has warnings cleaned or documented.

After adding the test:

1. add a membership guard in `backend/tests/test_offline_safe_validation_runner.py`,
2. run the focused test,
3. run the full offline-safe runner,
4. update current validation-count docs if the pass count changes,
5. commit a checkpoint note.

## 23. Documentation rules

Docs are part of the safety surface. Keep them truthful.

When changing validation counts, update:

- `docs/OFFLINE_SAFE_VALIDATION.md`,
- `docs/LOCAL_SMOKE_TEST_PLAN.md`,
- `docs/UI_MVP_STATUS.md`,
- `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md`,
- `README.md`,
- stale-count guard in `backend/tests/test_offline_docs_boundary.py`.

Avoid stale claims such as old pass counts with warnings.

## 24. Release/readiness states

Current local/offline MVP control plane is near-complete for planning, readiness, and manifest review.

Actual local generation readiness still requires real controlled-run evidence before claiming full render success.

Public readiness remains fail-closed until public gates exist, including:

- auth/rate limiting,
- abuse controls,
- benchmark evidence,
- recovery evidence,
- provenance,
- deterministic post validation,
- human QA.

## 25. Common developer tasks

### Start servers

```powershell
.\.venv\Scripts\python -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### Run focused backend test

```powershell
.\.venv\Scripts\python -B -m pytest -q -p no:cacheprovider backend/tests/test_provider_contract.py
```

### Run full offline validation

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py --fail-on-dirty
```

### Check clean state

```powershell
git status --short --ignored artifacts/watchdog/latest.json
```

### Inspect recent checkpoints

```powershell
git log --oneline -12
```

## 26. Troubleshooting for developers

### Frontend cannot reach backend

Confirm `frontend/src/api/client.ts` default and Vite env values point at the backend port. Current local backend URL is commonly `http://127.0.0.1:8010`.

### CORS error

Check `cors_allowed_origins` in `backend/app/core/config.py`. The current defaults include local Vite origins on port 5173.

### Curated runner pass count changed

Update docs and `test_offline_docs_boundary.py` in the same checkpoint.

### Static validator fails on docs

Read the finding code. The docs may have become a safety surface regression, especially around live routes, raw prompt references, unsafe endpoint matrix claims, or assistant/debug text leaks.

### Tests emit warnings

Prefer fixing warnings before committing. Recent cleanup has converted UTC timestamp helpers to explicit UTC-naive DB convention where the DB model expects naive timestamps.

## 27. Do-not-break list

Do not accidentally:

- expose public/autonomous generation,
- add direct raw prompt proxy routes,
- add UI buttons that submit prompts or queue generation without gates,
- call live probes on page load,
- run FFmpeg/ffprobe in validation,
- store provider secrets,
- turn declared provider capabilities into verified facts,
- mark archetypes/presets ready without evidence gates,
- treat Storyboard approval as generation approval,
- put generated runtime outputs into git,
- bypass path/hash/provenance checks.

## 28. Handoff checklist

Before handing off a change:

1. `git status --short --ignored artifacts/watchdog/latest.json`
2. focused tests for touched code,
3. full offline-safe validation when appropriate,
4. `git diff --check`,
5. checkpoint note under `artifacts/`,
6. commit,
7. run checkpoint watchdog,
8. continue next safe task unless directly asked to stop.
