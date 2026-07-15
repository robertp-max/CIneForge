# Runtime Inventory (M0)

Last updated: 2026-07-13

Scope: read-only local inventory for the ComfyUI/LTX implementation plan. This document records evidence; it is **not** a readiness claim. No ComfyUI launch, generation, model download, package install, Manager update, or workflow mutation was performed while collecting this inventory.

## Policy lock

- Default video product key: `ltx2_3_22b_distilled_1_1_fp8`.
- Required identity: LTX-2.3 22B Distilled **1.1**.
- Required runtime precision: proven FP8 via one recorded method: `loader_level`, `converted_derivative`, or `official_artifact`.
- Current FP8 method decision: `converted_derivative` — operator-selected local full-checkpoint FP8 artifact at `C:\AI\ComfyUI_windows_portable\ComfyUI\models\checkpoints\ltx-2.3-22b-distilled-1.1-fp8.safetensors`.
- Conversion provenance is not yet reproducible in-repo, so graph admission and hardware readiness remain `benchmark_required`.
- Non-1.1 FP8 files are not valid substitutes.
- Wan and older LTXV lanes are historical or optional secondary evidence, disabled by default.
- Public/autonomous generation remains disabled.

## CineForge repository

| Item | Finding |
|---|---|
| Repository path | `C:\AI\Git\CIneForge` |
| HEAD | `85af098638fd44b74fdf793f99589733d91a8b78` |
| Implementation plan | `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md` |
| `.env` | Absent; `.env.example` present |
| Queue worker default | `CINEFORGE_QUEUE_WORKER_ENABLED=false` in config defaults/example |
| Hardware operator gate | Must remain separate and default-off in implementation milestones |
| ComfyUI output root | `C:\AI\ComfyUI_windows_portable\ComfyUI\output` via `CINEFORGE_COMFYUI_OUTPUT_ROOT` |
| Project output contract | One sanitized folder per project under the ComfyUI output root |

Untracked user material observed and preserved:

- `CINEFORGE_COMFYUI_IMPLEMENTATION_PLAN.md`
- `CIneForge.code-workspace`
- `CineForge-Storyboard-Studio-v2.zip`
- `CineForge-Storyboard-Studio-v2/`

Do not delete, move, edit, or commit the Storyboard Studio workspace/archive without user approval.

## ComfyUI runtime

| Item | Finding |
|---|---|
| Portable root | `C:\AI\ComfyUI_windows_portable` |
| App root | `C:\AI\ComfyUI_windows_portable\ComfyUI` |
| App version hints | `comfyui_version.py` / `pyproject.toml` report `0.19.3` |
| Portable git SHA | `b435ed4a97cbbe9e66017370d1ac2ca49b7270c2` |
| Portable remote | `https://github.com/robertp-max/ComfyUI_windows_portable.git` |
| Upstream ComfyUI SHA | Unknown; the app resolves to the portable monorepo, not a clean upstream checkout |
| Current Manager startup evidence | July logs report `### ComfyUI Revision: UNKNOWN (The currently installed ComfyUI is not a Git repository)` |
| Stale historical log evidence | April logs mention `235 [30860264] *DETACHED | Released on '2026-04-17'`, but this is not accepted as the current runtime pin |
| Extra model path behavior | `extra_model_paths.yaml` maps `checkpoints` / `diffusion_models` to portable `models/checkpoints` |

The true upstream ComfyUI commit remains an M0 blocker for fully reproducible graph admission unless the project explicitly accepts the portable monorepo SHA plus ComfyUI version as the runtime identity.

## Custom nodes

