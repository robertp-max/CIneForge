# Checkpoint — Runtime UI Shows Read-only M4 Preflight

Generated: 2026-07-15 01:39 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `b4a36cc checkpoint: add read-only M4 preflight gate`

## Scope

Exposed the read-only M4 hardware preflight report in the frontend Runtime page.

Changes:

- Added `LocalM4PreflightReport` and `LocalM4PreflightCheck` API types.
- Added `api.localM4Preflight()` for `GET /local-runtime/m4-preflight`.
- Runtime page now loads the preflight report and displays:
  - blocked/ready status;
  - whether hardware operator probe is allowed;
  - confirmation that the report itself executed no live action;
  - blocking reason codes;
  - individual pass/block checks.

## Validation

```bash
cd frontend
npm run build
# tsc -b && vite build passed
```

## Safety notes

- UI is read-only; no submit button or generation action was added.
- Public `/prompt` remains unavailable.
- No live ComfyUI/GPU/render/benchmark action was run.
