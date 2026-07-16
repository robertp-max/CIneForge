# Runtime page auto live probe removal checkpoint

Date: 2026-07-15

## Scope

Removed automatic live runtime probing from the frontend Runtime page when opening the local readiness UI.

## Attestation

- `frontend/src/pages/Runtime.tsx` no longer calls `api.runtimeStatus()` on mount.
- The app shell no longer calls `api.runtimeStatus()` during automatic backend status refresh, preventing the shell from triggering ComfyUI/GPU telemetry while opening the local readiness UI.
- The Runtime page now loads only read-only local metadata through local-runtime/local-presets/local-archetypes/evidence/m4-preflight/m4-ladder/ffmpeg-recipes API helpers.
- ComfyUI reachability, `object_info`, runtime phase, queue capability, GPU telemetry, and live runtime status content were replaced with inert explanatory text stating live probes require explicit operator approval and are not auto-run.
- The app shell runtime strip wording was tightened so it no longer statically claims `ComfyUI ready` or specific hardware readiness while automatic runtime/GPU probes are disabled.
- No execute/start/approve controls, POST calls, FFmpeg/ffprobe execution, ComfyUI calls, GPU probes, render, benchmark, or live telemetry behavior were added.

## Validation

- `cd frontend && npm run lint` passed.
- `cd frontend && npm run build` passed.
- `git diff --check` passed with line-ending warnings only.
