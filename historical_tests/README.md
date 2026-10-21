# Ollama / adjudication validation lanes

Ordinary CI validates the **current source**. It does not reproduce historical
Ollama experiments. The normal full runner still compiles the project, runs all
configured zero-cost smoke checks and discovers the complete `tests/` tree:

```powershell
python scripts/run_project_checks.py --mode full --ci
```

The existing contained equivalent is:

```powershell
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_ci_isolation_full --full-project
```

No test exclusion list, unconditional skip, expected failure, environment-based
waiver or reduced full-project suite is installed. Current Ollama/adjudication
tests use `tests/ollama_current_fixtures.py` to construct disposable unit inputs.
The real freeze, selection, byte-hash, source, preparation and review validators
still execute. Synthetic prior-label controls are not independent human gold.
Existing historical source/expectation files are never updated by these helpers.

## Historical lane: prerequisite inspection, currently BLOCKED

List all retained original assertions under a separate historical namespace:

```powershell
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_ci_isolation --historical-ollama --list-historical
```

Check historical prerequisites without importing current or historical scorers:

```powershell
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_ci_isolation --historical-ollama
```

Inventory exits 0 with `INVENTORY_ONLY_NOT_REPRODUCTION`. Prerequisite inspection
exits 2 with `BLOCKED`, `attempted=false`, `validated=false`, and zero executed
historical tests. It reports missing artifacts and exact-byte mismatches. It
cannot infer that a matching source collection is a dependency-pinned runtime.
No inference, provider initialization, source restoration or artifact regeneration
is performed. `python -m scripts.run_ollama_historical_checks` is the underlying
read-only command; `--bundle-root` is available for prerequisite inspection only.

An approved historical execution recipe does **not** exist in this checkpoint.
Even supplying matching files cannot unlock execution through a switch. A future
review must establish the original per-plan source envelope, dependencies and
platform/encoding identities, reviewed artifact provenance/privacy and an offline
execution recipe. No old labels may be reapproved from current code. The original
independent-human gate remains separate from authored synthetic expectations.

## Assertion inventory and maintenance

`tests/fixtures/ollama_test_lanes_v1.json` registers:

- Current behavioral test modules (also covered by ordinary unittest discovery).
- Every archived original assertion and its exact source-byte hash.
- Each current behavioral counterpart, with the historical/current boundary.
- Historical-only assertions for actual original readiness and the original
  139-file / 34-verified / 4-partial source-recovery observation.
- Original artifact-byte pins and historical experiment identity metadata.

Files under `historical_tests/ollama/` are **data-only assertion source archives**
from Git revision `41b024d790013ec7120045744f1fb2b662ff1b81`. They are not an
approved historical runtime, nor permission to run old tests against current
imports. Original assertions are preserved, including those now given current
unit counterparts. Do not run archive files directly and label the result a
historical reproduction. Their `.gitattributes` rule preserves exact Git-blob
bytes on Windows and Unix; historical hash checks never normalize CRLF.

`scripts.check_ollama_test_lanes` is a registered normal-CI smoke check.
`tests.test_ollama_test_lanes` verifies source hashes, registration completeness,
unittest loading, real validator acceptance/rejection, byte/CRLF integrity,
missing prerequisites, distinct lane identities, no ignored-file dependency,
unchanged original gold, and direct unittest invocation under containment.

New archive files or methods must be explicitly reviewed and registered with a
current counterpart or a documented historical-only reason. Do not regenerate
archive hashes or frozen expectations merely to obtain a passing inventory.
Current-source PASS and historical reproduction PASS are different claims.
