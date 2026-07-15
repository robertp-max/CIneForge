# Model Feasibility Matrix

Target: single RTX 5090 Laptop GPU, 24GB VRAM, 192GB RAM. Feasibility below is intentionally conservative. "Feasible" means worth benchmarking locally, not production-approved.

**Default product lane (2026-07):** `ltx2_3_22b_distilled_1_1_fp8` means LTX-2.3 22B Distilled **1.1** at a proven FP8 runtime precision. The official Distilled 1.1 BF16 checkpoint is not an FP8 artifact, and non-1.1 FP8 files must not be silently substituted. M0 now records an operator-selected local full-checkpoint FP8 artifact as `converted_derivative`; admission remains `benchmark_required` until conversion provenance, runtime pins, graph compatibility, serialized 24GB benchmark evidence, and recovery evidence are recorded.

Wan and older LTXV entries below are retained as historical or optional secondary lanes, disabled by default; they are no longer the default MVP video contract.

## Model Matrix

| Model | Variant | Source | Params | File Size | Text Encoder | VAE | ComfyUI Support | Required Nodes | Quant Options | LoRA Support | 24GB Feasible? | Best Use | Risk |
|---|---|---|---:|---:|---|---|---|---|---|---|---|---|---|
| LTX-Video / LTXV | `ltxv-2b-0.9.8-distilled` | https://huggingface.co/Lightricks/LTX-Video | 2B | ~6.34GB FP16, ~4.46GB FP8 from HF API | T5 XXL family per model card | `AutoencoderKLLTXVideo` | Official `ComfyUI-LTXVideo`; some LTX nodes in ComfyUI core | LTXVideo nodes or official node pack | FP16, FP8, GGUF community variants | LTXV LoRA ecosystem exists; exact LoRA must match base/version | Compatible only at reduced resolution/frame count | Speed prototype, preview | Requires local benchmark for exact 5090 laptop thermal/perf |
| LTX-Video / LTXV | `ltxv-13b-0.9.8-dev` / distilled | https://huggingface.co/Lightricks/LTX-Video | 13B | ~28.58GB FP16, ~15.69GB FP8 | T5 XXL family | `AutoencoderKLLTXVideo` | Official `ComfyUI-LTXVideo` workflows | LTXVideo nodes | FP16, FP8, Q8/GGUF community paths | Official distilled LoRA lineage and community LoRAs | Compatible only with quantization/offload | Balanced/final candidate if benchmarks pass | 24GB borderline; text encoder/VAE can OOM |
| LTX-2 | `ltx-2-19b-dev`, distilled, FP8, FP4 | https://huggingface.co/Lightricks/LTX-2 | 19B | ~43.29GB FP16, ~27.08GB FP8, ~19.99GB FP4, ~7.67GB LoRA | Gemma3 family per official docs | `AutoencoderKLLTX2Video` | Lightricks says built-in LTXVideo nodes plus official repo | Built-in LTXVideo nodes; optional official pack | FP16, FP8, FP4, offload | Official distilled/control/detailer/camera LoRAs referenced | Compatible only with quantization/offload; needs local testing | Experimental high quality | Official 32GB+ signals make 24GB unproven |
| LTX-2.3 | `ltx-2.3-22b-distilled-1.1` / product key `ltx2_3_22b_distilled_1_1_fp8` | https://huggingface.co/Lightricks/LTX-2.3 | 22B | Source `ltx-2.3-22b-distilled-1.1.safetensors` = 46,149,345,334 bytes, SHA256 `b33b7fe4bbfe084f484be4aaf90b0f1d95dca20d403ac4c0e037eb8c4f0af7cc`; selected local FP8 `ltx-2.3-22b-distilled-1.1-fp8.safetensors` = 25,134,891,534 bytes, SHA256 `c5dd96a75c4b588171b9807a8a25fea91e71a3cc7386d8bc245f50a21756cfbb` | Gemma3 family | LTX2 VAE | Official `ComfyUI-LTXVideo` 2.3 workflows present locally | Built-in/official LTX nodes | Method recorded as operator-selected `converted_derivative`; header-equivalent to BF16 source with same tensor names/shapes/config, but conversion command/toolchain is not yet reproduced; do not substitute non-1.1 FP8 | Official distilled LoRA files; compatibility benchmark-required | Experimental on 24GB only after admitted FP8/offload path | Default video contract, not ready | Critical: official guidance implies 32GB+; local 24GB must prove graph compatibility, benchmark ladder, and recovery |
| LTX-2.3 | `ltx-2.3-22b-dev` and non-1.1 FP8 variants | https://huggingface.co/Lightricks/LTX-2.3 | 22B | Local `ltx-2.3-22b-dev.safetensors` and `ltx-2.3-22b-dev-fp8.safetensors` exist, but are not Distilled 1.1 | Gemma3 family | LTX2 VAE | Same LTXVideo ecosystem | Built-in/official LTX nodes | FP8/offload if template supports it | LoRA compatibility test-required | Secondary research only | Non-default comparison | High risk; not a valid substitute for product key |
| Wan2.1 | `Wan2.1-T2V-1.3B` | https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B | 1.3B | Comfy repack FP16 ~2.84GB | T5 / UMT5 path in Comfy workflows | `wan_2.1_vae.safetensors` | Native ComfyUI examples | Native Wan nodes | FP16/BF16/FP8 | Wan LoRA ecosystem, exact base match required | Compatible only at reduced resolution/frame count | Fast prototype, motion exploration | Quality below larger variants |
| Wan2.1 | `Wan2.1-T2V-14B` | https://huggingface.co/Wan-AI/Wan2.1-T2V-14B | 14B | Comfy repack ~28.58GB FP16, ~14.29GB FP8 scaled | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` in Comfy path | `wan_2.1_vae.safetensors` | Native ComfyUI examples | Native Wan nodes | FP16/BF16/FP8, GGUF via custom nodes | LoRAs exist; quant compatibility needs test | Compatible only with quantization/offload | Balanced/final candidate | 720p/81 frames may fill VRAM |
| Wan2.1 | `Wan2.1-I2V-14B-480P/720P` | https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P | 14B | Comfy repack ~32.79GB FP16, ~16.40GB FP8 scaled | UMT5/T5 | `wan_2.1_vae.safetensors` | Native ComfyUI examples | Native Wan I2V nodes | FP8/GGUF | LoRAs require exact I2V/base validation | Compatible only with quantization/offload | Continuity clips | Image conditioning increases workflow complexity |
| Wan2.2 | `Wan2.2-TI2V-5B` | https://docs.comfy.org/tutorials/video/wan/wan2_2 | 5B | Comfy repack ~10GB FP16 | UMT5 FP8 in Comfy docs | `wan2.2_vae.safetensors` | Native ComfyUI docs/examples | Native Wan2.2 nodes | FP16/FP8, offload | Lightx2v-related acceleration LoRAs listed in docs | Compatible only with quantization/offload | Fast/balanced T2V/I2V experiments | Exact 24GB performance needs local benchmark |
| Wan2.2 | `Wan2.2-T2V-A14B` | https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B | ~14B active, ~27B total experts | Comfy high/low FP8 files ~14.29GB each | UMT5 FP8 | Wan VAE | Native ComfyUI docs/examples | Native Wan2.2 high/low workflow | FP8 scaled; GGUF via custom nodes | Lightx2v 4-step LoRA in Comfy docs; other LoRAs test-required | Compatible only with quantization/offload | Best local final candidate if 24GB benchmark passes | Official CLI high-memory guidance conflicts with 24GB; Comfy FP8 may still work |
| Wan2.2 | `Wan2.2-I2V-A14B` | https://docs.comfy.org/tutorials/video/wan/wan2_2 | ~14B active, ~27B total experts | Comfy high/low FP8 files ~14.29GB each | UMT5 FP8 | Wan VAE | Native ComfyUI docs/examples | Native Wan2.2 I2V workflow | FP8 scaled; GGUF via custom nodes | LoRA compatibility test-required | Compatible only with quantization/offload | I2V continuity/final clips | High VRAM pressure and artifact risk |

