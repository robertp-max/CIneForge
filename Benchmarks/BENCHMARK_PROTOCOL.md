# Benchmark Protocol for RTX 5090 Laptop 24GB

Every production recommendation must be earned by local measurements on this exact machine.

**Primary product lane:** `ltx2_3_22b_distilled_1_1_fp8` means LTX-2.3 22B Distilled **1.1** at an admitted FP8 runtime method. M0 records the verified BF16 source hash and selected local full-checkpoint FP8 hash (`c5dd96a75c4b588171b9807a8a25fea91e71a3cc7386d8bc245f50a21756cfbb`) as an operator-selected `converted_derivative`; graph compatibility, conversion provenance, and hardware benchmarks are still required. Wan benchmarks are secondary/historical unless explicitly enabled as optional evidence.

## Benchmark Matrix

### Primary LTX-2.3 Distilled 1.1 suite

| Benchmark Case | Model | Quant | LoRA | Resolution | Frames | Steps | Runs | Metrics to Capture | Pass/Fail Criteria |
|---|---|---|---|---:|---:|---:|---:|---|---|
| M0 identity/admission precheck | `ltx2_3_22b_distilled_1_1_fp8` source + selected FP8 artifact | `converted_derivative` recorded; no generation in this precheck | None | N/A | N/A | N/A | 0 | source SHA256, FP8 artifact SHA256, method enum, header-equivalence evidence, workflow source, Comfy/LTXVideo pins | Distilled 1.1 identity proven; selected FP8 artifact has same tensor names/shapes/config as source; no non-1.1 substitution; still requires conversion-provenance review before promotion |
| LTX smoke tiny | LTX-2.3 Distilled 1.1 | admitted FP8 method only | None | lowest admitted tier, e.g. 512x288 or 704x384 | `8n+1`, start 49 | lowest admitted | 3 | load time, total time, peak VRAM, crash/OOM, output existence | Completes under 23GB peak, no memory leak, source/FP8 hashes in run record |
| LTX draft single-stage | LTX-2.3 Distilled 1.1 | admitted FP8 method only | None | reduced validated draft tier | `8n+1`, likely 49-81 | workflow default/validated | 5 | sec/frame, temp, artifacts, recovery after `/free` or restart | Stable outputs; memory returns or restart policy proven |
| LTX review single-stage | LTX-2.3 Distilled 1.1 | admitted FP8 method only | None | medium validated review tier | `8n+1`, likely 81-121 | workflow default/validated | 5 | quality, peak VRAM, warm-run delta, thermal behavior | Stable under 23GB peak and human-review acceptable |
| LTX final-candidate two-stage | LTX-2.3 Distilled 1.1 | admitted FP8 method only | optional admitted LoRA/upscaler only | final-candidate tier | `8n+1`, after single-stage passes | admitted two-stage settings | 3 | stage split timings, decode/upscale peak, output QA | Blocked until single-stage ladder passes and `CF-VID-02` is admitted |
| LTX controlled/lipdub probes | LTX-2.3 Distilled 1.1 | admitted FP8 method only | admitted IC-LoRA/lipdub only | controlled tier | graph-specific `8n+1` | admitted graph settings | 3 | control adherence, drift, VRAM delta, failure modes | Blocked until control/lipdub graph admission and recovery evidence |
| LTX overnight soak | Selected admitted LTX preview preset | same | representative admitted stack | preview tier | selected validated | selected validated | 20+ | failures, temp, leak, restart behavior | No unrecovered failure; no unsafe thermal/VRAM trend |

### Secondary / historical optional suite

