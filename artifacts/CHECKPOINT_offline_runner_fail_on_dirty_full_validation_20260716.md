# Checkpoint: offline runner fail-on-dirty full validation

Date: 2026-07-16

## Validation

After committing runner-level `--fail-on-dirty`, ran:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py --fail-on-dirty
```

Result:

- Static safe/local boundary validation: passed
- Curated backend tests: `155 passed, 71 warnings`
- Frontend lint/build: passed
- `git diff --check`: passed
- Checkpoint watchdog ran with `--fail-on-dirty`, reported tracked worktree clean and staged files `0`

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
