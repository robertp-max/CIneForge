# Architecture Reconciliation Report

Date: 2026-05-26

Scope: strict reconciliation against the authoritative CineForge research packet. No broad implementation is approved by this report.

Workspace note: `C:\AI\Git\CIneForge` currently contains the research packet and no generated backend source tree. This report audits the prior Sprint 1A implementation shape and defines the architecture that must govern the next implementation pass.

## Authoritative Sources

- `Architecture/ARCHITECTURE_BLUEPRINT.md`
- `MVP/MVP_ARCHITECTURE.md`
- `API/BACKEND_API_FLOW.md`
- `ComfyUI/HEADLESS_COMFYUI_API.md`
- `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`
- `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`
- `Database/POSTGRES_SCHEMA.sql`
- `Database/JSON_SCHEMAS.md`
- `Orchestration/OPTIONAL_AI_ORCHESTRATION_LAYER.md`
- `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`
- `Benchmarks/BENCHMARK_PROTOCOL.md`
- `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md`
- `Risk-Register/RISK_REGISTER.md`
- `Findings/FINAL_RECOMMENDATION.md`

## Non-Negotiable Architecture

CineForge is a deterministic local orchestration app. The backend owns project state, validation, queueing, ComfyUI submission, telemetry, FFmpeg assembly, provenance, and audit records.

ComfyUI must remain an isolated worker accessed over HTTP/WebSocket. CineForge must not import or embed ComfyUI in-process. GPU video generation must be serialized on the 24GB GPU.

AI agents are advisory only. They may create structured proposals, but they must not directly mutate workflow API JSON, queue state, database records, model or LoRA registry entries, FFmpeg command templates, asset paths, output manifests, or ComfyUI prompt submissions.

Future autonomy may let CineForge execute approved work under policy, but execution still passes through deterministic CineForge services, benchmark gates, queue control, manifest validation, telemetry, and audit logging.

## Queue Reconciliation

Required queue state model from `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`:

```text
pending -> reserved -> submitted -> running -> collecting_outputs -> complete
```

Required failure states:

```text
validation_failed
comfy_rejected
runtime_failed
timeout
interrupted
oom
postprocess_failed
```

The backend queue must be durable and DB-backed. ComfyUI queue depth should stay near 0-1. The backend, not ComfyUI and not AI agents, owns long queue state.

Implementation implication: do not use generic states such as `draft`, `validated`, `queued`, `succeeded`, `failed` as the generation job state machine. Those terms may exist in proposal or UI review flows, but not as the authoritative GPU generation queue.

## Workflow Manifest Reconciliation

Workflow mutation must follow `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`.

Required manifest behavior:

- Workflow API JSON and workflow manifest are separate versioned artifacts.
- Manifest maps semantic runtime parameters to node IDs and input names.
- Every mapped node must validate `class_type`.
- Every mapped input must exist before patching.
- Installed ComfyUI node metadata must be checked through `/object_info`.
- Runtime parameters must map to database fields from the runtime parameter matrix.
- Patched workflow JSON must be snapshotted immutably per run.
- Workflow runs must store template ID/version, original template SHA256, patch payload JSON, patched workflow JSON, ComfyUI commit, custom node snapshot, model hashes, LoRA hashes, text encoder hash, VAE hash, and ComfyUI `prompt_id`.

Implementation implication: simple manifest metadata validation is insufficient. Sprint 1A should implement schema and pure validation primitives for manifests, node references, runtime patch payloads, object-info compatibility, and immutable snapshot records. Actual ComfyUI submission can remain disabled until the queue worker is ready.

## AI Orchestration Reconciliation

Required model from `Orchestration/OPTIONAL_AI_ORCHESTRATION_LAYER.md`:

```text
AI Provider Adapter -> Proposal Inbox -> CineForge Validation -> Deterministic Execution Engine
```

Sprint 1A stubs should include:

- Provider abstraction contract.
- Structured proposal schema.
- Proposal inbox service boundary.
- Proposal validation result.
- Forbidden field detection.
- Proposal type taxonomy.
- Approval/rejection model.
- Audit-ready proposal records.
- Autonomy run schema stubs and events.

Allowed Sprint 1 behavior: insert/read proposal and autonomy records, validate proposals, document service boundaries.

Forbidden Sprint 1 behavior: execute autonomous changes, mutate workflows, mutate queue state, mutate DB records outside proposal/audit stubs, submit to ComfyUI, generate FFmpeg commands from AI output, or write asset paths from AI output.

## Database Reconciliation

The DB foundation must align with `Database/POSTGRES_SCHEMA.sql` and `Database/JSON_SCHEMAS.md`.

Core schema areas:

