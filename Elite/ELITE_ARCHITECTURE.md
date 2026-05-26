# Elite / Version-Two Architecture

Build only after MVP benchmark data identifies stable model/quant/resolution tiers.

## Elite Components

| Elite Component | Purpose | Dependency | Complexity | Expected Benefit |
|---|---|---|---|---|
| Model registry UI | Manage models, hashes, licenses, compatibility | DB schema | Medium | Safer experimentation |
| LoRA registry UI | Track LoRA purpose, strengths, base compatibility | LoRA smoke tests | Medium | Repeatable style/identity |
| Benchmark dashboard | Compare presets over time | Telemetry/benchmark logs | Medium | Evidence-based promotion |
| Thermal-aware scheduler | Pause/cooldown based on temp/clocks | NVML/nvidia-smi | Medium | Overnight stability |
| I2V continuity chain | Use previous clip end frame as next condition | I2V workflows | High | Better long-form continuity |
| Character bible | Store references, prompts, approved LoRAs | Creative review | Medium | Less character drift |
| Style bible | Prompt/style presets and examples | Creative review | Medium | Campaign consistency |
| Prompt optimizer | Generate prompt variants from brief | LLM service | Medium | Faster iteration |
| Auto quality scoring | Detect black frames, blur, face drift, temporal artifacts | CV models | High | Reduce review load |
| Human review UI | Compare iterations and select final | Asset store/DB | Medium | Production workflow |
| Audio timeline | VO/music/SFX/captions alignment | FFmpeg/media schema | Medium | Real campaign assembly |
| Subtitle pipeline | Generate, edit, burn or sidecar captions | ASR/LLM optional | Medium | Publish-ready output |
| Advanced workflow templates | Wan/LTX I2V, LoRA stacks, control adapters | Stable custom nodes | High | Better quality/control |
| Multi-pass rendering | Preview -> candidate -> final -> upscale | Benchmarked presets | High | Better resource use |
| Cloud burst fallback | Use remote GPU for impossible local jobs | API/cost controls | High | Escape 24GB limit |
| Multi-machine expansion | Distributed workers | Scheduler and storage | High | Throughput |
| Autonomous production controller | Produce complete short films from brief under policy | AI proposals, QA, budget, scheduler | High | End-to-end supervised automation |
| Autonomy policy engine | Enforce render, time, disk, VRAM, thermal, model, LoRA, workflow, hosted-AI, and final-review policies | Benchmark data and telemetry | High | Prevents runaway automation |
| Technical QA service | Decode, duration, black/frozen/flicker/blur, stream compatibility, hash checks | FFmpeg/ffprobe/CV checks | Medium | Automated candidate rejection |
| Creative continuity QA service | Prompt adherence, character, location, prop, motion, bridge-shot review | AI reviewers and human policy | High | Better autonomous story coherence |
| Retry and repair engine | Apply safe repair recipes for failed or weak clips | QA reports, error logs, benchmark bounds | High | Reduces manual intervention |
| Candidate scoring service | Rank clips by technical, creative, continuity, cost, and policy score | QA and telemetry | Medium | Automated selection with audit trail |
| Batch planner | Group jobs by model/quant/text encoder/VAE/LoRA while preserving dependencies | Queue and benchmark metadata | Medium | Less reload churn and better thermal control |

## Elite Production Pattern

1. Generate storyboard/timeline slots.
2. Use fast local preview model for all slots.
3. Promote selected slots to balanced model.
4. Use I2V continuity from adjacent selected frames.
5. Apply one approved LoRA stack per campaign style/character.
6. Render final clips in bounded thermal batches.
7. Normalize all selected clips to mezzanine.
8. Assemble, audio-align, subtitle, final encode.
9. Archive final manifest and all provenance.

## Elite Guardrails

- No new custom node enters production without snapshot, smoke test, and rollback plan.
- No LoRA stack enters production without compatibility entry and artifact review.
- No preset enters production without benchmark promotion gates.
- No 30-minute assembly is run without probe validation of every selected clip.
- No autonomous run may bypass CineForge proposal validation, policy gates, backend queue control, workflow manifest validation, or FFmpeg validation.
- No autonomous mode may create parallel GPU video renders on the 24GB GPU.
- No final autonomous delivery is marked complete without the final run report and any required human approval.

## Full Autonomous Production Layer

Elite CineForge may support L5 supervised autonomous production: a user provides a brief, target duration, style constraints, output profile, and policy budget; CineForge plans, renders, QA-checks, repairs, selects, assembles, validates, and reports.

The autonomous layer consists of:

| Module | Responsibility | Hard Boundary |
|---|---|---|
| Autonomous Director | Owns run state machine and next-action selection | Calls deterministic services only |
| AI Orchestration Adapter | Gets story, prompt, review, and repair proposals from local/hosted agents | Writes proposals only |
| Policy Engine | Enforces budgets, approvals, benchmark-safe presets, privacy, thermal/disk/VRAM limits | Blocks unsafe actions |
| Technical QA | Validates media integrity and objective defects | Cannot approve policy violations |
| Creative/Continuity QA | Scores story fit, prompt adherence, character/setting/prop/motion continuity | Advisory unless policy permits |
| Retry Engine | Converts failure classes into safe repair proposals | Must pass generation validation |
| Batch Planner | Reorders eligible jobs for efficiency | Cannot parallelize GPU renders |
| Final Assembly Validator | Confirms probes, duration, streams, audio, subtitles, hashes, manifest | Blocks final completion |
| Run Reporter | Exports provenance, failures, retries, approvals, telemetry, outputs | Required for completion |

## Autonomous Production State Machine

```text
draft_requested -> planning -> plan_validating -> timeline_created
-> prompt_drafting -> prompt_validating -> preview_rendering -> preview_qa
-> repair_planning -> retry_rendering -> candidate_selection
-> final_rendering -> assembly_preflight -> assembling -> final_validation
-> final_report_ready -> awaiting_human_review -> complete
```

Failure and control states:

```text
paused
canceled
failed_budget_exceeded
failed_policy_violation
failed_runtime_error
```

Detailed implementation architecture: `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.