| Node | Git SHA / status |
|---|---|
| `ComfyUI-LTXVideo` | `229437c6b65796d6a7a63ae34be2bd5ba31fa543` |
| `ComfyUI-Manager` | `7d611c051e442533b083831d562bd0660cf9e0b4` |
| `ComfyUI-KJNodes` | `2ac0b25bbd96c2ad4f7744fb6814de563d4b8592` |
| `ComfyUI-GGUF` | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` |
| `ComfyUI-VideoHelperSuite` | `4ee72c065db22c9d96c2427954dc69e7b908444b` |
| `ComfyUI-VFI` | `6176a430f12cd16003f4664c1e3c6af8e96cc3c6` |
| `ComfyUI-PuLID-Flux-Enhanced` | `edcb3af534b8ae7c2b9d234d1fce8b6bc169e01f` |
| `ComfyUI-PuLID-Flux-GR` | `ada7a7257a824fd696bd8459489b8b35dc302ac5` |
| `Nvidia_RTX_Nodes_ComfyUI` | `892515e3eb9a4920a131a502a047e47adca9eb0d` |
| `ComfyUI_Batch_from_CSV` | `0c267391d4e1290908286466a2fe1f365b0586dc` |
| `10S-Comfy-nodes` | `fb6edfed97abaf246a826812536eef018d7a1c3b` |
| `pulid-flux-chroma` | No independent git checkout observed; resolves to portable monorepo context |

Official LTX-2.3 workflow candidates present under `ComfyUI-LTXVideo\example_workflows\2.3`:

- `LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json`
- `LTX-2.3_T2V_I2V_Two_Stage_Distilled.json`
- `LTX-2.3_ICLoRA_Union_Control_Distilled.json`
- `LTX-2.3_ICLoRA_Lipdub_Two_Stage_Distilled.json`
- `LTX-2.3_ICLoRA_Motion_Track_Distilled.json`
- `LTX-2.3_ICLoRA_HDR_Distilled.json`

## Python, Torch, CUDA, and GPU

Portable ComfyUI Python:

| Component | Finding |
|---|---|
| Python | `3.13.11` from `C:\AI\ComfyUI_windows_portable\python_embeded\python.exe` |
| torch | `2.10.0+cu130` |
| torchvision | `0.25.0+cu130` |
| torchaudio | `2.10.0+cu130` |
| CUDA from torch | `13.0` |
| `torch.cuda.is_available()` | `True` |
| `sageattention` | Present |
| `xformers` | Absent |

CineForge project venv:

| Component | Finding |
|---|---|
| Python | `3.14.3` observed earlier from `.venv` |
| Backend deps | `fastapi`, `pydantic`, `sqlalchemy`, `httpx`, `alembic`, `pytest` present |
| torch | Absent in project venv; GPU inference belongs to isolated ComfyUI runtime |

GPU:

| Item | Finding |
|---|---|
| GPU | NVIDIA GeForce RTX 5090 Laptop GPU |
| Driver | `596.36` |
| VRAM | `24463 MiB` total |
| Free at inventory sample | `24137 MiB` |

## FFmpeg and system tools

| Tool | Finding |
|---|---|
| ComfyUI output root | `C:\AI\ComfyUI_windows_portable\ComfyUI\output` |
| Output folder policy | Save nodes must use `filename_prefix = <project-folder>/<run-stem>`; CineForge sanitizes both components and rejects absolute paths, traversal, drive prefixes, backslashes, and deeper directory trees |
| Preferred FFmpeg | `C:\AI\ffmpeg-2026-01-22-git-4561fc5e48-full_build\bin\ffmpeg.exe` |
| Preferred version | `2026-01-22-git-4561fc5e48-full_build-www.gyan.dev` |
| Preferred ffprobe | same `bin` directory |
| PATH behavior | `ffmpeg` / `ffprobe` currently resolve to the preferred local full build in this shell |
| `nvidia-smi` | Available |
| Disk C: | Approximately `170G` free of `1.9T` at inventory sample |

Implementation should still add explicit path pinning where appropriate; relying only on `PATH` can drift.

## Model and artifact inventory

Root: `C:\AI\ComfyUI_windows_portable\ComfyUI\models`

### LTX artifacts

| Relative path | Size bytes | SHA256 / status |
|---|---:|---|
| `checkpoints/ltx-2.3-22b-distilled-1.1.safetensors` | `46149345334` | `b33b7fe4bbfe084f484be4aaf90b0f1d95dca20d403ac4c0e037eb8c4f0af7cc` — verified local Distilled 1.1 BF16 source identity; header shows `model`, `vae`, `audio_vae`, and `vocoder` tensors with `BF16`/`F32` dtypes |
| `checkpoints/ltx-2.3-22b-distilled-1.1-fp8.safetensors` | `25134891534` | `c5dd96a75c4b588171b9807a8a25fea91e71a3cc7386d8bc245f50a21756cfbb` — operator-selected local full-checkpoint FP8 artifact; header has exactly the same 5,947 tensor names/shapes and same `model_version=2.3.0`/config as the verified BF16 source; dtype transitions are `BF16->BF16` for 1,503 tensors, `BF16->F8_E4M3` for 4,154 tensors, and `F32->F8_E4M3` for 290 tensors; method recorded as `converted_derivative`, conversion provenance pending |
| `checkpoints/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors` | `25226571988` | `0a1d7aac2b338e8ec7e832149f1dcf11c9323272482b1cca0673d229702370f0` — local transformer-only derivative candidate; header shows `model` tensors only with `F8_E4M3`, `U8`, `BF16`, and `F32` dtypes; not the selected product artifact |
| `checkpoints/ltx-2.3-22b-distilled-1.1_transformer_only_mxfp8_block32.safetensors` | `24052755552` | `b7a945ff24d65ad22c6977787c2e594e74df226e35f1f9dedb64be8fdbd6ffd8` — local transformer-only MXFP8 derivative candidate; header shows `model` tensors only with `F8_E4M3`, `U8`, `BF16`, and `F32` dtypes; not admitted |
| `checkpoints/ltx-2.3-22b-dev.safetensors` | `46149344974` | Dev variant, not Distilled 1.1 product source |
| `checkpoints/ltx-2.3-22b-dev-fp8.safetensors` | `29145431166` | Dev FP8, not Distilled 1.1 product source |
| `checkpoints/ltx-video-2b-v0.9.safetensors` | `9370442108` | Legacy/optional |
| `loras/ltx-2.3-22b-distilled-lora-384.safetensors` | `7605507256` | Candidate LoRA; compatibility benchmark-required |
| `loras/ltx-2.3-id-lora-talkvid-3k.safetensors` | `1157884304` | Candidate LoRA; compatibility benchmark-required |
| `latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | `995743560` | Candidate upscaler |
| `latent_upscale_models/ltx-2.3-temporal-upscaler-x2-1.0.safetensors` | `261944000` | Candidate upscaler |

