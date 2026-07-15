# Checkpoint — Read-only M4 Benchmark Ladder Manifest

Generated: 2026-07-15 08:01 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `ef25bf3 checkpoint: show M4 preflight in runtime UI`

## Scope

Added a read-only M4 benchmark ladder manifest and validator. This defines the allowed serialized hardware ladder plan without executing it.

Changes:

- Added `backend/app/schemas/benchmark_ladder.py`.
- Added `backend/app/services/benchmarks/ladder.py`.
- Added `storage/benchmark_ladders/m4_cf_vid01_ladder.json`.
- Added `backend/tests/test_benchmark_ladder.py`.

The M4 ladder manifest allows only stages `0, 1, 2, 3, 7` for `CF-VID-01`, explicitly defers stages `4, 5, 6`, requires serial hardware-operator execution, requires operator approval, requires an exclusive GPU lease per stage, and keeps all stages `live_action_approved=false`.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_benchmark_ladder.py \
  backend/tests/test_benchmark_services.py
# 12 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 495 passed, 9 skipped, warnings only, ~65.47s
```

## Safety notes

- Manifest loading is read-only.
- No live ComfyUI/GPU/render/benchmark action was run.
- Public generation remains disabled.
- The manifest itself cannot approve live hardware execution.
