# Checkpoint: Storyboard/Workflows readiness overclaim cleanup

Date: 2026-07-16

## Implemented

- Updated Studio Workflows page wording from simulated validation to planning-only review.
- Updated Storyboard generation-plan subtitle and workflow pill wording so it no longer implies live machine validation.

## Safety posture

No ComfyUI, `object_info`, GPU, FFmpeg/ffprobe, render, benchmark, install, download, queue, prompt submission, or runtime health action was added or run.

## Validation

- `cd frontend && npm run lint && npm run build`
  - Result: passed
- Stale wording scan found no remaining positive `validated against` / mock live probe wording. The only remaining `object_info validation` phrase is a negative safety statement: live object_info validation is not run here.
