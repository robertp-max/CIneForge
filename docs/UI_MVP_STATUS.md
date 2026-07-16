# CineForge UI MVP Status

## Run Backend

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The backend allows local Vite origins by default:

- `http://127.0.0.1:5173`
- `http://localhost:5173`

## Run Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend API base URL defaults to `http://127.0.0.1:8000`. Override it with:

```powershell
$env:VITE_CINEFORGE_API_BASE_URL="http://127.0.0.1:8000"
```

## UI Pages

Storyboard Phase A now provides Overview, Storyboard, Story & Chapters, Characters, Voices, Starting Images, Model Routing, Workflows, Exports, and Project Settings. These are planning surfaces: generation controls remain explicitly unavailable.

- Dashboard: system cards, backend root status, recent backend-backed activity, Phase 2 safety milestone.
- Projects: create projects, list projects, read project by ID.
- Campaigns: create campaigns for existing projects, list campaigns, read campaign by ID.
- Jobs: list persisted jobs, prepare offline local/semantic manifests with no-execution acknowledgements, and read job status by ID without live submission.
- Queue: read-only queue metadata surface; runtime worker status is not auto-probed.
- Runtime: file-backed local readiness, checkpoint watchdog with full no-live/non-stopping invariant list, safe-boundary, public-readiness, operator packet/runbook/template, M4 ladder/preflight, evidence, and FFmpeg recipe metadata without live probes.
- System Health: backend health card only; ComfyUI/GPU/FFmpeg live probes are not auto-called by the UI.
- Roadmap / Disabled Features: phase status and intentional capability gates.

## Integrated Backend Endpoints

- `GET /health`
- `GET /`
- `GET /favicon.ico`
- `GET /local-runtime/catalog`
- `GET /local-runtime/local-mvp-readiness`
- `GET /local-runtime/public-readiness`
- `GET /local-runtime/safe-boundary`
- `GET /local-runtime/checkpoint-watchdog`
- `GET /local-archetypes/readiness`
- `GET /local-presets/readiness`
- `GET /local-operator/approval-templates`
- `GET /local-operator/runbooks`
- `GET /local-operator/packets`
- `POST /local-operator/packets` (manifest-only; no approval/execution)
- `GET/POST /local-generation/semantic-requests` (offline manifests only)
- `POST /local-generation/storyboard-handoffs` (offline manifests only)
- `GET /local-post-production/plans`
- `GET /local-post-production/recipe-commands`
- `GET /projects`
- `POST /projects`
- `GET /projects/{project_id}`
- `GET /campaigns`
- `POST /campaigns`
- `GET /campaigns/{campaign_id}`
- `GET /jobs`
- `GET /jobs/{job_id}`

## Intentionally Disabled

- Public/user-facing ComfyUI `/prompt` submission.
- Public Generate button.
- WebSocket progress monitoring.
- Prompt history and output collection.
- FFmpeg assembly execution.
- Model downloads or model registry mutation.
- Queue mutation endpoints.
- Autonomous production execution.
- Automatic live calls to `/runtime/status`, `/health/comfy`, `/health/gpu`, or `/health/ffmpeg` from the UI.

These are intentionally gated, not missing because the UI is broken. The visible MVP exposes offline/read-only local readiness and manifest preparation surfaces while keeping live probes and generation disabled.

## Validation

Use:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py
```

The current checkpoint reports `153 passed, 71 warnings`, frontend lint/build passed, static safe-boundary validation passed, and the checkpoint watchdog banner printed. The suite does not run live runtime/media actions.
