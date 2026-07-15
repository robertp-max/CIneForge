# Checkpoint — M3 End-to-End Mocked Worker Lifecycle

Generated: 2026-07-14 23:23 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `0964658 checkpoint: add worker Comfy runtime client`

## Scope completed

Added an end-to-end mocked worker lifecycle test for the M3 controlled runtime path.

The new test covers:

1. Reserved worker-owned job with valid workflow/object_info.
2. Explicit GPU lease acquisition.
3. Controlled submission through `ControlledComfySubmissionService`.
4. Mock prompt submission result with `prompt_id`.
5. Progress event mapping:
   - `execution_start` -> `running`
   - completion signal -> `collecting_outputs`
6. Managed filesystem output discovery under sanitized project folder/prefix.
7. Persistence to `GeneratedAsset` and `FileOutput`.
8. Final `complete` state and workflow-run end metadata.
9. GPU lease release.

Files:

- Added `backend/tests/test_m3_mocked_worker_lifecycle.py`

## Validation

```bash
unset CINEFORGE_TEST_POSTGRES_URL
./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider backend/tests/test_m3_mocked_worker_lifecycle.py
# 1 passed

./.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
# 463 passed, 9 skipped, warnings only, ~81.27s
```

## Safety notes

- No public generation route was added.
- No live ComfyUI/GPU/render/benchmark action was run.
- The lifecycle test is fully mocked/offline and uses fake output bytes.

## Next dependency-ready work

1. Add process-tree recovery and post-restart health-check mocks before any M4 hardware ladder.
2. Add worker-controlled interrupt/queue cleanup/free wrappers only behind explicit operator/worker gates.
3. Consider frontend/operator visibility for M3 lifecycle states without enabling generation.
