# API Contract

Implemented endpoints:

- `GET /health` returns app liveness, runtime isolation mode, queue-worker flag, and autonomy mode.
- `GET /health/comfy` checks configured `CINEFORGE_COMFYUI_BASE_URL` and returns `unavailable` instead of failing if ComfyUI is offline.
- `GET /health/gpu` checks `nvidia-smi` availability and parses one telemetry sample when available.
- `GET /health/ffmpeg` reports `ffmpeg` and `ffprobe` availability.
- `POST /projects` validates `name` and optional `description`, returning a stub project record.
- `GET /projects/{project_id}` returns an existing stub project or `404`.
- `POST /campaigns` validates `project_id`, `name`, and optional positive duration, returning a stub campaign record.
- `GET /campaigns/{campaign_id}` returns an existing stub campaign or `404`.
- `GET /jobs/{job_id}` returns an existing stub job or `404`.

Example `POST /projects`:

```json
{ "name": "Demo Project", "description": "Smoke test" }
```

Known stubs:

- Project/campaign/job persistence is not DB-backed in Sprint 1A.
- No route submits work to ComfyUI.
- No route executes FFmpeg assembly.
- No route executes autonomy.

