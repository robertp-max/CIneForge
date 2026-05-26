# Architecture Blueprint

## Executive Summary

Build the system as a local orchestration app that controls an isolated ComfyUI worker over HTTP/WebSocket, stores every generation input/output in a database, and uses FFmpeg for deterministic media assembly. Do not embed ComfyUI in the app process. Do not run concurrent GPU video generations on the 24GB GPU.

CineForge is the deterministic execution engine. An optional AI Orchestration Layer may assist with creative planning, prompt drafting, continuity review, failure diagnosis, and next-action recommendations, but it does not replace CineForge and is not an MVP dependency. AI agents may propose changes; CineForge validates and executes them.

A future Autonomous Production Layer may let CineForge produce a complete short film from a user brief, but only as a policy-governed extension. It does not change the MVP execution path: ComfyUI remains isolated, the backend owns the queue, GPU video generation remains serialized, and agents remain proposal-only.

Recommended MVP path:

- Prototype models: Wan2.1 1.3B and LTXV 2B.
- First larger candidate: Wan2.2 5B or Wan2.1/2.2 14B FP8 after benchmarks.
- Final-candidate lane: Wan2.2 A14B FP8 only after 81-frame 480p/720p local tests pass.
- LTX-2.x: research/elite lane until 24GB laptop benchmarks prove stable.

## System Diagram

```text
React/Electron or Web UI
        |
        v
Local Backend API
  - project/timeline editor
  - prompt/version service
  - benchmark service
  - workflow mutation service
  - queue scheduler
        |
        +--> PostgreSQL or SQLite/Postgres-compatible DB
        +--> Asset Store: inputs, workflow snapshots, outputs, probes, logs
        +--> ComfyUI Worker Supervisor
        |       |
        |       +--> Headless ComfyUI HTTP/WebSocket API
        |       +--> Isolated Python/portable runtime
        |       +--> Models, VAEs, text encoders, LoRAs
        |
        +--> FFmpeg Worker
        +--> Telemetry Sampler: nvidia-smi/NVML, process metrics, disk

Optional AI Orchestration Layer
  - local or hosted agents: Brad, Grok CLI, Qwen3-Coder-Next, Kimi, GPT-5.5, Claude, similar
  - advisory only: creative plans, shot prompts, continuity notes, failed-shot diagnosis
  - writes proposal records only
        |
        v
  CineForge validation gates
  - schema validation
  - model/LoRA/workflow compatibility
  - benchmark bounds
  - human approval policy
  - audit logging

Future Autonomous Production Layer
  - autonomy levels L0-L5
  - autonomous director loop
  - policy engine and render budgets
  - technical QA and creative continuity QA
  - retry/repair recipes
  - batch planner
  - final autonomous run report
        |
        v
  CineForge deterministic services only
```

## Hardware Constraint Analysis

| Hardware Factor | Impact on LTX | Impact on Wan | Impact on LoRA Use | Impact on Quantization | Recommended Design Choice |
|---|---|---|---|---|---|
| 24GB VRAM | LTXV 2B comfortable; 13B/19B/22B require FP8/Q/offload | Wan 1.3B safe; 14B/A14B require FP8/offload | LoRAs add pressure and version risk | FP8/GGUF are necessary for large models | Serialize jobs, benchmark every preset |
| 192GB RAM | Useful for offload/model staging | Useful for T5/UMT5/offload | Can hold LoRA/model cache on CPU | Helps offload but slows inference | Use RAM for staging, not as performance substitute |
| Laptop thermals | Long LTX runs can throttle | Long Wan runs can throttle | Multi-LoRA can extend runtime | Slower quant may increase heat duration | Thermal-aware queue and cooldown |
| Windows native | Portable ComfyUI is practical | Native Comfy examples work | Node installs can drift | CUDA/PyTorch stack must be pinned | MVP on Windows portable/venv |
| VRAM fragmentation | Long sessions risky | Long sessions risky | Repeated LoRA swaps risky | Mixed loaders increase risk | Restart policy after high-risk batches |
| Single GPU | No parallel large jobs | No parallel large jobs | No parallel LoRA experiments | One quant/model loaded at a time | One GPU worker |

## Workload Feasibility

| Workload | Expected VRAM Pressure | 24GB Feasible? | Required Compromises | Risk |
|---|---:|---|---|---|
| 480p short preview | Medium | Yes | Small/FP8 models | Low |
| 720p short preview | Medium-high | Yes for small/FP8; test 14B | FP8, shorter frames | Medium |
| 1080p target output | Very high | Usually not natively for 14B | Generate lower-res, upscale/postprocess | High |
| 5-second clip | Medium-high | Yes with correct model | 49-121 frames depending FPS | Medium |
| 10-second clip | High | Prefer split clips | Stitch two 5-sec clips | High |
| 81-frame generation | Medium-high | Good benchmark tier | 480p/720p limits | Medium |
| 121-frame generation | High | Test-required | Lower resolution/quant/offload | High |
| 257-frame generation | Very high | Not MVP | LTX only if benchmark passes | Very high |
| 14B model with quantization | Very high | Candidate only | FP8/GGUF/offload | High |
| 1.3B model | Low-medium | Yes | Lower quality | Low |
| LoRA-enabled generation | Adds pressure | Test-required | One LoRA at a time initially | Medium |
| I2V | High | Yes with reduced settings | Image prep and shorter clips | Medium-high |
| T2V | Model-dependent | Yes | Use preview tiers | Medium |
| VAE decode | Burst pressure | Test-required | Tiling/offload | High |
| Upscale | High if GPU | Yes if separate stage | CPU/GPU scheduling | Medium |
| Interpolation | Medium/high | Optional | Use only after final selection | Medium |
| Overnight batch queue | Accumulated risk | Only after soak test | Bounded batches/restarts | High |

