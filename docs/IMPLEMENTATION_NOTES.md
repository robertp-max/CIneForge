# Implementation Notes

Sprint 1A uses Python/FastAPI because this repo has no existing application framework and the first backend layer needs local subprocess, HTTP, validation, and database boundaries.

Decisions:

- ComfyUI remains an external HTTP/WebSocket runtime. Mutating client methods are blocked unless a future queue-worker context explicitly enables them.
- API project/campaign/job endpoints are validated stubs backed by an in-memory Sprint 1A store; SQLAlchemy models define the persistence foundation for Sprint 1B wiring.
- SQLite is the default local development URL, while model names and columns are kept aligned with `Database/POSTGRES_SCHEMA.sql`.
- FFmpeg command execution is not exposed as free-form strings. Sprint 1A defines approved command template IDs and pure validation helpers.
- AI orchestration and autonomy are schema-only, advisory-only stubs. They cannot execute queue, workflow, registry, asset, ComfyUI, shell, or FFmpeg changes.

Unresolved:

- Alembic revision files are not generated yet; `scripts/create_db.py` creates local tables from SQLAlchemy metadata.
- ComfyUI WebSocket progress is an interface concern for Sprint 1B queue-worker implementation.
- Benchmark promotion gates are documented and telemetry parsing exists, but full benchmark runner orchestration is not implemented.

