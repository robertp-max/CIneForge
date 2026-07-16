# Checkpoint: Jobs offline manifest acknowledgement hardening

Date: 2026-07-16

## Implemented

- Updated `frontend/src/pages/Jobs.tsx` so offline semantic request manifest preparation requires a UI no-execution acknowledgement.
- Updated local file-backed manifest preparation to require a UI no-execution acknowledgement.
- Acknowledgements are reset after successful offline manifest preparation.

## Safety posture

This is UI-only safety hardening for already offline endpoints. It does not add backend execution, ComfyUI prompt submission, queue execution, GPU lease acquisition, runtime health calls, FFmpeg/ffprobe execution, rendering, benchmarking, approval, or public generation.

## Validation

- `cd frontend && npm run lint && npm run build`
  - Result: passed
