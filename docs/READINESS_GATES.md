# Storyboard Readiness Gates

The backend is authoritative. It calculates hierarchy duration rollups, target-duration discrepancy, missing narration, and explicitly blocked shots. Approval returns HTTP 409 until blockers clear. Frontend readiness displays mirror this response rather than localStorage or mock values.

Registry, ComfyUI, GPU, benchmark, workflow, and provider availability are Unknown/Unverified/Not Configured unless a real backend source supplies evidence. No UI should claim installed models, safe 1080p generation, connected providers, or render estimates without that evidence.

## Local ComfyUI Lane Status

Implemented local-only, DB-free records are evidence surfaces, not generation readiness claims:

- `/local-runtime/catalog` records the selected `ltx2_3_22b_distilled_1_1_fp8` local FP8 artifact and output policy.
- `/local-presets` validates exactly 64 disabled or benchmark-gated presets.
- `/local-archetypes` records `CF-VID-01`..`CF-VID-04` and `CF-IMG-01`, all disabled until admission/benchmark evidence exists.
- `/local-jobs` creates file-backed manifests with `state=prepared_offline` or `blocked_offline`, JSONL audit events, ComfyUI project output folders, and offline workflow snapshots only. It does **not** submit prompts to ComfyUI.
- `CF-VID-01` has UI source evidence plus an API-format T2V smoke candidate. After operator approval, `/object_info` passed and two minimal serialized local smoke generations succeeded. Evidence is exposed through `/local-runtime/evidence` and documented in `docs/CFVID01_RUNTIME_SMOKE.md`.

Catalogs and workflow templates fail closed from the configured `storage/` root; missing configured files are not silently substituted.

Public/preset generation remains disabled until the explicit worker/operator gates, admitted graph/model pins, exclusive GPU lease, broader benchmark evidence, recovery evidence, and human QA gates pass.
