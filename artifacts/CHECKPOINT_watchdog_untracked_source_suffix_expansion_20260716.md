# Checkpoint: watchdog untracked-source suffix expansion

Date: 2026-07-16

## Implemented

- Expanded checkpoint watchdog source-scoped untracked-file detection to include common text/config/lock suffixes: `.txt`, `.ini`, `.cfg`, `.lock`, and `.jsonl` in addition to existing source/doc suffixes.
- Updated regression coverage to ensure untracked `requirements.txt` and `.ini` config files are surfaced while ignored watchdog JSON artifacts and scratch temp files remain excluded.

## Validation

- Focused watchdog tests: `10 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `166 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
