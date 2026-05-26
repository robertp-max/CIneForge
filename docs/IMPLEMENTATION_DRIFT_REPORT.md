# Implementation Drift Report

Date: 2026-05-26

Scope: drift review of the prior Sprint 1A implementation shape against the authoritative research packet.

Workspace note: the correct `C:\AI\Git\CIneForge` workspace currently has no generated backend implementation files. The drift items below describe the implementation approach that must not be carried forward without correction.

## Summary

The prior implementation correctly preserved the broad safety intent: ComfyUI submissions were disabled, autonomy could not execute, and path safety was considered. However, several foundational abstractions were too generic or too small compared with the packet. If continued, they would create the wrong system spine.

## Drift Inventory

| Area | Prior Shape | Packet Requirement | Risk | Correction |
|---|---|---|---|---|
| Queue state machine | `draft`, `validated`, `queued`, `running`, `succeeded`, `failed`, `cancelled` | `pending`, `reserved`, `submitted`, `running`, `collecting_outputs`, `complete`, plus specific failure states | Wrong job lifecycle, weak recovery, cannot map Comfy submission/history phases | Replace with required GPU generation queue state machine and failure taxonomy |
| Queue durability | In-memory pure object | DB-backed durable queue | Cannot recover jobs or enforce ownership after restart | Define DB queue schema aligned to `comfy_jobs`, `workflow_runs`, and job event audit |
| Workflow manifest | Basic manifest metadata with required gates | Semantic node refs, `class_type`, input validation, object-info validation, runtime parameter matrix, immutable snapshots | Patching can silently target wrong nodes/fields | Define manifest schema with node refs and patch payload validation |
| Runtime parameter mapping | Not modeled | Runtime parameter matrix maps prompts, seed, dimensions, frames, fps, steps, sampler, scheduler, guidance, model, LoRA, VAE, encoder, inputs, output prefix | Missing DB provenance and unsafe patching | Implement typed patch payload and DB-field mapping |
| Object-info validation | Not modeled | Validate installed node classes and inputs via `/object_info` | Workflow may submit to missing or changed nodes | Add object-info compatibility validator and cache shape |
| ComfyUI client | Health check and disabled submission only | `/prompt`, `/ws`, `/history`, `/view`, `/upload/image`, `/interrupt`, `/queue`, `/free`, `/object_info` planned wrapper | Missing API contract for queue worker and validation | Scaffold full client interface but keep mutating calls disabled unless called by future worker |
| DB foundation | Filesystem `schema.json` placeholder | Postgres schema with provenance, registry, workflow, assets, benchmarks, FFmpeg, audit, autonomy stubs | Wrong persistence model and poor migration path | Start with DDL/migrations matching packet; SQLite adapter optional but schema-compatible |
| Benchmark storage | Not modeled | `benchmark_runs` plus JSONL telemetry and promotion gates | Cannot make model/preset decisions from evidence | Add benchmark schema and result validator |
| Telemetry parser | Simplified GPU CSV parser | Full nvidia-smi query fields plus peak metrics, thermal/clocks/power, queue latency, crash/failure metrics | Benchmarks cannot support promotion gates | Expand telemetry sample schema and parser |
| FFmpeg service | Binary availability and read-only probe args | Probe storage, compatibility validation, concat safety, mezzanine normalization, delivery normalization, decode validation, hash storage | Unsafe concat/assembly abstractions | Add approved command template catalog and pure validators |
| AI orchestration | Single proposal stub with execute throwing | Provider adapter, proposal inbox, schema, validation gates, forbidden fields, proposal types, approval/rejection, autonomy run model | Too small to enforce advisory-only boundary at scale | Define record schemas and validator services before execution APIs |
| Autonomy states | Not modeled | Autonomy run state machine with planning, validation, rendering, QA, repair, assembly, review, failed states | Future autonomy cannot be audited | Add schema-only autonomy run states/events |
| QA/retry/candidate scoring | Not modeled | Technical QA, creative notes, retry attempts, candidate scores as Sprint 1 schema stubs | Missing hooks for autonomous repair and candidate selection | Scaffold record-only tables/services |
| Runtime isolation | Partially stated | Isolated Comfy runtime, single GPU worker, restart policy, `/free`, interrupt, history fallback, no direct Comfy queue ownership | Later worker could bypass required runtime policy | Define supervisor and worker boundaries before submission implementation |
| Audit model | Basic gate list only | Audit logs for validation, approval, transitions, proposals, jobs, FFmpeg, policy decisions | Poor traceability | Add audit event contract tied to DB schema |
| Package scripts | Test script overwrite in wrong repo | Correct repo should choose scripts after scaffold exists | Wrong package behavior and wrong workspace risk | Do not add package behavior until app scaffold is chosen in `C:\AI\Git\CIneForge` |

## Specific Required Corrections

### Queue States

Replace the generic queue state machine with the exact generation lifecycle:

```text
pending -> reserved -> submitted -> running -> collecting_outputs -> complete
```

Add terminal failure states:

```text
validation_failed
comfy_rejected
runtime_failed
timeout
interrupted
oom
postprocess_failed
```

Cancellation should be modeled carefully. A pending/reserved job can become `interrupted` or a separate explicit canceled state only if the packet is extended. Do not invent new terminal states without documenting the extension.

### Workflow Manifest

The validator must require:

- `template_id`
- template `version`
- original workflow SHA256
- ComfyUI commit or install snapshot reference
- manifest node map
- each node ref: semantic key, node ID, expected `class_type`, input name, value type, required/optional flag
- patch payload schema for runtime parameters
- required model/quant/LoRA/text encoder/VAE references
- output prefix/path policy
- immutable snapshot write contract

### AI Orchestration

Replace simplistic proposal-only stubs with schema-first modules:

- `AiProviderAdapter`
- `ProposalInbox`
- `ProposalValidator`
- `ForbiddenFieldScanner`
- `ProposalApprovalService`
- `AutonomyRunStore`
- `AutonomyPolicyEvaluator`

These services must remain non-executing in Sprint 1A.

### Database

Remove any plan for an ad hoc filesystem DB foundation. Use `Database/POSTGRES_SCHEMA.sql` as the baseline and extend it only with documented Sprint 1 autonomy stub tables from `MVP/MVP_ARCHITECTURE.md` and `AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.

### Telemetry

A valid telemetry sample should include all fields from the benchmark command:

```text
timestamp,name,driver_version,pstate,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,power.draw,clocks.gr,clocks.mem
```

The parser must tolerate missing power/per-process fields on Windows WDDM.

### FFmpeg

Do not expose a free-form FFmpeg command builder. Use template IDs and validated manifests only. Store probe JSON, decode validation result, command template ID, input hashes, output hash, and final probe.

## Unsafe Abstractions To Avoid

- Generic `succeeded/failed` job status without failure class.
- Manifest validation that does not inspect node `class_type`.
- Workflow patching by direct node ID from an AI proposal.
- DB foundation that cannot represent workflow provenance and benchmarks.
- Telemetry that cannot prove peak VRAM, thermal behavior, and promotion gates.
- FFmpeg command strings produced by agents or UI input.
- ComfyUI submission outside the backend queue worker.
- Any autonomy module with direct write access to queue, workflow, registry, assets, or FFmpeg command tables.

## Current Workspace State

No implementation files were found outside the research packet in `C:\AI\Git\CIneForge` before these docs were added. Therefore, there is no current code to surgically rewrite in this workspace. The next step is to scaffold from the corrected plan, not continue from the prior simplified implementation.
