@echo off
setlocal

set "BUNDLE=%~1"
if "%BUNDLE%"=="" set "BUNDLE=test_inputs\phase6b_debug_bundle.json"

if not exist "%BUNDLE%" (
  echo Debug bundle not found: %BUNDLE%
  echo Usage: scripts\run_tailoring_trial.bat "C:\path\to\debug_bundle.json"
  exit /b 1
)

if "%RUNS%"=="" set "RUNS=3"
if "%MAX_PROJECTS%"=="" set "MAX_PROJECTS=3"
if "%MAX_BULLETS%"=="" set "MAX_BULLETS=3"
if "%ANALYSIS_MODEL%"=="" set "ANALYSIS_MODEL=openai/gpt-5.6-terra"
if "%REASONING_EFFORT%"=="" set "REASONING_EFFORT=low"

python -m scripts.run_tailoring_stability_trial ^
  --debug-bundle "%BUNDLE%" ^
  --runs %RUNS% ^
  --max-projects %MAX_PROJECTS% ^
  --max-bullets %MAX_BULLETS% ^
  --analysis-model "%ANALYSIS_MODEL%" ^
  --reasoning-effort %REASONING_EFFORT% ^
  --strict

exit /b %ERRORLEVEL%
