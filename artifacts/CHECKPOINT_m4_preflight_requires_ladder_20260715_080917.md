# Checkpoint — M4 Preflight Requires Valid Ladder Manifest

Generated: 2026-07-15 08:09 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `cd5f6d7 checkpoint: show M4 ladder in runtime UI`

## Scope

Hardened the read-only M4 hardware preflight report so it also requires the M4 serialized ladder manifest to be present and valid before reporting `operator_probe_ready`.

Changes:

- `M4HardwarePreflightService` now validates `BenchmarkLadderService.get_m4_ladder()`.
- Added preflight check code `m4_ladder_manifest_valid`.
- Missing or invalid ladder manifests become blocking reasons.
- Updated tests to use a temp ladder manifest for isolated approved-case validation.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_local_runtime_m4.py \
  backend/tests/test_benchmark_ladder.py
# 10 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 496 passed, 9 skipped, warnings only, ~73.32s
```

## Safety notes

- Preflight remains read-only.
- No live ComfyUI/GPU/render/benchmark action was run.
- Ladder manifest validation does not approve live hardware execution.
