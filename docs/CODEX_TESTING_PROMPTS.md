# Codex testing prompts

## Run and repair the complete suite

```text
Work in this repository only.

Run the complete automated check:
- Windows: run_tests.bat
- Other platforms: python scripts/run_project_checks.py --mode full

When a check fails:
1. inspect the failure and related production code;
2. decide whether it is a real defect or an outdated expectation;
3. make the smallest justified change;
4. run the narrowest affected test;
5. rerun the complete automated check;
6. summarize every changed file and command executed.

Do not weaken assertions just to make the suite pass.
Do not commit or push.
Do not edit .venv, database files, generated outputs, backups, debug
bundles, or secrets.
```

## Quick iteration

```text
Run run_tests_quick.bat. Fix only failures related to the current change.
Then run run_tests.bat before finishing. Do not commit or push.
```

## Review a proposed patch

```text
Review the working-tree diff for correctness, deterministic behavior,
accidental data changes, and test coverage. Run run_tests_quick.bat first,
then run_tests.bat. Do not change files unless a concrete problem is found.
Do not commit or push.
```

## Version-bump failure

```text
A test is failing after a production version constant changed. Determine
whether the test is validating a newly generated result or intentionally
preserving a historical fixture.

For newly generated results, compare against the production version
constant instead of copying a hard-coded version string. Preserve explicit
old-version fixtures when they are testing backward compatibility. Run the
focused test and then run_tests.bat. Do not commit or push.
```
