# Local Smoke Test Plan

Date: 2026-07-16

This document is historical and has been re-scoped to the current local-only safety boundary. The default smoke path is offline-safe validation. Live health probes, ComfyUI checks, GPU telemetry checks, FFmpeg/ffprobe checks, rendering, and benchmarking require explicit operator approval as described in `docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md`.

## Default offline-safe smoke path

Run:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py
```

This runs static safe-boundary validation, curated backend tests, frontend lint/build, and `git diff --check` without contacting ComfyUI, probing GPU/runtime health, running FFmpeg/ffprobe, submitting prompts, creating live jobs, rendering media, or benchmarking.

Current checkpoint result: `138 passed, 71 warnings`, frontend lint/build passed, and static boundary validation passed.

## Live probes are not part of the default smoke path

The following actions are live probes or live-tool checks and must not be run from the default smoke path:

- `GET /health/comfy`
- `GET /health/gpu`
- `GET /health/ffmpeg`
- `GET /runtime/status`
- ComfyUI `object_info` validation against a live runtime
- direct or controlled ComfyUI prompt submission
- FFmpeg/ffprobe availability or media validation against local binaries
- GPU telemetry sampling
- benchmark ladder stages

If a future operator explicitly approves one of these checks, approval must name the action family, target, scope, local-only constraint, and live-tool acknowledgement.

## Still forbidden without explicit approval

- Real video/image generation.
- Model or node downloads.
- ComfyUI installation/update/mutation.
- Autonomous execution.
- Parallel GPU generation.
- Raw public `/prompt` proxy exposure.
- Raw FFmpeg command-string execution.
