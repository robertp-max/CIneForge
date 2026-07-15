# CineForge Product Vision

CineForge is storyboard-first. A Project holds a user-supplied Story, its Characters and reference assets, Voice profiles, ordered Chapters, ordered Scenes, and ordered Shots. Storyboard Phase A produces an approved editable production plan; it does not render.

`Shot` is the 6–12 second generation-planning unit. A `Scene` is a narrative container. Timeline Slots and Clip Iterations remain downstream execution concepts and are not created during plan approval.

## Generation policy after Storyboard Phase A

The corrected ComfyUI implementation lane is planning-locked to LTX-2.3 22B Distilled **1.1** at proven FP8 runtime precision, with product key `ltx2_3_22b_distilled_1_1_fp8`.

This is a contract, not a readiness claim. The official Distilled 1.1 BF16 checkpoint must not be treated as an FP8 artifact, and non-1.1 FP8 artifacts must not be silently substituted. M0 records an operator-selected local full-checkpoint FP8 artifact as `converted_derivative`; admission stays `benchmark_required` until conversion provenance, runtime pins, graph compatibility, serialized 24GB benchmark evidence, and recovery evidence are recorded.

Wan and older LTXV workflows remain historical or optional secondary lanes, disabled by default. Still-image FLUX support is downstream and must follow the same admitted-graph, model-provenance, and benchmark gates.

Storyboard approval remains a planning boundary: it does not invoke ComfyUI, download models, mutate workflows, or enqueue generation.
