# Source Digests

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

## `backend/app/services/queue/service.py`

Purpose: central queue service for readiness, pending job claim, heartbeat, stale recovery, transition audit. Key facts: PostgreSQL claim and recovery use `FOR UPDATE SKIP LOCKED`; no-op heartbeat returns without commit; readiness validates worker ownership, reserved status, prompt absence, workflow snapshot, manifest, and object_info compatibility. Source of truth: yes.

## `backend/app/services/queue/worker.py`

Purpose: bounded worker boundary. Key facts: `run_once` claims a pending job; `run_batch` is bounded; heartbeat/recovery/preflight/controlled submission are explicit single-step methods. No daemon startup. Source of truth: yes.

## `backend/app/services/comfy/submission.py`

Purpose: controlled worker-only prompt submission path. Key facts: requires injected adapter, evaluates readiness, transitions through validating, handles adapter errors, node_errors, missing prompt_id, and marks submitted with audit. Concern: this is the first actual prompt submission capability, so it must stay worker-only and unexposed publicly. Source of truth: yes.

## `backend/app/services/comfy/client.py`

Purpose: external ComfyUI client with mutation/runtime blockers. Key facts: health/object_info/queue are HTTP reads; generic mutation and output/history/websocket methods raise blocked errors. Source of truth: yes.

## `backend/app/services/workflows/template_service.py`

Purpose: manifest-driven workflow validation and immutable snapshot writing. Key facts: validates SHA, node IDs, class_type, inputs, object_info refs; sanitizes output prefix. Source of truth: yes.

## `backend/app/db/base.py`

Purpose: SQLAlchemy schema. Key facts: includes queue/job ownership, registries, workflow runs/templates, assets, FFmpeg jobs, audit/error logs, autonomy stubs. Source of truth: yes.

## `frontend/src/api/client.ts` and `frontend/src/pages/*`

Purpose: local control dashboard. Key facts: calls backend health/runtime/project/campaign/job endpoints; exposes disabled runtime actions and no public generation. Source of truth: yes for UI code; build status uncertain.

## `docs/SPRINT_1C_PLAN.md`

Purpose: current-ish plan digest. Key facts: records completed queue/recovery/preflight work and says submitted/running recovery remains future. Source of truth: supporting only; code wins.

## `README.md`

Purpose: setup overview. Concern: status section is stale and says Sprint 1A/no polished frontend. Source of truth: no for implementation status; yes for broad setup commands only.

## `docs/UI_MVP_STATUS.md`

Purpose: current UI status and endpoints. Key facts: lists pages, integrated endpoints, disabled generation behavior, and next recommended readiness/telemetry work. Source of truth: supporting, current.

## `Benchmarks/BENCHMARK_PROTOCOL.md`

Purpose: future benchmark target. Key facts: 24GB RTX 5090 laptop constraints, telemetry, promotion gates. Source of truth: target policy, not implementation.
