# Safe local endpoint matrix

Date: 2026-07-16

This matrix documents local/offline CineForge surfaces that are allowed before explicit live approval. All listed surfaces are read-only or manifest-only and must not run live media/runtime work.

| Endpoint | Method(s) | Purpose | Executes live tools? | Records approval? | Starts generation/media work? |
|---|---:|---|---:|---:|---:|
| `/local-runtime/catalog` | GET | DB-free model/output catalog | No | No | No |
| `/local-runtime/output-policy` | GET | Output root/prefix policy | No | No | No |
| `/local-runtime/evidence` | GET | Existing evidence records | No | No | No |
| `/local-runtime/evidence/cf-vid-01-smoke` | GET | Existing CF-VID-01 smoke evidence | No | No | No |
| `/local-runtime/m4-preflight` | GET | Read-only M4 gate summary | No | No | No |
| `/local-runtime/m4-ladder` | GET | Serialized M4 ladder metadata | No | No | No |
| `/local-runtime/local-mvp-readiness` | GET | Local MVP readiness checkpoint | No | No | No |
| `/local-runtime/public-readiness` | GET | Fail-closed public readiness checkpoint | No | No | No |
| `/local-runtime/safe-boundary` | GET | Static safe-boundary check report | No | No | No |
| `/local-runtime/checkpoint-watchdog` | GET | Read-only checkpoint continuation watchdog report | No | No | No |
| `/local-runtime/ffmpeg-recipes` | GET | Read-only FFmpeg recipe catalog | No | No | No |
| `/local-archetypes/catalog` | GET | Archetype catalog envelope | No | No | No |
| `/local-archetypes` | GET | Archetype records | No | No | No |
| `/local-archetypes/{archetype_id}` | GET | Single archetype record | No | No | No |
| `/local-archetypes/readiness` | GET | Archetype readiness rollup | No | No | No |
| `/local-archetypes/{archetype_id}/readiness` | GET | Single archetype readiness record | No | No | No |
| `/local-presets/catalog` | GET | Preset catalog envelope | No | No | No |
| `/local-presets` | GET | Preset records | No | No | No |
| `/local-presets/{preset_id}` | GET | Single preset record | No | No | No |
| `/local-presets/readiness` | GET | Preset readiness rollup | No | No | No |
| `/local-presets/{preset_id}/readiness` | GET | Single preset readiness record | No | No | No |
| `/local-jobs` | GET/POST | File-backed offline job manifests | No | No | No |
| `/local-jobs/{job_id}` | GET | Offline job manifest lookup | No | No | No |
| `/local-generation/semantic-requests` | GET/POST | Offline semantic request manifests | No | No | No |
| `/local-generation/semantic-requests/{request_id}` | GET | Offline semantic manifest lookup | No | No | No |
| `/local-generation/storyboard-handoffs` | POST | Explicit Storyboard-to-offline semantic manifest bridge | No | No | No |
| `/local-operator/approval-templates` | GET | Approval wording templates | No | No | No |
| `/local-operator/approval-templates/{mode}` | GET | Approval wording template lookup | No | No | No |
| `/local-operator/runbooks` | GET | Operator prerequisites/stop rules/evidence expectations | No | No | No |
| `/local-operator/runbooks/{mode}` | GET | Operator runbook lookup | No | No | No |
| `/local-operator/packets` | GET/POST | Pending review packet manifests | No | No | No |
| `/local-operator/packets/{packet_id}` | GET | Pending review packet lookup | No | No | No |
| `/local-post-production/plans` | GET/POST | Offline post-production plan manifests | No | No | No |
| `/local-post-production/plans/{plan_id}` | GET | Offline post-production plan lookup | No | No | No |
| `/local-post-production/recipe-commands` | GET | Read-only stored recipe command manifests | No | No | No |
| `/local-post-production/recipe-commands/{plan_id}` | GET | Stored recipe command lookup | No | No | No |

## Explicitly absent local execution routes

The local/offline lane must not expose these route shapes:

- `/prompt` or `/api/prompt` public raw proxy,
- `/local-generation/*/execute`, `/submit`, `/run`, `/approve`, or `/prompt`,
- `/local-operator/run`, `/execute`, `/submit`, `/approve`, or `/prompt`,
- generic FFmpeg command-string execution endpoints,
- public/autonomous generation enablement endpoints.

## Live approval boundary

See `docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md`. Casual replies such as `k`, `ok`, `continue`, `f`, or abusive/threatening language are not approvals. A valid future live approval must name action family, target, scope, local-only constraint, and live-tool acknowledgement.
