# CineForge Frontend

React + Vite + TypeScript control dashboard for the local CineForge FastAPI backend.

## Run

```powershell
npm install
npm run dev
```

The app defaults to `http://127.0.0.1:8000` for backend API calls. Override with:

```powershell
$env:VITE_CINEFORGE_API_BASE_URL="http://127.0.0.1:8000"
```

## Build

```powershell
npm run build
```

## Scope

This UI shows live backend health, backend root status, DB-backed project and campaign creation, read-only job status, queue/runtime readiness, and explicit disabled-state messaging for generation. Controlled prompt submission is backend worker/runtime-only; the UI does not expose public generation, open WebSockets, collect outputs, run FFmpeg, download models, or execute autonomous production behavior.
