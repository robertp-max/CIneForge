# CineForge Wizard-of-Oz UAT Gap Report

**Date:** 2026-07-22  
**UAT project ID:** `c056b941-634d-4796-98ff-aff95a348526`  
**Requested working title:** `gogo power rangers`  
**Scope:** One-prompt planning orchestration through every currently representable production phase. No image, voice, video, ComfyUI, or FFmpeg production execution.

## Executive result

The planning-only UAT completed successfully within CineForge's current architecture boundary. CineForge accepted the supplied prompt, created a project, produced a source-grounded five-minute storyboard proposal, allowed QA review, and applied the accepted plan through the product UI. The accepted plan contains 5 chapters, 5 scenes, 40 shots, and exactly 300 seconds of planned duration.

The result is **not a generated film** and must not be presented as one. CineForge QA approved the planning snapshots for Phases 1–6, creating immutable approval iterations and audit records for each phase. Phase 7 is unlocked for planning but was deliberately not started or approved. The repository intentionally does not execute media generation: ComfyUI remained untouched, no generation job entered a queue, and no image, voice, clip, or final media asset was created.

## UAT evidence

- Project created and opened at `/projects/c056b941-634d-4796-98ff-aff95a348526/studio/overview`.
- The stored project name is `Please start a new project named gogo power rangers`; the editable story title was corrected in CineForge to `gogo power rangers`.
- Accepted proposal identifier observed in the UI/API: `ce2080d5…9120`.
- Accepted planning run identifier observed in the UI/API: `98d99a7d…3560`.
- Storyboard version after review and apply: version 2.
- Accepted hierarchy: 5 chapters, 5 scenes, 40 shots.
- Planned duration: 300 seconds exactly.
- Planned chapter durations: 45, 45, 52.5, 82.5, and 75 seconds.
- Voice placeholders retained: 4.
- Character coverage in the accepted plan:
  - Father: 27 shots.
  - Younger Son: 40 shots.
  - Older Son: 16 shots.
- The earlier invalid proposal was rejected by `CineForge UAT QA`; the corrected proposal was reviewed and applied.
- Project settings version: 3.
- Model and LoRA downloads: disabled.
- Rendering and video generation: disabled.
- Media jobs created during UAT: 0.
- Planning-ledger approvals: Phases 1–6 approved by `CineForge QA` through the CineForge UI.
- Phase 7 lifecycle at the stop point: `drafting`, unlocked, not approved, and not executed.
- Each approval note explicitly states that no media generation or execution was certified or started.

## Canonical seven-phase status

| Phase | CineForge phase | UAT status | What is still missing |
|---|---|---|---|
| 1 | Script and Narrative Development | Planning package produced, reviewed, corrected, applied, and planning snapshot approved | A configured live `gpt-5.6-sol` provider was not demonstrated. The run used CineForge's deterministic planning fallback, so model provenance must not claim GPT-5.6. |
| 2 | Scene and Shot Segmentation | Live hierarchy reviewed; planning snapshot approved | No independent downstream generator or phase-specific QA executor; the workspace derives its view from current planning records. |
| 3 | Character Development | Character identities and shot coverage reviewed; planning snapshot approved | No approved character reference images, provider-backed character design run, or generated identity assets. |
| 4 | Location and Key-Asset Development | Location and key-asset plan reviewed; planning snapshot approved | Key-asset completion schema, approved visual assets, and continuity-state evidence remain incomplete. |
| 5 | Production Prompt and Workflow Package | Prompt/workflow plan reviewed; planning snapshot approved | No validated workflow templates or immutable ComfyUI manifest snapshots are assigned to the project. |
| 6 | Image and Voice Generation and Mapping | Mapping design reviewed; planning snapshot approved with an explicit no-media caveat | 40/40 starting images are unassigned; character references are absent; voices remain placeholders; no provider generation ran. |
| 7 | Video Generation, Assembly, and Final QA | **Paused before start.** Unlocked for planning, lifecycle `drafting`, not approved | No video clips, audio stems, final timeline render, delivery manifest, or final-output QA exists. Execution is outside the planning-only contract. |

An `approved` phase in this report means its **planning snapshot** was reviewed and retained in the backend production ledger. It does **not** mean media was generated or that a production execution gate passed. Phase 7 was intentionally left at the boundary without an approval snapshot.

## Blockers fixed during this UAT

