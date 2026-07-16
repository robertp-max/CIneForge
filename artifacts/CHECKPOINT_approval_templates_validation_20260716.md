# Checkpoint: approval templates validation

Date: 2026-07-16

## Scope

- Added and documented machine-readable approval templates for local operator modes.
- Linked approval-template routes from README, implementation plan, and live-boundary docs.

## Validation

Backend offline-safe suite:

```text
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_local_archetypes.py \
  backend/tests/test_local_presets.py \
  backend/tests/test_local_jobs.py \
  backend/tests/test_local_generation.py \
  backend/tests/test_local_readiness.py \
  backend/tests/test_local_mvp_readiness.py \
  backend/tests/test_local_public_readiness.py \
  backend/tests/test_local_operator.py \
  backend/tests/test_local_runtime.py \
  backend/tests/test_local_runtime_m4.py \
  backend/tests/test_local_runtime_evidence.py \
  backend/tests/test_benchmark_ladder.py \
  backend/tests/test_ffmpeg_service.py \
  backend/tests/test_post_production.py \
  backend/tests/test_local_post_production.py \
  backend/tests/test_phase1_app_routing.py \
  backend/tests/test_production_gates.py \
  backend/tests/test_workflow_admission.py \
  backend/tests/test_workflow_registry_and_compiler.py
```

Result: `127 passed, 71 warnings`.

Frontend:

```text
cd frontend && npm run lint && npm run build
```

Result: passed.

Safety sweeps:

- No frontend live-probe callsites outside API client definitions.
- No exact public raw `/prompt` FastAPI route.
- No `/local-generation` or `/local-operator` execute/submit/approve/prompt child routes, and no `/local-operator/run` route. `/local-operator/runbooks` is reference metadata only.
- No enabled/ready local archetypes.
- No enabled/ready local presets.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
