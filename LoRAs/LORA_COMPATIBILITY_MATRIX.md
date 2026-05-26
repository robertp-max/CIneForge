# LoRA Compatibility and Purpose Matrix

LoRA is not a memory or speed solution by default. In this system, LoRAs should be treated as controllable behavioral/style deltas that may add VRAM pressure and version risk. A "speed LoRA" claim is accepted only when the source specifically documents fewer steps or acceleration for the exact model family.

## LoRA Matrix

| LoRA / Adapter Type | Compatible Base Model | Purpose | ComfyUI Loader | Quantized Base Compatible? | Strength Range | VRAM/Speed Impact | MVP Use? | Risk |
|---|---|---|---|---|---|---|---|---|
| LTX official distilled LoRA | Matching LTXV/LTX-2 base version | Lower-step distilled behavior / model-specific adaptation | LTX nodes or `pipe.load_lora_weights` in official examples; Comfy node names workflow-specific | Needs exact loader validation; Q8 path has `LTXVQ8LoraModelLoader` | Needs local tuning | Adds LoRA memory; may reduce steps only if source workflow uses distilled low-step settings | Later MVP after base benchmarks | Version mismatch, quality collapse |
| LTX camera/control/detailer LoRAs | Matching LTX-2/LTX-2.3 variant | Camera motion, control, detail refinement | Official LTXVideo nodes where supported | Needs local testing | Needs local tuning | Adds memory and may reduce stability | Elite | Control stacks can conflict |
| LTX GGUF LoRA | LTX GGUF base through compatible loader | Style/identity/control depending LoRA | `ComfyUI-LTXVideoLoRA` or GGUF-compatible path | Reported supported by maintained community nodes | Needs local tuning | Test-required; custom-node overhead | No | Requires custom nodes |
| Wan Lightx2v 4-step LoRA | Wan2.2 Comfy workflows listing Lightx2v assets | Step reduction / acceleration where documented | Native Wan workflow or wrapper-specific LoRA loader | Needs workflow-specific test | Needs local tuning | Potential speed benefit only if step reduction works | Benchmark candidate | Quality/artifact risk at low steps |
| Wan style LoRA | Exact Wan base/version | Look/style/domain | Native LoRA loader or WanVideoWrapper | Needs local testing, especially FP8/GGUF | Commonly 0.4-1.0 in diffusion ecosystems, but exact range unverified | Small to moderate VRAM; speed mostly unchanged | Optional | Style overfit, prompt drift |
| Wan character identity LoRA | Exact Wan T2V/I2V base | Character consistency | Native LoRA loader or wrapper | Needs local testing | Test-required | Adds memory; speed mostly unchanged | Elite | Identity drift, face artifacts |
| Wan camera/motion LoRA | Exact Wan base/version | Camera path/motion pattern | Native/wrapper loader | Needs local testing | Test-required | Adds memory; may affect temporal stability | Elite | Motion artifacts |
| Product/object LoRA | Exact base, often image-trained | Object consistency | Native/wrapper loader | Needs local testing | Test-required | Adds memory; speed mostly unchanged | Elite | Object deformation |
| Control adapters | LTX or Wan variant if supported | Pose/depth/canny/conditioning | Implementation-specific control nodes | Needs exact implementation | Test-required | Adds VRAM and preprocessing | Elite | Workflow complexity, node breakage |

## Backend Tracking Rules

Store LoRA usage as first-class reproducibility data:

- `lora_id`, file path, SHA256, source URL, license, compatible base model, compatible model version.
- Loader node class and input fields from the exported API workflow.
- Per-run ordered LoRA list, strength/model weight, clip strength if available, block selection if available.
- Quantized-base compatibility status: `verified`, `failed`, `unknown`.
- Quality tags: identity, style, motion, camera, prompt adherence, artifacts.

## Practical Guidance

- Rapid prototyping: use no LoRA first, then one LoRA at a time after base preset passes VRAM benchmark.
- Style/consistency: LoRAs help visual consistency but can reduce prompt flexibility.
- Photorealism risks: high-strength style/detail LoRAs can introduce plastic texture, facial drift, and temporal shimmer.
- Conflict risks: multiple LoRAs affecting identity, face, motion, and camera can fight; enforce ordered stacks and per-stack benchmark records.
- Model registry: every LoRA worth reusing belongs in the registry only after one successful smoke test on the intended base and quantization.

## Required Local Tests

1. Base model no LoRA, fixed seed.
2. One LoRA at strengths 0.3, 0.6, 0.9, fixed seed.
3. Same LoRA under FP8 and GGUF/Q path if supported.
4. Two-LoRA stack with swapped order if loader order matters.
5. Overnight queue with repeated LoRA load/unload to detect memory growth.