No full **official** artifact named Distilled 1.1 FP8 was found. The operator-selected local full-checkpoint FP8 file above is accepted as the M0 product artifact by explicit user instruction and recorded as `converted_derivative`, not `official_artifact`. Because its conversion command/toolchain has not been reproduced in-repo, graph admission and hardware readiness remain blocked pending conversion-provenance review, admitted workflow compatibility, serialized 24GB benchmark evidence, and recovery evidence.

### FLUX and supporting artifacts

| Relative path | Size bytes | Status |
|---|---:|---|
| `checkpoints/flux1-dev.safetensors` | `23802932552` | Candidate still-image source; admission later |
| `checkpoints/flux2_dev_fp8mixed.safetensors` | `35455599592` | Candidate still-image source; admission later |
| `checkpoints/flux-2-klein-9b-fp8.safetensors` | `9433061528` | Candidate still-image source; admission later |
| `loras/Flux_2-Turbo-LoRA_comfyui.safetensors` | `2760814880` | Candidate LoRA; compatibility benchmark-required |
| `loras/Flux_Skin_Detailer.safetensors` | `616306756` | Candidate LoRA; compatibility benchmark-required |
| `loras/Flux_Skin_Texture_V2.safetensors` | `612817272` | Candidate LoRA; compatibility benchmark-required |
| `text_encoders/mistral_3_small_flux2_bf16.safetensors` | `35584897447` | Candidate text encoder; admission later |
| `text_encoders/clip_l.safetensors` | `246144152` | Candidate text encoder; admission later |
| `text_encoders/gemma_3_12B_it_fp4_mixed.safetensors` | `9447702218` | Candidate LTX-2.x text path; graph role unconfirmed |
| `text_encoders/t5xxl_fp16.safetensors` | `9787841024` | Legacy/optional text encoder |
| `vae/ae.safetensors` | `335304388` | Candidate FLUX-style AE |
| `vae/full_encoder_small_decoder.safetensors` | `249519092` | Likely LTX-related VAE; graph role unconfirmed |

## No-download / no-update operational lock

Current Manager config (`C:\AI\ComfyUI_windows_portable\ComfyUI\user\__manager\config.ini`) says:

| Setting | Current value | M0 interpretation |
|---|---|---|
| `network_mode` | `public` | Not locked down; Manager may use external connections/cache refreshes |
| `update_policy` | `stable-comfyui` | Update target policy exists; no CineForge enforcement yet |
| `model_download_by_agent` | `False` | Agent-assisted model download disabled, but this is not a full no-download proof |
| `security_level` | `normal` | Install/update actions are not maximally blocked |
| `always_lazy_install` | `False` | Helps avoid some dependency installs, but not sufficient alone |

Observed July logs show Manager cache updates from external URLs during prior ComfyUI startup. No external ComfyUI mutation was performed by this M0 pass.

