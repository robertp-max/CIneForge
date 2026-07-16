# Checkpoint: watchdog brief integrated

Date: 2026-07-16

## Implemented

- Read the async watchdog subagent brief from `.pi-subagents` output.
- Added `docs/CHECKPOINT_WATCHDOG.md` with the restart loop directive and invariants.
- Expanded `scripts/checkpoint_watchdog.py` to include validation-truth and staged-content reminders.
- Updated watchdog tests for the expanded checklist.

## Watchdog directive

After every checkpoint commit, immediately restart the offline-safe continuation loop, select the next safe gap, implement it, validate truthfully, commit, and restart again. Do not stop for status chatter.

## Validation

Focused watchdog validation was run before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
