# Checkpoint — M3 Worker Comfy Runtime Client

Generated: 2026-07-14 23:20 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `47ec03c checkpoint: add worker terminal controls`

## Scope completed

Added worker-only Comfy history/view client wrappers for the controlled runtime path.

Changes:

- Added `ComfyWorkerRuntimeClient` in `backend/app/services/comfy/client.py`.
- It is constructible only with `tracked_worker_runtime=True`; untracked construction raises `ComfyRuntimeRouteBlocked`.
- Supports worker-only:
  - `GET /history/{prompt_id}`
  - `GET /history`
  - `GET /view` for managed output bytes
- Keeps existing public/general `ComfyUIClient` history/view/WebSocket methods blocked.
- Validates prompt id / view filename / output type before HTTP calls.
- Sanitizes project subfolder names with existing CineForge path safety.
- Added mock-transport tests proving safe request shape and unsafe path rejection without network calls.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests/test_comfy_client.py
# 6 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 462 passed, 9 skipped, warnings only, ~78.76s
```

## Safety notes

- No public history/view proxy route was added.
- No live ComfyUI/GPU/render/benchmark action was run.
- Worker runtime client is a lower-level wrapper only; it still needs integration into a complete worker lifecycle.

## Next dependency-ready work

1. Add an end-to-end mocked worker lifecycle test using submitted progress -> output collection complete.
2. Add process-tree recovery and post-restart health-check mocks before any M4 hardware ladder.
3. Add worker-controlled interrupt/queue cleanup/free wrappers only behind explicit operator/worker gates.
