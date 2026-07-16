# App-wide automatic live probe removal checkpoint

Date: 2026-07-15

## Scope

Neutralized remaining strict local-MVP frontend safety blockers by removing automatic UI paths that call live runtime/probe helpers outside the API client.

## Changes

- `frontend/src/components/AppShell.tsx`
  - Default runtime chrome now says `Local runtime` / `Read-only · probes off · approval required` instead of `ComfyUI ready` / RTX hardware readiness.
  - Backend health no longer marks the runtime card as ready.
- `frontend/src/pages/Dashboard.tsx`
  - Removed automatic `api.comfyHealth()`, `api.gpuHealth()`, and `api.ffmpegHealth()` calls.
  - Kept non-live root/backend/project/campaign/job reads.
  - Replaced ComfyUI/GPU/FFmpeg cards with inert not-auto-probed / approval-required text.
- `frontend/src/pages/SystemHealth.tsx`
  - Removed automatic ComfyUI/GPU/FFmpeg health probe calls.
  - Kept root/backend health reads.
  - Replaced external runtime health cards with inert approval-required text.
- `frontend/src/pages/Queue.tsx`
  - Removed automatic `api.runtimeStatus()` load.
  - Kept visible job read path.
  - Replaced worker/submission/supported-state runtime metadata with inert not-auto-probed text.
- `frontend/src/studio/pages/SettingsPage.tsx`
  - Removed automatic `api.runtimeStatus()` during settings load.
  - Removed live `Test connection` path that called `api.runtimeStatus()`.
  - Replaced runtime fields with read-only metadata explaining probes require approval.

## Attestation

No execute/start/approve controls, POST calls, backend changes, FFmpeg/ffprobe execution, ComfyUI calls, GPU probes, render, benchmark, or live telemetry behavior were added.

## Validation

- `rg -n -g '!**/api/client.ts' "runtimeStatus|comfyHealth|gpuHealth|ffmpegHealth" frontend/src` produced no output.
- `cd frontend && npm run lint` passed.
- `cd frontend && npm run build` passed.
- `git diff --check` passed with line-ending warnings only.
