# Source Register

This investigation prioritizes official model cards, official repositories, ComfyUI documentation/source, maintained custom-node repositories, Hugging Face model pages, and reproducible workflows. Claims that are not directly verified are labeled as test-required.

## Primary Sources

| Source | URL | Used For | Evidence Level |
|---|---|---|---|
| Lightricks LTX-Video model card | https://huggingface.co/Lightricks/LTX-Video | LTXV model variants, frame rules, resolution constraints, examples, VAE/text encoder references | Verified official documentation |
| Lightricks LTX-Video HF API | https://huggingface.co/api/models/Lightricks/LTX-Video?blobs=true | File-size verification for listed LTX artifacts | Verified official documentation |
| Lightricks LTX-2 model card | https://huggingface.co/Lightricks/LTX-2 | LTX-2 19B model family, text encoder, offload examples, precision variants | Verified official documentation |
| Lightricks LTX-2 HF API | https://huggingface.co/api/models/Lightricks/LTX-2?blobs=true | LTX-2 file-size verification | Verified official documentation |
| Lightricks LTX-2.3 model card | https://huggingface.co/Lightricks/LTX-2.3 | LTX-2.3 22B references and distilled variants | Verified official documentation |
| Lightricks ComfyUI-LTXVideo | https://github.com/Lightricks/ComfyUI-LTXVideo | Official ComfyUI support, workflows, low-VRAM loaders, LTX nodes | Verified maintainer repo |
| Lightricks LTXVideo Q8 Kernels | https://github.com/Lightricks/LTXVideo-Q8-Kernels | Q8 kernel path and LTX Q8 behavior | Verified maintainer repo |
| Wan2.1 T2V 1.3B | https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B | Wan 1.3B model scope and official memory guidance | Verified official documentation |
| Wan2.1 T2V 14B | https://huggingface.co/Wan-AI/Wan2.1-T2V-14B | Wan 14B model scope, official inference constraints | Verified official documentation |
| Wan2.1 I2V 14B 720P | https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P | Wan I2V constraints and model family | Verified official documentation |
| Wan2.2 T2V A14B | https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B | Wan2.2 A14B architecture and official high-memory expectations | Verified official documentation |
| ComfyUI Wan examples | https://comfyanonymous.github.io/ComfyUI_examples/wan/ | Native ComfyUI Wan2.1 workflows, fp16/bf16/fp8 quality ranking | Verified official documentation |
| ComfyUI Wan2.2 docs | https://docs.comfy.org/tutorials/video/wan/wan2_2 | Wan2.2 ComfyUI setup, model file placement, FP8 workflow references | Verified official documentation |
| ComfyUI Wan2.2 examples | https://comfyanonymous.github.io/ComfyUI_examples/wan22/ | Wan2.2 workflow templates and ComfyUI examples | Verified official documentation |
| Comfy-Org Wan2.1 repackaged HF API | https://huggingface.co/api/models/Comfy-Org/Wan_2.1_ComfyUI_repackaged?blobs=true | ComfyUI repackaged Wan file names and sizes | Verified official documentation |
| Comfy-Org Wan2.2 repackaged HF API | https://huggingface.co/api/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged?blobs=true | ComfyUI repackaged Wan2.2 high/low FP8 files, VAEs, text encoder | Verified official documentation |
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

Community reports of 24GB feasibility for large Wan/LTX workflows are useful as test leads, not production facts. For this laptop, every large-model recommendation must pass the local benchmark suite in `Benchmarks/BENCHMARK_PROTOCOL.md`.
