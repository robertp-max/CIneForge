# Checkpoint: end-user manual and developer guide

Date: 2026-07-16

## Implemented

- Added `docs/END_USER_MANUAL.md` with local app URLs, startup instructions, UI navigation, Storyboard Studio workflow, runtime/readiness guidance, operator packets/runbooks/templates, provider preference, troubleshooting, and current validation truth.
- Added `docs/DEVELOPER_GUIDE.md` with architecture layout, setup/run commands, configuration, route/service map, safe local endpoint policy, validation workflow, provider development notes, frontend/backend extension rules, and handoff checklist.

## Validation

- Static safe/local boundary validation: passed
- Focused offline docs boundary tests: `5 passed`
- `git diff --check`: passed

Full offline-safe runner was not rerun for this docs-only checkpoint; the current full validation truth remains `243 passed` from the provider contract runner checkpoint.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, external provider call, public generation, or live approval was run or enabled.
