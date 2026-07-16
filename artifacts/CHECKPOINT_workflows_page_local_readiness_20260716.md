# Checkpoint: Workflows page local readiness rollup

Date: 2026-07-16

## Implemented

- Updated `frontend/src/studio/pages/WorkflowsPage.tsx` to load `api.listLocalArchetypeReadiness()`.
- Added a bounded read-only local archetype readiness summary and sample records to the Studio Workflows page.
- The page now distinguishes demo workflow fixtures from backend evidence rollups.

## Safety posture

This UI integration calls only `GET /local-archetypes/readiness`. It does not call `/runtime/status`, `/health/comfy`, `/health/gpu`, `/health/ffmpeg`, ComfyUI `object_info`, prompt submission, queue execution, FFmpeg/ffprobe, render, benchmark, install, download, or any live mutation surface.

## Validation

- `cd frontend && npm run lint && npm run build`
  - Result: passed
