# Repository Map

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

## Concise Tree

```text
.
|-- backend/                 FastAPI backend, services, Alembic, tests
|-- frontend/                React/Vite TypeScript MVP dashboard
|-- docs/                    sprint/status/API/corpus docs
|-- Architecture/            high-level system architecture packet
|-- MVP/                     MVP architecture packet
|-- Runtime/                 runtime isolation and queueing policy
|-- ComfyUI/                 headless ComfyUI API notes
|-- Database/                PostgreSQL reference schema and JSON schemas
|-- Workflows/               workflow mutation strategy
|-- storage/                 tracked placeholders and smoke workflow template
|-- Models/, LoRAs/          feasibility/compatibility matrices
|-- Benchmarks/              benchmark protocol
|-- FFmpeg/                  FFmpeg strategy and command library
|-- Orchestration/           optional AI/autonomy architecture
|-- Risk-Register/           risk register
|-- scripts/                 local DB helper
|-- pyproject.toml           backend Python package and dev dependencies
|-- frontend/package.json    frontend scripts/dependencies
```

## Important Entry Points

- `backend/app/main.py`: FastAPI app.
- `backend/app/api/routes/health.py`: health, root, runtime status.
- `frontend/src/App.tsx`: UI page shell.
- `frontend/src/api/client.ts`: frontend API client.
- `scripts/create_db.py`: local DB creation helper.

## Configuration Files

- `.env.example`: placeholder local config; no secrets.
- `pyproject.toml`: Python deps/tests.
- `alembic.ini`: migration config.
- `frontend/package.json`, `frontend/tsconfig*.json`, `frontend/vite.config.ts`, `frontend/eslint.config.js`: frontend toolchain.

## Schemas And Migrations

- `backend/app/db/base.py`: SQLAlchemy source.
- `backend/alembic/versions/*.py`: migrations.
- `Database/POSTGRES_SCHEMA.sql`: reference schema.
- `Database/JSON_SCHEMAS.md`: planning schemas.

## Services

- Queue: `backend/app/services/queue/service.py`, `worker.py`.
- ComfyUI: `backend/app/services/comfy/*.py`.
- Workflow templates: `backend/app/services/workflows/template_service.py`.
- FFmpeg: `backend/app/services/ffmpeg/service.py`.
- Telemetry: `backend/app/services/telemetry/gpu.py`.
- Benchmarks: `backend/app/services/benchmarks/*.py`.
- AI/autonomy stubs: `backend/app/services/ai_orchestration/`, `autonomy/`, `policy/`, `qa/`, `retry/`, `batch_planner/`.

## Tests

- `backend/tests/test_queue_service.py`, `test_queue_worker.py`, `test_postgres_queue_claim.py`, `test_postgres_schema.py`: queue/DB behavior.
- `backend/tests/test_controlled_submission.py`, `test_comfy_client.py`: controlled submission and Comfy boundary.
- `backend/tests/test_project_campaign_routes.py`, `test_job_routes.py`, `test_health.py`: API behavior.
- Other tests cover FFmpeg, telemetry, workflows, path safety, benchmarks, progress monitor, AI proposal validation.

## Workflows And Storage

- `storage/workflow_templates/example_smoke/`: dummy manifest/workflow for validation tests.
- `storage/*/.gitkeep`: placeholders only; generated outputs/probes/logs are excluded.

## Documentation

- Current-ish: `docs/SPRINT_1C_PLAN.md`, `docs/UI_MVP_STATUS.md`.
- Stale/older: `README.md`, `docs/API_CONTRACT.md`, `docs/POSTGRES_VERIFICATION.md`, `docs/SPRINT_1A_STATUS.md`, parts of `docs/SPRINT_1B_CLOSEOUT.md`.
- Architecture packet: top-level folders such as `Architecture/`, `MVP/`, `Runtime/`, `Benchmarks/`, `Risk-Register/`.
