# Sprint 1C Plan

Date: 2026-05-26

## Current State

Sprint 1A established the backend foundation. Sprint 1B completed the non-generating durable spine:

- Alembic initial migration exists and is SQLite-smoke-tested.
- Project and campaign routes are DB-backed.
- Job read path is DB-backed.
- `QueueService` can transition and reserve `ComfyJob` rows and write `audit_logs`.
- ComfyUI object_info compatibility checks are available through an in-memory cache.
- WebSocket progress event parsing and `/history/{prompt_id}` fallback boundaries exist.
- Benchmark JSONL logging and pure promotion gates exist.
- Test suite currently passes with `55 passed`.

Known Sprint 1B limitations that Sprint 1C should address before real generation:

- PostgreSQL schema and migration behavior are not verified in this workspace.
- Queue reservation is service-layer only and has no DB-level concurrent worker locking.
- `comfy_jobs` has no worker ownership, heartbeat, reservation timestamp, timeout, or retry metadata.
- No queue worker loop exists.
- No code submits prompts to ComfyUI.
- No progress events are persisted to the database.
- Benchmark services do not run real benchmarks.

## Sprint 1C Goals

Sprint 1C should prove database correctness and worker-safety before any ComfyUI prompt submission is allowed:

1. Verify the Alembic schema against PostgreSQL.
2. Design and migrate worker-safe queue reservation fields.
3. Implement DB-level locking semantics for single-GPU job reservation.
4. Define timeout and recovery policy for reserved, submitted, and running jobs.
5. Persist audit logs for worker claims, releases, failures, timeouts, and recovery.
6. Add a safe queue worker boundary that can be tested without live generation.
7. Define explicit gates that must pass before enabling ComfyUI `/prompt` submission.

## Out Of Scope

- No real video generation.
- No model downloads.
- No ComfyUI runtime installation, mutation, restart, or prompt submission.
- No live queue worker loop that processes real jobs.
- No live WebSocket monitoring loop.
- No benchmark execution.
- No autonomous execution.
- No public API route that directly mutates queue state.
- No model registry mutation.

## Single-GPU Safety Rules

- The backend database queue remains the source of truth, not ComfyUI's internal queue.
- At most one GPU generation job may be owned by a worker at a time.
- ComfyUI queue depth should remain shallow, ideally 0-1.
- Job reservation must be atomic under PostgreSQL concurrency.
- A worker must have a durable identity and heartbeat before claiming jobs.
- Stale reservations must be recoverable without double-submitting to ComfyUI.
- Timeout recovery must prefer conservative failure states over duplicate execution.
- FFmpeg/post-processing work must remain separate from GPU diffusion scheduling.
- Any future ComfyUI mutation must be behind a worker-only boundary, never a public API route.

## No-ComfyUI-Generation Boundary

Sprint 1C must not call `ComfyUIClient.submit_prompt`, upload images, interrupt jobs, clear queues, free memory, or open a live WebSocket against ComfyUI. Tests should use mocks, fakes, temporary SQLite where appropriate, and PostgreSQL only for explicit schema/locking verification.

Before ComfyUI prompt submission is allowed in a later sprint, the project must prove:

- PostgreSQL migrations apply cleanly from an empty database.
- Queue reservation is atomic under concurrent workers.
- Worker ownership and heartbeat fields prevent duplicate claims.
- Timeout and recovery behavior is deterministic and audited.
- Workflow manifests pass object_info compatibility checks.
- Patched workflow snapshots are persisted before submission.
- Queue transition audit logs are complete enough to reconstruct worker decisions.
- WebSocket progress and history fallback events have a persistence plan.
- Benchmark and thermal safety gates are ready for generated workload validation.

## Vertical Slices

### Slice 1: PostgreSQL Schema Verification

Goal: verify the current Alembic schema against PostgreSQL, not only SQLite.

Implementation tasks:

- Add a PostgreSQL-gated test configuration that runs only when a test database URL is provided.
- Run `alembic upgrade head` against an empty PostgreSQL database.
- Inspect required tables, indexes, JSONB columns, UUID columns, foreign keys, and enum-compatible status columns.
- Compare drift against `Database/POSTGRES_SCHEMA.sql` and document intentional differences.
- Keep SQLite smoke tests as the default offline suite.

