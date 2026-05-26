# Sprint 1B Plan

Date: 2026-05-26

## Current State

Sprint 1A is complete and pushed. The backend foundation includes FastAPI, configuration loading, health endpoints, SQLAlchemy metadata, queue state-machine primitives, workflow manifest validation, path safety, offline-safe ComfyUI client boundaries, GPU telemetry parsing, FFmpeg validation primitives, AI/autonomy non-executing stubs, public repository hygiene, and 22 passing tests.

Known Sprint 1A gaps that Sprint 1B should address:

- Alembic has a scaffold but no initial migration revision.
- Project, campaign, and job routes are validated stubs and are not DB-backed.
- Queue transitions return audit payloads but do not write `audit_logs`.
- No durable single-GPU queue worker service exists.
- ComfyUI `/object_info` is not cached.
- WebSocket progress monitoring is only a placeholder boundary.
- Benchmark JSONL logging and promotion gate evaluation are not implemented.

## Sprint 1B Scope

Sprint 1B should turn the Sprint 1A foundation into a durable non-generating backend spine:

1. Alembic initial migration.
2. DB-backed project, campaign, and job read/create paths.
3. Durable queue service design for one GPU worker.
4. Audit log writes for queue transitions.
5. ComfyUI object-info cache service.
6. WebSocket progress monitor design and testable protocol parser.
7. Benchmark JSONL logging and promotion gate evaluator.

## Out Of Scope

- No real video generation.
- No model downloads.
- No ComfyUI installation or mutation.
- No direct ComfyUI prompt submission from public API routes.
- No autonomous production execution.
- No parallel GPU generation.
- No polished frontend.
- No raw FFmpeg command execution from user or AI input.

## Vertical Slices

### Slice 1: Initial Alembic Migration

Goal: create a migration-backed schema foundation from SQLAlchemy metadata.

Implementation tasks:

- Generate `backend/alembic/versions/<revision>_initial_schema.py`.
- Ensure migration includes all required Sprint 1A/Sprint 1 autonomy stub tables.
- Add a schema smoke test that creates a fresh SQLite test DB through Alembic.
- Document PostgreSQL verification as pending unless a PostgreSQL URL is provided.

Acceptance criteria:

- `alembic upgrade head` succeeds against a temporary SQLite DB.
- Required tables from `Database/POSTGRES_SCHEMA.sql` and autonomy stubs exist.
- Existing metadata schema test remains green.

Tests:

- `test_alembic_upgrade_creates_required_tables`
- Keep `test_required_schema_tables_exist`

Risk flags:

- PostgreSQL-specific UUID/JSONB defaults may require portable migration patterns for SQLite tests.
- Current SQLAlchemy models are close to the packet but not a byte-for-byte DDL mirror.

### Slice 2: DB-Backed Project And Campaign Routes

Goal: replace in-memory project/campaign stubs with database persistence.

Implementation tasks:

- Add request-scoped DB sessions to project and campaign routes.
- Persist `Project` and `Campaign` rows.
- Return deterministic 404s for missing records.
- Keep response schemas stable.

Acceptance criteria:

- `POST /projects` writes a project.
- `GET /projects/{id}` reads it back.
- `POST /campaigns` requires an existing `project_id`.
- `GET /campaigns/{id}` reads it back.
- Missing project/campaign returns 404.

Tests:

- `test_create_and_get_project_db_backed`
- `test_get_missing_project_returns_404`
- `test_create_campaign_requires_existing_project`
- `test_create_and_get_campaign_db_backed`

Risk flags:

- Tests need isolated DB setup to avoid cross-test state.

### Slice 3: DB-Backed Job Read Path

Goal: make `GET /jobs/{job_id}` read durable `comfy_jobs` state without enabling generation.

Implementation tasks:

- Add a job response mapper from `ComfyJob`.
- Return queue status, workflow run ID, Comfy prompt ID if present, and error info.
- Keep job creation out of public API unless it is an internal test fixture/service.

Acceptance criteria:

- Existing job rows are readable.
- Missing jobs return 404.
- No endpoint submits to ComfyUI.

Tests:

- `test_get_job_reads_comfy_job`
- `test_get_missing_job_returns_404`
- `test_jobs_route_does_not_submit_to_comfyui`

Risk flags:

- `WorkflowRun` and `ComfyJob` test fixtures require valid foreign-key graph.

### Slice 4: Durable Queue Service And Audit Logs

Goal: introduce a service-layer queue transition API that persists state and audit events.

Implementation tasks:

- Add `QueueService.reserve_job`.
- Add `QueueService.transition_job`.
- Persist state changes to `comfy_jobs.status`.
- Write `audit_logs` for every transition.
- Enforce single-worker ownership field design without starting a worker loop.

Acceptance criteria:

- Valid transitions update DB state.
- Invalid transitions rollback and do not create audit rows.
- Audit rows include previous state, new state, reason, and job ID.
- AI proposal code still cannot mutate queue state.

