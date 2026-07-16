# Route Contract and M7 Local-only Status Alignment

Date: 2026-07-16

## Scope aligned

- Added the newly implemented local readiness and handoff routes to the Phase 1 application routing contract:
  - `GET /local-archetypes/readiness`
  - `GET /local-archetypes/{archetype_id}/readiness`
  - `GET /local-presets/readiness`
  - `GET /local-presets/{preset_id}/readiness`
  - `POST /local-generation/storyboard-handoffs`
- Tightened focused route tests for local generation and readiness so the contract proves there are no `/execute`, `/submit`, `/run`, or `/prompt` child routes on those local-only surfaces.
- Updated the M7 local-only implementation status in `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md` to match the current code.

## Current status represented

- Readiness rollups are implemented for archetypes and presets as read-only evidence surfaces.
- Frontend Runtime rollups summarize local MVP/readiness state without live runtime probes.
- Offline semantic request manifests are implemented under `/local-generation/semantic-requests`.
- Storyboard-to-semantic handoff is explicit via `POST /local-generation/storyboard-handoffs` and is not automatic from Storyboard approval.
- All 64 presets remain disabled/gated.
- Public/autonomous generation remains disabled.
- No public raw `/prompt` route, ComfyUI submission, queue execution, GPU lease acquisition, FFmpeg/ffprobe execution, render, benchmark, or runtime health call was added by this alignment pass.
