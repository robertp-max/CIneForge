# PostgreSQL Verification

Sprint 1C Slice 1 adds PostgreSQL-gated schema verification tests. These tests are optional by default and run only when a disposable PostgreSQL test database URL is provided.

## Environment Variable

Set:

```powershell
$env:CINEFORGE_TEST_POSTGRES_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME"
```

The database identified by `CINEFORGE_TEST_POSTGRES_URL` must be a test database. Do not point this variable at production, shared staging, or any database whose contents must be preserved.

## Install Dev Dependencies

The dev extra includes `psycopg[binary]` for PostgreSQL SQLAlchemy connections:

```powershell
.\.venv\Scripts\python -m pip install -e .[dev]
```

## Run Tests

Default local test run:

```powershell
.\.venv\Scripts\python -m pytest
```

When `CINEFORGE_TEST_POSTGRES_URL` is not set, PostgreSQL verification tests skip cleanly.

PostgreSQL-focused run:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_postgres_schema.py
```

## What Is Verified

- Alembic `upgrade head` runs against the configured PostgreSQL database.
- Required Sprint 1A through Sprint 1B tables exist.
- Queue-critical tables exist:
  - `workflow_templates`
  - `workflow_runs`
  - `comfy_jobs`
  - `audit_logs`
  - `error_logs`
- Queue-critical columns are present.
- JSONB-oriented columns are reflected as PostgreSQL JSONB columns.
- UUID-oriented columns are reflected as PostgreSQL UUID columns.

## What Remains Pending

- PostgreSQL concurrent queue reservation is not implemented or verified yet.
- Worker ownership fields are not implemented yet.
- `SELECT ... FOR UPDATE SKIP LOCKED` behavior is not tested yet.
- Timeout and recovery policy is not implemented yet.
- No queue worker loop exists.
- No ComfyUI prompt submission or generation path is enabled.