1. **Route-selected project race** — the studio shell could briefly select another project while opening a project-specific URL. Route initialization now preserves the requested project.
2. **Second full-plan apply collision** — applying a corrected complete plan could violate SQLite chapter/scene ordering uniqueness. Existing ordering slots are vacated safely before the replacement hierarchy is written.
3. **Character coverage loss** — the deterministic fallback now preserves the three principal characters across the generated plan instead of collapsing coverage.
4. **Source and pacing fidelity** — the fallback now produces five source-grounded movements, 40 shots, and an exact target duration while retaining voice placeholders.
5. **Starting-image shot codes** — the Starting Images view derives canonical codes such as `S01A` from the hierarchy even when legacy titles do not contain a shot code.
6. **Misleading exports** — export entries now report their true readiness and no longer present missing media packages as ready.
7. **Visible routing terminology** — internal `character_bible` contract keys remain intact, while the user-facing label is `Character profile`. No visible `Bible` terminology remains in `frontend/src`.
8. **Future project-name parsing** — explicit prompts such as `Please start a new project named gogo power rangers:` now resolve to the requested short project name for newly created projects.
9. **Missing phase-approval UI** — the existing planning-ledger approval endpoint is now exposed as a fail-closed CineForge QA control. It labels approval as planning-only, preserves immutable history, enforces sequential approval, and never starts media execution.
10. **Misleading phase-rail status** — the seven-phase rail now displays the real backend lifecycle (`approved`, `drafting`, and so on) instead of continuing to say `Design available` after approval.

## Remaining product gaps

### Project and prompt ingestion

- The current UAT project's database display name is malformed because it predates the project-name parser fix. The story title is correct, but there is no demonstrated UI for editing the project entity name.
- The two supplied visual references were not imported into this project as managed reference assets.
- A duplicate empty project remains in the local project list and was not deleted because deletion was outside this UAT's safe scope.

### Images and continuity

- Starting images: 0 of 40 assigned.
- Approved character reference images: 0.
- No reference-image provenance, shot mapping, approval, or continuity chain exists for this UAT project.
- No image-generation workflow or ComfyUI submission was executed.

### Voice and audio

- Four voice records are placeholders rather than approved provider-backed voices.
- Provider assignment and provider health validation are incomplete.
- Narration/voice coverage is not complete across the 40-shot plan; the current summary and detailed assignment views need a single authoritative coverage calculation.
- No TTS, voice cloning, dialogue render, music, ambience, or final mix was generated.

### Providers, models, and workflows

- No live `gpt-5.6-sol` planning profile was verified for this run.
- The deterministic local fallback is useful for Wizard-of-Oz planning UAT but is not evidence that an external AI model executed.
- No registered image/video model variant was selected for production.
- No provider health-probe endpoint is exposed for all routing choices.
- No project-assigned, manifest-validated ComfyUI workflow package exists.
- ComfyUI was unavailable and deliberately not started or mutated.
- The backend production queue remained disabled and empty.

### Execution and export

- CineForge currently enforces a planning-only boundary. Phase 6's planning snapshot is approved, but its named media-generation work is not executed. Phase 7 video assembly remains paused and unapproved.
- Media exports remain blocked because there are no generated or approved media assets.
- PDF/ZIP/media delivery must not be simulated as a successful production export.
- The production build reports a 530.74 kB JavaScript chunk, above Vite's 500 kB warning threshold. This is a performance warning, not a UAT functional failure.

## Wizard-of-Oz boundary used

The Wizard-of-Oz MVP used CineForge's deterministic, source-grounded planning fallback to stand in for unavailable model orchestration. The fallback produced a reviewable proposal; it did not silently apply it. Human-visible QA rejected the invalid proposal and applied the corrected one. This preserves the product's proposal/review/apply boundary and does not claim that GPT-5.6, ComfyUI, TTS, or video generation ran.

Acceptable Wizard-of-Oz behavior:

- deterministic proposal generation;
- visible provenance and limitations;
- QA review before application;
- immutable retained versions;
- truthful empty or blocked media states.

Unacceptable behavior:

- claiming an external model ran when it did not;
- showing missing images, audio, clips, or exports as generated;
- submitting to ComfyUI from planning code;
- bypassing the backend queue or approval ledger;
- auto-approving production work without an auditable QA decision.

## Verification gates

- Frontend ESLint: passed.
- Frontend Vitest: 7 files, 29 tests passed.
- Frontend TypeScript and production Vite build: passed.
- Focused backend production history and approval-ledger tests: 6 passed.
- Focused backend pytest suite: 46 tests passed.
- Additional focused backend acceptance checks from the access recovery pass: 16 tests passed.
- `git diff --check`: passed after removing the single trailing blank-line defect.

## Release recommendation

The current branch is suitable for continued **planning-only UAT** through the approved Phase 6 snapshot. Phase 7 must remain paused. The product is not ready to advertise autonomous end-to-end film production. The next honest milestone is to finish managed reference ingestion, provider configuration/health reporting, starting-image and voice assignment coverage, and manifest-validated workflow selection before any separate authorization to implement or execute Phase 7 media production.