Acceptance criteria:

- PostgreSQL `alembic upgrade head` succeeds when `CINEFORGE_TEST_POSTGRES_URL` or equivalent is configured.
- Required Sprint 1A and 1B tables exist.
- `comfy_jobs`, `workflow_runs`, and `audit_logs` constraints are verified.
- Tests skip clearly when no PostgreSQL URL is configured.

Required tests:

- `test_postgres_alembic_upgrade_head`
- `test_postgres_required_tables_exist`
- `test_postgres_queue_tables_have_expected_columns`
- `test_postgres_schema_check_skips_without_url`

Risk flags:

- SQLite tests cannot prove PostgreSQL UUID, JSONB, locking, isolation, or enum behavior.
- Existing SQLAlchemy metadata may intentionally differ from `Database/POSTGRES_SCHEMA.sql`; drift must be explicit.

### Slice 2: Worker Ownership Schema Design

Goal: add durable fields needed for safe worker reservation and recovery.

Implementation tasks:

- Design ownership fields for `comfy_jobs`, likely including `worker_id`, `reserved_at`, `heartbeat_at`, `attempt_count`, `last_state_change_at`, and recovery/error metadata.
- Add SQLAlchemy model fields and Alembic migration.
- Preserve existing job read response compatibility.
- Update queue audit detail requirements to include worker ownership data when available.

Acceptance criteria:

- Migration applies on SQLite and PostgreSQL.
- Existing job read route still works.
- New fields are nullable or defaulted so existing rows remain valid.
- No worker loop or ComfyUI call is introduced.

Required tests:

- `test_queue_worker_fields_exist_in_metadata`
- `test_alembic_upgrade_includes_worker_ownership_fields`
- `test_existing_job_read_works_with_worker_fields`
- `test_queue_audit_details_include_worker_metadata_when_present`

Risk flags:

- Ownership fields must support PostgreSQL locking without overfitting to SQLite.
- Timestamp semantics should use timezone-aware values consistently.

### Slice 3: PostgreSQL Atomic Reservation Service

Goal: make job reservation atomic for competing workers.

Implementation tasks:

- Add a PostgreSQL reservation query using row-level locking, likely `FOR UPDATE SKIP LOCKED`.
- Reserve only `pending` jobs.
- Persist `reserved`, `worker_id`, `reserved_at`, `heartbeat_at`, and attempt count in one transaction.
- Write an audit log in the same transaction.
- Keep a SQLite fallback for unit tests that does not claim to prove concurrency.

Acceptance criteria:

- Two concurrent PostgreSQL reservation attempts cannot claim the same job.
- Only pending jobs can be reserved.
- Reservation writes status and audit atomically.
- Failed reservations do not write audit rows.

Required tests:

- `test_postgres_concurrent_reservation_claims_job_once`
- `test_reserve_next_job_skips_non_pending_jobs`
- `test_reserve_next_job_writes_worker_ownership`
- `test_reserve_next_job_writes_audit_log`
- `test_reserve_next_job_returns_none_when_no_pending_jobs`

Risk flags:

- SQLite cannot validate `SKIP LOCKED` or real transaction isolation.
- Concurrent tests can be flaky if the PostgreSQL test database is underpowered or shared.

### Slice 4: Timeout And Recovery Policy

Goal: define deterministic recovery for stale reserved/submitted/running jobs without duplicate generation.

Implementation tasks:

- Add pure policy functions for timeout classification.
- Define stale thresholds for `reserved`, `submitted`, and `running`.
- Add service methods for marking stale jobs as `timeout`, `interrupted`, or recovery candidates.
- Write audit logs for recovery decisions.
- Avoid any ComfyUI `/interrupt`, `/queue`, or `/free` calls in this slice.

Acceptance criteria:

- Stale reserved jobs can be released or failed according to policy.
- Stale submitted/running jobs are not blindly requeued.
- Every recovery action writes an audit log.
- Recovery is idempotent when run repeatedly.

Required tests:

- `test_reserved_job_timeout_marks_timeout`
- `test_running_job_timeout_requires_conservative_recovery`
- `test_recovery_writes_audit_log`
- `test_recovery_is_idempotent`
- `test_non_stale_job_not_recovered`

Risk flags:

