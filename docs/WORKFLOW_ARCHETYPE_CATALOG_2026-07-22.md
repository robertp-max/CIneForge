# CineForge Workflow Archetype Catalog

Date: 2026-07-22

## Product contract

CineForge uses shared, parameterized workflow archetypes rather than one ComfyUI
graph per shot or per preset.

- Image base model: `flux1-dev.safetensors` (`flux1_dev`)
- Video base model: `ltx-2.3-22b-distilled-1.1-fp8.safetensors`
  (`ltx2_3_22b_distilled_1_1_fp8`)
- Archetypes: 12
- Semantic presets: exactly 64
- GPU execution: one serialized GPU worker

No other checkpoint, UNet, GGUF or model family may be selected as a base model.
LoRAs, control adapters, VAEs and text encoders are auxiliary inputs and do not
change this rule.

## Current implementation

The canonical source registry is
`backend/app/services/workflows/candidate_catalog.py`. Its generated reader
artifact is `storage/workflow_candidates/catalog.json`.

The read-only API is:

`GET /runtime-catalog/workflow-candidates`

This endpoint does not probe ComfyUI, download files, execute a workflow, create
a queue item, acquire the GPU lease, render media or approve a preset.

## Admission gates

A candidate is not admitted until all of the following are true:

1. The source JSON has been downloaded from the recorded URL.
2. The bytes parse as JSON and have a recorded SHA-256.
3. Base-model loader nodes pass the exact model contract.
4. Semantic runtime bindings are captured in an immutable manifest.
5. Node classes and inputs validate against a recorded ComfyUI `object_info`
   snapshot.
6. The graph passes serialized 24 GB benchmark and recovery testing.
7. Human QA approves output quality.

All 64 presets remain `enabled: false`.

## Candidate disposition

- Six official Lightricks examples already present in the external local ComfyUI
  installation were imported with their original bytes and SHA-256 provenance.
  Disabled normalized copies change only their base-loader widget from the
  bundled `ltx-2.3-22b-dev.safetensors` default to the approved
  `ltx-2.3-22b-distilled-1.1-fp8.safetensors` artifact. They remain
  `benchmark_required`; import did not execute them.
- Remaining official and maintainer JSON sources are registered as
  download-pending.
- Official FLUX Redux and Control pages remain source-resolution-required until
  a direct immutable JSON URL is recorded.
- Community workflows require explicit human review even after technical
  validation.
- The GGUF FLUX workflow is explicitly rejected because it violates the base
  model contract.
- Fill/Kontext candidates remain blocked if their graph replaces
  `flux1-dev.safetensors` with a Fill or Kontext checkpoint.
- Phase 7 video generation remains outside this catalog operation.
