# Checkpoint — M3 Worker Terminal Wrappers

Generated: 2026-07-14 23:17 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `d884ba5 checkpoint: centralize terminal job handling`

## Scope completed

Added worker-facing terminal helpers for mocked timeout/interruption/cancel paths.

Changes:

- Added `QueueWorker.timeout_job_once(...)`.
- Added `QueueWorker.interrupt_job_once(...)`.
- Added `QueueWorker.cancel_job_once(...)`.
- Helpers only act on jobs owned by the worker; jobs owned by another worker return `None` and leave state/lease untouched.
- Helpers route through `QueueService.mark_terminal_job(...)`, so completion metadata, workflow-run terminal status, and bound GPU lease release are centralized.
- Added tests for timeout, interrupt, cancel, and wrong-worker no-op behavior.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_queue_worker.py \
  backend/tests/test_queue_service.py
# 62 passed, warnings only

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 459 passed, 9 skipped, warnings only, ~79.14s
```

## Safety notes

- No public generation route was added.
- No live ComfyUI/GPU/render/benchmark action was run.
- These are backend lifecycle wrappers only; process-tree recovery and live Comfy client integration remain pending.

## Next dependency-ready work

1. Add worker-only live Comfy history/view wrappers behind the controlled boundary.
2. Add process-tree recovery and post-restart health-check mocks before any M4 hardware ladder.
3. Add a single end-to-end mocked worker lifecycle test from submitted progress through output collection completion.
