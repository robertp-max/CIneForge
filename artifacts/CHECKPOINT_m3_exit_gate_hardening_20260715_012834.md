# Checkpoint — M3 Exit Gate Hardening After Reviewer Pass

Generated: 2026-07-15 01:28 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `97722ba checkpoint: harden production readiness gates`
Reviewer artifact: `.pi-subagents/artifacts/outputs/07a3150e-ed79-4c38-a3d2-f86c259137a3/.pi-subagents/artifacts/review/latest-m3-review.md`

## Reviewer blockers addressed

### Permit bypass hardening

- Removed public prompt-submission permit issuer from `WorkerPromptSubmissionPermit`.
- Added a module-private prompt permit issuer used only after `ControlledComfySubmissionService` has passed gate, worker ownership, static/readiness, and GPU lease checks.
- `ComfyWorkerPromptSubmissionAdapter` now rejects missing or forged permits before any HTTP call.
- Prompt permits bind to the expected `client_id` and patched-workflow SHA256, preventing reuse against a different prompt payload.
- Applied the same no-public-issuer / forged-permit rejection pattern to worker runtime-control permits for `/interrupt`, `/queue`, `/free`, and progress connector access.

### Worker lease acquisition/heartbeat

- `QueueWorker.controlled_submission_once(...)` now acquires and binds a GPU lease when one is not supplied.
- Added explicit `QueueWorker.acquire_gpu_lease_once(...)` and `heartbeat_gpu_lease_once(...)` helpers.
- Existing caller-provided leases are heartbeated before controlled submission.
- Added queue-worker tests proving owned reserved jobs acquire/heartbeat leases, unowned jobs do not, and the auto-acquired lease is bound before prompt submission.
- Fixed SQLite naive/aware datetime comparison in GPU lease heartbeat handling.

### Static admission enforcement at submission boundary

- `WorkflowAdmissionService` exposes static workflow scan for in-memory patched workflows.
- `QueueService.evaluate_submission_readiness(...)` now enforces the static workflow security scan before prompt submission.
- Controlled submission tests prove a forbidden `PythonScript` node blocks before adapter call and releases the lease.

### Worker-only runtime controls

- `ComfyWorkerRuntimeClient` gained permit-gated worker-only `/interrupt`, `/queue`, `/free`, and mocked progress connector methods.
- `QueueWorker` gained wrapper methods that issue runtime-control permits only for owned active jobs.
- Tests prove missing/forged runtime-control permits do not hit HTTP and worker wrappers ignore unowned/not-submitted jobs.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_controlled_submission.py \
  backend/tests/test_comfy_client.py \
  backend/tests/test_comfy_recovery.py \
  backend/tests/test_m3_mocked_worker_lifecycle.py \
  backend/tests/test_output_collector.py \
  backend/tests/test_workflow_admission.py \
  backend/tests/test_workflow_registry_and_compiler.py \
  backend/tests/test_queue_worker.py \
  backend/tests/test_queue_service.py \
  backend/tests/test_health.py
# 126 passed, warnings only

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 486 passed, 9 skipped, warnings only, ~85.43s
```

## Safety notes

- No public `/prompt` or raw Comfy proxy route was added.
- No live ComfyUI/GPU/render/benchmark action was run.
- Runtime-control routes remain worker-only and permit-gated.
- M4 hardware ladder remains blocked until explicit operator approval.
