# Checkpoint: README non-stopping watchdog note

Date: 2026-07-16

## Implemented

- Updated README watchdog helper docs to state that watchdog/status checks are not stopping points and the offline-safe loop must continue immediately unless blocked by the live boundary.

## Validation

- Focused offline docs boundary guard was run before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
