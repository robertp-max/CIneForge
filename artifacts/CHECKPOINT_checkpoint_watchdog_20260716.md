# Checkpoint: checkpoint watchdog

Date: 2026-07-16

## Implemented

- Added `scripts/checkpoint_watchdog.py`.
- Added `backend/tests/test_checkpoint_watchdog.py`.
- Integrated the watchdog into `scripts/run_offline_safe_validation.py` so the curated validation loop prints a restart reminder after validation.
- Updated validation-runner tests to assert the watchdog is invoked.
- Launched a read-only async watchdog subagent to produce an independent watchdog brief.

## Watchdog behavior

The watchdog prints:

- the latest commit,
- tracked worktree cleanliness,
- a reminder to immediately restart the offline-safe continuation loop after every checkpoint,
- invariants blocking live FFmpeg/ffprobe, ComfyUI/GPU/render/benchmark/runtime probes, prompt submission, queue execution, and public generation without explicit scoped approval.

## Validation

- Focused tests: `4 passed`
- `./.venv/Scripts/python.exe -B scripts/run_offline_safe_validation.py`
  - Static safe/local boundary validation: passed
  - Curated backend tests: `142 passed, 71 warnings`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
