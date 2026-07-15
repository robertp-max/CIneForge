# M5 Checkpoint: Offline Recipe Command Result Persistence

## Scope
- Extended backend-only generic FFmpeg recipe command manifests with offline success/error result recording.
- Added `PostProductionPlanStore.record_recipe_command_success` and `record_recipe_command_error`.
- Persisted normalized `output_sha256`, `final_probe_json`, timestamps, and error text while explicitly keeping `execution_submitted=false`.
- Did not add routes, frontend changes, raw command submission, execution paths, or generation gate changes.

## Validation
- `.venv/Scripts/python.exe -m pytest backend/tests/test_post_production.py backend/tests/test_ffmpeg_service.py` passed: 26 tests.
- New focused tests cover success persistence, error persistence, SHA256 validation, stale output metadata clearing on error, no FFmpeg execution guard, and get/list round-trip.

## Safety Notes
- This checkpoint records metadata only; it never invokes FFmpeg, ComfyUI, GPU rendering, benchmarks, or command submission.
- Existing allowlisted recipe command manifest creation remains path-safe and hash-gated.
- Raw command arrays remain internal persisted provenance and are not exposed through new public endpoints.
