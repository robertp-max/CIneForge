# CineForge ComfyUI Implementation Plan

**Date:** 2026-07-15<br>
**Status:** Documentation-only checkpoint for a personal/local-only MVP target; this document records offline/mock/local-gated implementation status without claiming public production readiness, live FFmpeg/ComfyUI/GPU enablement, or benchmark completion<br>
**Primary specification:** `C:\Users\razer\Documents\CineForge_ComfyUI_Workflow_Architecture_Consolidated_Corrected.md`  
**Repository:** `C:\AI\Git\CIneForge` at `85af098638fd` (`master`)  
**Orchestrator:** `openai-codex/gpt-5.5`  
**Workers and independent QA:** `xai-auth/grok-4.5`  
**Maximum Grok concurrency:** 48 agents; this is a ceiling, not a target

## 1. Recommended approach

Build the requested architecture on top of CineForge's existing deterministic backend spine rather than replacing it:

1. Preserve the current workflow hashing/patching, durable queue, controlled Comfy submission, GPU lease, runtime catalog, benchmark, path-safety, and FFmpeg foundations.
2. Add a versioned product layer consisting of approximately 10–12 admitted archetypes and exactly 64 semantic presets. Do not create 64 ComfyUI graphs.
3. Add an explicit model/provenance contract for `ltx2_3_22b_distilled_1_1_fp8`; do not confuse the official Distilled 1.1 BF16 checkpoint with an FP8 runtime artifact.
4. Complete workflow admission, semantic compilation, output collection, provenance, and failure recovery before enabling real generation.
5. Admit only the official LTX single-stage and official FLUX base graphs first.
6. Prove all LTX-2.3 profiles serially on the 24 GB RTX 5090 Laptop through a graduated benchmark ladder. Keep every unproven profile at `benchmark_required`.
7. Expand archetypes and enable the 64 presets only after their backing graph/model/profile passes admission, benchmark, recovery, and human QA gates.
8. Keep deterministic editing, captions, timing, normalization, and packaging in FFmpeg, outside ComfyUI.

### Personal/local-only MVP checkpoint (2026-07-16)

The immediate target is a personal, operator-run MVP on the local workstation, not a hosted, multi-user, internet-facing, or public production service. This narrows the immediate hardening bar: public exposure work and public API controls are not prerequisites for a private local trial of an already admitted and gated path. Safe/non-live M6 catalog expansion and M7 readiness/handoff surfaces now exist as planning evidence only; actual expanded preset capability still requires graph admission, benchmark/recovery evidence, and human QA before broader release or public enablement.

Public and autonomous generation remain out of scope and disabled: no public raw `/prompt` proxy, no internet-facing semantic generation endpoint, no job-initiated installs/downloads, and no automatic generation from Storyboard approval. Local operator-only FFmpeg, ComfyUI, and GPU-heavy actions may be considered only after explicit operator approval for the relevant mode/run and after the applicable gates are satisfied: safe managed paths, admitted graph/model/profile pins, local-only storage, default-off operator gates, exclusive GPU lease for Comfy/GPU work, queue-state checks, provenance/audit capture, recovery/stop rules, and human QA where required. This checkpoint does not approve or perform any live FFmpeg, ComfyUI, GPU, render, or benchmark action, and it does not claim runtime readiness.

Current read-only local MVP surfaces now exist: `GET /local-runtime/local-mvp-readiness`, fail-closed `GET /local-runtime/public-readiness`, read-only M6/M7 readiness rollups, offline semantic request manifests, explicit Storyboard-to-offline-semantic handoffs, and Runtime page panels for local/public readiness plus stored operator review packets. These surfaces are inert and evidence-only: they do not create live jobs, approve runs, submit ComfyUI work, execute FFmpeg/ffprobe, acquire a GPU lease, render media, benchmark, or mark any profile/preset public-ready. `POST /local-operator/packets` creates pending review metadata only and always records no approval or execution. M4 live hardware probing/benchmarking and M5 live FFmpeg/ffprobe/assembly remain blocked until explicit operator approval for the exact next run; no live execution has been performed by these readiness checkpoints. Public release hardening and actual expanded preset enablement remain deferred.

## 2. External-reference reconciliation

Primary sources were cross-checked on 2026-07-13.

### Confirmed facts