- Recovery policy must avoid duplicate ComfyUI submissions.
- Real runtime behavior may require adjusting thresholds after smoke tests.

### Slice 5: Worker Boundary Skeleton

Goal: introduce a worker interface that can reserve and transition jobs without submitting to ComfyUI.

Implementation tasks:

- Define a `QueueWorker` or `WorkerService` boundary with one-step methods such as `claim_once`, `heartbeat_once`, and `recover_once`.
- Keep execution dry-run only.
- Inject dependencies for queue service, clock, and ComfyUI submission adapter, but use a disabled/fake adapter by default.
- Ensure public API routes do not call worker mutation methods.

Acceptance criteria:

- Worker boundary can claim a pending job in dry-run mode.
- Worker heartbeat updates ownership metadata.
- Worker boundary cannot submit to ComfyUI in Sprint 1C.
- Public routes remain read-only for jobs.

Required tests:

- `test_worker_claim_once_reserves_pending_job`
- `test_worker_heartbeat_updates_worker_metadata`
- `test_worker_boundary_does_not_submit_to_comfyui`
- `test_public_routes_do_not_mutate_queue`

Risk flags:

- A worker skeleton can become an accidental execution path if mutation guards are weak.
- Dependency injection must make unsafe adapters impossible to use by default.

### Slice 6: Submission Readiness Gate

Goal: create a checklist and pure gate evaluator that must pass before future prompt submission.

Implementation tasks:

- Add a pure readiness evaluator for queue, workflow, object_info, storage, and benchmark prerequisites.
- Return pass/fail with reasons.
- Include checks for PostgreSQL verification, object_info freshness, manifest validation, snapshot persistence, queue ownership, and benchmark policy readiness.
- Do not submit prompts.

Acceptance criteria:

- Gate rejects missing PostgreSQL verification.
- Gate rejects missing object_info snapshot.
- Gate rejects missing workflow snapshot.
- Gate rejects unsafe benchmark/promotion status.
- Gate can pass only when all prerequisites are explicitly supplied.

Required tests:

- `test_submission_gate_rejects_missing_postgres_verification`
- `test_submission_gate_rejects_missing_object_info`
- `test_submission_gate_rejects_missing_workflow_snapshot`
- `test_submission_gate_rejects_unpromoted_benchmark_profile`
- `test_submission_gate_accepts_complete_prerequisites`

Risk flags:

- A readiness gate is only useful if future submission code is required to call it.
- Benchmark readiness may initially be a policy placeholder until real benchmark execution exists.

## PostgreSQL-Specific Risks

- UUID and JSONB behavior cannot be proven by SQLite.
- `SELECT ... FOR UPDATE SKIP LOCKED` has no SQLite equivalent.
- Transaction isolation, deadlock behavior, and lock wait timeouts require PostgreSQL tests.
- Concurrent worker tests need isolated test databases and cleanup.
- Alembic migrations may reveal drift between SQLAlchemy metadata and the reference SQL file.
- PostgreSQL timestamp timezone behavior must be checked before using heartbeat and timeout logic.

## SQLite Limitations

- SQLite remains useful for fast default unit tests and route tests.
- SQLite cannot prove row-level locking, concurrent reservation, `SKIP LOCKED`, JSONB semantics, or production isolation behavior.
- SQLite fallback reservation tests must be labeled as functional tests, not concurrency proof.

## Audit Logging Requirements

Queue and worker audit logs should include:

- `entity_type = "comfy_job"`
- `entity_id = job.id`
- action names such as `queue_transition`, `worker_claim`, `worker_heartbeat`, `worker_release`, `worker_timeout`, `worker_recovery`, and `worker_failure`
- previous state and new state
- reason
- actor
- worker_id
- attempt count when available
- timeout threshold and observed age for recovery decisions
- Comfy prompt ID only after a future submission path is explicitly enabled

Invalid transitions, failed claims, and rolled-back recovery attempts must not create misleading success audit rows.

## Recommended First Coding Slice

Start Sprint 1C with **Slice 1: PostgreSQL Schema Verification**.

Reason: worker-safe reservation depends on PostgreSQL behavior. The project should prove migrations, queue table shape, UUID/JSONB behavior, and test-database setup before adding worker ownership fields or lock-based reservation code.
