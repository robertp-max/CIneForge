# Checkpoint: offline-safe CI workflow

Date: 2026-07-16

## Implemented

- Updated `.github/workflows/test.yml` to run the curated offline-safe validation runner.
- CI now sets up Python and Node, installs backend/frontend dependencies, and runs:
  - `python scripts/run_offline_safe_validation.py`

## Safety posture

The CI workflow runs static boundary validation, curated backend tests, frontend lint/build, and whitespace checks only. It does not run FFmpeg/ffprobe, contact ComfyUI, probe GPU/runtime health, submit prompts, create jobs, render media, benchmark, or enable public generation.

## Local validation

The runner was already executed locally in this wave and passed. This checkpoint only changes CI wiring.
