# CineForge

CineForge is a local AI video-generation orchestration platform. It is designed to be the deterministic execution layer around an isolated ComfyUI runtime, durable backend-owned queues, manifest-validated workflow templates, reproducible provenance, GPU telemetry, and FFmpeg validation/assembly primitives.

## Current Status

This repository includes **Storyboard Phase A**, a planning-only foundation that ends with an approved, editable production plan.

What works now:

- FastAPI backend scaffold.
- Configuration loading from `.env`.
- Health endpoints for app plus explicit/operator-invoked ComfyUI reachability, GPU telemetry, and FFmpeg availability probes; frontend local readiness pages no longer auto-call the live probes.
- SQLAlchemy schema foundation aligned to the research packet.
- Queue state machine primitives.
- Workflow manifest validation and immutable snapshot writing.
- DB-free local runtime catalog for the selected LTX-2.3 Distilled 1.1 FP8 artifact.
- Local archetype catalog covering the canonical `CF-IMG-01`..`CF-IMG-05`, `CF-VID-01`..`CF-VID-05`, `CF-UTIL-01`, and `CF-POST-01` set as disabled/gated planning records plus exactly 64 disabled/gated presets.
- File-backed local job, semantic-generation, post-production, recipe-command, and operator-review manifests that prepare offline evidence without submitting prompts or executing FFmpeg/ffprobe.
- Path safety helpers.
- Offline-safe ComfyUI client wrapper.
- `nvidia-smi` parser for benchmark telemetry.
- FFmpeg/ffprobe validation primitives and structured allowlisted recipe builders; current local APIs persist/read manifests only and do not execute media tools.
- Non-executing AI/autonomy schemas and validators.
- Pytest coverage for the Sprint 1A primitives.
- Persisted `Project -> Story -> Chapter -> Scene -> Shot` planning hierarchy.
- Storyboard readiness checks, duration rollups, immutable approval versions, JSON and CSV planning exports.
- Storyboard Studio frontend views for planning, assets, routing, workflows, exports, and settings.

What does not work yet:

- No general user-facing or preset-enabled production video generation.
- No autonomous production execution.
- No live benchmark ladder evidence, recovery/OOM exercise, or human QA sign-off.
- No app-level ComfyUI Manager/download/update enforcement yet.
- A GPU queue-worker skeleton exists (`backend/app/services/queue/worker.py`), but it is not production-enabled for public/preset generation.
- No image/video generation is triggered by Storyboard Phase A approval.
- Project and campaign APIs are still planning/scaffold surfaces; `/local-jobs`, `/local-generation/*`, `/local-post-production/*`, and `/local-operator/packets` are file-backed/offline-only unless a separate future operator-approved live runner is added.

## Default video policy (2026-07)

- Product key: `ltx2_3_22b_distilled_1_1_fp8`.
- Source identity: official LTX-2.3 22B Distilled **1.1**; the BF16 source checkpoint is not itself an FP8 artifact.
- Runtime precision: proven FP8 only via a recorded method (`loader_level`, `converted_derivative`, or `official_artifact`); never silently substitute a non-1.1 FP8 file.
- M0 records a local full-checkpoint FP8 artifact as `converted_derivative`; CF-VID-01 has passed a minimal local T2V smoke, but admission remains `benchmark_required` until conversion provenance, full benchmark evidence, recovery behavior, and human QA are recorded.
- `/local-runtime/catalog`, `/local-runtime/local-mvp-readiness`, and fail-closed `/local-runtime/public-readiness` expose the DB-free local model/output/readiness contract; `/local-presets`, `/local-archetypes`, `/local-jobs`, `/local-generation/*`, `/local-operator/approval-templates`, `/local-operator/runbooks`, and `/local-operator/packets` expose the local file-backed ComfyUI lane without submitting generation.
- Outputs are saved under the local ComfyUI output root (`C:\AI\ComfyUI_windows_portable\ComfyUI\output` by default), with one sanitized folder per CineForge project and safe `filename_prefix=<project-folder>/<run-stem>`.
- Wan and older LTXV lanes are historical or optional secondary evidence, disabled by default.
- Storyboard approval does not automatically start generation.

See `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md`, `docs/SAFE_LOCAL_ENDPOINTS.md`, `docs/LOCAL_OPERATOR_LIVE_BOUNDARY.md`, `docs/OFFLINE_SAFE_VALIDATION.md`, `Models/MODEL_FEASIBILITY_MATRIX.md`, `Benchmarks/BENCHMARK_PROTOCOL.md`, `docs/RUNTIME_INVENTORY.md`, and `docs/CFVID01_RUNTIME_SMOKE.md`.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
Copy-Item .env.example .env
.\.venv\Scripts\python scripts\create_db.py
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

### ComfyUI auto-start contract (required, not yet implemented)

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

Run the static safe/local boundary check:

```powershell
.\.venv\Scripts\python scripts\validate_safe_local_boundary.py
```

Run the curated offline-safe validation suite. It runs static boundary checks, selected backend tests, frontend lint/build, `git diff --check`, and prints the checkpoint watchdog restart banner:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py
```

Current checkpoint result: `232 passed`, frontend lint/build passed, static boundary validation passed, `git diff --check` passed, and the checkpoint watchdog banner printed; the suite remains no-live/offline-safe.

Checkpoint watchdog helpers. A watchdog/status check is not a stopping point; after reading it, immediately continue the offline-safe loop unless blocked by the live boundary. `--fail-on-dirty` fails on dirty tracked files or source/docs/test/config-like untracked files while ignored local watchdog JSON artifacts remain excluded.

```powershell
.\.venv\Scripts\python scripts\checkpoint_watchdog.py --json
.\.venv\Scripts\python scripts\checkpoint_watchdog.py --fail-on-dirty
```

## Key Architecture Docs

- `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md` — current corrected ComfyUI/LTX implementation authority.
- `docs/RUNTIME_INVENTORY.md` — M0 local runtime and artifact inventory; not a readiness claim.
- `Models/MODEL_FEASIBILITY_MATRIX.md`
- `Benchmarks/BENCHMARK_PROTOCOL.md`
- `Sources/SOURCE_REGISTER.md`
- `Architecture/ARCHITECTURE_BLUEPRINT.md` — historical architecture research, superseded for default video policy.
- `MVP/MVP_ARCHITECTURE.md` — historical MVP research, superseded for default video policy.
- `API/BACKEND_API_FLOW.md`
- `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`
- `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`
- `ComfyUI/HEADLESS_COMFYUI_API.md`
- `Database/POSTGRES_SCHEMA.sql`
- `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md`
- `Orchestration/OPTIONAL_AI_ORCHESTRATION_LAYER.md`
- `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`
- `docs/SPRINT_1A_STATUS.md`
- `docs/CHECKPOINT_WATCHDOG.md` — checkpoint restart protocol and no-live invariants.

## Safety Boundary

CineForge is intended to remain the deterministic execution engine. AI modules are advisory only in Sprint 1A and cannot directly mutate workflow JSON, queue state, local state records, model registries, ComfyUI submissions, asset paths, or FFmpeg commands.

See `docs/STORYBOARD_PHASE_A_SPEC.md` for the planning boundary and `docs/PRODUCT_VISION.md` for current product direction. Older sprint documents are historical implementation records, not product direction.

