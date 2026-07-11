# CineForge Test Results

Generated: 2026-07-11

All commands used existing dependencies only. No packages were installed. No application code was modified. No Git commit, push, stash, reset, checkout, clean, or destructive command was run.

## Environment Notes

- Repository: `C:\AI\Git\CIneForge`
- Backend venv used: `.\.venv\Scripts\python.exe`
- Frontend dependencies already existed in `frontend\node_modules`
- Global `CINEFORGE_TEST_POSTGRES_URL` is set to `postgresql+psycopg://cineforge_test:cineforge_test_pw@127.0.0.1:55432/cineforge_test`
- TCP check to `127.0.0.1:55432` failed, so the configured PostgreSQL test endpoint is not reachable from this audit environment.

## Backend Offline Test Suite

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:CINEFORGE_TEST_POSTGRES_URL=$null
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

Result: pass.

Summary:

```text
128 passed, 8 skipped, 116 warnings in 18.68s
```

Notes:

- `CINEFORGE_TEST_POSTGRES_URL` was cleared only inside the command process so PostgreSQL-gated tests would skip instead of hanging.
- Warnings are SQLAlchemy deprecation warnings around `datetime.datetime.utcnow()`.

## PostgreSQL Connectivity Check

Command:

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 55432 | Select-Object ComputerName,RemotePort,TcpTestSucceeded
```

Result: fail.

Summary:

```text
WARNING: TCP connect to (127.0.0.1 : 55432) failed

ComputerName RemotePort TcpTestSucceeded
------------ ---------- ----------------
127.0.0.1         55432            False
```

Impact:

- PostgreSQL-gated tests are currently not runnable unless the local test database is started or the environment variable is cleared.
- Earlier full-suite attempts with the PostgreSQL URL present timed out because the test endpoint was unreachable.

## Frontend TypeScript

Command:

```powershell
.\node_modules\.bin\tsc.cmd -b --noEmit
```

Working directory:

```text
C:\AI\Git\CIneForge\frontend
```

Result: pass.

Output: no errors.

## Frontend ESLint

Command:

```powershell
.\node_modules\.bin\eslint.cmd .
```

Working directory:

```text
C:\AI\Git\CIneForge\frontend
```

Result: fail.

Summary:

```text
5 problems (5 errors, 0 warnings)
```

Exact errors:

```text
C:\AI\Git\CIneForge\frontend\src\api\client.ts
  115:5  error  There is no `cause` attached to the symptom error being thrown  preserve-caught-error

C:\AI\Git\CIneForge\frontend\src\components\Page.tsx
  19:17  error  Fast refresh only works when a file only exports components. Use a new file to share constants or functions between components  react-refresh/only-export-components

C:\AI\Git\CIneForge\frontend\src\pages\Campaigns.tsx
  36:10  error  Calling setState synchronously within an effect can trigger cascading renders  react-hooks/set-state-in-effect

C:\AI\Git\CIneForge\frontend\src\pages\Jobs.tsx
  29:10  error  Calling setState synchronously within an effect can trigger cascading renders  react-hooks/set-state-in-effect

C:\AI\Git\CIneForge\frontend\src\pages\Projects.tsx
  31:10  error  Calling setState synchronously within an effect can trigger cascading renders  react-hooks/set-state-in-effect
```

## Remote Checks

Command:

```powershell
git ls-remote origin HEAD refs/heads/master refs/heads/main
```

Result: pass.

Summary:

```text
5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b  HEAD
5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b  refs/heads/master
```

Command:

```powershell
git ls-remote https://github.com/tj1784/CIneForge.git HEAD refs/heads/master refs/heads/main
```

Result: fail.

Summary:

```text
remote: Repository not found.
fatal: repository 'https://github.com/tj1784/CIneForge.git/' not found
```

## Not Run

- `npm install` was not run.
- `npm run build` was not run because `vite build` writes `frontend/dist`.
- `npm run dev`, backend `uvicorn`, and Vite dev server were not started.
- Live ComfyUI tests were not run.
- Model downloads were not run.
- Real video generation was not run.
- `/history/{prompt_id}` output collection was not run.
- FFmpeg assembly execution was not run.
- GitHub push/commit/branch/checkout/reset/stash/clean commands were not run.

