# Architecture Map

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

## Frontend

- `frontend/src/App.tsx`: page shell router for Dashboard, Projects, Campaigns, Jobs, Queue, Runtime, System Health, Roadmap.
- `frontend/src/api/client.ts`: typed fetch client for `/`, health, runtime, project, campaign, and job endpoints.
- `frontend/src/pages/*`: operational dashboard and read-only safety surfaces. No public generation UI.

## Backend

- `backend/app/main.py`: FastAPI app factory, CORS for local Vite origins, API router.
- `backend/app/api/router.py`: includes health, projects, campaigns, jobs.
- `backend/app/api/routes/*.py`: DB-backed project/campaign/job reads and creates; runtime health/status; no `/prompt` route.
- `backend/app/core/config.py`: `.env` based settings, external ComfyUI base URL, storage roots, queue worker disabled by default.

## Database

- `backend/app/db/base.py`: SQLAlchemy models for projects, campaigns, workflows, queue jobs, assets, FFmpeg jobs, registries, audit/error logs, AI/autonomy stubs.
- `backend/alembic/versions/5a7d666d11d1_initial_schema.py`: initial schema.
- `backend/alembic/versions/c4f8d3f2e1a9_add_comfy_job_worker_ownership.py`: worker ownership fields.
- `Database/POSTGRES_SCHEMA.sql`: research/reference DDL, not necessarily byte-identical to SQLAlchemy.

## Queue And Worker

- `backend/app/queue/state_machine.py`: canonical queue states and transitions.
- `backend/app/services/queue/service.py`: claim, heartbeat, recovery, transitions, submission readiness. PostgreSQL claim/recovery use `FOR UPDATE SKIP LOCKED` when dialect is PostgreSQL.
- `backend/app/services/queue/worker.py`: bounded `run_once`, `run_batch`, heartbeat/recovery delegation, preflight, controlled submission call. No daemon startup.

## ComfyUI Integration

- `backend/app/services/comfy/client.py`: read-only health/object_info/queue methods; mutation/runtime output routes blocked in generic client.
- `backend/app/services/comfy/object_info_cache.py`: object_info fixture/cache validation for workflow manifests.
- `backend/app/services/comfy/progress_monitor.py`: progress event parser and history fallback boundary.
- `backend/app/services/comfy/submission.py`: controlled worker-only prompt submission via injected adapter; marks submitted/failure states and audit logs.

## Workflow Mutation

- `backend/app/services/workflows/template_service.py`: manifest validation, runtime patch planning, value validation, immutable workflow snapshot writing.
- `storage/workflow_templates/example_smoke/*`: dummy smoke workflow template, not production generation.

## Model And LoRA Registries

- `backend/app/db/base.py`: `Model`, `ModelVariant`, `Lora`, `LoraCombination`, `LoraCombinationItem`, `Quantization`, `TextEncoder`, `VAE`.
- `Models/MODEL_FEASIBILITY_MATRIX.md` and `LoRAs/LORA_COMPATIBILITY_MATRIX.md`: planning/reference guidance. Registry mutation workflows are not implemented.

## Telemetry

- `backend/app/services/telemetry/gpu.py`: `nvidia-smi` CSV parser and health probe.
- `Benchmarks/BENCHMARK_PROTOCOL.md`: required future benchmark telemetry.

## FFmpeg

- `backend/app/services/ffmpeg/service.py`: ffmpeg/ffprobe health, probe JSON saving, stream-copy compatibility, approved command template IDs. No assembly runner endpoint.

## Benchmark System

- `backend/app/services/benchmarks/logger.py`: JSONL event writer and metric aggregation.
- `backend/app/services/benchmarks/promotion.py`: pure promotion/retry/reject gate. No real benchmark execution.

## AI Orchestration And Autonomy Boundaries

- `backend/app/services/ai_orchestration/*`: proposal schema and forbidden-field validator.
- `backend/app/services/autonomy/schemas.py`: scaffold-only autonomy state and execution refusal.
- `Orchestration/*.md`: advisory/future autonomy architecture.

## Major Invariants

- Backend DB queue is source of truth.
- Single GPU generation must be serialized.
- Public API/UI must not submit prompts.
- ComfyUI stays external/isolated.
- Agents may propose but not mutate workflow JSON, queue, DB, registry, assets, or FFmpeg commands.
- Generated assets, logs, model files, DBs, and secrets stay out of Git/corpus.