| Benchmark Case | Model | Quant | LoRA | Resolution | Frames | Steps | Runs | Metrics to Capture | Pass/Fail Criteria |
|---|---|---|---|---:|---:|---:|---:|---|---|
| Smoke tiny | Wan2.1 1.3B | FP16/FP8 | None | 512x288 | 49 | 8-12 | 3 | load time, total time, peak VRAM | Completes, no memory leak; optional lane only |
| Fast preview | LTXV 2B | FP8 | None | 704x384 | 81 | workflow default | 5 | sec/frame, temp, artifacts | <23GB peak, stable outputs; optional lane only |
| Wan preview | Wan2.1 1.3B | FP16/FP8 | None | 832x480 | 81 | workflow default | 5 | same | No OOM; optional lane only |
| Wan 14B FP8 | Wan2.1 14B | FP8 scaled | None | 832x480 | 81 | workflow default | 3 | peak VRAM, warm run delta | <23GB, recovers memory; optional lane only |
| Wan2.2 5B | Wan2.2 TI2V 5B | FP8/FP16 as available | None | 1280x704 or lower | 81 | workflow default | 3 | quality, VRAM, speed | Stable at chosen preset; optional lane only |
| Wan2.2 A14B | Wan2.2 T2V A14B | FP8 high/low | None | 832x480 | 81 | workflow default | 3 | peak VRAM, temp, crash rate | Must not OOM; optional lane only |
| LoRA overhead | Best passing admitted model | Same | One LoRA | same | same | same | 3 | VRAM delta, speed delta, artifacts | Overhead acceptable |
| I2V continuity | LTX primary or optional Wan I2V | FP8 | optional | same | model-valid | same | 3 | continuity, drift | No severe drift |
| VAE stress | Best passing admitted model | same | same | final tier | model-valid | same | 3 | decode peak | No VAE OOM |
| Overnight soak | Selected admitted preview preset | same | representative | preview tier | selected validated | selected validated | 20+ | failures, temp, leak | No unrecovered failure |

## Metrics

- Model load time.
- First-run generation time.
- Warm-run generation time.
- Peak VRAM.
- Peak RAM.
- GPU utilization.
- Memory utilization.
- Temperature.
- Power draw if available.
- GPU clocks if available.
- Time per frame.
- Failure rate.
- Artifact rate.
- Queue latency.
- ComfyUI crash rate.
- Thermal throttling indicators.
- LoRA overhead.
- Quantization quality delta.
- VAE decode time.
- Upscale/interpolation time.
- FFmpeg assembly time.

## Telemetry Command

```powershell
nvidia-smi --query-gpu=timestamp,name,driver_version,pstate,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,power.draw,clocks.gr,clocks.mem --format=csv -l 1 > gpu_run.csv
```

NVIDIA documents `nvidia-smi` CSV query support and Windows limitations. Treat missing power/per-process fields on WDDM as expected.

## JSONL Logging Format

```json
{
  "ts": "2026-05-25T21:30:00Z",
  "event": "generation_completed",
  "run_id": "uuid",
  "prompt_id": "comfy_prompt_id",
  "model": "ltx2_3_22b_distilled_1_1_fp8",
  "quant": "fp8_converted_derivative",
  "workflow_template_id": "ltx23-distilled-single-stage-v001",
  "width": 704,
  "height": 384,
  "frames": 49,
  "fps": 24,
  "steps": 20,
  "seed": 123456789,
  "loras": [],
  "cold_start": false,
  "duration_sec": 420.5,
  "peak_vram_mib": 23210,
  "peak_ram_mib": 64200,
  "peak_temp_c": 78,
  "status": "complete",
  "output_sha256": "..."
}
```

## Benchmark Result Schema

```json
{
  "benchmark_id": "string",
  "hardware_profile_id": "string",
  "workflow_template_id": "string",
  "model_variant_id": "string",
  "quantization_id": "string",
  "lora_combination_id": "string|null",
  "resolution": { "width": 832, "height": 480 },
  "frames": 81,
  "fps": 16,
  "steps": 20,
  "guidance": 4.0,
  "runs": 5,
  "metrics": {
    "median_duration_sec": 0,
    "p95_duration_sec": 0,
    "peak_vram_mib": 0,
    "peak_ram_mib": 0,
    "peak_temp_c": 0,
    "failure_rate": 0,
    "artifact_rate": 0
  },
  "decision": "promote|retry|reject",
  "notes": "string"
}
```

## Promotion Gates

A preset graduates from prototype to production candidate only when:

- 3 cold runs and 5 warm runs complete.
- Peak VRAM stays below 23GB.
- Memory returns to expected baseline or restart policy is proven.
- No more than one recoverable failure in soak test.
- Output quality is acceptable under human review.
- Workflow snapshot, model hashes, and telemetry are stored.
- For LTX-2.3, width/height satisfy admitted graph divisibility rules and frame counts satisfy the `8n+1` rule where required.
- The Distilled 1.1 source hash, selected FP8 artifact hash, conversion provenance or explicit provenance gap, and ComfyUI/LTXVideo pins are stored.
- No non-1.1 official FP8 file or unproven derivative is promoted as `ltx2_3_22b_distilled_1_1_fp8`.

## Determinism Caveat

PyTorch and Diffusers both warn that exact reproducibility is not guaranteed across hardware, driver versions, library versions, and CPU/GPU paths. Store seeds and all environment data, but treat byte-identical replay as a stretch goal, not a guaranteed property.
