# Existing Qwen TTS runtime inventory

This is the bounded Wave-0 inventory for the workstation targeted by CineForge.
It records pre-existing evidence only. No package was installed, no model was
downloaded, no runtime was started, and no model weights were loaded while
collecting or validating this inventory.

## Audited installation

| Item | Existing evidence |
| --- | --- |
| Source/runtime | `C:\AI\Qwen3-TTS` with the `qwen_tts` package source |
| Isolated Python environment | `C:\AI\qwen3-tts-env` (Python 3.12.10) |
| Installed package | `qwen-tts` 0.1.1 |
| Core dependencies observed | `torch` 2.11.0+cu128 and `transformers` 4.57.3 |
| Local base model | `C:\AI\Qwen3-TTS-12Hz-1.7B-Base` |
| Local tokenizer | `C:\AI\Qwen3-TTS-Tokenizer-12Hz` |
| Cached VoiceDesign model | Hugging Face cache entry for `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` |
| Cached CustomVoice model | Hugging Face cache entry for `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` |

Each detected model directory contains both `config.json` and
`model.safetensors`. CineForge checks those bounded manifests without importing
the package or reading the weights. The discovery result exposes only booleans
to the public API; the local runtime path is redacted.

## Supported boundary

The installed package exposes VoiceDesign and CustomVoice. CineForge maps those
capabilities to `qwen_voice_design` and `qwen_custom_voice`. CustomVoice is
limited to installed preset speaker identifiers. Although the installed base
package also contains voice-cloning APIs, CineForge deliberately does not expose
them in Storyboard Phase 1 and rejects reference-audio or cloning metadata.

The installed model documentation lists Chinese, English, Japanese, Korean,
German, French, Russian, Portuguese, Spanish, and Italian. The Python examples
write generated samples as WAV using the model-returned sample rate. CineForge
does not claim a language, speaker, output, or health result until an explicit
preview worker reports it.

## Launch, health, and scheduling

The installed package provides the `qwen-tts-demo` CLI entry point, but no
approved always-on local service or health endpoint was found. CineForge does
not launch that demo and does not construct arbitrary shell commands. Its
current health check is therefore bounded filesystem/configuration evidence:
runtime source, isolated interpreter, and complete model manifests.

Public preview requests remain truthfully unavailable until a durable,
controller-owned preview worker is configured. Any future explicit preview
worker must use CineForge's shared GPU lease boundary so Qwen work cannot overlap
high-risk video GPU work. It must not submit ComfyUI prompts, mutate workflow
JSON, install packages, or download weights. Storyboard proposal apply and
approval never invoke Qwen.

## Configuration overrides

Portable deployments may point discovery at another pre-approved installation
with `CINEFORGE_LOCAL_AI_ROOT`, `CINEFORGE_QWEN_LOCAL_RUNTIME`,
`CINEFORGE_QWEN_LOCAL_VENV`, and `CINEFORGE_QWEN_LOCAL_MODEL`. Existing
`CINEFORGE_QWEN_RUNTIME_REF` / `CINEFORGE_QWEN_VOICE_MODEL` configuration takes
precedence. An enable flag by itself is never treated as availability.