- Hardware profiles.
- Projects, campaigns, tracks, timeline slots.
- Prompts and negative prompts.
- Models, model variants, quantizations, text encoders, VAEs.
- LoRAs and LoRA combinations.
- Workflow templates and workflow runs.
- Clips and clip iterations.
- Comfy jobs.
- Generated assets and file outputs.
- Benchmark runs.
- FFmpeg jobs.
- Audit logs and error logs.
- Sprint 1 autonomy stubs: `ai_proposal_records`, `autonomy_runs`, `autonomy_run_events`, `autonomy_policies`, `qa_reports`, `retry_attempts`, `creative_review_notes`, `candidate_scores`.

Implementation implication: a filesystem-only placeholder DB schema is not enough as the foundation. SQLite may be acceptable for the first spike only if the schema remains Postgres-compatible and maps directly to the packet. The source of truth should be migration files or schema DDL, not an ad hoc JSON table list.

## Telemetry Reconciliation

Telemetry must satisfy `Benchmarks/BENCHMARK_PROTOCOL.md`.

Required GPU sample fields:

- timestamp
- name
- driver_version
- pstate
- temperature.gpu
- utilization.gpu
- utilization.memory
- memory.total
- memory.used
- power.draw when available
- clocks.gr
- clocks.mem

Benchmark metrics must include model load time, cold/warm generation time, peak VRAM, peak RAM, GPU utilization, memory utilization, temperature, power draw if available, clocks, time per frame, failure rate, artifact rate, queue latency, ComfyUI crash rate, thermal throttling indicators, LoRA overhead, quantization quality delta, VAE decode time, upscale/interpolation time, and FFmpeg assembly time.

Implementation implication: a simplified parser for only index/name/utilization/memory/temp is not enough. Sprint 1A should define parsers and JSONL event schemas that can support benchmark promotion gates.

## FFmpeg Reconciliation

FFmpeg work must follow `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md`.

Required behavior:

- Probe every input with `ffprobe`.
- Store probe JSON.
- Reject stream-copy concat unless codec, dimensions, pixel format, fps, time base, audio sample rate, channel layout, and stream counts are compatible.
- Normalize mismatched clips before concat.
- Support mezzanine and delivery-compatible normalization strategies as approved command templates.
- Validate final output with `ffprobe` and full decode check.
- Record command template, input manifest, output path, probe JSON, status, errors, and hashes.

Implementation implication: binary availability checks and read-only probe args are necessary but not sufficient. Sprint 1A should create command template definitions and pure validation utilities, not ad hoc command construction.

## Runtime Isolation Reconciliation

Required runtime design:

- ComfyUI runs in a dedicated portable or isolated venv runtime.
- Backend talks to ComfyUI through HTTP/WebSocket only.
- One GPU worker owns ComfyUI generation submission.
- Backend queue is durable and bounded.
- ComfyUI queue remains shallow.
- Use WebSocket progress as primary completion channel and `/history/{prompt_id}` as fallback.
- Use `/interrupt`, `/queue`, `/free`, and supervised restart policy for recovery.
- Restart after memory thresholds, crash, hung job, or configured high-risk batch count.
- FFmpeg/post-processing runs through separate CPU/GPU-aware workers and must not overlap with diffusion until benchmarked.

Implementation implication: Sprint 1A should define interfaces for runtime supervisor, queue worker, Comfy client, and restart policy, but should not activate real production generation.

## Autonomy Boundary Verification

Correct boundary:

- AI can write structured proposal records only.
- AI cannot mutate workflow API JSON.
- AI cannot alter queue state.
- AI cannot write model/LoRA registry entries directly.
- AI cannot write asset paths or output manifests.
- AI cannot submit ComfyUI prompts.
- AI cannot create or execute raw FFmpeg commands.
- Approved proposals must be converted by CineForge into ordinary deterministic actions.

Implementation implication: proposal schemas must explicitly reject forbidden fields such as direct node IDs, raw FFmpeg commands, direct DB inserts, queue mutations, asset overwrite paths, Comfy prompt payloads, and registry writes.

## Reconciled Sprint 1A Definition

Sprint 1A should establish:

- Repository scaffolding matching the packet module boundaries.
- Postgres-compatible schema/migrations or a clearly marked SQLite-compatible development adapter.
- JSON schemas for generation requests, completed generation results, registry entries, workflow manifests, patch payloads, AI proposals, benchmark results, and FFmpeg manifests.
- Pure queue state machine matching the required generation states.
- Pure workflow manifest validator and patch planner.
- Object-info compatibility validator stub.
- Offline-safe ComfyUI client with no automatic submission unless queue worker invokes it later.
- Telemetry parser and benchmark JSONL schema aligned to the benchmark protocol.
- FFmpeg probe and compatibility validators plus approved command-template catalog.
- AI proposal inbox/autonomy stubs that cannot execute real actions.
- Documentation and tests for boundaries.

## Stop Condition Before Implementation Continues

Do not continue broad implementation until the current code plan is corrected to this reconciliation. Any existing or future Sprint 1A code that creates mismatched queue states, ad hoc manifests, filesystem-only DB abstractions, raw FFmpeg command builders, or executable autonomy stubs must be corrected before feature expansion.
