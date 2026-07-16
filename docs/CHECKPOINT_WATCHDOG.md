# Checkpoint Watchdog

Date: 2026-07-16

This watchdog protocol keeps the CineForge offline-safe implementation loop moving after every checkpoint.

## Loop directive

After every checkpoint commit:

1. Immediately restart the offline-safe continuation loop.
2. Pick the next safe hardening, documentation, test, route-contract, or validation gap.
3. Implement it without live runtime/media actions.
4. Run and record appropriate validation.
5. Commit the checkpoint.
6. Restart the loop again.

Do not stop for status chatter. Stop only if blocked by an explicit live-approval boundary or if the user explicitly asks for final status.

## Invariants

- No FFmpeg/ffprobe execution without explicit scoped live approval.
- No ComfyUI/GPU/render/benchmark/runtime-health probe without explicit scoped live approval.
- No prompt submission, queue execution, public generation, or public raw /prompt route.
- Keep local archetypes/presets disabled unless evidence gates and approval explicitly change that scope.
- Record validation truthfully in each checkpoint; if the full offline-safe suite was not run, say so.
- Before each checkpoint commit, verify staged contents intentionally match the checkpoint and no unrelated files are included.
- After each commit, immediately continue with the next offline-safe gap unless blocked by the live boundary.
- Casual `ok`, `k`, `continue`, planning approval, Storyboard approval, packet creation, or runbook viewing is not live approval.
- Public raw `/api/prompt` routes remain absent.
- Public/autonomous generation remains disabled.
- Local endpoints remain read-only or manifest-only; no execute/submit/approve/prompt child routes.

## Tooling

- `scripts/checkpoint_watchdog.py` prints the restart reminder and invariants; pass `--json` for machine-readable CI/tool output.
- `GET /local-runtime/checkpoint-watchdog` exposes the read-only watchdog report for API/UI visibility without approving or starting work.
- `scripts/run_offline_safe_validation.py` runs the curated offline-safe validation suite, prints the watchdog banner, and can write the watchdog JSON via `--watchdog-json <path>`.
- `docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md` defines valid live approval shape.
- `docs/OFFLINE_SAFE_VALIDATION.md` defines the no-live validation path.
- `docs/SAFE_LOCAL_ENDPOINTS.md` lists local/offline endpoint contracts.
