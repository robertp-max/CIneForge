# Checkpoint: local smoke plan offline rescope

Date: 2026-07-16

## Implemented

- Re-scoped `docs/LOCAL_SMOKE_TEST_PLAN.md` to the current offline-safe validation path.
- Marked live health/runtime probes, ComfyUI `object_info`, GPU telemetry, FFmpeg/ffprobe checks, rendering, and benchmarking as approval-required.

## Validation

- Documentation-only update; `git diff --check` was run before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
