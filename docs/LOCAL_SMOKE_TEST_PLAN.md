# Local Smoke Test Plan

Without ComfyUI:

1. Install dependencies in a virtual environment.
2. Run `pytest`.
3. Start the API with Uvicorn.
4. Check `GET /health`, `GET /health/comfy`, `GET /health/gpu`, and `GET /health/ffmpeg`.
5. Confirm `/health/comfy` returns `unavailable` when ComfyUI is offline.

With ComfyUI online later:

1. Start the isolated ComfyUI runtime outside CineForge.
2. Set `CINEFORGE_COMFYUI_BASE_URL`.
3. Recheck `GET /health/comfy`.
4. Use object-info validation against a known workflow template.

FFmpeg:

1. Confirm `/health/ffmpeg`.
2. Run unit tests for stream-copy compatibility with fixture probe JSON.
3. Do not run heavy assembly in Sprint 1A.

GPU telemetry:

1. Confirm `/health/gpu`.
2. If `nvidia-smi` is unavailable, the endpoint should fail gracefully.
3. Parser tests cover full CSV and WDDM `N/A` fields.

Do not test yet:

- Real video generation.
- Model downloads.
- ComfyUI installation or mutation.
- Autonomous execution.
- Parallel GPU generation.

