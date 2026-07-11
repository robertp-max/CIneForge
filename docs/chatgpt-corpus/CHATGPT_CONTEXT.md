# ChatGPT Context

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

CineForge is a local deterministic AI video orchestration platform for a single 24GB RTX 5090 laptop GPU. It wraps an external ComfyUI runtime, owns queue state in the backend database, stores workflow/provenance data, and keeps AI/autonomy advisory unless explicitly approved through deterministic services.

Current source commit `5ae274d` implements: FastAPI backend, DB-backed project/campaign/job reads, SQLAlchemy/Alembic schema, queue claim with PostgreSQL `SKIP LOCKED`, reserved-job heartbeat/recovery, bounded worker skeleton, submission readiness/preflight, controlled worker-only ComfyUI prompt submission through an injected adapter, and a React/Vite MVP dashboard. Public generation remains disabled.

Safety boundaries: no public `/prompt`; no UI Generate button; no direct ComfyUI mutation through generic client; no live WebSocket loop; no output collection; no FFmpeg assembly execution; no model downloads; no autonomy execution; one GPU worker only.

Important paths: `backend/app/services/queue/service.py`, `backend/app/services/queue/worker.py`, `backend/app/services/comfy/submission.py`, `backend/app/services/comfy/client.py`, `backend/app/services/workflows/template_service.py`, `backend/app/db/base.py`, `frontend/src/api/client.ts`, `frontend/src/pages/Runtime.tsx`, `docs/SPRINT_1C_PLAN.md`, `docs/UI_MVP_STATUS.md`.

Active blockers from corpus refresh: PostgreSQL test DB at `127.0.0.1:55432` unreachable; frontend dependencies not installed, so build/lint unverified.

Run backend: `C:\AI\Git\CIneForge\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`. Run backend tests: `C:\AI\Git\CIneForge\.venv\Scripts\python -m pytest`. Run frontend after user installs deps: `cd frontend; npm run dev`; build/lint: `npm run build`, `npm run lint`.

Canonical next step: implement progress persistence and history/output collection planning behind the worker/runtime boundary, without public generation or ComfyUI runtime mutation.
