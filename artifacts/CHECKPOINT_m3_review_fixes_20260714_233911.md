# Checkpoint — M3 Review Fixes: Lease Leaks, Gate Separation, Admission Scan

Generated: 2026-07-14 23:39 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `b00968c checkpoint: add mocked Comfy runtime recovery`
Review source: `.pi-subagents/artifacts/outputs/62f31b2a-f432-40fb-a786-e6f33f49528a/review/`

## Reviewer findings addressed

### Runtime blocker: preflight gate-disabled lease leak

Fixed `ControlledComfySubmissionService` so that if a valid worker/job-bound GPU lease is supplied but the submission gate is disabled, the lease is released before returning the terminal preflight result.

Tests now assert the lease is released for:

- queue-worker gate disabled;
- readiness failure after lease binding.

### Runtime blocker: stale reserved timeout bypassed terminal finalization/lease release

Updated `QueueService.recover_stale_reserved_jobs(...)` so stale reserved jobs that reach max attempts and become `timeout` now set:

- `ComfyJob.completed_at`;
- `ComfyJob.error_message`;
- `WorkflowRun.status`;
- `WorkflowRun.ended_at`;
- bound GPU lease release.

Recovered reserved jobs reset to pending also attempt to release any previous worker lease before detaching worker ownership.

### Contract blocker: hardware operator and queue worker gates were not mode-separated

Added `WorkerSubmissionContext.submission_mode`:

- `queue_worker` requires `queue_worker_enabled`;
- `hardware_operator` requires `hardware_operator_enabled`.

Hardware operator enablement alone no longer permits the default durable queue-worker submission mode. Tests prove:

- queue worker mode can submit with queue gate on and hardware gate off;
- hardware gate on + queue gate off rejects default queue-worker mode;
- hardware operator mode can submit with hardware gate on and queue gate off.

### M2 blocker: missing static workflow security scan

Extended `WorkflowAdmissionService` with static API-graph scanning for:

- script/shell/command/python/subprocess class/input indicators;
- download/install/url/http class indicators;
- workflow-provided URLs;
- unmanaged path/traversal/absolute/drive/backslash path inputs;
- unsafe SaveVideo `filename_prefix` values.

Added tests for forbidden script/download/url/path cases and for allowed managed save prefix + sampler names.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_controlled_submission.py \
  backend/tests/test_queue_service.py \
  backend/tests/test_workflow_admission.py \
  backend/tests/test_m3_mocked_worker_lifecycle.py
# 70 passed, warnings only

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 470 passed, 9 skipped, warnings only, ~84.39s
```

## Safety notes

- No public generation route was added.
- No live ComfyUI/GPU/render/benchmark action was run.
- M4 hardware ladder remains blocked pending final gate review/QA and explicit operator approval.