- The official [`Lightricks/ComfyUI-LTXVideo`](https://github.com/Lightricks/ComfyUI-LTXVideo) README currently requires **32 GB or more VRAM** and describes low-VRAM loaders as a way to fit generation into that class. A 24 GB laptop is therefore experimental, not supported by assumption.
- The official repository contains the requested LTX-2.3 examples under [`example_workflows/2.3`](https://github.com/Lightricks/ComfyUI-LTXVideo/tree/master/example_workflows/2.3), including:
  - `LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json`
  - `LTX-2.3_T2V_I2V_Two_Stage_Distilled.json`
  - `LTX-2.3_ICLoRA_Union_Control_Distilled.json`
  - `LTX-2.3_ICLoRA_Lipdub_Two_Stage_Distilled.json`
  - motion-track and V2V examples.
- The official [`ltx-2.3-22b-distilled-1.1.safetensors`](https://huggingface.co/Lightricks/LTX-2.3/blob/main/ltx-2.3-22b-distilled-1.1.safetensors) file is approximately 46.1 GB and has SHA256 `b33b7fe4bbfe084f484be4aaf90b0f1d95dca20d403ac4c0e037eb8c4f0af7cc`. It is not named or represented as FP8.
- The separate official [`Lightricks/LTX-2.3-fp8`](https://huggingface.co/Lightricks/LTX-2.3-fp8) repository contains distilled FP8 weights, but the current official listing does **not** establish a Distilled **1.1** FP8 artifact. Do not silently substitute the older official distilled FP8 file for the required 1.1 contract.
- M0 update: the operator selected local artifact `C:\AI\ComfyUI_windows_portable\ComfyUI\models\checkpoints\ltx-2.3-22b-distilled-1.1-fp8.safetensors` as the product FP8 artifact. SHA256 is `c5dd96a75c4b588171b9807a8a25fea91e71a3cc7386d8bc245f50a21756cfbb`; header inspection shows the same 5,947 tensor names/shapes and same model config as the verified BF16 source, with 4,444 tensors as `F8_E4M3`. Record it as `converted_derivative`, not `official_artifact`, until conversion provenance is reproduced or otherwise approved.
- Official ComfyUI documentation confirms the required local routes: `POST /prompt`, `GET /object_info`, `GET /history/{prompt_id}`, `/ws`, `/view`, `/upload/image`, `/interrupt`, `/queue`, and `/free`: [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes).
- Official FLUX starting points are available through [ComfyUI FLUX examples](https://comfyanonymous.github.io/ComfyUI_examples/flux/), [Comfy-Org workflow templates](https://github.com/Comfy-Org/workflow_templates), and official ComfyUI tutorials for FLUX base, Redux, Fill/Kontext, Canny, and Depth.

### Consequences for implementation

- Keep `ltx2_3_22b_distilled_1_1_fp8` as the required CineForge product key. M0 now records the operator-selected local full-checkpoint FP8 artifact as `converted_derivative`; admission remains `benchmark_required` until conversion provenance, graph compatibility, runtime pins, serialized 24GB hardware evidence, recovery evidence, and human QA are recorded.
- Community or local 1.1 FP8 derivatives are discovery leads only unless explicitly selected and admitted; the selected local artifact above is not production-ready without graph and benchmark admission.
- The official LTX repository may auto-download models on first use. CineForge must override that convenience behavior: pre-stage artifacts administratively and fail closed when a required artifact is absent.

## 3. Current repository state

### Reusable implementation spine

| Capability | Current evidence | Plan |
|---|---|---|
| Workflow hashing and patching | `backend/app/services/workflows/template_service.py:22-164` | Extend, do not rewrite |
| `/object_info` validation | `backend/app/services/comfy/object_info_cache.py` | Make mandatory on production submission |
| Durable queue/state machine | `backend/app/queue/state_machine.py`, `backend/app/services/queue/service.py` | Keep DB states initially |
| Controlled worker submission | `backend/app/services/comfy/submission.py` | Complete progress/output/recovery path |
| Worker skeleton | `backend/app/services/queue/worker.py` | Keep disabled until hardware gate |
| GPU exclusivity | `backend/app/services/runtime/gpu_leases.py` | Wire into every Comfy job |
| Model/workflow/job tables | `backend/app/db/base.py:102-313` | Extend provenance and product layer |
| Evidence-only runtime catalog | `backend/app/services/runtime_catalog.py` | Preserve fail-closed claims |
| Benchmark primitives | `backend/app/services/benchmarks/`, `backend/app/services/telemetry/` | Add LTX ladder runner/evidence |
| FFmpeg allowlist and probes | `backend/app/services/ffmpeg/service.py` | Extend into `CF-POST-01` |
| Path safety | `backend/app/utils/path_safety.py` | Apply to all inputs/outputs |
| Planning-first UI | `frontend/src/studio/` | Add readiness/presets later; approval must not auto-render |

### Important gaps

- No public-production-ready admitted `CF-*` workflow archetypes; `CF-VID-01` now has UI source evidence and an API-format T2V smoke candidate with prior operator-approved local smoke-evidence records, but remains benchmark/recovery/QA gated and not profile/preset ready.
- M1/M6 local JSON catalogs now include all canonical registry archetypes (`CF-IMG-01`..`CF-IMG-05`, `CF-VID-01`..`CF-VID-05`, `CF-UTIL-01`, `CF-POST-01`) and exactly 64 disabled/gated presets; the expansion is planning-only and non-executing.
- A DB-free local runtime catalog now records the canonical LTX-2.3 Distilled 1.1 FP8 model record and output policy.
- No complete API-format workflow admission service for all profiles; current `CF-VID-01` support includes a bounded API T2V smoke template plus manifest, not full preset/profile readiness.
- No enabled history/WebSocket/view output collection.
- No live end-to-end generation worker.
- M4 has a serialized non-executing LTX ladder manifest and readiness/preflight surfaces, but no live benchmark ladder evidence.
- M5 has deterministic post-production planning, allowlisted recipe builders, and offline manifests, but no live FFmpeg/ffprobe execution evidence.
- Older repository documents remain Wan-first and conflict with the corrected specification.
- `README.md` and older docs may still describe earlier runtime/worker capabilities; they must distinguish mocked/offline worker primitives from production-enabled live execution before release.

### Worktree and test preflight

The repository already contains untracked user material:

- `CIneForge.code-workspace`
- `CineForge-Storyboard-Studio-v2.zip`
- `CineForge-Storyboard-Studio-v2/`

Do not delete, move, edit, or commit these without user approval. Before worktree-based implementation, GPT-5.5 must establish a clean integration baseline while preserving them.

A planning-time full `pytest -q` attempt reached about 35% and timed out after 180 seconds near PostgreSQL concurrency tests; no pass/fail result is claimed for that run. The local-only product direction does **not** require PostgreSQL or any external database for the ComfyUI lane. M0 now treats the offline backend/frontend baseline with `CINEFORGE_TEST_POSTGRES_URL` cleared as the required baseline; PostgreSQL tests are optional legacy/compatibility checks only.

## 4. Decisions and invariants

1. **Authority:** the corrected July 2026 specification governs the new Comfy/model lane; actual code governs current capabilities.
2. **Video default:** LTX-2.3 22B Distilled 1.1 at proven FP8 runtime precision is the only default video contract. Wan may remain historical or optional, disabled by default.
3. **Archetypes/presets:** approximately 10–12 executable archetypes; exactly 64 versioned presets.
4. **Preset/state storage:** use version-controlled JSON/YAML as the reviewable source of truth and local filesystem manifests/JSONL records as the runtime authority for the ComfyUI lane. No PostgreSQL or external database is required.
5. **Binding identity:** admission requires graph SHA + node class + **unique semantic title** + input, matching the governing specification. The admitted compiler record also stores the resolved API node ID for execution, but a numeric ID is never sufficient by itself. If the API graph omits titles, admission must join it to the pinned UI graph and persist the immutable title-to-ID mapping; a missing or ambiguous title blocks admission. Any graph hash change invalidates the mapping and admission.
6. **Queue states:** retain the existing authoritative `JobState` initially. Represent `waiting_for_gpu`, `leased`, `loading`, `sampling`, `decoding`, `postprocessing`, and `verified` as structured substate/events until a demonstrated API need justifies a migration.
7. **Readiness:** model, graph, archetype, quality profile, and preset readiness are separate evidence-backed states.
8. **GPU:** one real GPU-heavy job at a time, including benchmark and recovery probes.
9. **Runtime mutation:** one worker-controlled Comfy mutation path; no public raw `/prompt` proxy.
10. **No downloads:** no job may install nodes, update ComfyUI, download models, or execute workflow-provided URLs.
11. **Post-production:** ComfyUI performs inference; FFmpeg performs deterministic editing/assembly.
12. **Product boundary:** Storyboard approval does not automatically start generation.

## 5. Target architecture and contracts

```text
Storyboard/preset intent
  -> FastAPI semantic request validation
  -> preset registry resolves archetype/profile/bounds
  -> admitted graph registry loads exact API graph by SHA256
  -> semantic compiler patches declared bindings only
  -> graph + model + dependency + /object_info admission checks
  -> local file-backed ComfyJob spool/queue
  -> exclusive GPU lease
  -> isolated headless ComfyUI submission
  -> Save node filename_prefix = <project-folder>/<run-stem>
  -> WebSocket progress with history fallback
  -> managed output collection from ComfyUI output/<project-folder>/ and SHA256/probe
  -> optional approved FFmpeg recipe
  -> verified managed artifact and local audit/provenance record
```

### Model provenance contract

Add fields or linked records for:

- `model_key`, family, parameter count, variant, revision;
- upstream repository, filename, SHA256, license;
- local artifact path, size, SHA256;
- runtime precision and quantization method;
- FP8 method: `loader_level | converted_derivative | official_artifact | unknown`;
- conversion tool/version/settings when applicable;
- Python, PyTorch, CUDA, ComfyUI, and loader/custom-node commits;
- `admission_state`: `candidate | blocked | benchmark_required | ready | retired`.

### Archetype contract

- `archetype_id`, modality, version;
- source URL, source commit, author/license;
- normalized API graph SHA256 and UI graph SHA256 when the API graph does not itself preserve the required unique semantic titles;
- ComfyUI/custom-node dependency snapshot;
- semantic bindings and allowed models/profiles;
- static-security, compatibility, dry-run, benchmark, recovery, and human-QA evidence;
- immutable admission decision/version.

### Preset contract

- exactly 64 stable IDs;
- one default archetype per preset plus optional admitted fallback metadata;
- quality profile, bounded input schema, required assets, post recipe;
- inherited readiness from graph/model/profile;
- no model paths, graph URLs, raw node IDs, shell commands, or output paths in user input.

### Canonical video quality profiles

Lock these five specification-defined IDs in M1; each profile has independent model/archetype/hardware readiness:

| Profile ID | Default path | Initial state |
|---|---|---|
| `draft` | `CF-VID-01`, reduced validated resolution/frame count | `benchmark_required` |
| `review` | `CF-VID-01`, validated medium profile | `benchmark_required` |
| `final_candidate` | `CF-VID-02` two-stage/upscaler | `blocked` until single-stage passes and `CF-VID-02` is admitted |
| `controlled` | `CF-VID-03` admitted IC-LoRA graph | `blocked` until control admission and Stage 5 |
| `lipdub` | `CF-VID-04` official Lipdub graph | `blocked` until Lipdub admission and Stage 6 |

Still-image presets may define bounded image-specific settings, but they must not weaken these video-profile contracts.

### Semantic job manifest

At minimum:

- `preset_id`, `archetype_id`, `model_key`, `quality_profile`;
- prompt and negative prompt;
- managed reference/input asset IDs;
- seed, width, height, frame count, FPS, and bounded workflow-specific values;
- model-specific constraints, including LTX width/height divisibility and the `8n+1` frame-count rule where required by the admitted graph;
- managed output contract: all ComfyUI outputs live under `C:\AI\ComfyUI_windows_portable\ComfyUI\output\<project-folder>\` by default, with the project folder and run stem built by CineForge and sanitized before patching `filename_prefix`.

## 6. Dependency-ordered implementation milestones

### M0 — Preflight, inventory, and policy lock

**Purpose:** establish truth before changing runtime code.

Work:

1. Preserve/resolve the existing untracked files and establish the clean worktree strategy.
2. Rerun and record backend/frontend offline baseline validation with external database variables cleared.
3. Inventory local ComfyUI location/commit, LTXVideo commit, custom nodes, Python/Torch/CUDA, driver, FFmpeg, disk capacity, and model files.
4. Hash the exact local Distilled 1.1 source and any FP8 artifact.
5. Resolve the FP8 method decision; no silent fallback to non-1.1 official FP8.
6. Pin an isolated runtime and disable automatic updates/downloads.
7. Reconcile Wan-first documentation with the corrected default-video decision.

Likely files:

- `README.md`
- `docs/ROADMAP.md`, `docs/PRODUCT_VISION.md`
- `Models/MODEL_FEASIBILITY_MATRIX.md`
- `Benchmarks/BENCHMARK_PROTOCOL.md`
- `Sources/SOURCE_REGISTER.md`
- a new runtime inventory document under `docs/`

**Exit gate:** clean offline implementation baseline, exact artifact decision, pinned runtime inventory, baseline test report, and no readiness claim. PostgreSQL is not an exit requirement for the local app.

### M1 — Local state and domain contracts

**Purpose:** encode provenance, archetypes, presets, admission, and quality profiles without enabling generation and without requiring any external database.

Work:

1. Add local JSON/YAML records for model provenance.
2. Add local archetype, preset version, binding, dependency snapshot, admission evidence, and readiness records.
3. Add Pydantic schemas for model provenance, archetype, preset, semantic job manifest, admission result, and file-backed job/provenance records.
4. Define the five canonical video quality-profile IDs (`draft`, `review`, `final_candidate`, `controlled`, `lipdub`), their default archetype coupling, and independent readiness state.
5. Add the exactly-64 preset source catalog with all entries initially blocked or `benchmark_required` as appropriate.
6. Extend runtime-catalog read models without turning recorded paths into false installation/validation claims.
7. Preserve compatibility with `storage/workflow_templates/example_smoke`.
8. Use local filesystem state under `storage/` for catalog snapshots, job manifests, audit JSONL, benchmark JSONL, and managed artifact indexes. Generated media itself is saved under the ComfyUI output root, with one sanitized project folder per project. Existing SQL scaffolding may remain for older Storyboard code, but it is not required for ComfyUI execution.

Likely files:

- `backend/app/schemas/runtime_catalog.py`
- new workflow/preset/local-state schema modules under `backend/app/schemas/`
- `backend/app/services/runtime_catalog.py`
- new registry modules under `backend/app/services/workflows/`
- new local state modules under `backend/app/services/local_state/`
- versioned catalog files under `storage/presets/`, `storage/archetypes/`, `storage/models/`, and `storage/runtime/`
- project output folders under `C:\AI\ComfyUI_windows_portable\ComfyUI\output\<project-folder>\`
- local-state, schema, runtime-catalog, and fixture tests

**Exit gate:** exactly 64 validated preset definitions, the five canonical video profiles and their readiness inheritance validated, backward-compatible smoke manifest, local file-state round-trip tests, and independent schema QA.

**Implementation status 2026-07-16:** M1 local contracts are implemented for the ComfyUI lane without requiring a database, and the local archetype catalog has been expanded for M6 planning only: `storage/presets/catalog.json` validates exactly 64 disabled/gated presets; `storage/archetypes/catalog.json` contains every canonical registry archetype (`CF-IMG-01`..`CF-IMG-05`, `CF-VID-01`..`CF-VID-05`, `CF-UTIL-01`, `CF-POST-01`) with public enablement still false and no readiness promotion. `/local-runtime/*`, `/local-presets/*`, `/local-archetypes/*`, and `/local-jobs/*` expose DB-free state. Local job creation writes `storage/local_jobs/*.json` plus JSONL audit, uses `prepared_offline`/`blocked_offline` states, and prepares the ComfyUI project output folder/prefix, but never submits to ComfyUI. Configured local catalog/template files fail closed if missing.

### M2 — Semantic compiler and workflow admission

**Purpose:** guarantee that only approved semantic input reaches an immutable admitted graph.

Work:

1. Extend manifest bindings with graph/API/UI hashes, source provenance, mandatory unique semantic title, resolved API node ID, and controller-owned model/output fields. API JSON without titles must be joined to its pinned UI graph; missing or ambiguous title mappings fail admission.
2. Implement semantic request -> preset -> archetype -> bounded patch compilation.
3. Implement the admission pipeline:
   - source and license capture;
   - normalized API/UI graph hashing;
   - static node inventory;
   - reject script/shell/download/URL-execution nodes and unmanaged paths;
   - dependency and model resolution against pinned registries;
   - title uniqueness, immutable title-to-ID mapping, and class/input validation;
   - `/object_info` compatibility;
   - dry-run/benchmark/recovery evidence references;
   - signed/immutable admission decision.
4. Treat JSON, PNG-embedded workflows, Civitai metadata, templates, and user graphs as untrusted imports.
5. Add negative fixtures for path escape, unknown nodes, missing/duplicate titles, title-to-ID drift, hash mismatch, forbidden downloads, arbitrary model paths, invalid LTX dimension divisibility, and explicit non-`8n+1` LTX frame counts.

Likely files:

- `backend/app/services/workflows/template_service.py`
- new `backend/app/services/workflows/compiler.py`
- new `backend/app/services/workflows/admission.py`
- new `backend/app/services/workflows/registry.py`
- `backend/app/services/ai_orchestration/validator.py`
- `backend/app/utils/path_safety.py`
- `docs/WORKFLOW_TEMPLATE_MANIFEST.md`
- `backend/tests/test_workflow_manifest_validation.py`
- `backend/tests/test_object_info_cache.py`
- new admission/compiler/security tests and fixtures

**Exit gate:** arbitrary/raw graphs cannot enter the submission path; all negative fixtures fail closed; independent security QA passes.

**Implementation status 2026-07-13:** `storage/workflow_templates/cf_vid_01_ltx23_single_stage/` contains the official LTX-2.3 single-stage UI export copied from the local portable runtime plus `workflow_ui_manifest.json`. `backend/app/services/workflows/ui_template_service.py` validates the UI graph hash, node class, widget index, output-prefix binding, selected FP8 checkpoint patch points, and immutable offline snapshots. Operator-approved local smoke evidence is recorded separately in `docs/CFVID01_RUNTIME_SMOKE.md`, and `workflow_api.json`/`workflow_manifest.json` were added for `cf_vid_01_ltx23_single_stage_t2v_smoke`. This planning checkpoint does not repeat, extend, or newly attest live ComfyUI/GPU execution; the path is still benchmark/recovery/human-QA gated and is not full profile/preset readiness.

### M3 — Complete the controlled runtime path with mocks

**Purpose:** complete the job lifecycle before risking the real GPU runtime.

Work:

1. Add worker-only clients for WebSocket progress, history fallback, output view/retrieval, interrupt, queue cleanup, and `/free`.
2. Collapse the current low-level `ComfyUIClient` mutation boundary and `ComfyWorkerPromptSubmissionAdapter` transport into one controlled submission path. A low-level adapter may remain internal, but it must be unreachable unless the feature/operator gate is enabled, the worker owns the reservation, an admitted workflow run is selected, and a valid GPU lease is held.
3. Use two explicit default-off gates at the controlled submission boundary: `hardware_operator_enabled` for the local M4 benchmark/probe path, and `queue_worker_enabled` for general durable worker execution. Enabling the former must not enable public/autonomous jobs. Add tests proving both gates fail closed and that there is no lease-less or direct adapter bypass.
4. Persist progress/events and map them to current queue states plus structured substates.
5. Acquire, heartbeat, and transactionally release the GPU lease for every Comfy job.
6. Collect outputs into a per-job managed workspace; hash/probe and create `GeneratedAsset`/`FileOutput` records.
7. Add timeout, disconnect, node error, OOM, process crash, cancellation, and stale-job recovery.
8. Add a bounded retry policy; never retry the same OOM workload indefinitely.
9. Add supervisor hooks to terminate the complete Comfy process tree, restart the pinned runtime, and require a health/minimal job before resuming.
10. Keep all public/autonomous generation disabled. M4 may enable only a tightly scoped hardware-operator mode after M0–M3 gates pass, under the exclusive lease and exact admitted graph/model pins; general worker enablement remains off until M4 evidence is accepted.

Likely files:

- `backend/app/services/comfy/client.py`
- `backend/app/services/comfy/progress_monitor.py`
- `backend/app/services/comfy/submission.py`
- `backend/app/services/queue/service.py`
- `backend/app/services/queue/worker.py`
- `backend/app/services/runtime/gpu_leases.py`
- `backend/app/core/config.py`
- related queue, Comfy, output, recovery, and lease tests

**Exit gate:** mocked end-to-end job completes with provenance; all terminal paths release the lease; direct/lease-less adapter bypass tests fail closed; the operator gate is proven; recovery and next-job tests pass.

**Implementation status 2026-07-15:** M3 mocked controlled-runtime plumbing is implemented and remains offline-only. The backend has worker-only prompt submission and runtime-control permits, separated default-off `queue_worker_enabled`/`hardware_operator_enabled` gates, worker GPU lease acquire/heartbeat/bind/release helpers, static workflow security scanning enforced at submission readiness, progress/event persistence, mocked history/view/output collection, terminal timeout/interrupt/cancel wrappers, stale-reservation recovery, mocked runtime process recovery hooks, and a mocked end-to-end lifecycle test that submits, tracks, collects provenance, and releases the lease without touching live ComfyUI. Public `/prompt` and raw Comfy proxy routes remain absent. Full backend validation at checkpoint `230f9b6` passed with `486 passed, 9 skipped`; no live ComfyUI/GPU/render/benchmark action was run. M4 remains blocked until explicit operator approval for the hardware-operator-only probe path and serialized hardware ladder.

### M4 — Admit the first graphs and run the serialized hardware ladder

**Purpose:** prove the architecture with only `CF-VID-01` and `CF-IMG-01`. M4 executes ladder Stages 0–3 and the controlled Stage 7 recovery exercise only; Stages 4–6 belong to separately admitted M6 archetypes.

Work:

1. Pin/fetch the official LTX single-stage and official FLUX base sources through an administrative process.
2. Export/normalize API JSON; retain UI JSON for provenance.
3. Derive bindings from the actual graph, not from report examples.
4. Validate against the pinned live `/object_info` and store a fixture snapshot.
5. Register both graphs as `benchmark_required`.
6. Enable the explicit hardware-operator-only submission gate and execute the M4 ladder subset below one job at a time. Do not enable public/autonomous generation.

Proposed template roots:

- `storage/workflow_templates/cf_vid_01_ltx23_single_stage/`
- `storage/workflow_templates/cf_img_01_flux_base/`

#### RTX 5090 Laptop 24 GB ladder

| Stage | Workload | Minimum pass condition |
|---|---|---|
| 0 | Load checkpoint, encoder, and VAE only | no crash; lease release; memory returns; health succeeds |
| 1 | Minimal useful low-resolution/short-frame generation | output collected and hashed; next job succeeds |
| 2 | Draft profile around 640x360 | repeated runs; peak VRAM below configured safe limit; acceptable thermals |
| 3 | Review profile around 768x432 | repeatable; no OOM; human quality acceptance |
| 7 | Controlled OOM sandbox using the admitted single-stage path, only after Stage 1 succeeds | process-tree restart; lease recovery; next valid job succeeds |

Stages 4–6 are part of the overall program ladder but are intentionally deferred: Stage 4 follows `CF-VID-02` admission, Stage 5 follows `CF-VID-03` admission, and Stage 6 follows `CF-VID-04` admission. No unadmitted two-stage, control, or Lipdub graph may be loaded during M4.

Record cold/warm duration, queue wait, peak dedicated/shared memory, peak RAM, temperature, power/clocks when available, graph/model/environment hashes, output/probe hashes, error fingerprint, and next-job health.

**Stop rule:** if Stage 0 or 1 fails twice after approved recovery adjustments, block LTX video expansion and return the decision to the GPT-5.5 orchestrator.

**Implementation status 2026-07-16:** M4 remains non-executing and blocked by default. `GET /local-runtime/m4-preflight` now reports a read-only hardware-operator preflight gate that requires public generation disabled, general queue-worker execution disabled, `CINEFORGE_HARDWARE_OPERATOR_ENABLED=true`, `CINEFORGE_M4_HARDWARE_PROBE_APPROVED=true`, CF-VID-01 smoke evidence, queue-empty smoke evidence, and a valid serialized ladder manifest. `storage/benchmark_ladders/m4_cf_vid01_ladder.json` and `GET /local-runtime/m4-ladder` define only stages 0, 1, 2, 3, and 7 for `CF-VID-01`, explicitly defer stages 4–6, keep every stage `live_action_approved=false`, and expose this state in the Runtime UI. `POST /local-operator/packets` can now persist a pending review packet for a future M4 hardware-ladder probe, but the packet always records `state=pending_explicit_operator_approval`, `approval_recorded=false`, `live_execution_started=false`, `generation_submitted=false`, and `ffmpeg_submitted=false`; it is not an approval route and has no execute/submit/run child route. These additions do not run ComfyUI, acquire a GPU lease, submit prompts, render media, benchmark, mutate runtime, or approve hardware execution.

### M5 — Deterministic `CF-POST-01`

**Purpose:** provide safe post-production independently of model viability.

Work:

1. Implement allowlisted recipes for probe, normalization, concat, mux, captions, loudness normalization, timing, transitions, delivery packaging, and full decode validation.
2. Require input hashes and probe compatibility before stream-copy concat.
3. Use structured argument arrays/templates only; never accept an AI- or user-authored command string.
4. Persist command template ID, inputs, probes, output hash, final probe, and errors.

Likely files:

- `backend/app/services/ffmpeg/service.py`
- new FFmpeg recipe/executor modules
- `backend/tests/test_ffmpeg_service.py`
- `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md`

**Implementation status 2026-07-16:** M5 deterministic post-production hardening remains safe and non-executing. `PostProductionService` resolves input/output media paths inside the configured storage root, requires a supplied input hash or existing file hash for each clip, validates supplied SHA256 strings, and refuses command-array construction unless one hash per clip is present. `FFmpegService.build_stream_copy_concat_manifest(...)` produces concat manifest text only after hashes, safe paths, and stored probe compatibility are proven. `PostProductionPlanStore` writes file-backed `planned_offline` manifests that persist command template IDs, structured command arrays, input paths/hashes, probe count, timeline fields, and embedded plans while keeping execution fields null. The M5 offline recipe-command manifest work extends that pattern to generic allowlisted recipe commands: manifests persist template IDs, structured argv provenance, normalized inputs and hashes, and explicit `execution_submitted=false`, and they can now record offline success/error outcomes such as output SHA256, final probe JSON, timestamps, or error text without submitting execution. `GET /local-runtime/ffmpeg-recipes` exposes the allowlisted command-template catalog as read-only metadata only, with `executes_from_catalog=false`, `user_authored_command_allowed=false`, and `structured_argument_array` command shape. The recipe command manifest API is GET-only via `GET /local-post-production/recipe-commands` and `GET /local-post-production/recipe-commands/{plan_id}` for already-persisted manifests; it adds no create, update, delete, execute, raw-command, or submission route. `POST /local-operator/packets` can persist pending M5 FFmpeg/ffprobe probe or assembly validation review packets with read-only recipe-catalog summaries, but packets remain `pending_explicit_operator_approval` and record `approval_recorded=false`, `live_execution_started=false`, `generation_submitted=false`, and `ffmpeg_submitted=false`; there is no FFmpeg execution/approval endpoint. The Runtime/Post-Production UI displays recipes and stored recipe command manifests as inert read-only text, including argv provenance, without execution controls, copy/run/download actions, or raw command inputs. No FFmpeg, ComfyUI, GPU, render, or benchmark command has been run or approved by this M5 work.

### M6 — Archetype expansion

Repeat full admission and hardware gates in this order:

1. `CF-VID-02` two-stage only after `CF-VID-01` passes Stage 2; then execute overall ladder Stage 4 (upscaler/model-thrash/decode-OOM gate).
2. `CF-IMG-04` Fill/Kontext and `CF-IMG-05` Canny/Depth.
3. `CF-IMG-02` Redux identity/reference.
4. `CF-IMG-03` PuLID only if Redux fails approved identity thresholds.
5. `CF-VID-03` Union/motion controls; then execute overall ladder Stage 5 (hidden-load and control-quality gate).
6. `CF-VID-04` official Lipdub before any LivePortrait fallback; then execute overall ladder Stage 6 (A/V alignment, identity, and quality gate).
7. `CF-VID-05` continuation/V2V.
8. `CF-UTIL-01` only for a demonstrated mask/alpha gap.
9. Keep preset #41 (upscale/face-detail pass) blocked until a distinct admitted and benchmarked utility path is approved; do not mislabel `CF-UTIL-01` as that capability.

**Implementation status 2026-07-16:** the local archetype catalog now contains planning-only records for the full canonical registry set, including the M6 expansion targets. Every added M6 record remains `enabled=false` and `readiness=blocked`; `CF-VID-01` remains disabled and `benchmark_required`. This catalog expansion is metadata-only and non-executing: it does not admit graphs, run benchmarks, submit ComfyUI prompts, acquire GPU leases, run FFmpeg/ffprobe, enable presets, or promote public generation.

### M7 — Preset enablement, API/UI, and Storyboard bridge

**Local-only status 2026-07-16:** M7 is partially implemented as local-only, evidence/handoff surfaces rather than generation enablement. Backend readiness rollups now expose read-only archetype and preset readiness at `GET /local-archetypes/readiness`, `GET /local-archetypes/{archetype_id}/readiness`, `GET /local-presets/readiness`, and `GET /local-presets/{preset_id}/readiness`; the frontend Runtime page summarizes the same local MVP/readiness posture without probing live runtimes. Local generation endpoints persist offline semantic request manifests and provide an explicit `POST /local-generation/storyboard-handoffs` bridge from approved Storyboard snapshots, but they do not automatically generate from approval, submit ComfyUI prompts, start queue execution, acquire GPU leases, call runtime health, run FFmpeg/ffprobe, render, or benchmark. All 64 presets remain disabled/gated, public and autonomous generation remain disabled, no raw `/prompt` route is public, and full M7 preset enablement remains deferred.

Work:

1. Expose read-only archetype/preset/readiness APIs first.
2. Enable the 64 presets in small reviewed batches; each must resolve to exactly one default admitted archetype/profile.
3. Add a semantic job-create endpoint only after M2–M4 acceptance.
4. Add frontend preset/readiness views driven exclusively by backend evidence.
5. Connect approved shots to semantic generation requests without enabling raw graph or autonomous execution.
6. Preserve the rule that Storyboard approval alone never triggers generation.

Likely files:

- new preset/archetype route and schema modules
- `backend/app/api/router.py` (single integration owner)
- `backend/app/api/routes/jobs.py`
- Storyboard handoff service/routes/tests
- `frontend/src/api/client.ts`
- `frontend/src/studio/pages/WorkflowsPage.tsx`
- `frontend/src/pages/Runtime.tsx`, `Jobs.tsx`, and focused UI tests

## 7. GPT-5.5/Grok-4.5 orchestration plan

### Authority and roles

- **GPT-5.5:** sole orchestrator, scope/architecture decision-maker, ownership allocator, conflict resolver, merge-gate authority, and final acceptor.
- **Grok 4.5 implementers:** one bounded work package and one owned worktree/path set each.
- **Grok 4.5 QA:** fresh-context agents independent from the author; review and validate, but do not merge or redefine scope.
- **Grok 4.5 hardware operator:** one designated session for real Comfy/model/GPU actions; all such actions remain serialized.

### Concurrency rules

- Maximum **48 simultaneous Grok agents**.
- Maximum normal writers: **12**, each in a separate worktree with exclusive file ownership.
- Maximum QA: **16**.
- Up to **20** remaining slots for read-only research, graph inspection, test analysis, or static validation.
- Safe maximum burst: `12 writers + 16 QA + 20 read-only = 48`.
- Never edit the same path from two workers.
- Never run more than one real GPU job or one runtime-mutating hardware operator.
- Conflict files are serially owned: `backend/app/db/base.py`, Alembic heads, `backend/app/api/router.py`, `backend/app/main.py`, shared config, root `README.md`, and shared catalog files.

### Branch and integration path

```text
worker worktree/branch
  -> independent Grok QA
  -> author fix pass
  -> integrate/wave-N
  -> GPT-5.5 integration review
  -> master
```

Suggested branch naming: `feat/wave-{n}/{lane}/{work-package}`.

### Wave allocation

| Wave | Scope | Grok writers | Grok QA | Read-only/static | GPU |
|---|---|---:|---:|---:|---:|
| A | M0/M1 inventory and contracts | 6–8 | 6–8 | up to 20 | 0 |
| B | M2 compiler/admission | 6–10 | 8–12 | up to 16 | 0 |
| C | M3 runtime completion | 6–10 | 8–12 | up to 12 | 0 |
| D | M4 proof + M5 post in parallel | 3–6 software | 6–10 | up to 12 | 1 serialized |
| E | M6 archetype expansion | 4–8 | 8–12 | up to 16 | 1 serialized per graph |
| F | M7 preset/API/UI batches | 8–12 | 10–16 | up to 20 | 0 unless validating a profile |

The orchestrator should launch only agents for ready, non-conflicting packages; unused capacity remains idle rather than creating speculative work.

### Mandatory package handoff

Every implementation worker returns:

- changed files;
- implemented scope and explicit omissions;
- commands with exit codes;
- test/validation evidence;
- migration/API compatibility notes;
- security implications;
- residual risks and decisions needing GPT-5.5 approval.

Every QA agent returns evidence-backed findings with severity and file/line references. A QA agent may not review its own implementation.

### Merge gates

1. File ownership respected.
2. Focused and affected offline tests pass.
3. Independent Grok QA passes correctness, tests, maintainability, and relevant specialist angles.
4. API/schema changes have contract tests.
5. Migrations are expand-only unless explicitly approved.
6. No secrets, weights, portable runtime, generated media, or agent artifacts are committed.
7. Graph/import changes include security-admission tests.
8. A readiness change cites matching hardware evidence.
9. GPT-5.5 accepts the integrated wave.

### Stop/escalation rules

Stop the affected lane and return to GPT-5.5 when:

- the exact Distilled 1.1 FP8 implementation is missing or ambiguous;
- any expected hash differs;
- an official graph requires an unpinned or unapproved dependency;
- a worker proposes community packs before the official path has failed its approved gate;
- a destructive DB migration or queue-state rewrite appears necessary;
- two work packages require the same file ownership;
- a graph contains shell, script, download, path-escape, or URL-execution behavior;
- Stage 0/1 fails twice;
- QA identifies an unapproved product or architecture decision.

## 8. Validation contract

### Software

```powershell
# Offline backend baseline: explicitly clear external DB variables for this local-only run
$env:PYTHONDONTWRITEBYTECODE='1'
Remove-Item Env:CINEFORGE_TEST_POSTGRES_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -B -m pytest -x -vv -p no:cacheprovider

# Workflow/admission
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  backend/tests/test_workflow_manifest_validation.py `
  backend/tests/test_object_info_cache.py `
  backend/tests/test_runtime_catalog.py

# Queue/Comfy
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  backend/tests/test_controlled_submission.py `
  backend/tests/test_queue_service.py `
  backend/tests/test_queue_worker.py `
  backend/tests/test_queue_state_machine.py

# FFmpeg and telemetry
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  backend/tests/test_ffmpeg_service.py `
  backend/tests/test_benchmark_services.py `
  backend/tests/test_gpu_telemetry_parser.py

# PostgreSQL compatibility tests are optional legacy checks and are not required for this local app.
# Keep CINEFORGE_TEST_POSTGRES_URL unset unless intentionally validating old DB compatibility.

# Frontend
Set-Location frontend
npm test --if-present
npm run build
```

### Security/admission

Required negative tests include:

- graph SHA mismatch and binding invalidation;
- duplicate semantic titles;
- node class/input drift;
- absent `/object_info` dependency;
- arbitrary model/output paths;
- path traversal and symlink/junction escape;
- shell/script/download/URL nodes;
- embedded workflow metadata treated as untrusted;
- lease conflict and double submission;
- output/history metadata attempting workspace escape.

### Hardware

```powershell
nvidia-smi --query-gpu=timestamp,name,driver_version,pstate,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,power.draw,clocks.gr,clocks.mem --format=csv -l 1
```

Hardware validation must include output inspection and next-job recovery. CI cannot substitute for this evidence.

## 9. Acceptance and rollback

### Archetype `ready`

An archetype is ready only after source/commit/license capture, graph hashes, node pins, model hashes, static scan, `/object_info`, API export, bounded dry run, required benchmark stage, controlled recovery, output provenance, deterministic post validation, and human QA all pass.

### Preset `ready`

A preset is ready only when its archetype/model/profile is ready, values and assets are bounded/validated, its output contract passes, and the UI reports backend evidence without overclaiming.

### Rollback

- Demote readiness to `blocked` or `benchmark_required` without deleting evidence.
- Preserve prior graph/model/template versions by hash; never overwrite admitted history.
- Use expand-only local schema/catalog changes and a compatibility period when contracts evolve.
- Revert the wave integration commit for software regressions.
- Keep the prior pinned Comfy runtime available for runtime rollback.
- On OOM/crash, terminate the process tree, preserve diagnostics, release the local lease atomically, restart the pinned runtime, and require a health/minimal job.
- Preserve failed job workspaces/logs for diagnosis.

## 10. Principal risks

| Risk | Severity | Mitigation |
|---|---|---|
| Selected Distilled 1.1 FP8 artifact lacks reproducible conversion provenance | Medium | record as operator-provided `converted_derivative`; require graph/hardware admission before readiness |
| 24 GB cannot run LTX-2.3 22B acceptably | High | serialized ladder; degrade/block profiles |
| Wan/LTX documentation conflict | High | policy lock before implementation |
| API graph/title/node drift | High | graph SHA invalidation; store ID/class/input/title |
| Untrusted workflow code or downloads | Critical | static admission; official-first; fail closed |
| Incomplete output/recovery path | High | mocked M3 gate before GPU enablement |
| Laptop thermal or memory instability | High | telemetry, cooldown, batch caps, restart gate |
| Dependency sprawl on Windows | High | Redux/Lipdub first; optional packs require approval |
| Multi-agent file or migration conflicts | High | ownership locks and one integration path |
| UI false readiness claims | High | backend evidence only |

## 11. Remaining questions and explicit assumptions

Questions requiring approval or M0 evidence:

1. The exact local Distilled 1.1 source and selected FP8 artifact are known; the remaining question is whether to reproduce/document the FP8 conversion toolchain or accept it as an operator-provided local artifact.
2. Which existing ComfyUI installation should be pinned; for this local app, the current Windows portable runtime is the working assumption unless the operator requests a rebuild.
3. Should Wan remain available as a disabled secondary family, or be removed from the active product catalog?
4. Who provides final human visual/audio QA for identity, lipdub, and high-risk presets?
5. When may a public semantic job-create endpoint be exposed relative to Storyboard Phase A?
6. How should the pre-existing untracked Storyboard Studio v2 folder/zip be preserved before worktree fanout?

Assumptions used by this plan unless changed:

- versioned files are the reviewable preset source, with local manifests/JSONL as runtime truth;
- generated media is written under ComfyUI `output/<project-folder>/`, one sanitized folder per project;
- graph SHA + node class + unique semantic title + input are mandatory admission identity; the resolved API node ID is stored only as the immutable compiled execution mapping;
- the existing queue states remain authoritative initially, implemented through local state for the ComfyUI lane;
- Wan is not a co-default;
- all public generation remains disabled unless and until a separate public-exposure decision and gate set is approved; the immediate MVP is personal/local-only;
- no new hardware claim is made by this checkpoint; local live runs require explicit operator approval and the applicable gates.

## 12. Implementation-ready meta-prompt

```text
You are the sole openai-codex/gpt-5.5 orchestrator for the approved CineForge ComfyUI implementation plan at C:\AI\Git\CIneForge\CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md. Use context:"fresh" for delegated work.

Implement only the next dependency-ready wave. Use xai-auth/grok-4.5 for implementation workers and separate independent QA. Up to 48 Grok agents may be active, but treat 48 as a ceiling: at most 12 non-overlapping writers in isolated worktrees, at most 16 QA, and remaining slots read-only. Maintain one writer per path, one serial migration owner, one integration path, and exactly one real GPU/runtime-mutating operator or job.

Preserve the existing workflow-template, queue, controlled-submission, GPU-lease, runtime-catalog, benchmark, path-safety, and FFmpeg spine. The target is approximately 10–12 admitted archetypes backing exactly 64 semantic presets. The canonical video key is ltx2_3_22b_distilled_1_1_fp8, but no worker may assume the official Distilled 1.1 BF16 checkpoint is FP8 or substitute the non-1.1 official FP8 file. M0 must identify and approve loader-level FP8, a reproducible derivative, or an explicit contract change.

Start with M0, obtain a real test baseline, preserve existing untracked user files, inventory/pin the runtime and artifacts, and close blocking decisions. Then execute M1–M3 with tests and independent QA before enabling the one hardware-operator-only probe path. M4 may enable that path only behind the explicit operator/feature gate, admitted graph/model pins, worker ownership, and exclusive GPU lease; public/autonomous generation stays disabled. Admit official LTX single-stage and official FLUX base first; all profiles remain benchmark_required until serialized 24 GB hardware, recovery, output provenance, and human-QA gates pass.

Hard constraints: semantic manifests only; admitted bindings require graph SHA + class + unique semantic title + input, with an immutable compiled API node ID; no raw graph/API proxy; no lease-less submission adapter; `hardware_operator_enabled` and `queue_worker_enabled` remain separate default-off gates; no runtime downloads or installs; no arbitrary community workflow execution; no unmanaged paths; no concurrent GPU jobs; no destructive migration or queue rewrite without approval; no public generation or readiness claim before its gate.

For every package, return changed files, scope/omissions, commands and exit codes, validation evidence, compatibility/security notes, residual risks, and decisions needing approval. Merge only after independent Grok QA and GPT-5.5 acceptance. Stop on ambiguous FP8 provenance, hash mismatch, unapproved dependency, ownership conflict, destructive migration, workflow shell/download/path behavior, or two failed Stage 0/1 attempts.
```
