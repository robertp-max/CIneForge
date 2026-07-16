# Offline-safe validation

Date: 2026-07-16

CineForge's local ComfyUI lane is intentionally fail-closed unless a separate explicit operator approval is given for a live action. Use this guide to validate the safe/local boundary without running live tools.

## One-command suite

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py
```

The runner performs:

1. Static safe/local boundary validation.
2. Curated backend tests for local catalogs, local jobs, offline generation manifests, readiness reports, operator packets/runbooks/templates, post-production manifests, production gates, and workflow admission/registry logic.
3. Frontend lint and build.
4. `git diff --check`.

Current checkpoint result: `140 passed, 71 warnings`, frontend lint/build passed, static boundary validation passed, endpoint-matrix path/method sync passed, and offline docs boundary checks passed.

## Static boundary check only

```powershell
.\.venv\Scripts\python scripts\validate_safe_local_boundary.py
```

This file-only check verifies:

- no enabled/ready local archetypes,
- no enabled/ready local presets,
- no frontend live-probe call sites outside API client definitions,
- no exact public raw `/prompt` FastAPI route,
- no `/local-generation` or `/local-operator` execute/submit/approve/prompt child routes,
- no `/local-operator/run` route while allowing `/local-operator/runbooks` reference metadata.

## What validation must not do

The offline-safe suite must not:

- run FFmpeg or ffprobe,
- contact ComfyUI,
- probe GPU or runtime health,
- submit prompts,
- create live jobs,
- render media,
- benchmark,
- approve live work,
- enable public/autonomous generation.

## Live-boundary reference

See `docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md` for exact approval language requirements. Casual phrases such as `k`, `ok`, and `continue` are not live-run approvals.