## Frame, Duration, Resolution Rules

| Model | Valid Frame Counts | FPS Assumption | Duration Result | VRAM Effect | Notes |
|---|---|---|---|---|---|
| LTXV 0.9.x | Official docs state frames must be `8n + 1`; examples include 161 frames | Examples use 24fps | 161 frames = ~6.7s at 24fps | Longer frames raise latent memory and VAE pressure | Width/height divisible by 32; official card advises under 720x1280 and below 257 frames |
| LTX-2.x | Official docs state frames must be `8n + 1`; examples include 121 frames | Examples use 24fps | 121 frames = ~5.0s | High due 19B/22B models | 24GB should start with FP8/FP4/offload and short clips |
| Wan2.1 1.3B | Comfy workflows expose latent length; common community values include 81 frames | Often 16fps in Comfy workflows | 81 frames = ~5.1s at 16fps | Moderate | Treat exact valid counts as workflow/node-specific; test 49/81/121 |
| Wan2.1 14B | Comfy workflows expose latent length; common 81 frames | Often 16fps | 81 frames = ~5.1s | High at 720p; FP8 recommended | 480p is safer than 720p for 24GB |
| Wan2.2 5B | Official docs describe 5-second workflows; common 81 frames | Often 16fps or 24fps depending template | 81 frames = 3.4s at 24fps or 5.1s at 16fps | Moderate/high | Verify FPS field in exported workflow, not by model family assumption |
| Wan2.2 A14B | Official Comfy examples use high/low noise model pair; common 81 frames | Workflow-specific | Depends on FPS | Very high | Start at 832x480 or 704x1280 only after benchmark |

