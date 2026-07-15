# CF-VID-01 Runtime Smoke Evidence

Date: 2026-07-13

## Runtime actions performed

- Started local portable ComfyUI with:
  - `C:\AI\ComfyUI_windows_portable\python_embeded\python.exe -s C:\AI\ComfyUI_windows_portable\ComfyUI\main.py --windows-standalone-build --disable-api-nodes --cuda-device 0`
- Installed missing official-workflow dependency:
  - `C:\AI\ComfyUI_windows_portable\ComfyUI\custom_nodes\RES4LYF`
  - Git SHA: `419de2d7c78f415dde9aa352a7231820ebfc17a4`
  - Installed missing embedded-Python requirement: `pywavelets==1.9.0`
- Re-ran `/object_info` after restart.
- Submitted two serialized CF-VID-01 T2V smoke jobs using the selected local 1.1 FP8 checkpoint.
- Called `/free` after completion to unload models and release memory.

## Object info

Saved object info:

- `storage/runtime/object_info_20260713_163704.json`

Result:

- Class count: `1170`
- Required CF-VID-01 class coverage: complete after RES4LYF install
- Pre-install blocker was missing `ClownSampler_Beta`

## API smoke graph

API candidate:

- `storage/workflow_templates/cf_vid_01_ltx23_single_stage/workflow_api.json`
- Manifest: `storage/workflow_templates/cf_vid_01_ltx23_single_stage/workflow_manifest.json`
- Template ID: `cf_vid_01_ltx23_single_stage_t2v_smoke`
- Version: `0.2.0-api-t2v-smoke`
- Canonical SHA256: `d040a311a80401dda3b7d2ecbbea0d8e24ca32b62a36e6d5801d0a7bda8865c1`

Smoke graph differences from the upstream UI example:

- Uses selected checkpoint `ltx-2.3-22b-distilled-1.1-fp8.safetensors`.
- Uses installed text encoder `gemma_3_12B_it_fp4_mixed.safetensors`.
- Uses T2V-only path and removes the bypassed I2V image branch.
- Removes missing `ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors` LoRA nodes rather than substituting the local non-1.1 LoRA.
- Keeps generation minimal for smoke: `512x288`, `17` frames, `24` fps, `4` steps.

## Output evidence

Outputs saved under ComfyUI output root:

1. `C:\AI\ComfyUI_windows_portable\ComfyUI\output\CineForge_runtime_validation\cfvid01_smoke_001_00001_.mp4`
   - Size: `64542` bytes
   - SHA256: `f258167157479d1e5b9f814004e46028b49b5e7431908644a24f9c705c8f28bf`
   - Video: H.264, `512x288`, `17` frames, `24 fps`, `0.708333s`, `yuv420p`
   - Audio: AAC, `48000 Hz`, stereo, `0.690000s`
   - Prompt result: `storage/runtime/cfvid01_smoke_20260713_164147_result.json`
   - Media summary: `storage/runtime/cfvid01_smoke_20260713_164147_media_summary.json`

2. `C:\AI\ComfyUI_windows_portable\ComfyUI\output\CineForge_runtime_validation\cfvid01_smoke_002_00001_.mp4`
   - Size: `58611` bytes
   - SHA256: `22cf59f36a767a576e013d6fded83599331401f6b855a0e1133397566e47e6c8`
   - Video: H.264, `512x288`, `17` frames, `24 fps`, `0.708333s`, `yuv420p`
   - Audio: AAC, `48000 Hz`, stereo, `0.690000s`
   - Prompt result: `storage/runtime/cfvid01_smoke_next_20260713_164328_result.json`

Combined output summary:

- `storage/runtime/cfvid01_smoke_outputs_summary.json`

## Timing and telemetry

First smoke:

- Comfy prompt ID: `c05d2d04-367b-44ef-bb5f-01f4f75b8583`
- Elapsed: about `45.9s`
- Peak telemetry from sampled `nvidia-smi`:
  - Peak GPU memory used: `21934 MiB`
  - Peak GPU util: `93%`
  - Peak temperature: `58 C`

Second smoke / next-job check:

- Comfy prompt ID: `01349020-03a9-4fff-ae6d-4e8427e96be9`
- Elapsed: about `20.3s`
- Queue empty after completion.

Post-`/free` memory:

- VRAM free: `24180031488` bytes
- Torch VRAM total: `33554432` bytes

## Dev-mode/API export retry

After enabling ComfyUI dev mode, the frontend API export path was retried through the same `app.graphToPrompt()` path behind **Export Workflow (API)**.

Artifacts:

- Export helper: `storage/runtime/devmode_api_export/cfvid01_devmode_export.py`
- Exported API graph: `storage/runtime/devmode_api_export/cfvid01_devmode_api_export.json`
- Export summary: `storage/runtime/devmode_api_export/cfvid01_devmode_api_export_summary.json`
- Non-executing validation: `storage/runtime/devmode_api_export/cfvid01_devmode_api_export_validation.json`
- Local smoke execution result: `storage/runtime/devmode_api_export/cfvid01_devmode_api_export_smoke_result.json`

Result:

- Dev-mode export SHA256: `b4a3a6b7c48d74dcf3f77fb22bac18ec48326538ba9b565ecb72495e2b444ee3`
- Exported API node count: `39`
- Validation: `valid: true`, `outputs_to_execute: ["4852", "4823"]`, `node_errors: {}`
- Missing 1.1 LoRA handling: bypassed `LoraLoaderModelOnly` nodes `4922` and `4968`; no non-1.1 LoRA substitution.
- Smoke parameters: `512x288`, `17` frames, `24` fps, `4` steps.
- Smoke prompt ID: `cfvid01-devmode-export-smoke-c01c3f56-4993-445d-bf1e-a38e86058138`
- Smoke elapsed: `41.35s`
- Peak sampled GPU memory: `22000 MiB`

Dev-mode export smoke outputs:

1. `C:\AI\ComfyUI_windows_portable\ComfyUI\output\CineForge_runtime_validation\cfvid01_devmode_export_F_00001_.mp4`
   - Size: `51838` bytes
   - SHA256: `cb9be5223bda8eeae821feecde5163fae40d14935737748cc5307fcffba2d538`
   - Video: H.264, `512x288`, `17` frames, `24 fps`, `0.708333s`
   - Audio: AAC, `0.690000s`

2. `C:\AI\ComfyUI_windows_portable\ComfyUI\output\CineForge_runtime_validation\cfvid01_devmode_export_D_00001_.mp4`
   - Size: `49418` bytes
   - SHA256: `63ab972c4977354fb9345e5549dc9e41a31d5e3f199d3bf04c01e2655fc59ae9`
   - Video: H.264, `512x288`, `17` frames, `24 fps`, `0.708333s`
   - Audio: AAC, `0.690000s`

Post-run `/free` was called. Final sampled post-free GPU memory was `336 MiB` used / `23802 MiB` free, with ComfyUI reporting `24180031488` bytes VRAM free.

## Current readiness conclusion

`CF-VID-01` has passed a minimal local T2V smoke, next-job check, and dev-mode/API-export smoke with the selected 1.1 FP8 checkpoint.

It remains `benchmark_required`, not production-ready, until:

- broader benchmark ladder runs at approved dimensions/profiles,
- output QA is reviewed by a human,
- recovery/OOM exercise is completed,
- full admission records are stored through deterministic CineForge services,
- UI preset enablement is explicitly approved.
