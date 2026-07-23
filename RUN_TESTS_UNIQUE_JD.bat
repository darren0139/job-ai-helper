@echo off
setlocal
python -m unittest tests.test_jd_identity tests.test_jd_dedup_integration tests.test_jd_chroma_identity -v
if errorlevel 1 exit /b 1
python -m py_compile app.py database\jd_library_manager.py rag\jd_identity.py rag\jd_chroma_rag.py scripts\apply_unique_jd_app_patch.py scripts\migrate_jd_identity.py scripts\inspect_jd_identity.py scripts\inspect_chroma_jd_identity.py
if errorlevel 1 exit /b 1
echo.
echo Unique JD targeted tests and compile checks passed.
