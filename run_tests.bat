@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv\Scripts\python.exe was not found.
    echo Create or restore the local virtual environment first.
    exit /b 1
)

".venv\Scripts\python.exe" scripts\run_project_checks.py --mode full
exit /b %ERRORLEVEL%
