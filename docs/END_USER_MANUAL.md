# CineForge End User Manual

Date: 2026-07-16

This manual explains how to use the current CineForge local app from the browser. It is written for an operator using CineForge on a local workstation.

## 1. What CineForge is

CineForge is a local AI video-production control app. The current app is focused on:

- project and campaign planning,
- Storyboard Phase A planning,
- provider/model-routing records,
- local runtime readiness visibility,
- safe local job and handoff manifests,
- gated local queue, runtime, and post-production operator controls,
- operator packets/runbooks/templates,
- checkpoint/watchdog visibility.

The app is intentionally local-first. Public/autonomous generation is not enabled by default.

## 2. Current local app URLs

When started with the current development setup:

- Frontend UI: `http://127.0.0.1:5173/`
- Backend API: `http://127.0.0.1:8010/`

If your backend is started on another port, set the frontend API base URL before starting Vite:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8010"
# or
$env:VITE_CINEFORGE_API_BASE_URL="http://127.0.0.1:8010"
```

## 3. Starting the app

From the repository root:

```powershell
.\.venv\Scripts\python -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

In a second terminal:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173/
```

## 4. What the app does not do automatically

The current UI does not automatically:

- start ComfyUI unless both auto-start and hardware-operator configuration gates were explicitly enabled,
- contact ComfyUI,
- probe GPU hardware,
- run runtime-health probes,
- run FFmpeg or ffprobe,
- submit generation prompts,
- enqueue live generation jobs,
- render media,
- run benchmarks,
- enable public generation.

Planning approval is not the same as live generation. Storyboard approval records an approved planning snapshot; it does not start a render.

## 5. Main navigation

The frontend contains top-level app pages and the Storyboard Studio.

### Dashboard

Use Dashboard to confirm the FastAPI backend is reachable and to see high-level local-control status.

Typical checks:

1. Open the frontend.
2. Confirm the backend status card reports a connected backend.
3. Review local safety and project summary cards.

### Projects

Use Projects to create and view CineForge projects.

Common actions:

1. Click Projects.
2. Create a project with a name and optional description.
3. Copy the project ID if you need to create a Storyboard story manually.

Projects are database-backed planning records. Creating a project does not generate media.

### Campaigns

Use Campaigns to create campaign records linked to projects. Campaigns are planning/scaffold records only.

### Jobs

Use Jobs to inspect backend jobs and semantic manifests. An acknowledged Queue action creates a durable job through the operator endpoint; it does not directly submit work to ComfyUI. Submission can occur only when the separate queue-worker and hardware-operator gates are enabled and the workflow/model binding is admitted.

A local job may record:

- project/run naming,
- sanitized output prefix,
- offline readiness state,
- no-execution acknowledgement.

### Queue

Queue is a read-only queue metadata page. It does not mutate the queue and does not start a worker.

### Runtime

Runtime is the main local-readiness page. It shows:

- local runtime catalog,
- output policy,
- local MVP readiness,
- public readiness,
- safe-boundary status,
- checkpoint watchdog status,
- M4 preflight and ladder metadata,
- existing runtime evidence,
- FFmpeg recipe catalog metadata,
- operator templates/runbooks/packets.

Runtime loads readiness, configuration, and owned-process state passively. Probe, start, restart, and stop buttons require explicit acknowledgement and call default-off operator endpoints; they are not executed on page load.

### System Health

System Health shows backend health only by default. It does not automatically call live ComfyUI, GPU, or FFmpeg health probes.

### Roadmap / Disabled Features

These pages explain intentionally disabled features and phase status.

## 6. Storyboard Studio

Storyboard Studio is the main planning workspace.

Current Studio areas include:

- Overview,
- Story & Chapters,
- Storyboard,
- Characters,
- Voices,
- Starting Images,
- Model Routing,
- Workflows,
- Exports,
- Project Settings.

### 6.1 Creating a planning story

1. Create or select a Project.
2. Open Storyboard Studio.
3. Create a story record using the project ID.
4. Enter title, base story, and target duration.

This creates planning data only.

### 6.2 Story & Chapters

Use Story & Chapters to shape the story hierarchy:

- story details,
- chapters,
- scenes,
- shots,
- duration planning,
- narrative structure.

### 6.3 Storyboard

Use Storyboard to edit shot-level planning information:

- shot title,
- duration,
- visual description,
- prompt package text,
- production status,
- approval state,
- character links.

Approving a shot is a planning state change only. It does not render the shot.

### 6.4 Characters

Use Characters to create and maintain planning character records and character-reference links. Managed asset APIs may be available depending on backend state; these are still planning assets, not generated outputs.

### 6.5 Voices

Use Voices to configure voice profile records, consent metadata, and preview-related planning records. Voice preview/generation is not automatic from planning approval.

### 6.6 Starting Images

Use Starting Images for planning records and managed asset references. Uploading or approving a starting image is not the same as image generation.

### 6.7 Model Routing

Use Model Routing to manage planning-provider profiles and task assignments.

Current provider preference policy:

1. OpenAI is the default hosted planning provider when configured.
2. xAI/Grok is the secondary hosted planning provider option.
3. The deterministic mock provider remains available for offline/local testing.

Current implementation note: OpenAI has an implemented planning adapter; xAI/Grok is represented as a provider identity and switch target, and can be promoted once the xAI adapter is implemented/configured.

### 6.8 Workflows

Use Workflows to review workflow/template metadata. This page does not install models, download nodes, or mutate ComfyUI.

### 6.9 Exports

Exports provides planning exports such as JSON and CSV through backend APIs. PDF, EDL, render packages, and media outputs remain disabled unless future implementation enables them.

### 6.10 Project Settings

Use Project Settings for planning settings and policy labels. API credentials are not stored through this page.

## 7. Local runtime readiness

The Runtime page summarizes whether the local MVP is ready for the next controlled stage.

Important statuses:

- Local MVP readiness: whether the local control-plane requirements are met.
- Public readiness: intentionally fail-closed unless public-release gates are satisfied.
- Safe boundary: static evidence that unsafe local/public execution surfaces are absent.
- Checkpoint watchdog: confirms implementation loop discipline and clean-state visibility.
- M4 ladder/preflight: serialized metadata for future live hardware/probe stages.
- FFmpeg recipes: allowlisted recipe metadata only, not execution.

## 8. Operator packets, runbooks, and templates

### Approval templates

Approval templates show exact wording shapes for future live actions. They are reference material only.

### Runbooks

Runbooks describe prerequisites, stop rules, and expected evidence. Viewing a runbook does not approve or start a run.

### Operator packets

Operator packets are pending review records. Creating a packet records intent/review metadata only. It does not approve work and does not start execution.

## 9. Offline local manifests

CineForge can create safe, offline manifests for later review.

Examples:

- local job manifests,
- semantic generation request manifests,
- storyboard-to-semantic handoff manifests,
- post-production plan manifests,
- stored recipe command manifests.

These manifests are evidence/planning artifacts. They do not execute tools by themselves.

## 10. Post-production planning

Post-production pages and APIs can prepare deterministic recipe plans and command-array metadata. An acknowledged Execute action can run only a persisted allowlisted recipe when the FFmpeg-operator gate is enabled. The executor revalidates argv, managed paths, input hashes, output nonexistence, and the final probe/hash evidence.

The current system forbids raw user-authored FFmpeg command strings.

## 11. Generation readiness

The current app is ready to prepare and inspect controlled local-generation planning state. A successful real render still requires a controlled local generation run and evidence capture.

Before treating a profile or preset as generation-ready, CineForge needs evidence such as:

- admitted workflow/template graph,
- object-info compatibility,
- model/source/hash evidence,
- successful local smoke output,
- recovery/next-job behavior,
- benchmark evidence where required,
- output provenance,
- deterministic post-production validation,
- human QA.

## 12. Provider engine preference

Current operator preference:

- Default planning engine: OpenAI.
- Secondary planning engine: xAI/Grok.
- Switch option: provider routing/profile configuration should allow choosing the provider once the corresponding adapter is implemented and configured.
- Offline fallback/testing: deterministic mock provider.

Never enter API keys into planning notes, project descriptions, prompt text, or arbitrary metadata fields.

## 13. Troubleshooting

### Frontend does not load

Check that Vite is running:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Then open `http://127.0.0.1:5173/`.

