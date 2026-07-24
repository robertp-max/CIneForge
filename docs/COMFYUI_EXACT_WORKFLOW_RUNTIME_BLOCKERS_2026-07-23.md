# ComfyUI exact workflow runtime blockers — 2026-07-23

This record corrects the earlier overstatement that the exact FLUX.2 / Klein workflow support was packaged and published. At this checkpoint, the work is a guarded local installer plus this blocker record only.

## Current truth

- External escalated execution failed before any ComfyUI mutation. Sanitized observed errors:
  - Windows sandbox process launch error: `windows sandbox: runner failed during SpawnChild: CreateProcessAsUserW failed: 1312 (A specified logon session does not exist. It may already have been terminated.)`.
  - Escalation request error: `Automatic approval review failed: unsupported_value: This model is not supported when using X-OpenAI-Internal-Codex-Responses-Lite.`
- `scripts/install_exact_flux2_klein_workflow_nodes.ps1` exists locally, but it has not been executed.
- ComfyUI was not modified by this checkpoint.
- CineForge runtime behavior was not modified by this checkpoint; this repository checkpoint only adds this blocker record and the guarded installer script.
- No custom-node installation has been verified.
- No VAE download has been verified locally.
- No workflow execution has been verified.
- No generated media is included in this checkpoint.
- GitHub commit/push status: repository-only Git execution was unblocked by using direct `git` argument-vector calls instead of the failing PowerShell shell wrapper. This file is authored for branch `chore/comfyui-exact-workflow-installer`; the immutable commit SHA and push verification are reported in the accompanying checkpoint response rather than embedded in this self-referential file.

## What the installer is allowed to do later

The installer is deliberately fail-closed and dry-run by default. It requires an explicit external ComfyUI root and the exact workflow JSON path. It refuses to treat the CineForge repository as a ComfyUI runtime root.

The installer only mutates the external ComfyUI runtime when all of the following are true:

1. A valid ComfyUI root is supplied.
2. The expected ComfyUI marker paths are present.
3. The supplied workflow file is the exact `Flux 2D & Klein_9b ver 7.0.json`.
4. `-Execute` is supplied.
5. All reviewed GitHub URLs and commit pins validate.
6. The FLUX.2 VAE URL and SHA-256 validate.

## Guardrails implemented

- Requires explicit `-ComfyUIRoot`.
- Canonicalizes and validates paths before work.
- Verifies `main.py`, `custom_nodes`, `models`, and `user` under the supplied ComfyUI root.
- Verifies marker path types before making changes.
- Requires the exact workflow file to live under the supplied external ComfyUI root.
- Defaults to dry-run.
- Requires explicit `-Execute` for mutation.
- Does not request admin elevation.
- Does not modify CineForge source files.
- Does not start or stop ComfyUI.
- Does not touch CineForge Git history.
- Does not recursively delete directories.
- Does not overwrite existing custom-node checkouts by default.
- Requires `-UpdateExistingCheckouts` in addition to `-Execute` before updating an existing checkout.
- Refuses to update an existing checkout unless it is a clean Git worktree with the reviewed origin URL.
- Pins every executable custom-node package to a full reviewed commit SHA.
- Restricts custom-node repositories to an HTTPS GitHub allowlist.
- Restricts the VAE download to the reviewed Hugging Face FLUX.2 VAE URL.
- Verifies `flux2-vae.safetensors` by SHA-256 before placement.
- Downloads the VAE to a temporary file before final same-directory atomic move.
- Fails closed on download, path, Git, hash, or dependency errors.
- Does not place model binaries, checkpoints, VAEs, caches, runtime files, or generated media in the CineForge repository.
- Does not print credentials, tokens, cookies, or private URLs.
- Sanitizes child-process error output before surfacing it.
- Produces a final dry-run JSON summary.
- Produces a rollback manifest for manual review.
- Is intended to be idempotent.

## Reviewed executable package pins

These are the only custom-node packages the installer may install or update. Any package not listed here remains blocked until a separate commit pin is reviewed and added.

| Package | Repository | Pinned commit |
| --- | --- | --- |
| ComfyUI-Flux2Klein-Enhancer | `https://github.com/capitan01R/ComfyUI-Flux2Klein-Enhancer.git` | `6804643bff9a20926106427ff08d5b1bd2e49861` |
| rgthree-comfy | `https://github.com/rgthree/rgthree-comfy.git` | `27b4f4cdcf3b127c29d5d8135ac1536ecbd4c383` |
| ComfyUI-GGUF | `https://github.com/city96/ComfyUI-GGUF.git` | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` |
| ComfyUI-Custom-Scripts | `https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git` | `609f3afaa74b2f88ef9ce8d939626065e3247469` |
| comfyui_controlnet_aux | `https://github.com/Fannovel16/comfyui_controlnet_aux.git` | `055e2442e4b3a6c8d71baf02f48b934acaf6fe61` |
| ComfyUI-Crystools | `https://github.com/crystian/ComfyUI-Crystools.git` | `2f18256c5b5063937106f29a8e0a7db3ae3869b7` |
| ComfyUI-Impact-Pack | `https://github.com/ltdrdata/ComfyUI-Impact-Pack.git` | `429d0159ad429e64d2b3916e6e7be9c22d025c3c` |
| ComfyUI-Impact-Subpack | `https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git` | `d63cdfb3f99571b7681107456645e61a194b47f3` |
| ComfyUI_JPS-Nodes | `https://github.com/JPS-GER/ComfyUI_JPS-Nodes.git` | `0e2a9aca02b17dde91577bfe4b65861df622dcaf` |
| ComfyUI_LayerStyle | `https://github.com/chflame163/ComfyUI_LayerStyle.git` | `3d4a3526a9d1a19671a133e9215077bda520ee5d` |

## Reviewed VAE

| File | Source | SHA-256 |
| --- | --- | --- |
| `flux2-vae.safetensors` | `https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors` | `d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5` |

## Deferred / still blocked

- The installer has not been executed.
- ComfyUI has not been restarted by this workflow.
- The exact workflow has not been loaded after node installation.
- The first ten project images have not been regenerated under this guarded package set.
- Additional workflow archetype packages mentioned in earlier planning are not installed unless they are added to the reviewed executable package list with exact commit pins.

## Safe dry-run example

```powershell
.\scripts\install_exact_flux2_klein_workflow_nodes.ps1 `
  -ComfyUIRoot "C:\AI\ComfyUI_windows_portable\ComfyUI" `
  -WorkflowPath "C:\AI\ComfyUI_windows_portable\ComfyUI\user\default\workflows\flux2Klein9bProGradeWorkflowHigh_v70MajorUpdates\Flux 2d and Klein_9b ver 7.0\Flux 2D & Klein_9b ver 7.0.json"
```

## Explicit execution example

```powershell
.\scripts\install_exact_flux2_klein_workflow_nodes.ps1 `
  -ComfyUIRoot "C:\AI\ComfyUI_windows_portable\ComfyUI" `
  -WorkflowPath "C:\AI\ComfyUI_windows_portable\ComfyUI\user\default\workflows\flux2Klein9bProGradeWorkflowHigh_v70MajorUpdates\Flux 2d and Klein_9b ver 7.0\Flux 2D & Klein_9b ver 7.0.json" `
  -Execute
```

Do not use the execution example until the dry-run summary has been reviewed.
