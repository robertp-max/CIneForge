# Next Action Prompt

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

## Objective

Implement progress persistence and history/output collection planning behind the worker/runtime boundary, without public generation or ComfyUI runtime mutation.

## Exact Scope

Add durable database/service support for recording normalized ComfyUI progress events and defining a safe history/output collection boundary for already-submitted jobs. This should be a non-generating, testable slice.

## Files Likely Involved

- `backend/app/db/base.py`
- `backend/alembic/versions/`
- `backend/app/services/comfy/progress_monitor.py`
- `backend/app/services/comfy/client.py`
- `backend/app/services/comfy/submission.py`
- `backend/app/services/queue/service.py`
- `backend/app/services/queue/worker.py`
- `backend/tests/test_progress_monitor.py`
- new focused tests as needed
- `docs/SPRINT_1C_PLAN.md`

## Forbidden Actions

- Do not expose public `/prompt` or a Generate button.
- Do not run generation.
- Do not open a real WebSocket in tests.
- Do not collect real outputs from ComfyUI.
- Do not execute FFmpeg.
- Do not start a daemon/scheduler/autonomy loop.
- Do not touch ComfyUI runtime files, model folders, generated media, or unrelated architecture docs.
- Do not install dependencies.

## Acceptance Criteria

- Progress events can be persisted or represented in DB-backed job fields/audit records using existing parser output.
- Unknown events are preserved.
- Runtime failure candidates can be recorded without falsely completing jobs.
- History/output collection remains a declared worker-only boundary and is not executed against live ComfyUI.
- Existing controlled submission and queue tests still pass.
- Docs clearly state what is implemented versus future work.

## Required Tests

- Parser/persistence tests for execution start, progress, executing, executed, error, unknown events.
- Service tests proving progress event recording updates only expected job fields/audit.
- Tests proving public routes still do not expose prompt/history/output collection.
- Full backend pytest with PostgreSQL URL cleared if local PostgreSQL is unavailable.
- PostgreSQL-gated tests if schema/migration changes are added and test DB is available.

## Stop Conditions

- Repo path/remote/branch safety gate fails.
- Active worktree has unrelated changes in files needed for the slice and cannot be safely worked around.
- PostgreSQL migration conflict cannot be resolved by normal forward migration.
- Any prompt suggests running pasted shell commands from a browser/dialog/CAPTCHA.

## Expected Final Report

Report files changed, schema changes, tests run/results, skipped/blocked tests, confirmation no generation/runtime mutation occurred, commit SHA, push result, and remaining limitations.
