# Dry-run readiness checklist (planning-only)

**Repo:** `C:\AI\Git\CIneForge`  
**Branch tip (prep work):** `feature/cineforge-gold-edition-ui`  
**Mode:** production-phase UI + history review — **no image/video generation, no Comfy submit, no model download**

## Stack

| Process | Command | URL |
|---------|---------|-----|
| Backend | `.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010` | `http://127.0.0.1:8010` |
| Frontend | `cd frontend; npm run dev -- --host 127.0.0.1 --port 5174` | `http://127.0.0.1:5174` |

Frontend API default: `http://127.0.0.1:8010` (`VITE_API_BASE_URL` / code default).

## Pre-flight (must be true)

- [ ] `GET /health` → `status=ok`, `queue_worker_enabled=false`
- [ ] Root `/` → `generation_enabled=false`
- [ ] CORS allows `http://127.0.0.1:5174` (and localhost)
- [ ] DB alembic head includes phase history (`b7c8d9e0f1a2`)
- [ ] Project settings: `allow_rendering=false`, `allow_model_download=false`
- [ ] Frontend lint / unit tests / build green
- [ ] Studio never opens with slug `a-new-journey` — only real project UUIDs
- [ ] Media: managed asset content preferred; static `/transfiguration/*` **only** for Transfiguration canon

## In-scope dry-run actions

1. Open Projects → verify Transfiguration **cover thumb** (managed or canon static).
2. Open Transfiguration studio (real UUID) → Overview / Story / Phases 1–7.
3. Phase history: list versions, open retained snapshot, confirm **immutable** banner / no overwrite.
4. Starting images: assigned shots load **managed** `/assets/{id}/content` (or Transfiguration static only when unassigned + canon).
5. Characters: portraits from managed refs or Transfiguration character pack only for that project.
6. Create-project wizard UI walk-through **optional** — avoid Phase 1 generate POST unless intentional history write.

## Out of scope (do not run)

- `POST .../phases/1/generate` unless explicitly authorized as a history write
- Enabling `CINEFORGE_QUEUE_WORKER_ENABLED`
- Settings PUT `allow_rendering=true` / model download
- ComfyUI prompt submit, FFmpeg assembly, video generation
- Force-push, DB wipe, storage purge

## Known soft warnings

- `GET /production/stories/{id}` may **seed empty phase baselines** (append-only; idempotent when versions exist).
- Docs historically said port **8000**; code + this checklist use **8010**.
- Pipeline GET is not pure-read on first open of a project with zero versions.

## Smoke commands (read-only)

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-RestMethod http://127.0.0.1:8010/projects
# story / production / assets — GET only
```

## Quality gates (prep)

```powershell
cd frontend
npm run lint
npx tsc --noEmit -p tsconfig.app.json
npx vitest run
npm run build

# backend focused
.\.venv\Scripts\python -m pytest backend/tests/test_health.py backend/tests/test_production_phase_history.py backend/tests/test_production_phase_immutability.py backend/tests/test_production_phase_one.py backend/tests/test_reference_assets.py -q
```
