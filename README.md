# CineForge

CineForge is a local AI video-generation orchestration platform. It is designed to be the deterministic execution layer around an isolated ComfyUI runtime, durable backend-owned queues, manifest-validated workflow templates, reproducible provenance, GPU telemetry, and FFmpeg validation/assembly primitives.

## Current Status

This repository is currently at **Sprint 1A backend foundation only**.

What works now:

- FastAPI backend scaffold.
- Configuration loading from `.env`.
- Health endpoints for app, ComfyUI reachability, GPU telemetry, and FFmpeg availability.
- SQLAlchemy schema foundation aligned to the research packet.
- Queue state machine primitives.
- Workflow manifest validation and immutable snapshot writing.
- Path safety helpers.
- Offline-safe ComfyUI client wrapper.
- `nvidia-smi` parser for benchmark telemetry.
- FFmpeg/ffprobe validation primitives.
- Non-executing AI/autonomy schemas and validators.
- Pytest coverage for the Sprint 1A primitives.

What does not work yet:

- No real video generation.
- No model downloads.
- No ComfyUI installation or mutation.
- No autonomous production execution.
- No GPU queue worker yet.
- No polished frontend.
- Project, campaign, and job APIs are validation stubs, not fully DB-backed.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
Copy-Item .env.example .env
.\.venv\Scripts\python scripts\create_db.py
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Run tests:

```powershell
.\.venv\Scripts\python -m pytest
```

## Key Architecture Docs

- `Architecture/ARCHITECTURE_BLUEPRINT.md`
- `MVP/MVP_ARCHITECTURE.md`
- `API/BACKEND_API_FLOW.md`
- `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`
- `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`
- `ComfyUI/HEADLESS_COMFYUI_API.md`
- `Database/POSTGRES_SCHEMA.sql`
- `Benchmarks/BENCHMARK_PROTOCOL.md`
- `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md`
- `Orchestration/OPTIONAL_AI_ORCHESTRATION_LAYER.md`
- `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`
- `docs/SPRINT_1A_STATUS.md`

## Safety Boundary

CineForge is intended to remain the deterministic execution engine. AI modules are advisory only in Sprint 1A and cannot directly mutate workflow JSON, queue state, database records, model registries, ComfyUI submissions, asset paths, or FFmpeg commands.

