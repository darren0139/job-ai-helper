# AGENTS.md

## Repository

This is the Job AI Helper Streamlit repository. Python 3.13 is the
supported development and CI version.

## Test commands

On Windows, use:

```bat
run_tests_quick
```

while iterating, and:

```bat
run_tests
```

before declaring work complete.

On Linux, macOS, WSL, or GitHub Actions, use:

```bash
python scripts/run_project_checks.py --mode quick
python scripts/run_project_checks.py --mode full
```

The runner compiles repository Python files, executes configured zero-cost
smoke checks, and runs focused or complete unittest suites.

## Required engineering behavior

- Diagnose whether a failure is a production defect or an outdated test.
- Do not weaken assertions merely to obtain a green test result.
- Prefer production version constants over duplicated hard-coded version
  strings in tests.
- Run the smallest relevant test first, then the full runner.
- Keep deterministic scoring and candidate fingerprint behavior stable
  unless the task explicitly changes their versions.
- Do not make model or embedding calls during unit/smoke tests.
- Do not commit or push unless the user explicitly requests it.
- Summarize every modified file and the test commands executed.

## Files and data that must not be edited

Do not modify or commit:

- `.venv/`
- `__pycache__/`
- `*.bak.*`
- local SQLite/database files
- generated résumé outputs
- downloaded debug bundles
- temporary Streamlit output
- secret or `.env` files

## Current workflow

GitHub Actions runs the full cross-platform Python runner on Ubuntu and
Windows, followed by the existing Streamlit startup health check.
