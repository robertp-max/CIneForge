# Checkpoint — M3 Runtime Recovery Mock

Generated: 2026-07-14 23:26 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `6500a3e checkpoint: cover mocked M3 worker lifecycle`

## Scope completed

Added mockable ComfyUI runtime recovery orchestration without performing any real process or GPU operations.

Changes:

- Added `backend/app/services/comfy/recovery.py`.
- Introduced `ComfyRuntimeSupervisor` protocol with injected methods:
  - `terminate_process_tree(reason)`
  - `restart_pinned_runtime()`
  - `health_check()`
- Added `ComfyRuntimeRecoveryService.recover_failed_runtime(...)`.
- Recovery service:
  - marks the job terminal via `QueueService.mark_terminal_job(...)`;
  - releases bound GPU lease;
  - calls injected supervisor terminate/restart/health hooks;
  - returns `RuntimeRecoveryResult` without overclaiming if health fails.
- Added tests with a fake supervisor for successful recovery, failed health, and unsupported status rejection.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests/test_comfy_recovery.py
# 3 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 466 passed, 9 skipped, warnings only, ~77.95s
```

## Safety notes

- No real ComfyUI process was killed or restarted.
- No live ComfyUI/GPU/render/benchmark action was run.
- Recovery is protocol/injection based and remains default-inert until a hardware operator supplies a concrete supervisor.

## Next dependency-ready work

1. Add worker-controlled interrupt/queue cleanup/free wrappers only behind explicit operator/worker gates.
2. Add readiness/API reporting for M3 mocked lifecycle without enabling generation.
3. Before any M4 hardware ladder, review all M3 gates and run independent QA.
