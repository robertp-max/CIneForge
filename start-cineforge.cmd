@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo CineForge virtual environment is missing: %CD%\.venv
  echo Create it and install dependencies before starting CineForge.
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\start_cineforge.py" %*
