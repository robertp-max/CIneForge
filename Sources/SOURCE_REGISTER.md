# Source Register

This investigation prioritizes official model cards, official repositories, ComfyUI documentation/source, maintained custom-node repositories, Hugging Face model pages, and reproducible workflows. Claims that are not directly verified are labeled as test-required.

**2026-07 product-source policy:** the default video lane is `ltx2_3_22b_distilled_1_1_fp8`, meaning official LTX-2.3 22B Distilled **1.1** identity plus a proven FP8 runtime method. The official Distilled 1.1 BF16 checkpoint is not assumed to be FP8, and non-1.1 FP8 files are not valid substitutes unless the product contract is explicitly changed. Wan sources remain secondary/historical evidence.

## Primary Sources

| Source | URL | Used For | Evidence Level |
|---|---|---|---|
| Lightricks LTX-Video model card | https://huggingface.co/Lightricks/LTX-Video | LTXV model variants, frame rules, resolution constraints, examples, VAE/text encoder references | Verified official documentation |
| Lightricks LTX-Video HF API | https://huggingface.co/api/models/Lightricks/LTX-Video?blobs=true | File-size verification for listed LTX artifacts | Verified official documentation |
| Lightricks LTX-2 model card | https://huggingface.co/Lightricks/LTX-2 | LTX-2 19B model family, text encoder, offload examples, precision variants | Verified official documentation |
| Lightricks LTX-2 HF API | https://huggingface.co/api/models/Lightricks/LTX-2?blobs=true | LTX-2 file-size verification | Verified official documentation |
| Lightricks LTX-2.3 model card | https://huggingface.co/Lightricks/LTX-2.3 | LTX-2.3 22B references and official Distilled 1.1 source identity | Verified official documentation |
| Lightricks LTX-2.3-fp8 model card | https://huggingface.co/Lightricks/LTX-2.3-fp8 | Official FP8 lineage check; **not** a silent substitute for Distilled 1.1 unless identity is proven or contract changes | Verified official documentation, blocked for product key without identity proof |
| Lightricks ComfyUI-LTXVideo | https://github.com/Lightricks/ComfyUI-LTXVideo | Official ComfyUI support, workflows, low-VRAM loaders, LTX nodes | Verified maintainer repo |
| Lightricks ComfyUI-LTXVideo 2.3 example workflows | https://github.com/Lightricks/ComfyUI-LTXVideo/tree/main/example_workflows/2.3 | Source for official LTX-2.3 single-stage, two-stage, control, and lipdub graph admission candidates | Verified maintainer repo |
| Lightricks LTXVideo Q8 Kernels | https://github.com/Lightricks/LTXVideo-Q8-Kernels | Q8 kernel path and LTX Q8 behavior | Verified maintainer repo |
| Wan2.1 T2V 1.3B | https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B | Secondary/historical Wan 1.3B model scope and official memory guidance | Verified official documentation; optional lane only |
| Wan2.1 T2V 14B | https://huggingface.co/Wan-AI/Wan2.1-T2V-14B | Secondary/historical Wan 14B model scope and official inference constraints | Verified official documentation; optional lane only |
| Wan2.1 I2V 14B 720P | https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P | Secondary/historical Wan I2V constraints and model family | Verified official documentation; optional lane only |
| Wan2.2 T2V A14B | https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B | Secondary/historical Wan2.2 A14B architecture and official high-memory expectations | Verified official documentation; optional lane only |
| ComfyUI Wan examples | https://comfyanonymous.github.io/ComfyUI_examples/wan/ | Secondary/historical native ComfyUI Wan2.1 workflows, fp16/bf16/fp8 quality ranking | Verified official documentation; optional lane only |
| ComfyUI Wan2.2 docs | https://docs.comfy.org/tutorials/video/wan/wan2_2 | Secondary/historical Wan2.2 ComfyUI setup, model file placement, FP8 workflow references | Verified official documentation; optional lane only |
| ComfyUI Wan2.2 examples | https://comfyanonymous.github.io/ComfyUI_examples/wan22/ | Secondary/historical Wan2.2 workflow templates and ComfyUI examples | Verified official documentation; optional lane only |
| Comfy-Org Wan2.1 repackaged HF API | https://huggingface.co/api/models/Comfy-Org/Wan_2.1_ComfyUI_repackaged?blobs=true | Secondary/historical ComfyUI repackaged Wan file names and sizes | Verified official documentation; optional lane only |
| Comfy-Org Wan2.2 repackaged HF API | https://huggingface.co/api/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged?blobs=true | Secondary/historical ComfyUI repackaged Wan2.2 high/low FP8 files, VAEs, text encoder | Verified official documentation; optional lane only |
| ComfyUI server routes docs | https://docs.comfy.org/development/comfyui-server/comms_routes | API routes and communication architecture | Verified official documentation |
| ComfyUI message docs | https://docs.comfy.org/development/comfyui-server/comms_messages | WebSocket event types and progress messages | Verified official documentation |
| ComfyUI server source | https://github.com/Comfy-Org/ComfyUI/blob/master/server.py | Endpoint behavior, queue/history/view/upload/free/interrupt routes | Verified maintainer repo |
| ComfyUI API examples | https://github.com/comfyanonymous/ComfyUI/blob/master/script_examples/websockets_api_example.py | Python WebSocket API flow | Verified maintainer repo |
| ComfyUI custom-node backend docs | https://docs.comfy.org/custom-nodes/backend/server_overview | Execution graph and `IS_CHANGED` cache behavior | Verified official documentation |
| ComfyUI model management source | https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/model_management.py | Smart memory, offload, loaded model behavior | Verified maintainer repo |
| ComfyUI CLI args source | https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/cli_args.py | `--highvram`, `--disable-smart-memory`, `--reserve-vram` | Verified maintainer repo |
| ComfyUI Manager docs | https://docs.comfy.org/manager/install | Manager install and node management | Verified official documentation |
| ComfyUI Manager repo | https://github.com/Comfy-Org/ComfyUI-Manager | Snapshot/update behavior and CLI support | Verified maintainer repo |
| City96 ComfyUI-GGUF | https://github.com/city96/ComfyUI-GGUF | GGUF loader, GGUF T5 loader, experimental LoRA compatibility | Verified maintainer repo |
| City96 LTX GGUF | https://huggingface.co/city96/LTX-Video-0.9.6-dev-gguf | LTX GGUF Q variants and placement instructions | Reproducible community workflow |
| Kijai WanVideoWrapper | https://github.com/kijai/ComfyUI-WanVideoWrapper | Wan wrapper, FP8/GGUF/block swap/LoRA notes | Verified maintainer repo |
| FFmpeg formats docs | https://www.ffmpeg.org/ffmpeg-formats.html | concat demuxer constraints | Verified official documentation |
| FFmpeg filters docs | https://ffmpeg.org/ffmpeg-filters.html | concat filter, loudnorm, subtitles, xfade behavior | Verified official documentation |
| FFmpeg manual | https://ffmpeg.org/ffmpeg.html | stream mapping, codec copy, transcode behavior | Verified official documentation |
| FFprobe docs | https://ffmpeg.org/ffprobe.html | JSON probing and validation | Verified official documentation |
| NVIDIA SMI docs | https://docs.nvidia.com/deploy/nvidia-smi/index.html | GPU telemetry, CSV query, Windows limitations | Verified official documentation |
| PyTorch reproducibility docs | https://docs.pytorch.org/docs/2.11/notes/randomness.html | reproducibility limits and deterministic mode caveats | Verified official documentation |
| Diffusers reproducible pipelines | https://huggingface.co/docs/diffusers/en/using-diffusers/reusing_seeds | seed handling and generator caveats | Verified official documentation |
| TorchAO quantization docs | https://huggingface.co/docs/transformers/en/quantization/torchao | General TorchAO capability; not verified for Wan/LTX ComfyUI production | Verified official documentation, Unknown / insufficient evidence for this use case |
| MLflow tracking docs | https://www.mlflow.org/docs/latest/ml/tracking/ | params/metrics/artifacts/run metadata model | Verified official documentation |
| DVC pipeline docs | https://docs.dvc.org/user-guide/project-structure/dvcyaml-files | dependencies, outputs, params, hashes for reproducible pipelines | Verified official documentation |
| W3C PROV-DM | https://www.w3.org/TR/2013/REC-prov-dm-20130430/Overview.html | provenance model concepts | Verified official documentation |

## Evidence Caveat

Community reports of 24GB feasibility for large Wan/LTX workflows are useful as test leads, not production facts. Community or local LTX-2.3 Distilled 1.1 FP8 derivatives are leads only until conversion provenance, hashes, graph admission, and operator approval are recorded. For this laptop, every large-model recommendation must pass the local benchmark suite in `Benchmarks/BENCHMARK_PROTOCOL.md`.