### Backend unavailable

Check that FastAPI is running:

```powershell
.\.venv\Scripts\python -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

Then open `http://127.0.0.1:8010/`.

### Frontend points at the wrong backend port

Set:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8010"
```

Then restart Vite.

### Database missing or empty

Create or refresh the local DB:

```powershell
.\.venv\Scripts\python scripts\create_db.py
```

### Runtime page says something is blocked

Blocked readiness means evidence is missing or a gate is intentionally fail-closed. It does not necessarily mean the app is broken.

### No Generate button is visible

That is expected in the current planning/local-readiness UI. Generation is not exposed as a public/autonomous UI button.

## 14. Validation command for users/operators

Run the offline-safe validation suite from the repo root:

```powershell
.\.venv\Scripts\python scripts\run_offline_safe_validation.py --fail-on-dirty
```

Current checkpoint truth: `308 passed`, frontend lint/build passed, static safe-boundary validation passed, and checkpoint watchdog passed.

This validation suite does not run live runtime/media actions.

## 15. Glossary

- Archetype: a high-level capability profile such as CF-VID-01.
- Preset: a specific disabled/gated configuration record for a capability.
- Storyboard Phase A: planning phase ending in an approved production plan.
- Operator packet: pending review metadata for a future live or offline action.
- Runbook: human-readable prerequisites and stop rules.
- Local MVP readiness: local-only readiness rollup.
- Public readiness: public-release gate, currently fail-closed.
- Safe boundary: static and API-visible proof that unsafe public/live paths are absent.
- Checkpoint watchdog: implementation-loop guard and clean-state report.
- Manifest: a file-backed plan/evidence record that does not execute by itself.
