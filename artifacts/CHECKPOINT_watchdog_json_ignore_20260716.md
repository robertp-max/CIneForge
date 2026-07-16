# Checkpoint: ignored local watchdog JSON artifacts

Date: 2026-07-16

## Implemented

- Added `artifacts/watchdog/*.json` to `.gitignore` so optional `--watchdog-json` outputs do not dirty checkpoint commits.
- Documented the ignore behavior in `docs/OFFLINE_SAFE_VALIDATION.md`.

## Validation

- Ran full offline-safe runner with JSON output:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py --watchdog-json artifacts/watchdog/latest.json
```

Result:

- Static safe/local boundary validation: passed
- Curated backend tests: `147 passed, 71 warnings`
- Frontend lint/build: passed
- `git diff --check`: passed with CRLF warnings only
- Checkpoint watchdog banner printed
- `artifacts/watchdog/latest.json` was written and shown as ignored (`!!`)

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
