# Quantization Matrix

VRAM is the primary constraint. Quantization is recommended to make candidates fit, not automatically to make them faster. Smaller weights can reduce memory transfers but may add dequantization overhead or custom-kernel instability.

## Quantization Options

| Quant Format | Applies To | Loader / Node | VRAM Savings | Speed Impact | Quality Impact | LoRA Compatible? | ComfyUI Stable? | 24GB Recommendation |
|---|---|---|---|---|---|---|---|---|
| FP32 | Model weights, text encoders, VAE | Standard PyTorch/Comfy loaders | None | Slow/high memory | Highest precision, unnecessary for inference | Usually yes | Stable but impractical | Not recommended |
| FP16 | Diffusion model, VAE, sometimes text encoder | Native Comfy loaders | ~50% vs FP32 | Often fast on NVIDIA | Best practical quality | Usually yes | Stable | Use for small models only; risky for 14B+ |
| BF16 | Diffusion model where supported | Native Comfy loaders | Similar to FP16 | Hardware-dependent | Slightly different numeric behavior | Usually yes | Stable where supported | Benchmark against FP16; not default for Wan if docs prefer FP16 |
| FP8 scaled | Wan/LTX diffusion weights, text encoder variants | Native Comfy Wan examples, LTX official variants | Large savings vs FP16 | Often good, but benchmark required | Some quality loss vs FP16 | Supported only when loader/base/LoRA path supports it | Best verified low-memory path | Default for Wan 14B/A14B and LTX large tests |
| FP8 e4m3fn | Text encoders and some model weights | Comfy repackaged text encoder names such as `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | Large savings | Usually memory-oriented | Possible prompt adherence loss if text encoder degradation matters | N/A or loader-specific | Stable in Comfy Wan examples | Recommended for text encoder VRAM control |
| INT8 | General quantization concept | No verified production Comfy Wan/LTX path found | High | Can help or hurt | Quality risk | Unknown | Unknown | Avoid unless a specific loader/workflow is verified |
| NF4 / bitsandbytes | Transformer weights in some ecosystems | No verified Wan/LTX Comfy production path found | Very high | Often dequant overhead; platform-dependent | Quality loss possible | Unknown | Unknown | Not recommended for MVP |
| Q4 GGUF | Diffusion model and some text encoders | `ComfyUI-GGUF` `Unet Loader (GGUF)` / GGUF T5 loaders; WanVideoWrapper GGUF path | Very high | May be slower than FP8 | More visible quality loss | Experimental according to GGUF loader notes | Requires custom nodes | Use only to fit otherwise impossible jobs |
| Q5 GGUF | Diffusion model and text encoders where available | Same GGUF loaders | High | Benchmark required | Better than Q4 | Experimental/test-required | Requires custom nodes | Good fallback if FP8 OOMs |
| Q6 GGUF | Diffusion model and text encoders where available | Same GGUF loaders | Moderate/high | Benchmark required | Better quality than Q4/Q5 | Experimental/test-required | Requires custom nodes | Balanced custom-node fallback |
| Q8 GGUF | Diffusion model and text encoders where available | Same GGUF loaders | Moderate | May be close to FP16, not guaranteed faster | Lower quality loss | Experimental/test-required | Requires custom nodes | Use when FP16 too large but quality matters |
| LTX Q8 kernels | LTX/LTXV-specific transformer path | `LTXVQ8Patch`, `LTXVQ8LoraModelLoader` in official LTX Q8 code | Moderate/high | Kernel-dependent | Intended to preserve quality | Yes through Q8 LoRA loader path | Requires exact patch/load sequence | Test-required but attractive for LTX LoRA work |
| TorchAO | General PyTorch modules | No verified Wan/LTX Comfy loader path | Potentially high | Hardware/kernel-dependent | Unknown for these workflows | Unknown | Unknown for this use | Research only |

## Ranked Recommendation

1. Fastest usable prototype quant: Wan/LTX official FP8 scaled variants, because they are documented in native or maintainer workflows.
2. Best balanced quant: FP8 scaled for Wan2.1/2.2 14B and LTX 13B/19B; Q6 GGUF only after custom-node smoke tests.
3. Best visual-quality quant: FP16 for 1.3B/2B models; Q8/FP8 for larger models where FP16 exceeds 24GB.
4. Avoid unless testing: Q4 GGUF, NF4/bitsandbytes, TorchAO, INT8 paths without exact Wan/LTX Comfy workflow proof.
5. Not recommended: FP32, unverified loader combinations, multi-LoRA stacks on quantized large bases without benchmark evidence.

## Component Guidance

| Component | Quantize? | Notes |
|---|---|---|
| Diffusion transformer / DiT | Yes, first target | Largest VRAM savings; FP8/GGUF paths matter most |
| Text encoder | Yes if large | UMT5/Gemma/T5 can consume major VRAM; CPU/offload/FP8 may be necessary |
| VAE | Prefer FP16/BF16 with tiling/offload before aggressive quant | VAE decode can OOM; quality and color stability matter |
| LoRA | Do not quantize blindly | LoRA compatibility depends on loader, base, rank, and quantized path |
| Control adapters | Treat as additive VRAM | Benchmark with adapter enabled, not separately |

## Required Local Tests

| Test | Pass Criteria |
|---|---|
| Wan2.2 A14B FP8 832x480x81, no LoRA | Completes 3 cold/warm runs under 23GB peak and recovers memory |
| Same with Lightx2v 4-step LoRA | No OOM, no obvious quality collapse, measurable speed benefit if claiming acceleration |
| Wan GGUF Q5/Q6 vs FP8 same prompt/seed | Lower peak VRAM without unacceptable motion/detail loss |
| LTX 13B FP8 vs LTX Q8 path | Verify loader order, peak VRAM, LoRA response |
| Text encoder FP8/offload A/B | Prompt adherence not materially degraded for production prompts |
