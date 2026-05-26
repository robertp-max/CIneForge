# Autonomous Production Architecture

This document defines a future, fully autonomous CineForge production mode that can generate a complete short film from a user brief while preserving validation, provenance, reproducibility, safety, render budgets, human-review policy, and deterministic execution.

This is not an MVP dependency.

## Non-Negotiable Execution Boundary

CineForge remains the deterministic execution engine.

- ComfyUI remains isolated.
- The backend owns queue state.
- GPU video generation remains serialized on the 24GB VRAM machine.
- Workflow mutation remains manifest-based.
- Benchmark gates remain mandatory.
- FFmpeg probe validation remains mandatory.
- AI agents remain advisory and proposal-based.
- Agents must not directly mutate workflow JSON, queue state, database records, model registry entries, asset paths, ComfyUI submissions, or FFmpeg commands.

Autonomy means CineForge can decide which validated proposal to execute next under policy. It does not mean agents receive direct write access.

## Autonomy Levels

| Level | Name | Description | Human Required? | Execution Authority |
|---|---|---|---|---|
| L0 | Manual | User creates shots, prompts, queues, and assemblies manually. | Yes | User actions through CineForge |
| L1 | Assisted | AI suggests prompts, shot lists, continuity notes, and fixes. | Yes | CineForge validates proposals; user executes |
| L2 | Auto-Draft | AI can create draft storyboards, timelines, prompts, and retry suggestions, but cannot execute renders without approval. | Yes for execution | CineForge stores draft proposals |
| L3 | Auto-Render | CineForge may auto-render approved timeline slots within policy limits and benchmark-safe presets. | Only for high-risk actions | CineForge queue scheduler |
| L4 | Auto-Repair | CineForge may detect failed/weak clips, generate revised prompts/settings, re-render, and select better candidates within budget. | Only for major changes | CineForge retry and QA services |
| L5 | Supervised Autonomous Production | CineForge can produce a complete short film from a brief, including planning, rendering, QA, retries, assembly, and final report, pausing only for policy violations, budget overruns, unsafe model changes, or final approval. | Final approval and policy escalations | CineForge autonomous director under policy engine |

## Autonomous Director Loop

The fully autonomous workflow is a controlled loop:

1. User submits creative brief, target duration, output profile, and autonomy level.
2. AI Orchestration Layer proposes story plan, style guide, character bible, shot list, and duration plan.
3. CineForge validates the plan against runtime, duration, model, benchmark, safety, privacy, and budget policies.
4. CineForge creates timeline slots only after plan approval or allowed policy.
5. AI proposes shot prompts, negative prompts, continuity references, and retry intent.
6. CineForge validates prompts, settings, model/LoRA compatibility, and workflow template manifests.
7. CineForge renders preview candidates using benchmark-safe presets.
8. Automated Technical QA scores outputs for decode, duration, stream compatibility, black frames, frozen frames, flicker, blur, and metadata.
9. Creative and Continuity QA evaluates prompt adherence, character consistency, location continuity, prop continuity, motion continuity, and story usefulness.
10. CineForge decides accept, retry, repair, request human review, or abandon slot.
11. Retry engine generates safe repair attempts within render budget and benchmark bounds.
12. CineForge ranks candidate clips and selects best candidates according to policy.
13. Batch Planner groups eligible jobs by model, quantization, text encoder, VAE, LoRA stack, and risk tier while preserving dependencies.
14. FFmpeg service validates clip compatibility with `ffprobe`.
15. CineForge assembles a draft cut.
16. Final assembly validation checks duration, decode integrity, missing clips, audio/subtitle presence, output profile, hashes, and manifest completeness.
17. CineForge creates final autonomous run report with all prompts, seeds, workflows, telemetry, hashes, failures, retries, selected outputs, approvals, and policy decisions.
18. Human reviews final cut if required by policy.

## AI Proposal API Endpoints

These endpoints belong in an `ai_orchestration` or `autonomy` module, not in the GPU worker.

