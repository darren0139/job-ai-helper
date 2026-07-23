@echo off
setlocal

python -m unittest ^
  tests.test_evidence_aware_fitting ^
  tests.test_evidence_aware_fitter_integration ^
  tests.test_phase6c_patch ^
  -v

if errorlevel 1 (
  echo.
  echo Phase 6C tests FAILED.
  exit /b 1
)

echo.
echo Phase 6C tests PASSED.
exit /b 0
