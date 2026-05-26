# Benchmark Protocol for RTX 5090 Laptop 24GB

Every production recommendation must be earned by local measurements on this exact machine.

## Benchmark Matrix

| Benchmark Case | Model | Quant | LoRA | Resolution | Frames | Steps | Runs | Metrics to Capture | Pass/Fail Criteria |
|---|---|---|---|---:|---:|---:|---:|---|---|
| Smoke tiny | Wan2.1 1.3B | FP16/FP8 | None | 512x288 | 49 | 8-12 | 3 | load time, total time, peak VRAM | Completes, no memory leak |
| Fast preview | LTXV 2B | FP8 | None | 704x384 | 81 | workflow default | 5 | sec/frame, temp, artifacts | <23GB peak, stable outputs |
| Wan preview | Wan2.1 1.3B | FP16/FP8 | None | 832x480 | 81 | workflow default | 5 | same | No OOM |
| Wan 14B FP8 | Wan2.1 14B | FP8 scaled | None | 832x480 | 81 | workflow default | 3 | peak VRAM, warm run delta | <23GB, recovers memory |
| Wan2.2 5B | Wan2.2 TI2V 5B | FP8/FP16 as available | None | 1280x704 or lower | 81 | workflow default | 3 | quality, VRAM, speed | Stable at chosen preset |
| Wan2.2 A14B | Wan2.2 T2V A14B | FP8 high/low | None | 832x480 | 81 | workflow default | 3 | peak VRAM, temp, crash rate | Must not OOM |
| LoRA overhead | Best passing model | Same | One LoRA | same | same | same | 3 | VRAM delta, speed delta, artifacts | Overhead acceptable |
| I2V continuity | Wan/LTX I2V | FP8 | optional | same | 81 | same | 3 | continuity, drift | No severe drift |
| VAE stress | Best final model | same | same | final tier | 121 | same | 3 | decode peak | No VAE OOM |
| Overnight soak | Selected preview preset | same | representative | preview tier | 81 | same | 20+ | failures, temp, leak | No unrecovered failure |

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
  "model": "Wan2.2-T2V-A14B",
  "quant": "fp8_scaled",
  "workflow_template_id": "wan22-a14b-fp8-v001",
  "width": 832,
  "height": 480,
  "frames": 81,
  "fps": 16,
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

## Determinism Caveat

PyTorch and Diffusers both warn that exact reproducibility is not guaranteed across hardware, driver versions, library versions, and CPU/GPU paths. Store seeds and all environment data, but treat byte-identical replay as a stretch goal, not a guaranteed property.
