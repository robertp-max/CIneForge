# Checkpoint: watchdog prompt invariant full validation

Date: 2026-07-16

## Validation

After committing watchdog `/prompt` and `/api/prompt` invariant alignment, ran:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py
```

Result:

- Static safe/local boundary validation: passed
- Curated backend tests: `154 passed, 71 warnings`
- Frontend lint/build: passed
- `git diff --check`: passed
- Checkpoint watchdog banner printed the aligned `/prompt` and `/api/prompt` invariant

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
