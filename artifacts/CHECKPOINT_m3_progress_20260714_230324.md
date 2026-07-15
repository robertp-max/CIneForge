# Checkpoint — M3 Progress/Event Mapping and Lease Release

Generated: 2026-07-14 23:03 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `76d63b2 checkpoint: local ComfyUI runtime gates`

## Scope completed

Continued M3 controlled-runtime mocks without touching ComfyUI or running GPU work.

Changes:

- Added GPU lease binding/release helpers to `QueueService`:
  - `bind_gpu_lease(...)`
  - `release_bound_gpu_lease(...)`
- Controlled Comfy submission now binds the validated lease to `ComfyJob.recovery_metadata` before readiness/submission.
- Controlled submission now releases bound leases on readiness failure and prompt submission rejection/node-error/missing-prompt terminal paths.
- Added `ComfyJobProgressRecorder` in `progress_monitor.py`:
  - persists parsed progress events to `ComfyJob.websocket_events`;
  - maps `execution_start` to `submitted -> running`;
  - maps completion signal to `running -> collecting_outputs`;
  - maps runtime errors to terminal `oom` or `runtime_failed`;
  - releases the bound GPU lease on terminal runtime failure.
- Added tests for progress event persistence/state mapping and OOM lease release.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_progress_monitor.py \
  backend/tests/test_controlled_submission.py \
  backend/tests/test_queue_service.py
# 66 passed, warnings only

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 451 passed, 9 skipped, warnings only, ~76.97s
```

## Safety notes

- No public `/prompt` route was added.
- No ComfyUI/GPU render, benchmark, or runtime mutation was run.
- Completion moves to `collecting_outputs`; the lease intentionally remains active until output collection is implemented.
- Terminal runtime failures release the bound lease.

## Next dependency-ready work

1. Implement mocked history/output collection from `collecting_outputs` to `complete` / `postprocess_failed`.
2. Persist collected outputs to `FileOutput`/`GeneratedAsset` or local equivalent with hashes/probe metadata.
3. Add timeout/cancel/interrupted terminal mapping and lease release tests.
