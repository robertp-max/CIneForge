# MVP Prototype Architecture

Goal: fastest reliable local prototype that proves workflow automation, reproducibility, queueing, and FFmpeg assembly before chasing final quality.

The MVP does not depend on AI agents. CineForge remains the deterministic execution engine for state, validation, queueing, ComfyUI submission, telemetry, FFmpeg assembly, and provenance.

## MVP Components

| MVP Component | Recommended Choice | Why | Risk | Upgrade Path |
|---|---|---|---|---|
| ComfyUI runtime | Windows portable or isolated venv, headless | Fastest local setup, isolated from app | Dependency drift | Clone-based upgrade lane |
| Backend | Python FastAPI or Node service | Easy HTTP/WebSocket orchestration | Long tasks need worker discipline | Add durable workers |
| DB | PostgreSQL if available; SQLite acceptable for first spike | Provenance and queryability | SQLite concurrency limits | Move to Postgres |
| Queue | DB-backed single GPU worker | Avoids overloading 24GB VRAM | Lower throughput | Redis/RQ or Celery later |
| Prototype model | Wan2.1 1.3B and/or LTXV 2B | Lower VRAM risk | Lower final quality | Promote Wan2.2 5B/14B after benchmark |
| Quant | FP16 for small if it fits; FP8 for larger | Verified paths | Quality/speed tradeoffs | GGUF/Q only if needed |
| Clip length | 3-5 seconds | Faster iteration | More stitching | I2V continuity later |
| Frame count | 49-81 initial | Lower VRAM and faster | Less temporal context | 121 after benchmark |
| Resolution | 480p preview | Fits and iterates fast | Not final quality | 720p candidate, upscale final |
| LoRA | None initially | Baseline first | Less style consistency | One LoRA at a time |
| Workflow mutation | Versioned API JSON + manifest | Reproducible | Manifest upkeep | Workflow editor UI |
| FFmpeg | Normalize then concat; stream copy only when compatible | Practical for many clips | Disk cost | Mezzanine policy |
| Benchmarks | Required before promotion | Avoids hype | Time cost | Dashboard |

## MVP Flow

```text
Create campaign -> create 10-sec timeline slots -> generate 3-5 sec preview candidates
-> store prompt/seed/workflow/model hashes -> human selects candidate
-> optionally regenerate seed/prompt -> normalize selected clips -> assemble proof video
-> run validation/probe -> archive manifest
```

## MVP Presets

| Prototype Preset | Model | Quant | Resolution | Frames | Duration | Steps | Sampler/Scheduler | Expected Speed | VRAM Risk | Use Case |
|---|---|---|---:|---:|---:|---:|---|---|---|---|
| Ultra-fast sanity | Wan2.1 1.3B | FP16/FP8 | 512x288 | 49 | ~3s | workflow default low | Needs local benchmark | Fastest | Low | API smoke |
| Fast prompt exploration | LTXV 2B | FP8 | 704x384 | 81 | ~3-5s | workflow default | Needs local benchmark | Fast | Low-medium | Prompt search |
| Character/style exploration | Wan2.1 1.3B | FP8 | 832x480 | 81 | ~5s | workflow default | Needs local benchmark | Medium | Medium | Visual iteration |
| Motion exploration | Wan2.2 5B | FP8/FP16 | 832x480 | 81 | ~5s | workflow default | Needs local benchmark | Medium | Medium-high | Better motion |
| Near-final preview | Wan2.1/2.2 14B | FP8 | 832x480 | 81 | ~5s | workflow default | Needs local benchmark | Slow | High | Candidate QA |
| Final candidate render | Wan2.2 A14B | FP8 | 720p only if benchmark passes | 81-121 | 5s | workflow default | Needs local benchmark | Slow | Very high | Final test |

Do not hard-code sampler/scheduler claims until extracted from the installed workflow and locally benchmarked.

## Optional AI Layer Boundary

An AI Orchestration Layer may be added after the MVP is functional, but it is advisory only.

| Optional Capability | Allowed in MVP? | Execution Boundary |
|---|---|---|
| Draft alternate prompts | Optional | CineForge validates and stores prompt versions |
| Suggest shot lists | Optional | CineForge creates timeline slots only after approval |
| Diagnose failed shots | Optional | CineForge validates retry settings before enqueue |
| Review continuity | Optional | CineForge stores notes/proposals, not direct asset changes |
| Recommend next actions | Optional | Human or policy approval before CineForge execution |
| Direct workflow JSON mutation by agent | No | Forbidden |
| Direct queue/database/model registry mutation by agent | No | Forbidden |
| Direct FFmpeg command execution by agent | No | Forbidden |

This keeps the MVP execution path deterministic and reproducible while leaving room for provider-agnostic local or hosted agents later.

## Optional Autonomy Stubs

Sprint 1 may include non-executing autonomy stubs for future development, but the MVP must not depend on them.

Allowed stubs:

- `backend/app/services/ai_orchestration/`
- `backend/app/services/autonomy/`
- `backend/app/services/qa/`
- `backend/app/services/policy/`
- `backend/app/services/retry/`
- `backend/app/services/batch_planner/`

Allowed schema stubs:

- `ai_proposal_records`
- `autonomy_runs`
- `autonomy_run_events`
- `autonomy_policies`
- `qa_reports`
- `retry_attempts`
- `creative_review_notes`
- `candidate_scores`

Sprint 1 behavior: create schemas, service boundaries, proposal validation, and documentation only. These modules must not execute autonomous changes. All real work still passes through CineForge validation gates, workflow manifest validation, benchmark bounds, backend queue control, ComfyUI submission, FFmpeg probe validation, telemetry, and audit logging.
