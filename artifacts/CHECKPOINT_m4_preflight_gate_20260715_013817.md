# Checkpoint — Read-only M4 Hardware Preflight Gate

Generated: 2026-07-15 01:38 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `96193ac checkpoint: record M3 controlled runtime status`

## Scope

Added a read-only M4 hardware-operator preflight report without enabling generation or touching live runtime.

Changes:

- Added setting `CINEFORGE_M4_HARDWARE_PROBE_APPROVED=false` via `Settings.m4_hardware_probe_approved`.
- Added `backend/app/schemas/local_runtime_m4.py` for the preflight report/check schemas.
- Added `backend/app/services/local_runtime_m4.py` to evaluate M4 probe readiness from local flags and existing smoke evidence only.
- Added `GET /local-runtime/m4-preflight`.
- Added tests in `backend/tests/test_local_runtime_m4.py` for:
  - default blocked state without operator gate/approval;
  - blocked state when smoke evidence is missing;
  - operator-probe-ready report when all flags/evidence are provided in a temp test setup;
  - route remains read-only/default-blocked.

## Safety behavior

The report explicitly does **not**:

- launch ComfyUI;
- load models;
- submit prompts;
- acquire GPU leases;
- render media;
- run benchmarks;
- install nodes;
- download files;
- enable public generation.

Default behavior remains blocked because both `hardware_operator_enabled` and `m4_hardware_probe_approved` default to false.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_local_runtime_m4.py \
  backend/tests/test_local_runtime.py \
  backend/tests/test_local_runtime_evidence.py \
  backend/tests/test_health.py
# 22 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 490 passed, 9 skipped, warnings only, ~83.43s
```

## Next gate

M4 live hardware probing remains blocked unless the operator explicitly enables both the hardware-operator gate and the M4 hardware-probe approval flag, and then runs the serialized ladder outside this read-only report.
