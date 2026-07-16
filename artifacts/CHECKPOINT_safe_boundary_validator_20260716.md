# Checkpoint: static safe/local boundary validator

Date: 2026-07-16

## Implemented

- Added `scripts/validate_safe_local_boundary.py`.
- Added `backend/tests/test_safe_local_boundary_script.py`.
- Linked the validator from `README.md`.

## Checks covered

The validator is static/file-only and checks:

- no enabled/ready local archetypes,
- no enabled/ready local presets,
- no frontend live-probe callsites outside API client definitions,
- no exact public raw `/prompt` backend route,
- no `/local-generation` or `/local-operator` execute/submit/approve/prompt child route,
- no `/local-operator/run` route while allowing `/local-operator/runbooks` reference metadata.

## Validation

- `./.venv/Scripts/python.exe -B scripts/validate_safe_local_boundary.py`
  - Result: passed
- `./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests/test_safe_local_boundary_script.py backend/tests/test_local_operator.py backend/tests/test_phase1_app_routing.py`
  - Result: `17 passed`

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
