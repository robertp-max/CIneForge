# Checkpoint — Runtime UI Shows Read-only FFmpeg Recipes

Generated: 2026-07-15 08:19 local
Working directory: `C:/AI/Git/CIneForge`
Base commit before this checkpoint: `a09d780 checkpoint: add read-only FFmpeg recipe catalog`

## Scope

Displayed the read-only FFmpeg recipe catalog on the frontend Runtime page.

Changes:

- Added frontend type `FFmpegCommandTemplateRecord`.
- Added `api.listFFmpegRecipes()` for `GET /local-runtime/ffmpeg-recipes`.
- Runtime page now displays allowlisted recipe metadata and explicitly shows that catalog entries do not execute FFmpeg.

## Validation

```bash
cd frontend
npm run build
# tsc -b && vite build passed
```

## Safety notes

- UI is read-only; no FFmpeg execution controls were added.
- No raw command input was added.
- No FFmpeg command was executed.
- No live ComfyUI/GPU/render/benchmark action was run.
