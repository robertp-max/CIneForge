# Checkpoint — Implementation Plan Review + Proceed Pass

Generated: 2026-07-14 22:49 local
Working directory: `C:/AI/Git/CIneForge`
Plan reviewed: `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md`

## What changed in this pass

Addressed the highest-priority blockers from the plan review while preserving the no-public-generation boundary.

### M1/M2 local contract hardening

- Local job creation now rejects invalid LTX video contracts before writing manifests, audit JSONL, output folders, or workflow snapshots:
  - dimensions must be >=64 and divisible by 32;
  - frame count must satisfy the LTX `8n+1` rule;
  - schema bounds now cap width/height/frames/fps/steps to manifest-safe ranges.
- Added route/store tests proving invalid local jobs return 422 / raise `ValidationError` and leave no manifest/audit state behind.

### M2 workflow registry/compiler baseline

- Added `storage/workflow_registry/catalog.json` with all canonical archetype IDs required by `WorkflowRegistryService`:
  - `CF-IMG-01` through `CF-IMG-05`
  - `CF-VID-01` through `CF-VID-05`
  - `CF-UTIL-01`
  - `CF-POST-01`
- `CF-VID-01` points to the current smoke API/UI template and records semantic bindings, required classes, dependencies, supported mode/profile, and blocked benchmark/recovery/QA reasons.
- All other archetypes are explicitly blocked/planned, not ready.
- Added registry/compiler tests for canonical coverage, missing catalog fail-closed behavior, non-production CF-VID-01 compilation, invalid LTX geometry/frame rejection, and production smoke/blocked rejection.
- Added admission negative tests for duplicate semantic titles, missing `/object_info` classes, public enablement, API hash mismatch readiness demotion, and binding class drift.

### M3 controlled submission boundary hardening

- `ControlledComfySubmissionService` now requires:
  - either `hardware_operator_enabled` or `queue_worker_enabled`; and
  - an active GPU lease bound to the worker and job/workflow before any `/prompt` adapter call.
- `WorkerSubmissionContext` carries `gpu_lease_id`.
- `QueueWorker.controlled_submission_once()` forwards the lease id.
- Added tests proving:
  - default-off gates fail closed without prompt calls;
  - missing/released leases fail closed without prompt calls;
  - queue-worker gate can work independently of hardware-operator gate when a lease exists;
  - untracked direct construction of the Comfy `/prompt` adapter remains blocked;
  - public `POST /prompt` remains 404.

### Git hygiene

- `.gitignore` now ignores generated local runtime state under:
  - `storage/local_jobs/`
  - `storage/projects/`
  - `storage/runtime/*`
- Curated fixture `storage/runtime/cf_vid_01_smoke_evidence.json` remains unignored for tests/API evidence.

## Validation run

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 448 passed, 9 skipped, warnings only, ~73.82s

cd frontend && npm run build
# TypeScript + Vite production build succeeded
```

Earlier focused run:

```bash
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_local_runtime.py \
  backend/tests/test_local_presets.py \
  backend/tests/test_local_archetypes.py \
  backend/tests/test_local_jobs.py \
  backend/tests/test_local_runtime_evidence.py \
  backend/tests/test_path_safety.py \
  backend/tests/test_workflow_manifest_validation.py \
  backend/tests/test_cf_vid01_api_workflow_template.py \
  backend/tests/test_ui_workflow_template_service.py \
  backend/tests/test_workflow_registry_and_compiler.py \
  backend/tests/test_health.py \
  backend/tests/test_phase1_app_routing.py \
  backend/tests/test_controlled_submission.py \
  backend/tests/test_queue_worker.py \
  backend/tests/test_queue_service.py \
  backend/tests/test_queue_state_machine.py
# 140 passed, warnings only
```

## Still not done / do not overclaim

- No new ComfyUI/GPU render, benchmark, recovery exercise, or runtime mutation was run in this pass.
- `CF-VID-01` remains a smoke candidate, not production-ready.
- Presets remain disabled/gated.
- Public/autonomous generation remains disabled.
- M3 is only partially hardened: WebSocket/history/output collection, process-tree recovery, timeout/OOM mapping, and managed artifact persistence still need implementation before any M4 hardware ladder.
- The evidence API still returns absolute local paths from `storage/runtime/cf_vid_01_smoke_evidence.json`; acceptable for local operator use, but should be redacted/aliased before any broader exposure.

## Next dependency-ready work

1. Continue M3 mocks: history/progress/output collection and terminal-state mapping with lease release on every path.
2. Add managed output persistence into `GeneratedAsset`/`FileOutput` records or local file-backed equivalent before enabling hardware operator probes.
3. Add process-tree recovery, timeout/OOM classification, and next-job health checks before any M4 hardware ladder.
