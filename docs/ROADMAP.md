# Roadmap

## Current: Storyboard Phase A

Planning foundation and a production-plan approval boundary are implemented. It is intentionally before image/video generation.

## Next Slice

Persist Phase A settings, reference asset upload through managed storage, full prompt/recommendation CRUD, and real runtime registry/readiness read models. Continue to keep execution, model download, and provider invocation outside public Storyboard routes.

## Generation Lane Planning Lock

`CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md` governs the post-Phase-A ComfyUI lane. M0 policy is locked to LTX-2.3 22B Distilled **1.1** at proven FP8 runtime precision with product key `ltx2_3_22b_distilled_1_1_fp8`.

M0 now records the selected local full-checkpoint FP8 artifact and hashes. Admission remains `benchmark_required` until conversion provenance, isolated runtime pins, graph compatibility, local file-backed state/output handling, no-download/no-update controls, serialized 24GB benchmark evidence, and recovery evidence are recorded. Outputs are saved under the ComfyUI output root with one sanitized folder per project. Wan-era roadmap and MVP notes remain historical or optional secondary evidence, disabled by default.

`SPRINT_1C_PLAN.md` and earlier sprint documents remain historical queue/runtime safety records and do not override this product direction.
