# Checkpoint: provider contract in curated runner

Date: 2026-07-16

## Implemented

- Added provider discovery/routing/connection contract tests (`backend/tests/test_provider_contract.py`) to the curated offline validation runner.
- These tests use SQLite, TestClient, and `httpx.MockTransport`; they do not perform external provider calls.
- Cleaned service-level `datetime.utcnow()` warnings in `backend/app/services/storyboard_crud.py` by using an explicit UTC timestamp converted to the existing naive DB convention.
- Extended runner membership guard so provider contract coverage remains in `BACKEND_TESTS`.
- Updated README/offline validation docs and current validation-count docs to warning-free `243 passed`.

## Validation

- Focused provider contract + offline runner tests: `15 passed`
- Full offline-safe runner:
  - Static safe/local boundary validation: passed
  - Curated backend tests: `243 passed`
  - Frontend lint/build: passed
  - `git diff --check`: passed with CRLF warnings only
  - Checkpoint watchdog banner printed
- Focused offline docs boundary tests were run after count updates before commit.

## Not performed

No FFmpeg, ffprobe, ComfyUI, GPU workload, runtime health probe, render, benchmark, queue execution, prompt submission, external provider call, public generation, or live approval was run or enabled.
