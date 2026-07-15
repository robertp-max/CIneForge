# Checkpoint — Production Gate Hardening and Review Follow-through

Generated: 2026-07-15 01:06 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `bd002b4 checkpoint: fix M3 review blockers`

## Scope completed

Continued after the M3 reviewer findings and hardened the remaining readiness contract note.

Changes:

- `ProductionGateService` now requires production archetypes to have:
  - `implemented=true`
  - `dependency_verified=true`
  - `locally_tested=true`
  - `benchmark_passed=true`
  - `human_approved=true`
  - `readiness == "ready"`
  - no `blocked_reasons`
- The same readiness helper is used by plan and semantic generation request gates.
- Added `backend/tests/test_production_gates.py` for:
  - benchmark/human/readiness blocks even when local test/dependency flags are true;
  - allow only ready preset + ready archetype for a simple T2V production request;
  - block disabled ready presets.

Also included current review-fix changes in validation scope:

- preflight/gate-disabled GPU lease release;
- stale timeout terminal metadata + lease release;
- queue-worker vs hardware-operator submission mode separation;
- static workflow admission scan for scripts/downloads/URLs/unmanaged paths.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_production_gates.py \
  backend/tests/test_controlled_submission.py \
  backend/tests/test_queue_service.py \
  backend/tests/test_workflow_admission.py
# 72 passed, warnings only

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 473 passed, 9 skipped, warnings only, ~84.90s
```

## Safety notes

- No public generation route was added.
- No live ComfyUI/GPU/render/benchmark action was run.
- M4 hardware ladder remains blocked until explicit operator approval and final gate review.