Tests:

- `test_queue_service_valid_transition_persists_status`
- `test_queue_service_invalid_transition_rolls_back`
- `test_queue_transition_writes_audit_log`
- `test_ai_proposal_cannot_request_queue_mutation`

Risk flags:

- Worker ownership and lock semantics differ between SQLite and PostgreSQL.
- Real reservation concurrency should be PostgreSQL-tested before production use.

### Slice 5: ComfyUI Object-Info Cache

Goal: cache `/object_info` snapshots for manifest compatibility checks without requiring ComfyUI in unit tests.

Implementation tasks:

- Add `ObjectInfoCacheService`.
- Support refresh from `ComfyUIClient.get_object_info`.
- Store cache JSON and timestamp in a DB table or storage cache file; DB table is preferred if migration allows.
- Validate workflow manifests against cached object-info.
- Offline refresh must fail gracefully.

Acceptance criteria:

- Object-info can be loaded from a supplied fixture.
- Cache refresh handles ComfyUI offline without crashing the API.
- Workflow manifest object-info validation passes/fails predictably.

Tests:

- `test_object_info_cache_loads_fixture`
- `test_object_info_cache_offline_refresh_graceful`
- `test_manifest_object_info_missing_class_fails`
- `test_manifest_object_info_missing_input_fails`

Risk flags:

- Source docs require `/object_info`, but custom node metadata shapes can vary.

### Slice 6: WebSocket Progress Monitor Design

Goal: add testable WebSocket event parsing and monitor interfaces without submitting real prompts.

Implementation tasks:

- Define progress event schemas.
- Parse execution start, progress, node complete, error, and completion-like events.
- Define fallback handoff to `/history/{prompt_id}`.
- Keep network WebSocket connection behind an interface and mock it in tests.

Acceptance criteria:

- Event parser normalizes known ComfyUI progress events.
- Unknown events are preserved, not discarded.
- Error events classify queue state failure candidates without mutating jobs directly.
- No real WebSocket connection is required in tests.

Tests:

- `test_progress_parser_execution_start`
- `test_progress_parser_progress_update`
- `test_progress_parser_error_event`
- `test_progress_parser_preserves_unknown_event`
- `test_monitor_interface_uses_history_fallback_boundary`

Risk flags:

- ComfyUI WebSocket event shapes may vary by version and custom node behavior.

### Slice 7: Benchmark JSONL Logging And Promotion Gates

Goal: add benchmark event logging and pure promotion decision logic.

Implementation tasks:

- Add benchmark event schema matching `Benchmarks/BENCHMARK_PROTOCOL.md`.
- Add append-only JSONL writer under `storage/benchmarks`.
- Add metric aggregation helpers for peak VRAM, peak RAM, peak temp, duration, and failure rate.
- Add promotion gate evaluator.
- Do not run real benchmark jobs.

Acceptance criteria:

- JSONL writer appends events safely.
- Promotion gate rejects peak VRAM at or above 23GB.
- Promotion gate rejects excessive failure rate.
- Promotion gate can return `promote`, `retry`, or `reject` with reasons.

Tests:

- `test_benchmark_jsonl_writer_appends_event`
- `test_benchmark_peak_metric_aggregation`
- `test_promotion_gate_rejects_high_vram`
- `test_promotion_gate_rejects_failure_rate`
- `test_promotion_gate_promotes_passing_metrics`

Risk flags:

- Benchmark metrics are only as good as future telemetry collection and run labeling.

## Test Plan

Sprint 1B should keep the existing 22 tests passing and add focused tests per slice. The suite should continue to avoid GPU, ComfyUI, model, video, and network requirements. All ComfyUI, WebSocket, and benchmark inputs should use fixtures or mocks.

Minimum expected new tests:

- Alembic upgrade smoke test.
- DB-backed project/campaign route tests.
- DB-backed job read tests.
- Queue service persistence and audit tests.
- Object-info cache and manifest compatibility tests.
- WebSocket event parser tests.
- Benchmark JSONL and promotion gate tests.

## Risk Flags

- SQLite is acceptable for local tests, but queue reservation and worker locking need PostgreSQL validation before production use.
- Alembic migration generation may expose drift between SQLAlchemy metadata and `Database/POSTGRES_SCHEMA.sql`.
- ComfyUI object-info and WebSocket event payloads may vary by runtime version.
- Public repo hygiene must continue to exclude generated DBs, logs, probes, outputs, inputs, benchmarks, snapshots, model files, and secrets.
- No Sprint 1B slice should open an execution path for real generation.

## Recommended First Coding Slice

Start with **Slice 1: Initial Alembic Migration**.

Reason: every DB-backed route, durable queue transition, audit write, object-info cache, and benchmark persistence feature depends on having a migration-backed schema that can be recreated consistently in tests and local development.

