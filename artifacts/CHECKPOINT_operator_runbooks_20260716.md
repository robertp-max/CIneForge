# Checkpoint: local operator runbooks

Date: 2026-07-16

## Implemented

- Added GET-only local operator runbook endpoints:
  - `GET /local-operator/runbooks`
  - `GET /local-operator/runbooks/{mode}`
- Added typed read-only runbooks for:
  - `m4_hardware_ladder_probe`
  - `m5_ffmpeg_probe_validation`
  - `m5_ffmpeg_assembly_validation`
- Runtime UI now displays bounded runbook summaries with state, approval/execution flags, step counts, evidence-field counts, and stop-rule counts.

## Safety posture

Runbooks are reference metadata only. They expose prerequisites, stop rules, expected evidence fields, forbidden actions, and safe metadata sources. They do not expose command strings, approve execution, start live execution, submit prompts, probe runtime health, acquire GPU leases, run FFmpeg/ffprobe, contact ComfyUI, render, benchmark, create jobs, or enable public/autonomous generation.

All runbooks record:

- `state=read_only_reference`
- `public_generation_enabled=false`
- `endpoint_approves_execution=false`
- `endpoint_starts_live_execution=false`
- `raw_command_strings_allowed=false`

## Validation

- `./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests/test_local_operator.py backend/tests/test_phase1_app_routing.py`
  - Result: `13 passed`
- `cd frontend && npm run lint && npm run build`
  - Result: passed
- `git diff --check`
  - Result: no whitespace errors; CRLF warnings only
