# Backend API Flow

This is the app-facing API shape for the local video editor. It wraps ComfyUI, database writes, benchmark logging, and FFmpeg jobs.

Future autonomy APIs must wrap the same deterministic services. They must not give agents direct write access to workflow JSON, queue state, database records, model registry entries, asset paths, ComfyUI submissions, or FFmpeg commands.

## Core Endpoints

| Endpoint | Purpose | Notes |
|---|---|---|
| `POST /projects` | Create project | Stores campaign root |
| `POST /campaigns` | Create campaign | Target duration and output profile |
| `POST /timeline-slots/bulk` | Create 180+ clip slots | Use 5-10 second slots |
| `POST /clips/{clip_id}/iterations` | Create generation request | Validates model/workflow/LoRA compatibility |
| `POST /queue/generation` | Enqueue generation | Backend queue, not direct Comfy queue |
| `GET /jobs/{job_id}` | Job status | Includes Comfy `prompt_id` if submitted |
| `POST /jobs/{job_id}/cancel` | Cancel pending/running | Maps to queue delete or Comfy interrupt |
| `POST /benchmarks/run` | Run benchmark case | Writes telemetry and benchmark rows |
| `POST /assets/{asset_id}/probe` | ffprobe asset | Stores probe JSON |
| `POST /campaigns/{id}/assemble` | Build final video | Creates FFmpeg job |
| `GET /campaigns/{id}/manifest` | Final assembly manifest | Reproducible output plan |

## AI Proposal and Autonomy Endpoints

These are future extension endpoints for `ai_orchestration` and `autonomy` modules. They are not part of the GPU worker and do not bypass validation.

| Endpoint | Purpose | Notes |
|---|---|---|
| `POST /ai/proposals` | Store an AI-generated proposal | Proposal record only; no execution |
| `GET /ai/proposals/{proposal_id}` | Retrieve proposal | Read-only |
| `POST /ai/proposals/{proposal_id}/validate` | Validate proposal against schemas, policy, benchmark bounds, workflow manifests | No execution |
| `POST /ai/proposals/{proposal_id}/approve` | Approve proposal | Approval record; may require human |
| `POST /ai/proposals/{proposal_id}/reject` | Reject proposal with reason | Audit logged |
| `POST /ai/proposals/{proposal_id}/execute` | Convert approved proposal into normal CineForge action | Calls existing deterministic endpoints/services |
| `POST /autonomy/runs` | Start autonomous production run | Creates run state and policy budget |
| `GET /autonomy/runs/{run_id}` | Get autonomous run state | Read-only |
| `POST /autonomy/runs/{run_id}/pause` | Pause autonomous run | Scheduler flag |
| `POST /autonomy/runs/{run_id}/resume` | Resume after policy check | Scheduler flag |
| `POST /autonomy/runs/{run_id}/cancel` | Cancel autonomous run | Cancels future steps; running jobs use normal cancel path |
| `GET /autonomy/runs/{run_id}/report` | Final autonomous run report | Read-only report |

## Generation Request Flow

```text
Client -> Backend: create clip iteration
Backend:
  validate model registry entry
  validate quantization compatibility
  validate LoRA stack compatibility status
  load workflow template + manifest
  patch workflow parameters
  store clip_iteration and workflow_run
  enqueue local GPU job

GPU Worker:
  open Comfy WebSocket
  POST /prompt
  stream events
  collect /history/{prompt_id}
  hash outputs
  ffprobe outputs
  store metrics and status
```

## Queue Policy

- Client never submits directly to ComfyUI.
- AI agents never submit directly to ComfyUI.
- Backend queue is durable and bounded.
- ComfyUI queue depth should stay near 0-1 for GPU generation.
- FFmpeg jobs may run in a separate queue, but GPU encoding should not overlap with diffusion until benchmarked.
- Autonomous runs use the same queue and must not create parallel GPU video renders on the 24GB GPU.

## Validation Gates

Reject a request before ComfyUI if:

- Workflow manifest is missing a required node.
- Model/LoRA compatibility is marked failed.
- Requested resolution/frame count exceeds benchmarked safe tier.
- Disk free-space estimate fails.
- Another high-risk GPU job is running.

Mark as "needs benchmark" instead of rejecting if the user explicitly starts a benchmark job.

## Autonomy Run Flow

```text
User -> Backend: POST /autonomy/runs with brief, target duration, autonomy level, budget
Autonomy Controller:
  create autonomy_run
  request story/shot proposal from AI Orchestration Layer
  store proposal
  validate proposal against policy
  require approval if policy demands
  convert approved proposal into normal CineForge project/timeline actions
  create generation requests through existing validation path
  enqueue serialized GPU jobs through existing queue
  run technical QA and creative QA
  create retry proposals when needed
  select candidates only if QA and policy pass
  assemble through existing FFmpeg path
  validate final output
  create final autonomous run report
```

## Autonomy Policy Checks

Reject, pause, or escalate autonomous actions when:

- Render attempts exceed run or slot budgets.
- Wall-clock, disk, hosted-AI-call, or retry-depth budgets are exceeded.
- Requested model/quant/LoRA/workflow is unbenchmarked or unverified.
- Workflow manifest validation fails.
- FFmpeg probe validation fails.
- Thermal, VRAM, RAM, or disk thresholds are unsafe.
- Human review is required for final output, high-risk model changes, selected final clips, or registry changes.
