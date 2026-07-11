# Implementation Matrix

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

| Area | Capability | Status | Main Source Files | Tests | Evidence | Known Gap |
|---|---|---|---|---|---|---|
| Backend API | FastAPI app and health/runtime routes | implemented | `backend/app/main.py`; `backend/app/api/routes/health.py` | `backend/tests/test_health.py` | Root/health/runtime endpoints tested; current phase reports controlled submission backend capability | No production deployment config |
| Projects/Campaigns | DB-backed create/list/get | implemented | `backend/app/api/routes/projects.py`; `backend/app/api/routes/campaigns.py` | `backend/tests/test_project_campaign_routes.py` | Tests cover persistence and 404s | Minimal CRUD only |
| Jobs API | Read-only DB-backed job list/get | implemented | `backend/app/api/routes/jobs.py` | `backend/tests/test_job_routes.py` | No public mutation endpoint | No job creation API |
| Database | SQLAlchemy schema and Alembic migrations | implemented | `backend/app/db/base.py`; `backend/alembic/versions/*.py` | `backend/tests/test_db_schema.py`; `backend/tests/test_postgres_schema.py` | SQLite/offline tests pass; PostgreSQL tests skip/block if DB absent | Reference SQL drift must be tracked |
| Queue claim | Pending job claim with PostgreSQL SKIP LOCKED | implemented | `backend/app/services/queue/service.py` | `test_queue_service.py`; `test_postgres_queue_claim.py` | Code uses `with_for_update(skip_locked=True)` for PostgreSQL | PostgreSQL unavailable in this run |
| Queue recovery | Reserved-job heartbeat/stale recovery/timeout | implemented | `backend/app/services/queue/service.py` | `test_queue_service.py`; `test_queue_worker.py` | Tests cover wrong worker, terminal states, requeue, timeout, metadata, audit | Submitted/running recovery still future |
| Worker skeleton | Bounded run_once/run_batch/heartbeat/recover/preflight/submission delegation | partially_implemented | `backend/app/services/queue/worker.py` | `test_queue_worker.py`; `test_controlled_submission.py` | No daemon; delegates only | No live recurring worker loop |
| Controlled submission | Worker-only adapter-backed `/prompt` submission service | partially_implemented | `backend/app/services/comfy/submission.py` | `test_controlled_submission.py` | Readiness checked, adapter injected, public route absent | No live Comfy smoke; output/progress absent |
| Comfy generic client | Health/object_info/queue and blocked mutation/runtime routes | implemented | `backend/app/services/comfy/client.py` | `test_comfy_client.py` | Mutation methods raise blocked errors even with `allow_mutation` | Controlled adapter is separate |
| Progress monitoring | Event parser/history fallback boundary | scaffold_only | `backend/app/services/comfy/progress_monitor.py` | `test_progress_monitor.py` | Parser tested with fixtures | No live WebSocket loop or DB persistence |
| Workflow mutation | Manifest validation, patch plan, immutable snapshots | implemented | `backend/app/services/workflows/template_service.py` | `test_workflow_manifest_validation.py` | Validates SHA, node class/input, object_info optional | Only smoke workflow checked |
| Frontend UI | React/Vite dashboard/control surface | partially_implemented | `frontend/src/*` | not run; npm build/lint blocked | UI files present, package scripts defined | Build unverified due missing node_modules |
| FFmpeg | Health/probe/compatibility/template validators | implemented | `backend/app/services/ffmpeg/service.py` | `test_ffmpeg_service.py` | Pure validation and health covered | No assembly execution |
| Telemetry | `nvidia-smi` parser and health | implemented | `backend/app/services/telemetry/gpu.py` | `test_gpu_telemetry_parser.py` | Parser handles WDDM `N/A` fields | No long-running sampler |
| Benchmarks | JSONL logging, metrics, promotion gates | implemented | `backend/app/services/benchmarks/*.py` | `test_benchmark_services.py` | Pure gates tested | No real benchmark runner |
| AI proposals | Forbidden-field validation | implemented | `backend/app/services/ai_orchestration/*` | `test_ai_proposal_validator.py` | Rejects direct queue/workflow/DB/shell/etc fields | No proposal persistence workflow |
| Autonomy | Schema stubs only | scaffold_only | `backend/app/services/autonomy/schemas.py` | covered indirectly | Execution raises `RuntimeError` | No autonomous behavior |
| Model/LoRA registries | DB tables and planning docs | scaffold_only | `backend/app/db/base.py`; `Models/`; `LoRAs/` | `test_db_schema.py` | Tables and docs exist | No registry CRUD/import/download |