| Endpoint | Purpose | Execution Boundary |
|---|---|---|
| `POST /ai/proposals` | Store an AI-generated proposal | Writes proposal record only |
| `GET /ai/proposals/{proposal_id}` | Retrieve proposal | Read-only |
| `POST /ai/proposals/{proposal_id}/validate` | Validate proposal against CineForge policy and schemas | No execution |
| `POST /ai/proposals/{proposal_id}/approve` | Approve proposal for execution | Approval record only |
| `POST /ai/proposals/{proposal_id}/reject` | Reject proposal with reason | Rejection record only |
| `POST /ai/proposals/{proposal_id}/execute` | Convert approved proposal into normal CineForge action | Calls existing deterministic services |
| `POST /autonomy/runs` | Start autonomous production run | Creates run state, no direct ComfyUI access |
| `GET /autonomy/runs/{run_id}` | Get autonomous run state | Read-only |
| `POST /autonomy/runs/{run_id}/pause` | Pause autonomous run | Scheduler flag |
| `POST /autonomy/runs/{run_id}/resume` | Resume autonomous run after policy check | Scheduler flag |
| `POST /autonomy/runs/{run_id}/cancel` | Cancel autonomous run | Stops future actions; running Comfy job uses normal cancel path |
| `GET /autonomy/runs/{run_id}/report` | Retrieve final autonomous run report | Read-only |

## Autonomy Run State Machine

Autonomous production runs should use explicit states:

```text
draft_requested
planning
plan_validating
timeline_created
prompt_drafting
prompt_validating
preview_rendering
preview_qa
repair_planning
retry_rendering
candidate_selection
final_rendering
assembly_preflight
assembling
final_validation
final_report_ready
awaiting_human_review
complete
paused
canceled
failed_budget_exceeded
failed_policy_violation
failed_runtime_error
```

Every state transition writes an `autonomy_run_events` record containing actor, reason, input hashes, output hashes, policy result, and next allowed states.

## Autonomy Policy Engine

CineForge must enforce policy before any autonomous action executes.

| Policy Area | Example Rule | Blocking Behavior |
|---|---|---|
| Render budget | Maximum render attempts per clip | Pause or fail run when exceeded |
| Time budget | Maximum runtime per campaign | Pause and request approval |
| Disk budget | Stop if free disk falls below threshold | Pause before enqueue/assembly |
| VRAM risk | Block presets above benchmark-safe tier | Reject proposal |
| Thermal risk | Pause when temperature exceeds threshold | Cooldown and resume if allowed |
| Model risk | Block unbenchmarked model promotion | Require human approval and benchmark |
| LoRA risk | Block unverified LoRA stack | Reject or require validation run |
| Workflow risk | Block workflow template changes without approval | Require human approval |
| Queue risk | Keep GPU render jobs serialized | Never create parallel GPU renders |
| Assembly risk | Require probe validation before final assembly | Block assembly |
| Hosted AI risk | Do not send sensitive local files or full workflow JSON unless allowed | Redact or require approval |
| Final output | Require human approval before marking final delivery complete | Await review |

## Render Budget Controls

Every autonomous run must define:

| Budget | Example |
|---|---|
| Max total render attempts | 300 |
| Max attempts per timeline slot | 3 preview, 2 candidate, 1 final |
| Max wall-clock time | 12 hours |
| Max disk usage | 500GB |
| Max final clips | 48 for a 4-minute short at 5 seconds each |
| Max high-risk jobs | 5 before forced restart/cooldown |
| Max hosted AI calls | Configurable |
| Max retry depth | 2 automatic repair rounds |
| Stop condition | Missing model, repeated OOM, no acceptable clip after N attempts |

Budget accounting must include failed jobs, interrupted jobs, QA-rejected jobs, FFmpeg intermediates, previews, final candidates, hosted AI calls, and telemetry files.

## Automated Technical QA Service

The Technical QA Service evaluates generated clips before they are accepted into a timeline.

