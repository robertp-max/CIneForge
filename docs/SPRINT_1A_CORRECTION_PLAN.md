# Sprint 1A Correction Plan

Date: 2026-05-26

Purpose: corrected plan for Sprint 1A after architecture reconciliation. This plan supersedes the prior broad implementation direction.

## Guardrails

- Do not implement real video generation in Sprint 1A.
- Do not download models.
- Do not mutate or install ComfyUI.
- Do not implement autonomous production execution.
- Do not create parallel GPU generation logic.
- Do not allow AI agents to directly mutate workflow JSON, queue state, database records, model registry entries, FFmpeg commands, asset paths, output manifests, or ComfyUI submissions.
- All future execution must pass through validation, policy, queue, benchmark, workflow manifest, and audit gates.

## Corrected Sprint 1A Objective

Build the architecture-correct backend foundation: schemas, validators, service boundaries, safe clients, queue lifecycle, provenance contracts, telemetry parsing, FFmpeg validation primitives, and non-executing AI/autonomy stubs.

## Phase 0: Scaffold Decision

Choose the backend stack before writing broad code:

- Preferred: Node/TypeScript service if the app will align with an Electron/Web UI and existing TypeScript tooling.
- Acceptable: Python/FastAPI if local worker/process orchestration is prioritized.
- DB: PostgreSQL-compatible schema is authoritative. SQLite may be used only as a local adapter if migrations remain compatible with the Postgres schema.

Deliverables:

- App source root.
- Test runner.
- Config loader.
- Local runtime directories.
- No ComfyUI mutation.

## Phase 1: Schema Foundation

Implement schema/migration files based on `Database/POSTGRES_SCHEMA.sql`.

Required baseline tables:

- `hardware_profiles`
- `projects`
- `campaigns`
- `tracks`
- `timeline_slots`
- `prompts`
- `negative_prompts`
- `models`
- `model_variants`
- `quantizations`
- `text_encoders`
- `vaes`
- `loras`
- `lora_combinations`
- `lora_combination_items`
- `workflow_templates`
- `clips`
- `clip_iterations`
- `workflow_runs`
- `comfy_jobs`
- `generated_assets`
- `file_outputs`
- `benchmark_runs`
- `ffmpeg_jobs`
- `audit_logs`
- `error_logs`

Add Sprint 1 autonomy stub tables:

- `ai_proposal_records`
- `autonomy_runs`
- `autonomy_run_events`
- `autonomy_policies`
- `qa_reports`
- `retry_attempts`
- `creative_review_notes`
- `candidate_scores`

Acceptance:

- Migration/schema file exists.
- Schema is documented.
- Tests or schema checks confirm required tables and key columns exist.

## Phase 2: Queue State Machine

Implement the generation queue state machine exactly:

```text
pending -> reserved -> submitted -> running -> collecting_outputs -> complete
```

Failure states:

```text
validation_failed
comfy_rejected
runtime_failed
timeout
interrupted
oom
postprocess_failed
```

Rules:

- Only backend queue worker can reserve or submit jobs.
- ComfyUI queue is not the source of truth.
- Queue state transitions must emit audit/event records.
- Jobs must carry workflow run ID, risk tier, model/quant/LoRA grouping keys, retry counters, timeout policy, and benchmark requirement status.

Acceptance:

- Transition table tests.
- Invalid transition tests.
- Failure classification tests.
- Tests prove no AI proposal can mutate queue state.

## Phase 3: Workflow Manifest and Patch Plan

Implement schema-first validation for workflow templates and manifests.

Required structures:

- Workflow API JSON type.
- Manifest type with semantic node refs.
- Node ref fields: semantic key, node ID, expected `class_type`, input name, runtime parameter name, value schema.
- Runtime patch payload type aligned to the runtime parameter matrix.
- Patch planner that validates and returns a patch plan.
- Patch applier that validates `class_type` and input existence before mutation.
- Immutable snapshot writer.
- Object-info compatibility validator stub that can validate from supplied object-info JSON without needing live ComfyUI.

Runtime parameters to cover:

- Positive prompt.
- Negative prompt.
- Seed.
- Width.
- Height.
- Frame count.
- FPS.
- Steps.
- Sampler.
- Scheduler.
- CFG/guidance.
- Optional STG/extra params.
- Model checkpoint.
- Text encoder.
- VAE.
- Quant loader.
- LoRA list and strengths.
- Input/conditioning asset path.
- Output filename prefix.
- Save path policy.

Acceptance:

- Tests for valid patch.
- Tests for missing node.
- Tests for class type mismatch.
- Tests for missing input.
- Tests for unsafe output path.
- Tests for object-info missing class/input.

## Phase 4: ComfyUI Client Boundary

Scaffold a complete client interface but keep production submission inactive until the queue worker is implemented.

Client methods:

- `getObjectInfo`
- `health`
- `submitPrompt`
- `connectProgressWebSocket` or equivalent interface
- `getHistory`
- `viewOutput`
- `uploadImage`
- `interrupt`
- `getQueue`
- `deleteQueueItems`
- `freeMemory`

