# Checkpoint — Read-only M4 Ladder API

Generated: 2026-07-15 08:05 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `9552111 checkpoint: add read-only M4 ladder manifest`

## Scope

Exposed the validated M4 ladder manifest through a read-only local-runtime API route.

Changes:

- Added `GET /local-runtime/m4-ladder` returning `BenchmarkLadderManifest`.
- The route fails closed if the manifest is missing or invalid.
- Added a route test proving the endpoint returns the read-only M4 plan with:
  - allowed stages `[0, 1, 2, 3, 7]`;
  - deferred stages `[4, 5, 6]`;
  - public generation disabled;
  - serial execution required;
  - all stage live approvals false.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_benchmark_ladder.py \
  backend/tests/test_local_runtime_m4.py \
  backend/tests/test_local_runtime.py
# 13 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 496 passed, 9 skipped, warnings only, ~66.26s
```

## Safety notes

- API is read-only.
- Loading the ladder does not approve or run hardware work.
- No live ComfyUI/GPU/render/benchmark action was run.