| QA Check | Purpose | Implementation Signal |
|---|---|---|
| Decode validation | Confirms file can be read fully | `ffmpeg -v error -i file -f null NUL` |
| Duration check | Confirms clip length matches target tolerance | `ffprobe` format duration |
| Resolution/fps check | Confirms output profile compatibility | `ffprobe` streams |
| Black-frame detection | Rejects failed/empty generations | Histogram/luma thresholds |
| Frozen-frame detection | Detects no-motion failures | Frame difference sampling |
| Severe flicker detection | Flags unstable temporal outputs | Luma/color deltas over time |
| Blur/sharpness estimate | Flags unusably soft clips | Laplacian/edge score |
| Brightness/exposure histogram | Detects overdark/overbright outputs | Histogram percentiles |
| Audio presence check | Required for final outputs with audio | `ffprobe` audio streams |
| Subtitle presence check | Required for captioned outputs | sidecar or subtitle stream |
| FFprobe compatibility | Determines stream-copy concat safety | stream profile comparison |
| Output hash recording | Supports provenance and replay | SHA256 |

Technical QA can reject or escalate. It cannot bypass benchmark gates or workflow validation.

## Creative and Continuity QA Service

AI agents may evaluate creative quality, but CineForge stores their evaluations as review records, not ground truth.

| Dimension | Example Question | Output |
|---|---|---|
| Prompt adherence | Does the clip match the requested action? | score + rationale |
| Character consistency | Does the same character remain recognizable? | score + issue tags |
| Location consistency | Does the setting remain coherent? | score + issue tags |
| Prop continuity | Does the object remain consistent? | score + issue tags |
| Motion continuity | Does action flow from the prior shot? | score + bridge recommendation |
| Comedy/dramatic beat clarity | Is the intended beat understandable? | score + rewrite suggestion |
| Shot usefulness | Can this clip be used in the current slot? | accept/retry/escalate |
| Bridge-shot need | Is an extra transition shot needed? | proposal |
| Regeneration need | Should the clip be retried with safer prompt/settings? | retry proposal |

Creative QA results are advisory unless policy explicitly permits auto-selection below a risk threshold.

## Retry and Repair Recipes

CineForge should maintain structured retry recipes.

| Failure Type | Detection | Safe Retry Action |
|---|---|---|
| OOM | ComfyUI error, process crash, peak VRAM | Reduce frame count, then resolution, then steps, then use smaller/stronger quant |
| Node error | `/prompt` `node_errors` | Validate workflow manifest and `object_info`; block until fixed |
| Missing model file | Loader failure | Mark model unavailable; do not retry until registry corrected |
| WebSocket disconnect | WS closed unexpectedly | Poll history with backoff before marking failed |
| Stuck job | No progress + low GPU utilization | Interrupt; if VRAM is not released, restart ComfyUI |
| Black frames | QA histogram | Retry with different seed/settings or mark preset failed |
| Frozen/no-motion clip | Frame-diff QA | Retry with motion prompt/settings or alternate seed |
| Temporal artifacts | QA/human/AI review | Shorter clip, lower motion, I2V continuity, alternate seed |
| Character drift | Continuity review | Use reference image/I2V, character prompt reinforcement, approved LoRA only |
| Prompt mismatch | Creative QA | Repair prompt; keep benchmark-safe settings |
| FFmpeg concat failure | Probe mismatch or FFmpeg error | Normalize clips to common mezzanine/delivery profile |
| Thermal issue | Sustained high temp/clocks drop | Pause queue, cooldown, resume later |
| Disk-space issue | Preflight check fails | Stop run and request cleanup |

Repair recipes are parameterized proposals. CineForge still validates the resulting generation request.

## Batch Planner for Efficiency

The Batch Planner may reorder eligible jobs to reduce model reloads while preserving timeline dependencies and priority.

| Goal | Strategy |
|---|---|
| Reduce model reloads | Group by model/quant/text encoder/VAE |
| Reduce LoRA churn | Group by LoRA stack |
| Reduce thermal risk | Insert cooldowns after high-risk jobs |
| Reduce VRAM fragmentation | Restart ComfyUI after high-risk batches |
| Preserve continuity | Keep dependent I2V bridge shots ordered |
| Preserve priority | Do not reorder urgent/final jobs behind low-priority previews |
| Protect disk | Estimate output size before batch execution |