Until implementation adds enforceable settings and admission checks:

- Do not run ComfyUI Manager installs/updates from CineForge jobs.
- Do not allow workflow-provided URLs, arbitrary model paths, custom node installs, or runtime package installs.
- Do not enable public raw `/prompt` proxy behavior.
- Do not launch generation from Storyboard approval.
- Keep `queue_worker_enabled` default-off.
- Keep any future `hardware_operator_enabled` gate separate and default-off.

Manager auto-update/download prevention is policy-only in this repo and not fully enforced by the current external runtime. Locking the external Manager config to offline/stronger settings requires explicit operator approval because it mutates the ComfyUI installation outside the repository.

## Baseline validation status

| Item | Status |
|---|---|
| Backend offline pytest baseline | **Passed**: `430 passed, 9 skipped, 2912 warnings in 67.84s` with `CINEFORGE_TEST_POSTGRES_URL` cleared |
| Backend command | `env -u CINEFORGE_TEST_POSTGRES_URL .venv/Scripts/python.exe -B -m pytest -x -vv -p no:cacheprovider` |
| Database policy | No external database is required for this local app; PostgreSQL-gated tests are optional legacy/compatibility checks only |
| Prior planning run | Timed out after 180s near PostgreSQL concurrency tests; superseded by the offline baseline |
| Frontend build | **Passed**: `npm --prefix frontend run build` |
| Frontend lint | **Passed**: `npm --prefix frontend run lint` |

## Local ComfyUI lane implementation evidence

| Area | Current local artifact |
|---|---|
| Runtime model contract | `backend/app/services/local_runtime.py`, `/local-runtime/catalog` |
| Output policy | `comfyui_output_root`, `CINEFORGE_COMFYUI_OUTPUT_ROOT`, `/local-runtime/output-policy` |
| Preset catalog | `storage/presets/catalog.json` — exactly 64 disabled/gated presets validated by `backend/app/schemas/local_presets.py` |
| Archetype catalog | `storage/archetypes/catalog.json` — `CF-VID-01`..`CF-VID-04`, `CF-IMG-01`, all disabled/gated |
| Local job manifests | `backend/app/services/local_jobs.py`, `/local-jobs`, `storage/local_jobs/*.json`, `events.jsonl` |
| CF-VID-01 workflow candidate | UI source plus admitted API T2V smoke candidate: `workflow_api.json`, `workflow_manifest.json`, template `cf_vid_01_ltx23_single_stage_t2v_smoke` |
| Frontend surfaces | Runtime page local catalog cards; Jobs page local manifest creation/listing with explicit no-generation wording |

Runtime validation update: ComfyUI was launched locally after operator approval. Missing official-workflow dependency RES4LYF was installed at SHA `419de2d7c78f415dde9aa352a7231820ebfc17a4` with `pywavelets==1.9.0`; `/object_info` then covered all CF-VID-01 node classes. Two serialized minimal T2V smoke jobs completed successfully. Evidence is recorded in `docs/CFVID01_RUNTIME_SMOKE.md` and `storage/runtime/cfvid01_smoke_outputs_summary.json`. Local catalog/template loaders fail closed from the configured `storage/` root; tests copy fixtures explicitly when using temporary storage roots.

Offline backend baseline command used:

```bash
unset CINEFORGE_TEST_POSTGRES_URL
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests
```

PostgreSQL is not required for the local ComfyUI app path.

## M0 decision status

| Decision | Status |
|---|---|
| Preserve untracked Storyboard material | Observed and preserved |
| Distilled 1.1 source identity | Verified by SHA256 |
| FP8 method | Selected: `converted_derivative` via operator-provided full FP8 artifact `ltx-2.3-22b-distilled-1.1-fp8.safetensors`; conversion provenance and graph/hardware admission still pending |
| True upstream ComfyUI commit | Unknown; portable monorepo SHA and current `ComfyUI Revision: UNKNOWN` evidence recorded |
| LTXVideo node pin | Recorded |
| Runtime no-download/no-update enforcement | Policy recorded; operator-approved RES4LYF install was performed manually outside Manager; current external Manager config remains `network_mode=public`; app-level Manager/download enforcement still not complete |
| Baseline tests | Offline backend and frontend build/lint passed; no external database required |
| Readiness claim | CF-VID-01 minimal T2V smoke passed; profiles remain `benchmark_required` or `blocked` until benchmark ladder/recovery/human QA |
