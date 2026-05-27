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

- Dashboard: system cards, backend root status, recent backend-backed activity, Phase 2 safety milestone.
- Projects: create projects, list projects, read project by ID.
- Campaigns: create campaigns for existing projects, list campaigns, read campaign by ID.
- Jobs: list persisted jobs and read job status by ID without creating jobs.
- Queue: read-only queue capability surface and supported queue states.
- Runtime: ComfyUI reachability, `object_info` availability, and disabled runtime actions.
- System Health: readable cards and optional raw debug panels for health endpoints.
- Roadmap / Disabled Features: phase status and intentional capability gates.

## Integrated Backend Endpoints

- `GET /health`
- `GET /`
- `GET /favicon.ico`
- `GET /health/comfy`
- `GET /health/gpu`
- `GET /health/ffmpeg`
- `GET /runtime/status`
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

These are intentionally gated, not missing because the UI is broken. The visible MVP exposes current live backend capability and makes unavailable generation behavior explicit.

## Next Recommended Step

Phase 2 backend capability is now present as a worker/runtime-only controlled submission service behind readiness checks. The next recommended step is to add worker telemetry and operator-facing readiness visibility without exposing a public Generate button.
