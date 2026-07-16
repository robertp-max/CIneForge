# Checkpoint: API contract watchdog untracked field

Date: 2026-07-16

## Implemented

- Updated `docs/API_CONTRACT.md` to state that `GET /local-runtime/checkpoint-watchdog` exposes staged filenames and source-scoped untracked-file visibility while remaining read-only/non-approving.

## Validation

- Focused offline docs boundary tests and `git diff --check` were run before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
