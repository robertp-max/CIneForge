# Research Traceability

Implementation module to source mapping:

- `backend/app/main.py`, `backend/app/api/*`: `API/BACKEND_API_FLOW.md`, `MVP/MVP_ARCHITECTURE.md`.
- `backend/app/core/config.py`: `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`.
- `backend/app/db/base.py`: `Database/POSTGRES_SCHEMA.sql`, `Database/JSON_SCHEMAS.md`, `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.
- `backend/app/queue/state_machine.py`: `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`, reconciliation docs.
- `backend/app/services/comfy/client.py`: `ComfyUI/HEADLESS_COMFYUI_API.md`, `Runtime/RUNTIME_ISOLATION_AND_QUEUEING.md`.
- `backend/app/services/workflows/template_service.py`: `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`.
- `backend/app/services/telemetry/gpu.py`: `Benchmarks/BENCHMARK_PROTOCOL.md`.
- `backend/app/services/ffmpeg/service.py`: `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md`.
- `backend/app/utils/path_safety.py`: `Risk-Register/RISK_REGISTER.md`, `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`, `FFmpeg/FFMPEG_STRATEGY_COMMAND_LIBRARY.md`.
- `backend/app/services/ai_orchestration/*`: `Orchestration/OPTIONAL_AI_ORCHESTRATION_LAYER.md`.
- `backend/app/services/autonomy/*`: `Orchestration/AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.
- `backend/app/services/policy`, `qa`, `retry`, `batch_planner`: `MVP/MVP_ARCHITECTURE.md`, `OPTIONAL_AI_ORCHESTRATION_LAYER.md`, `AUTONOMOUS_PRODUCTION_ARCHITECTURE.md`.
- `storage/workflow_templates/example_smoke`: `Workflows/WORKFLOW_JSON_MUTATION_STRATEGY.md`.

