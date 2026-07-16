# Checkpoint: API/UI docs offline rescope

Date: 2026-07-16

## Implemented

- Updated `docs/API_CONTRACT.md` so live health endpoints are explicitly marked approval-required and outside the default offline-safe path.
- Updated `docs/UI_MVP_STATUS.md` to describe the current read-only/offline UI surfaces and no auto live-probe behavior.

## Safety posture

Documentation only. No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, public generation, or live approval was run or enabled.