## Recommended Frame Counts

| Target | Preview Recommendation | Final Recommendation | Evidence / Caveat |
|---|---|---|---|
| 3 seconds | 49 or 57 frames depending workflow FPS and valid-count rule | 73 or 81 if continuity matters | Needs local testing because Comfy nodes differ |
| 5 seconds | 81 frames for Wan-style 16fps workflows; 121 frames for 24fps LTX-2 | 81-121 frames | Source-backed examples; exact FPS must be stored |
| 8 seconds | Avoid initially on 24GB; split into two continuity-linked clips | Only after smaller tests pass | Needs local benchmark |
| 10 seconds | Prefer two 5-second clips with overlap/crossfade/I2V continuity | 161-257 only for LTX if VRAM permits | Compatible only at reduced resolution/frame count |

## Compatibility Conclusions

1. The default product video contract is LTX-2.3 22B Distilled **1.1** at proven FP8 runtime precision (`ltx2_3_22b_distilled_1_1_fp8`). M0 records the selected local FP8 artifact and source hash; graph/hardware admission is still pending.
2. The selected local full-checkpoint FP8 artifact is header-equivalent to the verified BF16 source and recorded as `converted_derivative`, but conversion provenance must still be reviewed or reproduced before promotion beyond `benchmark_required`.
3. Older transformer-only FP8 derivatives, Wan, LTXV 0.9.x, and non-1.1 LTX files remain useful historical/optional secondary lanes, disabled by default and never a silent substitute for the product key.
4. No 14B+ or 22B workflow is production-approved on the 24GB laptop until cold/warm/soak benchmarks show stable peak VRAM, temperature, output quality, and restart recovery.
5. All quality profiles remain `benchmark_required` or `blocked` until the serialized ladder in `Benchmarks/BENCHMARK_PROTOCOL.md` passes.
