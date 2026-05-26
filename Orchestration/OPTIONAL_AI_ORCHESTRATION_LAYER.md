# Optional AI Orchestration Layer

This is an optional extension path, not an MVP dependency. The deterministic CineForge execution engine remains the source of truth for project state, database provenance, workflow validation, queue control, ComfyUI submission, telemetry, FFmpeg assembly, and audit/reproducibility records.

## Core Rule

AI agents may propose changes. CineForge must validate and execute changes.

AI agents must not directly mutate:

- Workflow API JSON.
- Queue state.
- Database records.
- Model registry entries.
- LoRA registry entries.
- FFmpeg commands.
- Asset paths or output manifests.
- ComfyUI prompt submissions.

Every proposed change passes through CineForge validation gates before execution.

This layer can later support autonomous production, but only by creating validated proposal records and autonomy run events. It still cannot directly execute or mutate CineForge state.

## Position in Architecture

```text
Local or Hosted AI Agents
  - Brad
  - Grok CLI
  - Qwen3-Coder-Next
  - Kimi
  - GPT-5.5
  - Claude
  - similar swappable providers
        |
        v
AI Orchestration Adapter
  - provider abstraction
  - prompt/context packaging
  - structured proposal parser
  - policy guardrails
        |
        v
CineForge Proposal Inbox
  - validates schema
  - checks permissions
  - compares against benchmark gates
  - checks model/LoRA/workflow compatibility
  - creates reviewable proposal records
        |
        v
CineForge Deterministic Execution Engine
  - project state
  - database provenance
  - workflow mutation
  - queue scheduling
  - ComfyUI API submission
  - telemetry capture
  - FFmpeg assembly
  - audit log
```

## Supported Advisory Tasks

| AI-Assisted Task | Agent Output | CineForge Validation | CineForge Execution |
|---|---|---|---|
| Creative planning | Story beats, shot list, campaign outline | Schema, duration, slot count, brand rules | Creates timeline slots only after approval |
| Shot prompting | Candidate prompt/negative prompt text | Prompt schema, banned terms, length, project policy | Stores prompt version and enqueues if approved |
| Continuity review | Notes on character drift, scene mismatch, missing bridge shots | Asset existence, clip metadata, reviewer confidence | Creates review notes or replacement suggestions |
| Gap detection | Missing slots, short duration, absent audio/captions | Timeline manifest validation | Opens tasks/proposals |
| Failed-shot diagnosis | Likely cause and next settings to try | Error logs, benchmark caps, model compatibility | Creates safe retry request |
| Prompt repair | Revised prompt and parameter recommendations | Parameter bounds, model preset gates | Creates new clip iteration |
| Next-action recommendations | Ranked action list | Permissions and project state | Presents to human or automation policy |
| Benchmark interpretation | Suggested preset promotion/rejection | Benchmark thresholds and stored telemetry | Updates preset status only through CineForge |

## Provider-Agnostic Adapter Contract

The AI layer should expose a narrow interface:

```json
{
  "provider": "gpt-5.5|claude|grok-cli|qwen3-coder-next|kimi|brad|local",
  "model": "string",
  "task_type": "creative_plan|shot_prompt|continuity_review|failure_diagnosis|prompt_repair|next_action",
  "input_context_hash": "sha256",
  "proposal": {
    "proposal_type": "string",
    "summary": "string",
    "changes": [],
    "rationale": "string",
    "confidence": "low|medium|high",
    "requires_human_review": true
  },
  "citations_or_context_refs": [],
  "created_at": "iso-8601"
}
```

Agents return proposals, not commands. The adapter must reject free-form outputs that cannot be parsed into a known proposal schema.

## Proposal Types

| Proposal Type | Allowed Fields | Forbidden Fields |
|---|---|---|
| `create_shot_list` | slot descriptions, target duration, creative intent | direct DB inserts |
| `revise_prompt` | prompt text, negative prompt text, rationale | direct workflow node IDs |
| `retry_failed_shot` | suggested preset, seed policy, lower-risk settings | direct queue mutation |
| `continuity_fix` | source clip, target clip, issue type, proposed bridge shot | direct asset overwrite |
| `benchmark_recommendation` | promote/reject/needs-test and rationale | direct model registry update |
| `assembly_note` | clip ordering notes, transition suggestions | raw FFmpeg command execution |
| `autonomy_plan` | story plan, style guide, character bible, duration plan | direct timeline/database mutation |
| `qa_review` | technical/creative scores, issue tags, retry recommendation | direct candidate selection |
| `batch_plan` | grouped job order and cooldown recommendations | direct queue reorder |

