# Local Codex JD Extraction POC

This directory is intentionally not imported by the Streamlit application. It
tests the official local Codex Python SDK as a possible future alternative for
only the JD structured-extraction stage.

## Architecture

`extract_job_description_with_codex(jd_text)` returns the existing exact JD
profile dictionary contract. The underlying result function measures the SDK
call, parses the final response as JSON, and rejects output unless every existing field is
present with the correct type and no additional field exists. It does not score
alignment or alter canonical requirements.

The invocation is logically:

```text
from openai_codex import Codex, Sandbox
with Codex() as codex:
    thread = codex.thread_start(sandbox=Sandbox.read_only)
    response = thread.run(extraction_prompt)
```

It sends only the extraction prompt and never requests write access. The SDK
must be installed and authenticated in the local user/runtime context; it
provides a pinned Codex CLI runtime. This package is deliberately not added to
the production requirements.

## Evaluation

From the repository root, run (with the project Python environment):

```text
python scripts/evaluate_codex_jd_extraction.py --repeat 2
```

The script reads a checked-in synthetic JD fixture copied from an existing test
without mutation and runs both the current API extractor and this local Codex
adapter. The available Phase 9C saved-JD fixture has no raw JD text, so it is
not usable for this extraction evaluation. The harness reports
schema validity, requested field-level values/deltas, empty fields, lexically
potentially unsupported values, latency, invocation errors, API metadata, and
determinism fingerprints. Add `--skip-api` only to diagnose the local Codex
runtime without making API calls. Output is stdout unless `--report-out` is
specified.

## Current environment finding (2026-08-14)

The stable official Python SDK is `openai-codex` (Python 3.10+). It could not be
installed or imported here because this worktree has no project virtual
environment or Python launcher. The desktop-installed `codex.exe` also fails
with `Access is denied` when invoked from this shell. A future local evaluation
therefore needs an isolated POC virtual environment and `pip install
openai-codex`; this POC intentionally does not modify production dependencies.
