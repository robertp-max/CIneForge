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

- No FFmpeg or ffprobe execution without explicit scoped live approval.
- No ComfyUI, GPU probe, runtime health probe, render, benchmark, queue execution, prompt submission, or public generation without explicit scoped live approval.
- Casual `ok`, `k`, `continue`, planning approval, Storyboard approval, packet creation, or runbook viewing is not live approval.
- Public raw `/prompt` and `/api/prompt` routes remain absent.
- Public/autonomous generation remains disabled.
- Local endpoints remain read-only or manifest-only; no execute/submit/approve/prompt child routes.
- Local archetypes and presets stay disabled/not-ready unless explicit gates and approvals change scope.
- Record validation truthfully in each checkpoint; if the full offline-safe suite was not run, say so.
- Before each checkpoint commit, verify staged contents intentionally match the checkpoint and no unrelated files are included.
- After each checkpoint commit, immediately resume offline-safe work.

## Tooling

- `scripts/checkpoint_watchdog.py` prints the restart reminder and invariants; pass `--json` for machine-readable CI/tool output.
- `GET /local-runtime/checkpoint-watchdog` exposes the read-only watchdog report for API/UI visibility without approving or starting work.
- `scripts/run_offline_safe_validation.py` runs the curated offline-safe validation suite, prints the watchdog banner, and can write the watchdog JSON via `--watchdog-json <path>`.
- `docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md` defines valid live approval shape.
- `docs/OFFLINE_SAFE_VALIDATION.md` defines the no-live validation path.
- `docs/SAFE_LOCAL_ENDPOINTS.md` lists local/offline endpoint contracts.
