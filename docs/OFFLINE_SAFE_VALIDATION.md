# Offline-safe validation

Date: 2026-07-16

CineForge's local ComfyUI lane is intentionally fail-closed unless a separate explicit operator approval is given for a live action. Use this guide to validate the safe/local boundary without running live tools.

## One-command suite

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py
```

GitHub Actions runs the same offline-safe runner with `--watchdog-json artifacts/watchdog/ci.json --fail-on-dirty`.

Optional machine-readable watchdog artifact; `artifacts/watchdog/*.json` is ignored for local checkpoint use:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py --watchdog-json artifacts\watchdog\latest.json
```

Optional clean tracked tree enforcement after validation:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py --fail-on-dirty
```

The runner performs:

1. Static safe/local boundary validation.
2. Curated backend tests for local catalogs, local jobs, offline generation manifests, readiness reports, operator packets/runbooks/templates, post-production manifests, production gates, and workflow admission/registry logic.
3. Frontend lint and build.
4. `git diff --check`.

Current checkpoint result: `157 passed, 71 warnings`, frontend lint/build passed, static boundary validation passed, endpoint-matrix path/method sync passed, offline docs boundary checks passed, and the checkpoint watchdog banner printed.

## Static boundary check only

```powershell
.\.venv\Scripts\python scripts\validate_safe_local_boundary.py
```

This file-only check verifies:

- no enabled/ready local archetypes,
- no enabled/ready local presets,
- no frontend live-probe call sites outside API client definitions,
- no frontend/API-client raw `/prompt` or `/api/prompt` references,
- no exact public raw `/prompt` FastAPI route,
- no GitHub Actions workflow live-probe/media fragments,
- no accidental assistant-analysis/debug text leaks in tracked source/docs/workflows/artifacts,
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

See `docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md` for exact approval language requirements. Casual phrases such as `k`, `ok`, `continue`, `f`, or abusive/threatening language are not live-run approvals.
