# Security Policy

## Public Repository Notice

This repository is public. Do not commit:

- `.env` files or local secrets.
- API keys or provider tokens.
- Database passwords.
- Private keys or certificates.
- Generated videos, model files, checkpoints, LoRAs, or local databases.
- ComfyUI runtime installs, caches, or downloaded model assets.

## Supported Version

The project is pre-release. Security reports should target the current `master` branch.

## Reporting

Open a GitHub security advisory or private issue with:

- Affected file or component.
- Risk category.
- Reproduction steps when safe.
- Suggested fix if known.

Do not include live secrets in reports.

## Current Security Boundaries

- ComfyUI is treated as an external isolated runtime.
- Sprint 1A does not execute generation jobs.
- AI/autonomy modules are non-executing stubs.
- FFmpeg commands must come from approved templates, not free-form AI or user strings.