Sprint 1A behavior:

- Read/health/object-info methods may be safe and offline-graceful.
- Mutating methods must require explicit deterministic service context and must not be callable by AI modules.
- No direct Comfy queue ownership by UI or AI.

Acceptance:

- Offline health test.
- Object-info parser test.
- Submit method is blocked unless called through future queue worker interface.

## Phase 5: Telemetry and Benchmark Foundation

Implement telemetry sample schema and parser aligned with the benchmark protocol.

Required nvidia-smi fields:

- `timestamp`
- `name`
- `driver_version`
- `pstate`
- `temperature.gpu`
- `utilization.gpu`
- `utilization.memory`
- `memory.total`
- `memory.used`
- `power.draw`
- `clocks.gr`
- `clocks.mem`

Benchmark schemas:

- JSONL event schema.
- Benchmark result schema.
- Promotion gate evaluator.

Acceptance:

- Parser handles full CSV.
- Parser tolerates missing WDDM power fields.
- Peak metric aggregation test.
- Promotion gate test for peak VRAM below 23GB and failure rate.

## Phase 6: FFmpeg Validation Foundation

Implement only approved FFmpeg command template definitions and pure validation utilities.

Required pieces:

- Probe JSON schema.
- Stream compatibility comparator.
- Stream-copy concat eligibility validator.
- Normalization strategy selector.
- Mezzanine command template definition.
- Delivery-compatible MP4 command template definition.
- Decode validation command template definition.
- Hash/probe storage contract.

Rules:

- No free-form command execution from AI or UI.
- Command strings must be generated from approved templates only.
- Store input manifest and probe data before assembly.

Acceptance:

- Matching probe compatibility test.
- Mismatched fps/resolution/pixel format rejection test.
- Normalization plan test.
- Command injection/path safety test.

## Phase 7: AI Proposal and Autonomy Stubs

Implement non-executing proposal and autonomy modules.

AI proposal components:

- Provider adapter interface.
- Proposal record schema.
- Proposal type enum:
  - `create_shot_list`
  - `revise_prompt`
  - `retry_failed_shot`
  - `continuity_fix`
  - `benchmark_recommendation`
  - `assembly_note`
  - `autonomy_plan`
  - `qa_review`
  - `batch_plan`
- Forbidden field scanner.
- Proposal validator.
- Approval/rejection record model.

Autonomy components:

- Autonomy run state enum from `AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.
- Autonomy run event schema.
- Policy/budget schema.
- Read/create-only run store.

Acceptance:

- Valid proposal stores as pending/reviewable.
- Proposal with raw FFmpeg command is rejected.
- Proposal with direct workflow node IDs is rejected.
- Proposal with queue mutation is rejected.
- Proposal with asset overwrite path is rejected.
- Autonomy execute path is absent or throws a clear scaffold-only error.

## Phase 8: Health and Documentation

Health endpoints should report:

- API liveness.
- DB connectivity/schema version.
- ComfyUI reachability without taking ownership.
- Queue worker disabled/enabled state.
- Runtime isolation configuration.
- FFmpeg binary availability.
- Benchmark gate status.
- Autonomy mode: scaffold-only.

Docs:

- Architecture reconciliation report.
- Implementation drift report.
- Sprint 1A correction plan.
- Developer setup.
- Safety boundaries.
- API flow summary.

Acceptance:

- Health endpoint starts locally.
- Docs state what is scaffolded vs executable.
- No production autonomy active.

## Corrected Definition of Done

Sprint 1A is done when:

- Backend starts locally.
- Config loads from `.env`.
- DB schema foundation aligns with `POSTGRES_SCHEMA.sql` and JSON schema docs.
- Queue state machine matches the packet and is tested.
- Workflow manifest validation covers class_type, inputs, object-info compatibility, runtime parameter matrix, and immutable snapshots.
- ComfyUI client wrapper exists and fails gracefully offline.
- Telemetry parser and benchmark result schemas match the benchmark protocol.
- FFmpeg probe/compatibility/normalization validators exist and are tested.
- Path safety helpers exist and are tested.
- AI proposal/autonomy stubs exist but cannot execute changes.
- Runtime isolation boundaries are documented in code and docs.
- Tests pass, or failures are documented with exact next fixes.

## Work Not Allowed In Sprint 1A

- Real video generation.
- Model download or registry mutation from agents.
- ComfyUI install, update, or package mutation.
- Parallel GPU generation.
- Autonomous production execution.
- Raw FFmpeg command execution from AI output.
- Direct workflow JSON mutation outside manifest-driven patching.
- Direct database, queue, or asset mutation by AI modules.

## Immediate Next Step

Before writing backend code, create a minimal implementation issue/checklist from this plan and confirm the source root and backend stack. Then implement in small vertical slices:

1. Schema and types.
2. Queue state machine.
3. Workflow manifest validator.
4. Telemetry parser.
5. FFmpeg validators.
6. AI proposal stubs.
7. Health endpoints.

Each slice must include tests before moving to the next one.
