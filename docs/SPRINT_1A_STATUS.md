# Sprint 1A Status

Completed:

- FastAPI backend scaffold with configuration loading from `.env`.
- Health endpoints for API, ComfyUI reachability, GPU telemetry, and FFmpeg availability.
- PostgreSQL-aligned SQLAlchemy model foundation, including core provenance tables and autonomy stub tables.
- Queue state machine using the corrected lifecycle and failure taxonomy.
- Manifest-based workflow validation, patch planning, output prefix sanitization, object-info compatibility stub, and immutable snapshot writing.
- Offline-safe ComfyUI client boundary with mutating calls blocked by default.
- `nvidia-smi` CSV telemetry parser aligned to the benchmark protocol and tolerant of Windows WDDM `N/A` fields.
- FFmpeg/ffprobe availability checks, probe JSON storage contract, SHA256 helper, stream-copy compatibility validation, normalization plan selection, and approved command template IDs.
- Path safety utilities for storage-root confinement and output prefix sanitation.
- Non-executing AI proposal, autonomy, policy, QA, retry, and batch planner stubs.
- Example smoke workflow template under `storage/workflow_templates/example_smoke`.

Partial:

- Project, campaign, and job routes validate requests and return clear stub responses, but they are not DB-backed yet.
- Database foundation exists as SQLAlchemy metadata and local `create_db.py`; Alembic migrations are a Sprint 1B task.
- ComfyUI WebSocket progress and queue-worker submission context are scaffolded only.

Blocked:

- No PostgreSQL instance is configured in this workspace, so local default remains SQLite.

Sprint 1B recommendations:

- Add Alembic migrations from the SQLAlchemy metadata and verify against PostgreSQL.
- Wire project/campaign/job APIs to the database.
- Implement the single GPU queue worker with durable reservations, timeout policy, and audit log writes.
- Add ComfyUI object-info cache and WebSocket progress monitor.
- Add benchmark runner JSONL logging and promotion gate evaluator.