The Batch Planner must not create parallel GPU generation jobs on the 24GB GPU.

## Thermal, Disk, and VRAM-Aware Autonomous Scheduling

Autonomous scheduling uses telemetry gates before every render and assembly step:

- Free VRAM estimate and benchmark risk tier.
- Current GPU temperature, clocks, and recent throttling.
- System RAM headroom.
- Disk free-space estimate including intermediates.
- Current ComfyUI process health.
- Queue depth and current job state.
- Restart/cooldown counters.

High-risk jobs are serialized, separated by cooldowns, and followed by memory recovery checks. If `/free` does not recover memory, the supervised ComfyUI worker is restarted before the next render.

## Candidate Clip Scoring and Selection

Candidate selection should combine technical, creative, continuity, and policy scores.

| Score | Inputs | Notes |
|---|---|---|
| Technical score | decode, duration, black/frozen/flicker/blur, output profile | Hard failures reject candidate |
| Creative score | prompt adherence, shot usefulness, beat clarity | AI advisory or human review |
| Continuity score | character, location, prop, motion, bridge need | AI advisory plus project rules |
| Cost score | render time, attempts used, thermal impact | Used for budget-aware decisions |
| Policy score | model/LoRA/workflow risk, approval requirements | Can force escalation |

Default rule: select the highest-scoring candidate only if hard QA passes and policy allows auto-selection. Otherwise pause for human review.

## Final Assembly Validation

Before final delivery, CineForge validates:

- Every required timeline slot has a selected asset.
- Selected assets exist and hashes match.
- Every selected clip has passed technical QA.
- `ffprobe` confirms compatible stream properties or normalization plan exists.
- Output duration is within target tolerance.
- Audio, music, SFX, and subtitles match campaign requirements.
- FFmpeg command is generated from approved templates only.
- Final output decodes without errors.
- Final manifest includes clips, order, transitions, audio, subtitles, hashes, workflow run IDs, and approvals.

## Final Autonomous Run Report

The final report should include:

- User brief and autonomy level.
- Policy configuration and budget limits.
- Story plan, style guide, character bible, and shot list.
- Timeline slots and selected candidates.
- All prompts, negative prompts, seeds, models, quantizations, LoRAs, workflow templates, and workflow snapshots.
- ComfyUI prompt IDs and job statuses.
- Telemetry summaries: VRAM, RAM, temperature, duration, failures.
- QA reports and scores.
- Retry attempts and repair recipes used.
- FFmpeg commands, probes, output hashes, and final manifest.
- Human approvals, escalations, rejected proposals, and policy violations.
- Known limitations and recommended manual review points.

## Sprint 1 Schema and Module Stubs

Sprint 1 should scaffold autonomy without allowing real autonomous execution.

Suggested module stubs:

```text
backend/app/services/ai_orchestration/
backend/app/services/autonomy/
backend/app/services/qa/
backend/app/services/policy/
backend/app/services/retry/
backend/app/services/batch_planner/
```

Suggested database stubs:

| Table | Purpose | Sprint 1 Behavior |
|---|---|---|
| `ai_proposal_records` | Store provider proposals and validation state | Insert/read only |
| `autonomy_runs` | Store autonomous run config and state | Create/read only; no execution |
| `autonomy_run_events` | Audit state transitions | Append-only |
| `autonomy_policies` | Store budget/safety/review policy | Read by validators |
| `qa_reports` | Store technical and creative QA outputs | Insert from manual/test runs |
| `retry_attempts` | Track repair recipes and attempts | Record-only |
| `creative_review_notes` | Store AI/human continuity notes | Record-only |
| `candidate_scores` | Store candidate ranking components | Record-only |

Sprint 1 stubs must not execute autonomous changes. They define schemas, service boundaries, proposal validation, and documentation. Execution still passes through CineForge validation gates, queue control, workflow manifest validation, benchmark bounds, and audit logging.
