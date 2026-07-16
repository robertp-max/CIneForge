# API Contract

Implemented endpoints:

- `GET /health` returns app liveness, runtime isolation mode, queue-worker flag, and autonomy mode.
- `GET /health/comfy` is a live ComfyUI reachability probe. It is not part of the default offline-safe validation path and requires explicit operator approval before use.
- `GET /health/gpu` is a live GPU telemetry probe. It is not part of the default offline-safe validation path and requires explicit operator approval before use.
- `GET /health/ffmpeg` is a live FFmpeg/ffprobe availability probe. It is not part of the default offline-safe validation path and requires explicit operator approval before use.
- `POST /projects` validates `name` and optional `description`, returning a stub project record.
- `GET /projects/{project_id}` returns an existing stub project or `404`.
- `POST /campaigns` validates `project_id`, `name`, and optional positive duration, returning a stub campaign record.
- `GET /campaigns/{campaign_id}` returns an existing stub campaign or `404`.
- `GET /jobs/{job_id}` returns an existing stub job or `404`.

Example `POST /projects`:

```json
{ "name": "Demo Project", "description": "Smoke test" }
```

Known local/offline boundary:

- Use `scripts/run_offline_safe_validation.py` for the default no-live validation path.
- `GET /local-runtime/*`, `/local-generation/*`, `/local-operator/*`, and `/local-post-production/*` include read-only or manifest-only local surfaces documented in `docs/SAFE_LOCAL_ENDPOINTS.md`.
- No public raw `/prompt` route submits work to ComfyUI.
- Local operator packet/runbook/template routes do not record approval or start live work.
- No offline/local route executes FFmpeg assembly or autonomy.

