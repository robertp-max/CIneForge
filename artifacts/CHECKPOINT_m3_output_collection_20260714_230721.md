# Checkpoint — M3 Managed Output Collection Mock

Generated: 2026-07-14 23:07 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `d19c2a3 checkpoint: record Comfy progress and release leases`

## Scope completed

Continued M3 controlled-runtime mocks without touching ComfyUI or running GPU work.

Changes:

- Extended `OutputCollector` with `collect_for_job(...)` for jobs in `collecting_outputs` state.
- Collects only managed files already saved under the sanitized ComfyUI output project folder/prefix.
- Persists collected outputs into:
  - `GeneratedAsset`
  - `FileOutput`
- Records SHA256 and optional ffprobe metadata.
- Advances queue state:
  - outputs found: `collecting_outputs -> complete`
  - no outputs found: `collecting_outputs -> postprocess_failed`
- Sets `ComfyJob.completed_at` and `WorkflowRun.ended_at` on success.
- Releases the bound GPU lease on both success and output-collection failure.
- Added output collection tests with fake local files; no FFmpeg probe or ComfyUI call is required.

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_output_collector.py \
  backend/tests/test_progress_monitor.py \
  backend/tests/test_controlled_submission.py \
  backend/tests/test_queue_service.py
# 69 passed, warnings only

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 454 passed, 9 skipped, warnings only, ~74.68s
```

## Safety notes

- No public generation route was added.
- No ComfyUI/GPU render, benchmark, or runtime mutation was run.
- Output collection is still mock/offline filesystem behavior; live history/view/WebSocket client integration remains pending.

## Next dependency-ready work

1. Add timeout/cancel/interrupted terminal mapping and lease release tests.
2. Add worker-only live Comfy history/view wrappers behind the same controlled boundary.
3. Add process-tree recovery/health-check mocks before any M4 hardware ladder.
