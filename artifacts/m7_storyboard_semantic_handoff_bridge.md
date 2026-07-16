# M7 Storyboard-to-offline-semantic Handoff Bridge

Implemented an explicit local-only bridge from approved storyboard snapshots to offline semantic generation request manifests.

## Scope

- Adds `POST /local-generation/storyboard-handoffs`.
- Requires an explicit API call; storyboard approval remains non-generative and does not create handoffs.
- Requires `story.approval_state == approved`, an active approved storyboard version, and an immutable approved snapshot.
- Creates semantic generation request manifests via `SemanticGenerationRequestManifestStore.create` only after approval checks pass.
- Does not submit to ComfyUI, start queue execution, acquire GPU leases, render, probe runtime health, or expose execute/submit/run child routes.

## Request defaults

- `preset_id`: `CF-PRESET-001`
- `archetype_id`: `CF-VID-01`
- `quality_profile`: `draft`
- `mode`: `t2v`
- Optional selection: `shot_id`
- Optional safe output naming: `output_project_key`, `run_stem`

## Manifest mapping

For each selected shot in the approved active snapshot:

- Prompt uses latest prompt package `video_prompt`, falling back to `visual_description`, `story_purpose`, then shot/story title.
- Negative prompt uses latest prompt package `negative_prompt` or empty string.
- FPS defaults to 24.
- Frame count is calculated with the LTX `8n+1` rule.
- Geometry uses draft 16:9 local generation defaults unless the bounded quality profile override changes it.
- Output prefix is sanitized and limited to a project folder plus run stem.

## Frontend consumption

- Adds frontend API types and helper for `POST /local-generation/storyboard-handoffs`.
- Adds an explicit Storyboard workspace control labeled `Local/offline semantic handoff`.
- The control uses the current `story_id` and selected `shot_id` only after an explicit button click.
- The UI states that it prepares offline semantic manifest files only and does not generate, render, submit to ComfyUI, start queue execution, acquire GPU leases, or call runtime health.
- The bounded response summary shows selected shot count, created manifest IDs/states, blocked reasons, and the false safety flags: `generation_submitted`, `execution_started`, and `automatic_from_approval`.
- Storyboard approval remains separate and does not call the handoff helper.

## Validation

Focused tests were added/updated in `backend/tests/test_local_generation.py` for:

- Unapproved storyboard handoff blocks without creating manifests.
- Approved explicit handoff creates blocked-by-gates semantic manifest(s) without Comfy submission.
- Local-generation routes expose no execute/submit/run handoff children.
- Storyboard approval route does not automatically create a handoff.
