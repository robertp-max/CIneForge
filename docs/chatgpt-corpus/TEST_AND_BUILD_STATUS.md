# Test And Build Status

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

## Commands Run

| Command | Result | Notes |
|---|---|---|
| `$env:CINEFORGE_TEST_POSTGRES_URL=...; python -m pytest` | timeout after 120s | PostgreSQL URL appeared inherited/used; no summary before timeout |
| `$env:CINEFORGE_TEST_POSTGRES_URL=...; python -m pytest backend/tests/test_postgres_schema.py backend/tests/test_postgres_queue_claim.py` | timeout after 120s | `Test-NetConnection 127.0.0.1 -Port 55432` failed |
| `python -m pytest backend/tests/test_queue_service.py backend/tests/test_queue_worker.py backend/tests/test_queue_state_machine.py` | 61 passed, 91 warnings | Queue/recovery/worker/state tests pass |
| `python -m pytest backend/tests/test_controlled_submission.py backend/tests/test_comfy_client.py` | 9 passed, 13 warnings | Controlled submission and Comfy boundary pass |
| `$env:CINEFORGE_TEST_POSTGRES_URL=$null; python -m pytest` | 128 passed, 8 skipped, 116 warnings | Default offline backend suite passes |
| `npm run build` in `frontend/` | failed | `tsc` not recognized; dependencies not installed |
| `npm run lint` in `frontend/` | failed | `eslint` not recognized; dependencies not installed |
| `Test-NetConnection 127.0.0.1 -Port 55432` | `TcpTestSucceeded=False` | PostgreSQL-gated tests blocked by environment |

## Backend Tests

Default backend suite passed with PostgreSQL URL explicitly cleared: `128 passed, 8 skipped, 116 warnings`. PostgreSQL-specific tests skipped in that run.

## Database-Dependent Tests

Blocked in this session because local PostgreSQL test port was unreachable. This is an environmental blocker, not a captured assertion failure. Previous project history indicates these tests can pass when the disposable PostgreSQL container is running.

## Frontend Build/Lint

Not verified. `npm run build` and `npm run lint` failed immediately because `tsc` and `eslint` were not available. The worktree does not have `node_modules`, and package installation was forbidden.

## Commands Intentionally Not Run

- `npm install`: forbidden by request.
- Uvicorn dev server: not needed for corpus and could create local state.
- ComfyUI runtime/generation/WebSocket/output/FFmpeg execution: forbidden and out of scope.
