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
- File-backed local job, semantic-generation, post-production, recipe-command, and operator-review manifests, plus explicit operator-only queue and post-production actions behind independent default-off gates.
- Path safety helpers.
- Isolated ComfyUI runtime owner, controlled client/submission adapter, WebSocket progress tracking, history/output collection, provenance hashing, GPU leases, stale-job recovery, and bounded retry handling.
- `nvidia-smi` parser for benchmark telemetry.
- FFmpeg/ffprobe validation primitives, structured allowlisted recipe builders, and a default-off executor that revalidates persisted argv, input hashes, managed paths, and output probes.
- Non-executing AI/autonomy schemas and validators.
- Pytest coverage for the Sprint 1A primitives.
- Persisted `Project -> Story -> Chapter -> Scene -> Shot` planning hierarchy.
- Storyboard readiness checks, duration rollups, immutable approval versions, JSON and CSV planning exports.
- Storyboard Studio frontend views for planning, assets, routing, workflows, exports, and settings.

What does not work yet:

- No general user-facing or preset-enabled production video generation.
- No autonomous production execution.
- No live benchmark ladder evidence, recovery/OOM exercise, or human QA sign-off.
- No ComfyUI Manager/download/update automation; the runtime owner deliberately starts only the configured pinned local runtime and never installs or updates it.
- The controlled GPU worker is implemented but remains unavailable until queue, hardware-operator, workflow-admission, model, and evidence gates all pass.
- No image/video generation is triggered by Storyboard Phase A approval.
- Project and campaign APIs remain planning/scaffold surfaces. `/local-*` routes remain passive or manifest-only; explicit mutations are separated under `/operator-generation`, `/operator-runtime`, and `/operator-post-production` and fail closed while their gates are disabled.

## Default video policy (2026-07)

- Product key: `ltx2_3_22b_distilled_1_1_fp8`.
- Source identity: official LTX-2.3 22B Distilled **1.1**; the BF16 source checkpoint is not itself an FP8 artifact.
- Runtime precision: proven FP8 only via a recorded method (`loader_level`, `converted_derivative`, or `official_artifact`); never silently substitute a non-1.1 FP8 file.
- M0 records a local full-checkpoint FP8 artifact as `converted_derivative`; CF-VID-01 has passed a minimal local T2V smoke, but admission remains `benchmark_required` until conversion provenance, full benchmark evidence, recovery behavior, and human QA are recorded.
- `/local-runtime/catalog`, `/local-runtime/local-mvp-readiness`, and fail-closed `/local-runtime/public-readiness` expose the DB-free local model/output/readiness contract. Passive and manifest surfaces stay under `/local-*`; durable queueing and live-tool controls use separate `/operator-*` routes with explicit acknowledgement and default-off backend gates.
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

### ComfyUI runtime ownership and optional auto-start

ComfyUI remains an isolated process; CineForge never imports it in-process or treats a listening port alone as generation readiness. Automatic startup is implemented but disabled by default. It runs only when both `CINEFORGE_COMFYUI_AUTOSTART_ENABLED=true` and `CINEFORGE_HARDWARE_OPERATOR_ENABLED=true`; otherwise startup is passive and performs no ComfyUI network probe.

The runtime owner:

1. Reads explicitly configured ComfyUI root, embedded Python, `main.py`, output root, base URL, and bounded timeouts.
2. On an approved start, probes the configured localhost URL before launching; a healthy compatible runtime is reused instead of duplicated.
3. Starts only the fixed Python/`main.py` argv assembled from configuration. AI-authored text never becomes a shell command or executable path.
4. Waits for both the ComfyUI root endpoint and `/object_info` within a bounded timeout before reporting readiness.
5. Fail honestly: if startup or `/object_info` validation fails, keep planning available, block image/video generation, and show the exact runtime-readiness blocker. Never display a generated, reviewed, approved, or playable state for media that does not exist.
6. Record whether CineForge owns the child process. On shutdown, CineForge may stop only the process it started; it must not terminate an independently running ComfyUI instance.
7. Never installs, updates, or downloads models, mutates custom nodes, or weakens host security as part of startup.

Auto-start does not enable generation. Controlled generation additionally requires the independently enabled queue worker and hardware operator, an admitted workflow/model/profile compatible with live `/object_info`, an exclusive GPU lease, managed output collection, and provenance persistence. Public/autonomous generation and unadmitted image/video archetypes remain disabled.

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

Current checkpoint result: `308 passed`, frontend lint/build passed, static boundary validation passed, `git diff --check` passed, and the checkpoint watchdog banner printed; the suite remains no-live/offline-safe.

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

