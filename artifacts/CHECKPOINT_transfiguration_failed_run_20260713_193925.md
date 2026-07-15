# Checkpoint — Transfiguration Failed Run Audit

## Current state

- Generation stopped.
- No further render/upscale/interpolation/retry should be run unless explicitly requested.
- ComfyUI queue was confirmed empty after stop.
- Audit/export completed in one timestamped folder.

## Audit folder

Absolute path:

`C:\AI\Git\CIneForge\artifacts\transfiguration_70s_FAILED_RUN_AUDIT_20260713_193925`

Key files:

- `00_EXECUTIVE_FAILURE_EXPLANATION.md`
- `02_RUN_INVENTORY.csv`
- `03_FILE_TREE.txt`
- `08_SHOT_AND_SUBSCENE_MANIFEST/shot_manifest.json`
- `09_GENERATION_PROVENANCE/seeds_and_settings.csv`
- `10_FAILED_OUTPUTS/original_clips/`
- `11_QA/per_clip_qa.csv`

## Render status

Rendered successfully before stop:

1. S01
   - Output: `C:/AI/ComfyUI_windows_portable/ComfyUI/output/transfiguration_70s/ascent_to_holy_mountain_00001_.mp4`
   - SHA256: `67bab153095e23e55c813d71b106522efc917adeec4c6133aea2b703d8bf5068`

2. S02
   - Output: `C:/AI/ComfyUI_windows_portable/ComfyUI/output/transfiguration_70s/summit_arrival_and_solitude_00001_.mp4`
   - SHA256: `498db9a414bf72f1f26e2af998e426dfaba3e30e45cccbd7bc12ea69e8531176`

Interrupted:

- S03 interrupted at ComfyUI node `4802` / `SamplerCustomAdvanced`.
- Prompt ID: `cineforge-transfiguration-s03-ed45a5bb-d3d1-4563-9337-5df9c790274c`
- No S03 output file.

Not rendered:

- S04, S05, S06, S07, S08.

## Main failure causes captured in audit

- Smoke/preview workflow was used for production.
- Actual render resolution was `512x288`; “8K IMAX” existed only as prompt text.
- Clips were T2V from `EmptyLTXVLatentVideo`, not I2V from approved start images.
- No character bible, storyboard, narration spine, reference images, or identity adapters existed.
- No final-frame-to-next-clip conditioning existed.
- CineForge manifests remained `generation_submitted: false` despite direct render script submission, exposing an orchestration gap.

## Do not forget

Before any future production render, add/enforce hard gate:

`PRODUCTION_RENDER_ALLOWED=false` unless approved character bible, references, storyboard/animatic, start images, continuity map, narration/no-narration signoff, benchmark admission, and tracked CineForge operator submission all exist.
