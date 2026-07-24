# CineForge

CineForge is a local AI video-generation orchestration platform. It is designed to be the deterministic execution layer around an isolated ComfyUI runtime, durable backend-owned queues, manifest-validated workflow templates, reproducible provenance, GPU telemetry, and FFmpeg validation/assembly primitives.

## Current Status

This repository includes **Storyboard Phase A**, a planning-only foundation that ends with an approved, editable production plan.

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
- Persisted `Project -> Story -> Chapter -> Scene -> Shot` planning hierarchy.
- Storyboard readiness checks, duration rollups, immutable approval versions, JSON and CSV planning exports.
- Storyboard Studio frontend views for planning, assets, routing, workflows, exports, and settings.

What does not work yet:

- No real video generation.
- No model downloads.
- No ComfyUI installation or mutation.
- No autonomous production execution.
- No GPU queue worker yet.
- No image/video generation is triggered by Storyboard Phase A approval.
- Project, campaign, and job APIs are validation stubs, not fully DB-backed.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
Copy-Item .env.example .env
.\.venv\Scripts\python scripts\create_db.py
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

### One-command supervised startup

Start the complete local stack from the repository root:

```powershell
.\start-cineforge.cmd
```

The trusted launcher starts ComfyUI, the FastAPI backend, and the Vite frontend in that
order. It reuses services that already pass their full readiness probes, writes logs and
owned process metadata under `storage/runtime/supervisor/`, and stops only processes it
started when you press Ctrl+C. Run `.\start-cineforge.cmd --check` for a read-only
configuration and readiness check.

Administrator overrides are supported through `CINEFORGE_COMFYUI_WORKING_DIR`,
`CINEFORGE_COMFYUI_LAUNCHER`, `CINEFORGE_PYTHON_EXECUTABLE`, and
`CINEFORGE_NPM_EXECUTABLE`. These values are local configuration only; no API request,
story text, AI proposal, or prompt can supply an executable path or shell command.
Readiness URLs are restricted to loopback HTTP origins, shell metacharacters are rejected
from command paths, ports and timeouts are range-checked, and a singleton lock prevents
competing supervisors. Logs rotate at 10 MiB per stream.

### ComfyUI auto-start contract

Starting CineForge must also start the explicitly configured external ComfyUI runtime when it is not already reachable. ComfyUI remains an isolated process; CineForge must not import it in-process or treat a listening port alone as generation readiness.

The startup orchestrator must:

1. Read an administrator-configured ComfyUI working directory and launcher path. On the primary Windows workstation, the current runtime is `C:\AI\ComfyUI_windows_portable` and its launcher is `run_nvidia_gpu.bat`.
2. Probe `CINEFORGE_COMFYUI_BASE_URL` before launching. If ComfyUI is already healthy, reuse it and do not start a duplicate process.
3. Start the configured launcher as a hidden background child process with the configured runtime directory as its working directory. AI-authored text must never become a shell command or executable path.
4. Wait for both the ComfyUI root endpoint and `/object_info` to respond within a bounded timeout. Only then may CineForge report ComfyUI as ready.
5. Fail honestly: if startup or `/object_info` validation fails, keep planning available, block image/video generation, and show the exact runtime-readiness blocker. Never display a generated, reviewed, approved, or playable state for media that does not exist.
6. Record whether CineForge owns the child process. On shutdown, CineForge may stop only the process it started; it must not terminate an independently running ComfyUI instance.
7. Never install, update, download models, mutate custom nodes, or weaken host security as part of auto-start.

Auto-start does not by itself enable generation. Image generation additionally requires an enabled backend worker/submission path, a validated workflow manifest compatible with live `/object_info`, registered model evidence, output collection, and provenance persistence. Video generation remains a separately gated phase.

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

See `docs/STORYBOARD_PHASE_A_SPEC.md` for the planning boundary and `docs/PRODUCT_VISION.md` for current product direction. Older sprint documents are historical implementation records, not product direction.

