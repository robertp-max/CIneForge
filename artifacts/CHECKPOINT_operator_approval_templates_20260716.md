# Checkpoint: local operator approval templates

Date: 2026-07-16

## Implemented

- Added GET-only approval-template endpoints:
  - `GET /local-operator/approval-templates`
  - `GET /local-operator/approval-templates/{mode}`
- Added templates for:
  - `m4_hardware_ladder_probe`
  - `m5_ffmpeg_probe_validation`
  - `m5_ffmpeg_assembly_validation`
- Runtime UI now displays bounded approval-template summaries and example approval text.

## Safety posture

Approval templates are reference text only. They explicitly list non-approval phrases such as `k`, `ok`, and `continue`, and they do not record approval or start live work.

All templates record:

- `endpoint_records_approval=false`
- `endpoint_starts_live_execution=false`

No FFmpeg, ffprobe, ComfyUI, GPU workload, render, benchmark, runtime health probe, queue execution, prompt submission, public generation, or live approval was run or enabled.

## Validation

- `./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests/test_local_operator.py backend/tests/test_phase1_app_routing.py`
  - Result: `15 passed`
- `cd frontend && npm run lint && npm run build`
  - Result: passed
- `git diff --check`
  - Result: no whitespace errors; CRLF warnings only
