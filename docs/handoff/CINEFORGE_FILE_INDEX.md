# CineForge File Index

Generated: 2026-07-11

This index lists the report, plan, roadmap, benchmark, architecture, and status files reviewed for the handoff package.

## Generated Handoff Files

- `docs/handoff/CINEFORGE_FULL_STATUS_REPORT.md` - Master handoff status report for the parent ChatGPT conversation.
- `docs/handoff/CINEFORGE_FILE_INDEX.md` - Index of reviewed reports and supporting documents.
- `docs/handoff/CINEFORGE_TEST_RESULTS.md` - Verification commands, results, failures, and omitted checks.
- `docs/handoff/CINEFORGE_GIT_STATE.txt` - Raw Git status, remotes, and recent log output captured for the handoff.

## Current Status And Sprint Docs

- `README.md` - Root project overview; currently stale because it still describes Sprint 1A only.
- `docs/UI_MVP_STATUS.md` - Newest status doc for the integrated UI MVP and Phase 2 controlled-submission backend capability.
- `docs/SPRINT_1C_PLAN.md` - Sprint 1C plan and current state for PostgreSQL verification, worker safety, recovery, worker skeleton, and readiness gates.
- `docs/SPRINT_1B_CLOSEOUT.md` - Sprint 1B completion report covering DB-backed routes, durable queue/audit service, object-info cache, progress parser, and benchmark gates.
- `docs/SPRINT_1B_PLAN.md` - Sprint 1B implementation plan for turning Sprint 1A primitives into a durable non-generating backend spine.
- `docs/SPRINT_1A_STATUS.md` - Sprint 1A status report for backend foundation primitives and remaining Sprint 1B recommendations.
- `docs/SPRINT_1A_CORRECTION_PLAN.md` - Corrected Sprint 1A guardrails and phased foundation plan after architecture reconciliation.
- `docs/PUBLIC_REPO_STATUS.md` - Public repository hygiene/status note, including excluded local files and secret-scan summary.
- `docs/POSTGRES_VERIFICATION.md` - PostgreSQL-gated test instructions and schema verification scope.
- `docs/LOCAL_SMOKE_TEST_PLAN.md` - Local smoke-test plan for backend health, ComfyUI health, FFmpeg, and GPU telemetry.
- `docs/IMPLEMENTATION_NOTES.md` - Early implementation decisions and unresolved items from Sprint 1A.
- `docs/IMPLEMENTATION_DRIFT_REPORT.md` - Drift report explaining unsafe prior abstractions and required corrections.
- `docs/ARCHITECTURE_RECONCILIATION_REPORT.md` - Strict architecture reconciliation against the research packet and non-negotiable boundaries.

## API, Queue, Workflow, And Traceability Docs

- `docs/API_CONTRACT.md` - Implemented early API contract and known Sprint 1A stubs.
- `docs/QUEUE_STATE_MACHINE.md` - Queue lifecycle and terminal/failure states for generation jobs.
- `docs/WORKFLOW_TEMPLATE_MANIFEST.md` - Workflow template and manifest requirements for deterministic patching and snapshots.
- `docs/RESEARCH_TRACEABILITY.md` - Mapping from implementation modules to authoritative source documents.
- `storage/workflow_templates/example_smoke/README.md` - Notes that the example workflow is a dummy smoke template, not a production workflow.
- `frontend/README.md` - Frontend scope and run/build notes for the React/Vite control dashboard.

## Architecture And Product Docs

- `Architecture/ARCHITECTURE_BLUEPRINT.md` - Top-level local orchestration architecture around isolated ComfyUI, DB provenance, FFmpeg, telemetry, and optional AI.
- `MVP/MVP_ARCHITECTURE.md` - MVP architecture and fastest reliable prototype path before final-quality lanes.
- `API/BACKEND_API_FLOW.md` - Target app-facing API flow for projects, timeline slots, queueing, jobs, benchmarks, assets, and assembly.
- `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md` - Runtime isolation, ComfyUI management, cache behavior, queue policy, and memory/stability guidance.
- `Elite/ELITE_ARCHITECTURE.md` - Version-two/elite architecture for model registry UI, benchmark dashboard, QA, autonomy, and production workflows.
- `Findings/FINAL_RECOMMENDATION.md` - Final recommendation and decision tree for MVP lane, candidate/final lane, and model/quant strategy.

## ComfyUI, Workflow, Database, Benchmark, And FFmpeg Docs

- `ComfyUI/HEADLESS_COMFYUI_API.md` - Planned ComfyUI HTTP/WebSocket API use, submission flow, history fallback, and output discovery requirements.
- `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md` - Deterministic ComfyUI API workflow patching strategy using versioned manifests.
- `Database/POSTGRES_SCHEMA.sql` - Authoritative PostgreSQL schema for projects, jobs, workflow runs, model registry, generated assets, benchmarks, FFmpeg jobs, and audit logs.
- `Database/JSON_SCHEMAS.md` - Starting JSON schema definitions for generation requests, completed results, registry entries, and related payloads.
- `Benchmarks/BENCHMARK_PROTOCOL.md` - RTX 5090 Laptop 24GB benchmark matrix, telemetry fields, JSONL format, and promotion requirements.
- `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md` - FFmpeg probe, concat, normalization, mux, loudness, subtitle, and command-template strategy.

## Model, LoRA, Quantization, Source, And Risk Docs

- `Models/MODEL_FEASIBILITY_MATRIX.md` - Conservative feasibility matrix for Wan/LTX model families on the 24GB laptop GPU.
- `LoRAs/LORA_COMPATIBILITY_MATRIX.md` - LoRA purpose, compatibility, loader, quantization, risk, and local test guidance.
- `Quantization/QUANTIZATION_MATRIX.md` - FP16/FP8/GGUF/other quantization options, tradeoffs, and required local tests.
- `Sources/SOURCE_REGISTER.md` - Source register for official docs, model cards, ComfyUI docs/source, custom-node repos, FFmpeg, NVIDIA, and reproducibility references.
- `Risk-Register/RISK_REGISTER.md` - Risk matrix covering VRAM, thermals, model compatibility, LoRA mismatch, queue/runtime failure, FFmpeg, storage, autonomy, and security.

## AI And Autonomy Docs

- `Orchestration/OPTIONAL_AI_ORCHESTRATION_LAYER.md` - Optional advisory AI proposal architecture and forbidden mutation boundaries.
- `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md` - Future autonomous production architecture, autonomy levels, state machine, policy boundaries, QA, retries, and final reporting.

## Stack Manifests Reviewed

- `pyproject.toml` - Backend package metadata, Python dependency list, dev extras, setuptools config, and pytest settings.
- `frontend/package.json` - Frontend scripts and dependencies for React, Vite, TypeScript, and ESLint.