## LTX vs Wan

| Dimension | LTX | Wan | Winner for RTX 5090 Laptop Prototype | Winner for Final Quality | Evidence |
|---|---|---|---|---|---|
| Small-model lane | LTXV 2B | Wan2.1 1.3B | Tie | Depends prompt | Official model cards |
| Larger local lane | 13B/19B/22B high pressure | 14B/A14B FP8 Comfy path | Wan | Wan if benchmarks pass | Comfy Wan docs, LTX docs |
| Frame rules | Clear `8n+1` in official LTX docs | Workflow-dependent in Comfy | LTX | Tie | Official LTX docs; Comfy templates |
| Comfy maturity | Official LTX node repo and built-ins | Native Comfy examples/templates | Tie | Tie | Maintainer repos |
| 24GB risk | High for LTX-2.x | High for A14B but better Comfy FP8 path | Wan | Needs benchmark | Source-backed |
| I2V continuity | Supported | Strong Wan I2V ecosystem | Wan | Wan | Official Wan docs |
| Quant ecosystem | FP8/FP4/Q8/GGUF paths | FP8/GGUF/wrapper paths | Tie | Needs local test | Maintainer repos |

## Preview vs Production Strategy

- Preview: 480p or 704/832-wide, 49-81 frames, low steps, no LoRA initially.
- Candidate: 720p if VRAM allows, 81 frames, one LoRA max.
- Final: generate at the highest stable benchmarked tier, then normalize/upscale/assemble outside ComfyUI.
- Long-form: assemble 180+ short clips, not one long diffusion render.

## MVP vs Elite

MVP optimizes learning speed and reproducibility. Elite adds quality automation, style/character registries, I2V continuity, quality scoring, audio timelines, and thermal-aware scheduling.

Do not build Elite features until the MVP has benchmark data proving which model/quant/frame/resolution tiers are reliable on this exact laptop.

## Optional AI Orchestration Extension

The AI Orchestration Layer is swappable and provider-agnostic. It can use local or hosted agents such as Brad, Grok CLI, Qwen3-Coder-Next, Kimi, GPT-5.5, Claude, or similar systems to propose creative and operational improvements.

Hard boundary:

- Agents may propose shot lists, prompt repairs, continuity notes, failed-shot diagnoses, and next actions.
- Agents must not directly mutate workflow JSON, queue state, database records, model registry entries, or FFmpeg commands.
- CineForge remains responsible for validation, execution, provenance, telemetry, and audit records.

Detailed extension design: `Orchestration/OPTIONAL_AI_ORCHESTRATION_LAYER.md`.

## Future Autonomous Production Layer

Autonomous production is an Elite extension path, not an MVP dependency. It adds a policy-governed director loop on top of the optional AI proposal layer.

| Capability | Future Behavior | Deterministic Boundary |
|---|---|---|
| Autonomy levels | L0 manual through L5 supervised autonomous production | Level controls allowed proposal/execution scope |
| Autonomous director loop | Brief -> plan -> timeline -> prompts -> renders -> QA -> repair -> assembly -> report | CineForge performs every state transition |
| Policy engine | Enforces budgets, benchmark-safe presets, thermal/disk/VRAM limits, privacy, approvals | Blocks or pauses unsafe actions |
| Automated QA | Scores decode, duration, black frames, frozen frames, flicker, blur, stream compatibility | QA results are stored and auditable |
| Creative QA | Reviews prompt adherence, character, setting, props, motion continuity, bridge-shot needs | AI reviews are advisory records |
| Retry engine | Applies safe repair recipes for OOM, node errors, black frames, drift, concat failures | Generates validated retry requests only |
| Batch planner | Groups eligible jobs by model/quant/text encoder/VAE/LoRA while preserving dependencies | Never creates parallel GPU renders |
| Final report | Exports all prompts, seeds, workflows, telemetry, hashes, failures, retries, approvals, outputs | Required before completion |

Detailed autonomous design: `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.

## Autonomy Levels

| Level | Name | Description | Human Required? |
|---|---|---|---|
| L0 | Manual | User creates shots, prompts, queues, and assemblies manually. | Yes |
| L1 | Assisted | AI suggests prompts, shot lists, continuity notes, and fixes. | Yes |
| L2 | Auto-Draft | AI can create draft storyboards, timelines, prompts, and retry suggestions, but not execute renders without approval. | Yes for execution |
| L3 | Auto-Render | CineForge may auto-render approved timeline slots within policy limits and benchmark-safe presets. | Only for high-risk actions |
| L4 | Auto-Repair | CineForge may detect failed/weak clips, generate revised prompts/settings, re-render, and select better candidates within budget. | Only for major changes |
| L5 | Supervised Autonomous Production | CineForge can produce a complete short film from a brief while pausing for policy violations, budget overruns, unsafe model changes, or final approval. | Final approval only |
