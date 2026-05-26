# Risk Register

| Risk | Likelihood | Impact | Detection Method | Mitigation | Owner |
|---|---|---|---|---|---|
| 24GB VRAM insufficient for desired model | High | High | OOM logs, peak VRAM | FP8/GGUF, lower res/frames, smaller model | Backend/GPU |
| Laptop thermal throttling | High | High | nvidia-smi temp/clocks | Cooldown, batch limits, fan/power profile | Ops |
| Quantized model unsupported in ComfyUI | Medium | High | `/object_info`, failed workflow | Use verified native FP8 first | ML Eng |
| LoRA incompatible with quantized base | High | Medium | Smoke test same seed | Registry compatibility gates | ML Eng |
| LoRA version mismatch | Medium | Medium | Artifacts/failure | Match base version and hash | ML Eng |
| Text encoder too large | Medium | High | VRAM/RAM telemetry | FP8/offload text encoder | Backend |
| VAE decode OOM | Medium | High | OOM during decode | VAE tiling/offload/lower frames | Backend |
| Long frame count OOM | High | High | OOM at sampler/VAE | Split clips, 81-frame tier | Product/ML |
| Resolution OOM | High | High | OOM by tier | Preview at 480p, upscale later | Product/ML |
| Model file naming confusion | High | Medium | Loader file not found | Model registry and hashes | Backend |
| Custom node abandoned | Medium | High | repo inactivity, breakage | Prefer native/official, pin commits | Ops |
| ComfyUI update breaks workflow | High | High | smoke test failure | snapshots, clone upgrade path | Ops |
| Workflow node IDs change | High | High | manifest validation fails | versioned manifest/snapshots | Backend |
| API payload invalid | Medium | Medium | `/prompt` node_errors | schema validation/object_info | Backend |
| WebSocket disconnect | Medium | Medium | connection close | fallback history polling | Backend |
| Queue stuck | Medium | High | no progress timeout | interrupt/restart worker | Backend |
| Memory leak overnight | Medium | High | rising RAM/VRAM | bounded batches/restarts | Ops |
| VRAM fragmentation | Medium | High | OOM after prior success | `/free`, restart policy | Ops |
| Output black frames | Medium | High | frame histogram/human QA | mark preset failed | QA |
| Temporal artifacts | High | Medium | QA review | shorter clips, I2V continuity | Creative/ML |
| Character drift | High | Medium | QA review | character LoRA/I2V references | Creative |
| Bad prompt adherence | Medium | Medium | QA rating | prompt templates, text encoder tests | Creative |
| Audio sync impossible natively | High | Medium | timeline validation | post-production alignment | Media |
| FFmpeg concat fails | High | Medium | ffmpeg error/probe mismatch | normalize clips first | Media |
| Re-encoding quality loss | Medium | Medium | visual QA/bitrate checks | mezzanine, final encode once | Media |
| File paths break | Medium | Medium | missing file errors | content-addressed assets | Backend |
| License restriction | Medium | High | registry review | license field/gates | Product/Legal |
| Model download too large | Medium | Medium | disk telemetry | model staging plan | Ops |
| Storage fills overnight | Medium | High | free-space guard | batch size, cleanup policy | Ops |
| Benchmark not reproducible | Medium | High | inconsistent metrics | environment snapshots | ML Eng |
| Driver/CUDA mismatch | Medium | High | import/runtime errors | pinned torch/CUDA stack | Ops |
| Windows/WSL/Linux inconsistency | Medium | Medium | benchmark deltas | platform-specific profiles | Ops |
| Custom node dependency conflict | High | High | pip resolver/runtime errors | isolated runtime, snapshots | Ops |
| Generation settings not stored | Low | High | missing audit fields | DB constraints, required schemas | Backend |
| ComfyUI `/free` not sufficient | Medium | Medium | VRAM remains high | supervised restart | Backend |
| Large queue API slowdown | Medium | Medium | queue latency | backend-owned bounded queue | Backend |
| GGUF slower than FP8 | Medium | Medium | benchmark timing | use only if FP8 OOMs | ML Eng |
| Multi-LoRA artifact explosion | Medium | Medium | QA failures | one-at-a-time gates | Creative/ML |
| NVENC competes with diffusion | Medium | Medium | GPU utilization overlap | schedule FFmpeg separately | Media/Ops |
| Autonomous run exceeds render budget | Medium | High | autonomy budget counters | hard max attempts/time/disk limits | Autonomy |
| Autonomous retry loop repeats bad recipe | Medium | High | repeated failure class per slot | retry-depth caps and escalation | Autonomy/QA |
| Agent proposal bypass attempt | Medium | High | forbidden fields in proposal schema | reject proposal and audit | Backend/Security |
| Agent hallucinates model/workflow capability | High | Medium | registry and benchmark validation failure | require CineForge compatibility gates | ML Eng |
| Auto-selection chooses technically valid but creatively wrong clip | Medium | Medium | creative QA/human review | require review threshold and final approval | Creative |
| Creative QA over-trusts AI reviewer | Medium | Medium | disagreement with human review | store AI QA as advisory, not ground truth | Product |
| Autonomous planner creates impossible timeline duration | Medium | Medium | duration validation | timeline policy validation | Backend |
| Batch planner breaks I2V dependency order | Medium | High | dependency graph validation | preserve dependency constraints | Backend |
| Batch planner creates parallel GPU renders | Low | High | queue invariant check | enforce single GPU worker | Backend |
| Autonomous run fills disk with intermediates | Medium | High | disk telemetry and estimates | disk budget and cleanup hold | Ops |
| Thermal-aware scheduler resumes too early | Medium | Medium | temp/clocks remain unsafe | cooldown hysteresis thresholds | Ops |
| Hosted AI leaks sensitive local context | Medium | High | provider payload audit | redaction and approval policy | Security |
| Policy engine misconfigured too permissive | Medium | High | policy review and dry-run | safe defaults and human approval | Product/Security |
| Final report missing provenance | Low | High | report completeness validation | block final completion | Backend |
| QA false negatives allow black/frozen clips | Medium | Medium | human review finds defect | tune QA thresholds, sample review | QA |
| QA false positives waste render budget | Medium | Medium | high reject rate | threshold tuning and override path | QA |
| Autonomous final assembly misses clip/audio/subtitle | Medium | High | final assembly validation | block final delivery | Media |
| Proposal approval ambiguity | Medium | Medium | missing actor/approval state | explicit approval records | Backend |
| Autonomous state machine stuck | Medium | Medium | no state transition timeout | watchdog and pause/escalate | Backend |
| Agent-generated FFmpeg command injection | Low | High | proposal contains raw command | forbid raw command execution; template-only commands | Security/Media |
