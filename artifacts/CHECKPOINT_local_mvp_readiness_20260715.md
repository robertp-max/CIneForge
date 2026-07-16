# Local-only MVP readiness checkpoint

Date: 2026-07-15

## Scope

Added a read-only backend checkpoint endpoint at `GET /local-runtime/local-mvp-readiness`.

## Attestation

- Local-only target is reported as `true`.
- The endpoint does not execute FFmpeg/ffprobe, ComfyUI, GPU work, rendering, benchmarks, prompt submission, or job creation.
- The endpoint does not approve live execution.
- Public generation remains reported disabled by the local runtime catalog.
- Autonomous queue execution is summarized from `CINEFORGE_QUEUE_WORKER_ENABLED` and is a blocker if enabled.
- M4 status is summarized from the existing read-only M4 preflight service.
- M5 status is summarized from safe FFmpeg recipe catalog metadata only: catalog count, read-only flags, no execution endpoint, and no user-authored command path.

## Validation notes

- Route contract coverage includes `GET /local-runtime/local-mvp-readiness` in `backend/tests/test_phase1_app_routing.py`.

## Remaining blockers before local operator live runs

1. Explicit operator approval for the specific live run.
2. Applicable production gates for the exact workflow/request/preset/assets/profile.
3. Managed GPU lease/admission before ComfyUI hardware work.
4. Managed paths, hashes, probes, and provenance records.