## Validation Gates

CineForge validates every proposal using:

- JSON schema validation.
- Project permission checks.
- Timeline duration and slot constraints.
- Model/quant/LoRA compatibility registry.
- Benchmark promotion gates.
- Workflow template manifest validation.
- Resolution/frame/step safety bounds.
- Disk-space and path safety checks.
- Human review rules for high-impact changes.
- Audit logging.

If validation fails, CineForge stores the proposal as rejected with reasons. The agent may be asked for a revised proposal, but the agent still does not execute anything.

## Human Review Policy

Human approval is required when a proposal:

- Changes selected final clips.
- Promotes a benchmark preset.
- Introduces a new model, quantization, workflow template, or LoRA.
- Changes final assembly settings.
- Increases VRAM risk tier.
- Uses hosted AI with sensitive project material.
- Deletes or supersedes assets.

Lower-risk proposals, such as alternate prompt drafts, may be auto-accepted only if project policy allows it and CineForge validation passes.

## Autonomy Extension Contract

For L3-L5 autonomy, agents still produce proposals. CineForge's Autonomy Controller decides whether an approved proposal can become a deterministic CineForge action.

| Autonomous Need | Agent Role | CineForge Role |
|---|---|---|
| Story planning | Propose plan, acts, shots, duration, style | Validate policy, create timeline slots |
| Prompt generation | Propose prompt/negative prompt candidates | Validate prompt schema and benchmark-safe settings |
| QA review | Propose creative/continuity scores | Store review records and combine with technical QA |
| Retry repair | Propose failure diagnosis and repair intent | Apply safe retry recipe and enqueue normal job |
| Candidate selection | Propose ranked candidates | Enforce hard QA, policy, budget, and approval rules |
| Final assembly | Propose assembly notes | Generate FFmpeg commands only from approved templates |

The full autonomous architecture is documented in `AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.

## AI Proposal API Additions

These endpoints are future extension endpoints, not GPU worker endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /ai/proposals` | Store an AI-generated proposal |
| `GET /ai/proposals/{proposal_id}` | Retrieve proposal |
| `POST /ai/proposals/{proposal_id}/validate` | Validate proposal against CineForge rules |
| `POST /ai/proposals/{proposal_id}/approve` | Approve proposal for execution |
| `POST /ai/proposals/{proposal_id}/reject` | Reject proposal with reason |
| `POST /ai/proposals/{proposal_id}/execute` | Convert approved proposal into a normal CineForge action |
| `POST /autonomy/runs` | Start an autonomous production run |
| `GET /autonomy/runs/{run_id}` | Get autonomous run state |
| `POST /autonomy/runs/{run_id}/pause` | Pause autonomous run |
| `POST /autonomy/runs/{run_id}/resume` | Resume autonomous run |
| `POST /autonomy/runs/{run_id}/cancel` | Cancel autonomous run |
| `GET /autonomy/runs/{run_id}/report` | Retrieve final run report |

## Security and Reproducibility

- Hosted providers receive only the minimum necessary context.
- Do not send local file paths, secrets, proprietary assets, or full workflow JSON unless explicitly allowed.
- Store provider, model, prompt/context hash, response hash, proposal JSON, validation result, and human approval result.
- Treat agent output as untrusted input.
- Never allow shell command execution from agent output.
- Never allow agents to write directly into the ComfyUI folder, model folders, database, or FFmpeg command templates.

## MVP Boundary

The MVP must work without this layer. The MVP execution design remains:

```text
User or UI creates generation request
-> CineForge validates workflow/model/settings
-> CineForge queues one GPU job
-> CineForge submits to ComfyUI
-> CineForge records telemetry/assets/provenance
-> CineForge assembles with FFmpeg
```

The AI Orchestration Layer can be added later as:

```text
AI proposes generation request or review note
-> CineForge validates proposal
-> Human or policy approves
-> CineForge executes deterministic flow
```

## Implementation Recommendation

Add the layer as a separate module named `ai_orchestration` or `advisory_agents`, not inside the queue worker or workflow mutation service. Its only write path should be `proposal_records`. CineForge services then convert approved proposals into ordinary first-class project actions.
