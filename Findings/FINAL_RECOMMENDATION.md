# Final Recommendation and Decision Tree

## Direct Recommendation

Use a two-lane architecture:

1. MVP lane: Wan2.1 1.3B and/or LTXV 2B for fast local preview generation, workflow automation, database provenance, and FFmpeg assembly.
2. Candidate/final lane: Wan2.2 5B and Wan2.1/2.2 14B FP8 after local benchmarks prove the exact resolution/frame/step tier fits under 24GB VRAM.

Treat LTX-2/LTX-2.3 as an Elite research lane on this laptop. Official sizes and 32GB+ signals make 24GB use plausible only with FP8/FP4/offload and local proof.

Add the AI Orchestration Layer only as an optional advisory extension. CineForge remains the deterministic execution engine and must validate every proposed change before it affects workflows, queue state, database records, registry data, ComfyUI submissions, or FFmpeg assembly.

## Best Choices

| Goal | Recommendation | Evidence Level |
|---|---|---|
| Fastest preview | Wan2.1 1.3B or LTXV 2B at 480p, 49-81 frames | Verified official docs; needs local timing |
| Balanced quality | Wan2.2 5B or Wan2.1 14B FP8 at 480p/720p after benchmark | Verified Comfy docs; compatible only with quantization/offload |
| Final local render | Wan2.2 A14B FP8 if 81-frame benchmark passes | Verified docs for model/workflow; 24GB requires local testing |
| Best quant strategy | Native FP8 scaled first, GGUF Q5/Q6 fallback | Verified maintainer repos; custom-node paths require tests |
| Best LoRA strategy | No LoRA baseline, then one verified LoRA at a time | Needs local testing |
| Best ComfyUI setup | Isolated ComfyUI process controlled by backend API | Verified Comfy API/docs |
| Best clip length | 3-5 sec previews, 5 sec final slots; stitch for long-form | Operationally realistic |
| Best frame count | 49-81 preview, 81-121 candidate, larger only after tests | Source-backed, workflow-specific |
| Best resolution | 480p preview, 720p candidate if stable, upscale/post outside generation | Needs local benchmark |
| Best FFmpeg strategy | Probe, normalize mismatched clips, concat demuxer only when compatible | Verified FFmpeg docs |
| Best AI orchestration strategy | Provider-agnostic advisory agents that write proposals only | Optional extension; not MVP dependency |

## Decision Tree

```text
If goal is fastest preview
  -> use Wan2.1 1.3B or LTXV 2B, 480p, 49-81 frames, no LoRA.

If goal is character consistency
  -> first create baseline I2V/seed workflow, then test one character LoRA on the exact base/quant.

If goal is photoreal final
  -> benchmark Wan2.2 A14B FP8 at 832x480x81.
  -> if stable, test 720p or 121 frames separately, not together.

If 24GB OOM occurs
  -> reduce frame count, then resolution, then steps, then move to smaller/stronger quant, then smaller model.

If VAE decode OOM occurs
  -> enable tiling/offload if workflow supports it, or decode shorter/lower-res clips.

If ComfyUI node unsupported
  -> restore Manager snapshot or use native Comfy workflow before custom-node fallback.

If LoRA incompatible
  -> disable LoRA, verify base workflow, then test matching base/version/loader.

If FFmpeg concat fails
  -> normalize all clips to common mezzanine or delivery profile, then concat.

If audio sync is required
  -> align audio after video clip selection and before final mux.

If an AI agent proposes a change
  -> store it as a proposal, validate through CineForge gates, require approval when policy demands, then execute through the normal deterministic flow.
```

## Biggest Unknowns

- Sustained thermals and clock behavior of the specific RTX 5090 laptop.
- Exact ComfyUI commit behavior with current Wan/LTX nodes.
- Actual peak VRAM for Wan2.2 A14B FP8 on 81-frame and 121-frame settings.
- Whether GGUF is faster, slower, or only memory-saving on this hardware.
- LoRA compatibility and artifact behavior under quantized bases.
- VAE decode peak memory for larger frame counts.
- Overnight memory recovery after repeated model/LoRA swaps.

## Required Local Benchmarks Before Production Decisions

1. Wan2.1 1.3B and LTXV 2B preview smoke tests.
2. Wan2.2 5B 81-frame preview test.
3. Wan2.1/2.2 14B FP8 832x480x81 test.
4. One LoRA overhead test on the best passing model.
5. VAE decode stress test at candidate final resolution.
6. 20-job overnight soak with telemetry and automatic restart recovery.
7. FFmpeg assembly test with 20 generated clips, then extrapolate disk/time for 180+ clips.

## Production Architecture Gate

Do not choose the final model stack from documentation alone. Choose it from the benchmark table produced by this laptop, with the winning preset satisfying:

- Peak VRAM below 23GB.
- No unrecovered OOM.
- Acceptable thermal behavior.
- Recoverable ComfyUI process state.
- Stored workflow/model hashes.
- Successful FFmpeg assembly validation.

## AI Orchestration Boundary

Optional agents such as Brad, Grok CLI, Qwen3-Coder-Next, Kimi, GPT-5.5, Claude, or similar models can help with creative planning, shot prompting, continuity review, gap detection, failed-shot diagnosis, prompt repair, and next-action recommendations.

They are not trusted execution components. They produce structured proposals. CineForge validates, approves, executes, records provenance, and audits the result.
