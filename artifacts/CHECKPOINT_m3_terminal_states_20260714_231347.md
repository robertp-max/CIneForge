# Checkpoint — M3 Terminal State and Lease Release Helpers

Generated: 2026-07-14 23:13 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `78200d4 checkpoint: persist managed Comfy outputs`

## Scope completed

Continued M3 mocked runtime lifecycle work without touching ComfyUI or running GPU work.

Changes:

- Added `QueueService.mark_terminal_job(...)` for terminal queue outcomes:
  - validates terminal target state;
  - sets `ComfyJob.completed_at`;
  - sets `ComfyJob.error_message` when supplied;
  - updates `WorkflowRun.status` and `WorkflowRun.ended_at`;
  - releases bound GPU lease by default.
- Refactored runtime failure progress handling to use `mark_terminal_job(...)`.
- Refactored output collection success/failure to use `mark_terminal_job(...)`.
- Added queue service tests proving terminal timeout metadata and lease release, plus rejection of non-terminal targets without releasing the lease.
- Tightened OOM progress test to assert `completed_at` and `error_message`.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_queue_service.py \
  backend/tests/test_progress_monitor.py \
  backend/tests/test_output_collector.py
# 60 passed, warnings only

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 456 passed, 9 skipped, warnings only, ~80.63s
```

## Safety notes

- No public generation route was added.
- No live ComfyUI/GPU/render/benchmark action was run.
- Terminal lifecycle and lease release are still mock/backend state handling; live process-tree recovery remains pending.

## Next dependency-ready work

1. Add worker-only timeout/interruption/cancel path wrappers that call `mark_terminal_job(...)`.
2. Add live Comfy history/view wrappers behind controlled worker boundary.
3. Add process-tree recovery/health-check mocks before any M4 hardware ladder.
