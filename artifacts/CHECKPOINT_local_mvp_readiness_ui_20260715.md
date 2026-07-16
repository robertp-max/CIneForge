# Local MVP readiness UI checkpoint

Date: 2026-07-15

## Scope

Surfaced the existing read-only `GET /local-runtime/local-mvp-readiness` report in the local runtime frontend UI.

## Attestation

- Added frontend API typing and a GET-only helper for the local MVP readiness report.
- Rendered an inert Runtime page section showing the local-only target, blocked/checkpoint status, disabled public/autonomous generation flags, M4 summary, M5 summary, and remaining blockers before local operator live runs.
- Added no execute, approve, start, POST, ComfyUI, FFmpeg, public generation, render, benchmark, GPU, or ffprobe behavior.
- Display is bounded by summarizing blockers in the card and preserving read-only status text.

## Validation

- `cd frontend && npm run lint` passed.
- `cd frontend && npm run build` passed.
