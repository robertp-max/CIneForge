# Runtime Isolation, Queueing, Caching, and Memory Management

## Recommended Runtime Strategy

Use a hybrid runtime: the video editor backend is its own application process and drives ComfyUI over HTTP/WebSocket. ComfyUI stays isolated in a dedicated runtime folder or environment.

| Strategy | Strength | Weakness | Recommendation |
|---|---|---|---|
| Windows portable ComfyUI | Easy local setup; embedded Python; aligns with Windows operator machine | Packages must be installed with `python_embeded`; upgrades can drift | Best MVP choice |
| Isolated Python venv | Reproducible server-style setup; easier dependency locking | More setup work on Windows | Best controlled engineering choice |
| Container | Strong isolation; repeatable Linux deployment | Windows GPU/container friction; driver stack complexity | Use later for Linux/fleet, not MVP Windows laptop |
| In-process ComfyUI import | Low network overhead | Crashes/dependency conflicts take down app | Avoid |
| Multiple ComfyUI instances | Useful for model separation on multi-GPU | Dangerous on 24GB single GPU | Avoid concurrent GPU workers |

## ComfyUI Manager and Safe Upgrades

ComfyUI Manager is useful for installing, updating, disabling, and snapshotting custom nodes, but production reproducibility requires discipline:

1. Pin ComfyUI commit or stable release.
2. Save Manager snapshot before any update.
3. Record custom node commit hashes.
4. Record `pip freeze`, Python version, torch/torchvision/torchaudio, CUDA wheel index, xformers/sage-attention versions.
5. Upgrade in a clone/second portable folder first.
6. Run smoke workflows and representative Wan/LTX workflows.
7. Promote only after API, output retrieval, VRAM recovery, and benchmark deltas pass.

## CUDA/PyTorch Pinning

Treat the torch stack as a compatibility unit:

- Python version.
- Torch, torchvision, torchaudio.
- CUDA wheel index (`cu126`, `cu128`, `cu130`, etc.).
- xFormers or attention package if used.
- ComfyUI commit.
- Custom-node commits.

xFormers and related acceleration packages can force torch changes. Never run package installs from the wrong Python interpreter in the portable build.

## Cache Behavior Matrix

| Change Type | Expected Cache Impact | VRAM Impact | Backend Strategy |
|---|---|---|---|
| Seed only | Sampler path recomputes; model/text encoders may remain loaded | Low additional load if model stays warm | Group seed sweeps together |
| Positive prompt only | Text encode recomputes; generation recomputes | Text encoder may load/warm | Group prompt variants by same model |
| Negative prompt only | Same as prompt | Same | Store prompt pair per run |
| LoRA strength only | LoRA/model path invalidates downstream | May reload/patch model | Benchmark one LoRA stack before batching |
| LoRA file changed | Model conditioning changes; cache invalid | Adds load time and VRAM | Group by LoRA stack |
| Model changed | Full reload | Very high | Avoid frequent switching |
| Quant changed | Full loader/workflow change | Very high | Separate queues per quant |
| VAE changed | Decode path invalidates | Decode VRAM risk | Keep one VAE per batch |
| Text encoder changed | Text encoding path invalidates | High RAM/VRAM pressure | Prefer one encoder per queue group |
| Resolution changed | Latents/sampler/VAE recompute | Higher peak VRAM | Benchmark by resolution tier |
| Frame count changed | Latents/sampler/VAE recompute | Higher peak VRAM | Use fixed preview/final tiers |
| Steps changed | Sampler recomputes | Time impact, not usually loader impact | Sweep after feasibility established |

## Queue Design

Use a durable database queue with one GPU worker for ComfyUI jobs.

Recommended states:

`pending -> reserved -> submitted -> running -> collecting_outputs -> complete`

Failure states:

`validation_failed`, `comfy_rejected`, `runtime_failed`, `timeout`, `interrupted`, `oom`, `postprocess_failed`

Rules:

- Serialize GPU generation jobs on the 24GB GPU.
- Keep ComfyUI queue depth small; the backend owns long queue state.
- Use WebSocket completion; poll history only as fallback.
- Group jobs by model, quant, text encoder, VAE, and LoRA stack to reduce reload churn.
- Separate preview queues from final queues.
- Restart ComfyUI after memory thresholds, crash, hung job, or a configured number of high-risk jobs.
- Run FFmpeg/post-processing in separate CPU/GPU-aware workers so it does not interfere with generation.

## Memory and Stability Policy

| Condition | Detection | Action |
|---|---|---|
| Peak VRAM > 23GB | NVML/nvidia-smi sample | Mark preset unsafe; reduce resolution/frames/quant |
| VRAM not released after job | Post-job sample remains high after `/free` | Restart ComfyUI worker |
| Temperature sustained above laptop-safe threshold | nvidia-smi telemetry | Pause queue/cooldown |
| Job no progress | No WebSocket progress and low GPU util | Interrupt, then restart if needed |
| Repeated OOM | Error logs and process crash | Disable preset until benchmarked |
| Output black frames | Automated frame histogram / human QA | Mark model/preset failed |

## Overnight Stability

Do not run unbounded overnight queues. Use batches:

- 10-20 preview clips per batch for small models.
- 3-5 final clips per batch for 14B+ FP8/GGUF.
- Automatic cooldown between high-temperature jobs.
- Disk free-space guard before each job.
- Post-batch health check and optional ComfyUI restart.

## Local Smoke Tests

1. Start ComfyUI headless, submit a small known workflow, verify `/history/{prompt_id}` output.
2. Submit same workflow twice with same seed; verify output repeatability level and metadata capture.
3. Submit seed-only sweep; verify model warm-load behavior.
4. Run `/free`; measure VRAM before and after.
5. Kill/restart ComfyUI during pending job; verify backend recovery.
