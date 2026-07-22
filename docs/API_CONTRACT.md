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

- Use `scripts/run_offline_safe_validation.py` for the default no-live validation path; it prints the checkpoint watchdog restart banner.
- `GET /local-runtime/checkpoint-watchdog` exposes the read-only checkpoint continuation reminder, staged filenames, and source-scoped untracked-file visibility; it does not approve or start work.
- `/local-runtime/*`, `/local-generation/*`, `/local-operator/*`, and `/local-post-production/*` are passive or manifest-only surfaces documented in `docs/SAFE_LOCAL_ENDPOINTS.md`. `GET /local-runtime/live-status` reports configuration and owned-process state without a network probe.
- No public raw `/prompt` route submits work to ComfyUI.
- Local operator packet/runbook/template routes do not record approval or start live work.
- The offline validation suite never executes ComfyUI, GPU, FFmpeg, ffprobe, provider, rendering, or benchmark work.

Explicit local-operator actions are separated from the safe `/local-*` namespace:

- `POST /operator-runtime/probe` performs an acknowledged localhost reachability and `/object_info` probe.
- `POST /operator-runtime/start`, `/restart`, and `/stop` manage only the configured pinned runtime and only while the hardware-operator gate is enabled. Stop/restart refuse processes CineForge does not own.
- `POST /operator-generation/semantic-requests/{request_id}/queue` compiles a persisted semantic request into a durable backend job. Queue-worker and hardware-operator gates remain independent and default off.
- `POST /operator-post-production/plans/{plan_id}/execute` and `POST /operator-post-production/recipe-commands/{plan_id}/execute` execute only persisted, allowlisted commands while the FFmpeg-operator gate is enabled. Raw commands are never accepted.

These operator endpoints are local-only control surfaces, not public generation APIs. Their presence is not a readiness claim: graph/model admission, hardware evidence, recovery evidence, provenance, and human QA remain mandatory where applicable.

