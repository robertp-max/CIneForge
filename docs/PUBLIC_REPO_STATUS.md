# Public Repo Status

Date: 2026-05-26

Repository: `https://github.com/robertp-max/CIneForge.git`

## Current Public Scope

- Research packet documentation.
- Sprint 1A FastAPI backend foundation.
- Local-development configuration example.
- Unit tests for non-generating primitives.
- Example dummy workflow template for manifest validation.

## Explicitly Not Included

- No `.env` files.
- No API keys or provider tokens.
- No generated videos.
- No model checkpoints or LoRA files.
- No ComfyUI runtime install.
- No local SQLite database.
- No generated workflow snapshots or probe JSON.

## Hygiene Rules

`.gitignore` excludes local environments, Python caches, generated DB files, generated workflow snapshots, generated probe JSON, logs, output assets, input assets, benchmark result files, and packaging metadata.

## Risk Scan Summary

Content scan found no secret-bearing files matching common API key, token, password, private-key, AWS, OpenAI, xAI, Anthropic, or DB-password patterns.

Filename scan noted local generated development folders:

- `.venv` - ignored local virtual environment.
- `cineforge.egg-info` - ignored packaging metadata.

`.env.example` is intentionally tracked and contains placeholder local configuration only.

