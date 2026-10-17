# Stage 2–2C checkpoint readiness

No commit or push is authorized or performed. This is a research checkpoint, not
approval to implement coordinated-action production parsing/scoring.

This document supersedes the earlier reports' dependency on local preview JSON and
private launchers. Earlier Stage 2/2B/2C findings remain preserved as historical research.

## Repository and scope

Repository: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch: `feat/bulk-unresolved-resolution-v1`. HEAD:
`5756d5f840dd09e3c0c48c6fcfc9298246a8790b`.

Entry status contained one modified tracked file (`source_aware_inventory.py`, the
existing two-line security integration), fifteen untracked Stage 2–2C files and no
staged changes. All existing content was preserved. Only five entry-state files are
intentionally different at checkpoint completion: `.gitignore`, the Stage 2B and 2C
research scripts, and their two test modules. No production scoring/parser/matching,
taxonomy, registry, historical fixture, original report or original diagnostic changed.

## Exact recommended staging list

Stage these **17 exact paths**, relative to the verified repository root. Do not
stage directories wholesale or use `git add .`. This list is a recommendation;
the resolver's index remains untouched.

```text
.gitignore
taxonomy_discovery/source_aware_inventory.py
taxonomy_discovery/source_inventory_safety.py
taxonomy_discovery/coordinated_ownership_preview.py
scripts/preview_coordinated_actions_v1.py
scripts/preview_coordinated_evidence_v1.py
scripts/preview_coordinated_ownership_v1.py
scripts/run_coordinated_preview_checks.py
tests/test_source_inventory_export_safety.py
tests/test_coordinated_action_preview.py
tests/test_coordinated_evidence_preview.py
tests/test_coordinated_ownership_preview.py
tests/fixtures/coordinated_action_ownership_oracle_v1.json
bulk_unresolved_stage2_review.md
bulk_unresolved_stage2b_review.md
bulk_unresolved_stage2c_review.md
bulk_unresolved_stage2_2c_checkpoint_review.md
```

| Classification | Exact files / rationale |
|---|---|
| Safe source and tests | Three `taxonomy_discovery` files, four `scripts` files and four `tests/test_...` files above. Includes existing export security integration and research-only detectors/wrappers; no new production-policy import. |
| Safe test/config metadata | `.gitignore` and the compact independent synthetic oracle fixture. |
| Reviewable Markdown | The four root Markdown reports above. Earlier reports remain byte-identical, including their historical runtime commands and local-only JSON references. This checkpoint report supplies the portable replacement instructions. |
| Large diagnostic JSON | The three exact excluded files below; reviewed locally, preserved, not staging candidates. |
| Disposable runtime output | All ignored environments, logs, ledgers, materialized trees, local test clone, scratch and synthetic SQLite data. |
| Unexpected/unrelated changes | No new unrelated tracked/untracked changes. Pre-existing duplicate/malformed Stage 0 ignore entries were observed and left unchanged; the new rules do not rely on them. |

## Exact excluded files and ignore rules

These files remain byte-identical, local and untracked:

```text
bulk_unresolved_stage2_preview.json
bulk_unresolved_stage2b_preview.json
bulk_unresolved_stage2c_preview.json
```

The following exact anchored rules were added to `.gitignore` and confirmed using
`git check-ignore -v`:

```gitignore
/bulk_unresolved_stage2_preview.json
/bulk_unresolved_stage2b_preview.json
/bulk_unresolved_stage2c_preview.json
```

Other excluded local files/groups include `.env`, `.venv/`, `venv/`,
`bulk_unresolved_v1_inventory.json`, `bulk_unresolved_v1_preview.json`,
`data/blueprint_artifacts/`, `outputs/` (including résumé previews), `reports/`,
`__pycache__/`, `*.pyc`, database files and existing backup patterns. Existing tracked
placeholders/exceptions are unaffected. No ignored file is in the recommended list.

The ignored-path inventory has 84 Git-reported directory/file entries, with directory
collapsing. Metadata was inspected without loading secrets or generated résumés.
Some older Windows temporary directories deny enumeration; their contents remain
uninspected and excluded, not repaired or deleted. No claim is made that inaccessible
runtime artifacts were content-reviewed. This does not admit them to the checkpoint.
The complete observed ignored-path listing is local in the checkpoint scratch folder.

### Diagnostic privacy review

| Local diagnostic | Bytes | Recursive strings scanned | SHA-256 |
|---|---:|---:|---|
| Stage 2 | 297,202 | 2,141 | `53f30b8f8bc7813f0256c24b273403d9c212552946333a655a95c6d6efb49ee9` |
| Stage 2B | 1,496,078 | 16,015 | `3a53758cece37927cb3c4111af1ed91953f7db0083c16d611f455e6c79e34c22` |
| Stage 2C | 9,607,499 | 88,714 | `301562778078dc65d33b8eae2990f7965d05cbb48ba5de441b922a7bf4999990` |

Review covered complete parsed structures, source types, repeated evidence fields and
all string values for email, credential assignment, private-key, token and absolute
user-path patterns. No hits were found for those patterns; there are no `resume_profile`
or `raw_resume_text` keys. Stage 2B/2C nevertheless contain extensive synthetic selected
evidence, action receipts and repository-wide protection ledgers (913/917 entries).
Stage 2 contains raw-JD source/recognition receipts and 808 protected hashes.

The evidence inputs trace to public-JD extracts already in tracked fixtures and explicitly
hypothetical statements, not a supplied actual résumé. Pattern scanning is not a general
guarantee that an export is suitable for publication. All three are excluded because
they are large local diagnostics and future runs could contain sensitive source material.
None was uploaded, deleted, rewritten or copied into the portable checkout.

## Small offline portability changes

1. Added `tests/fixtures/coordinated_action_ownership_oracle_v1.json` (29,494 bytes).
   It freezes the **76 original synthetic scenarios**, five original JD parent identities,
   exact evidence strings and independently declared action expectations from the reviewed
   Stage 2B packet. It contains no selected native results, real candidate profile or local
   protection ledger. The action-oracle content remained unchanged during normalization;
   its canonical SHA-256 is
   `d0b705c6cad99db7a1db05b744b6684d5c9f0ce7335487ee7fe971173e8a19f3`.
2. Stage 2B's research helper regenerates JD rows/weights/provenance from the tracked
   30-job raw fixture and checks the frozen source identity. Stage 2C consumes this compact
   independent oracle rather than a root diagnostic JSON. Expected actions never become
   detector/selector inputs; the deliberately-wrong-oracle regression remains intact.
3. Replaced whole-diagnostic-file test comparisons with **frozen full-result semantic
   digests calculated from the pre-change reviewed JSON**, not from new implementation
   outputs. Every native decision, requirement/source/evidence ID, weight, offset, receipt,
   confusion result and version identity remains covered. The only omitted fields are
   local protection ledgers, oracle-storage identity and filesystem artifact hashes.
   Oracle identity is checked separately against its committed fixture.
4. Raw artifact hashes vary with `core.autocrlf`. Seven independent frozen production
   source hashes now normalize CRLF to LF; unexpected source changes still fail. Runtime
   artifact-hash metadata must also match the current checkout's native knowledge identity.
   Versions remain inside the full-result digest. This separates newline configuration
   from scoring semantics without accepting new scoring results.
5. The disposable snapshot test no longer requires `EVIDENCE_TEST_SCRATCH`. It uses the
   standard library's temporary path when absent, verifies its UUID path is new and removes
   only its own synthetic DB file. Source/snapshot/currentness assertions remain unchanged.
6. Added the cross-platform, test-only `scripts/run_coordinated_preview_checks.py` entry
   point. It configures offline imports before project code, disables dotenv/retrieval/
   remote cost metadata, rejects all network access and non-disposable SQLite, blocks reads
   of `.env` and the three root diagnostics, disables bytecode and verifies that project
   imports resolve inside the tested checkout. It never calls a full/quick runner.

Frozen full-result semantic digests:

```text
Stage 2B  52069681c83b8e6474d968c311b5e732baa5c74efc8b37f753cbd15adbd58574
Stage 2C  62be52c5eaa806847528980b2b85fb75e393a720ed0b80b2d2c98e051e3472b8
```

These are not automatically refreshed by tests. A future deliberate behavior change
requires reviewing/updating the independent baseline; merely recomputing outputs cannot
make a failing test pass. No assertion or oracle action label was weakened.

## Fresh-checkout verification and dependencies

Portable focused command, after the normal Python 3.13 repository dependencies exist:

```text
python -B scripts/run_coordinated_preview_checks.py
```

No PowerShell launcher, ignored `sitecustomize.py`, local preview JSON, private ledger,
`.env`, model service or `EVIDENCE_TEST_SCRATCH` is required. `--scratch-root PATH` is an
optional caller-selected output location. Old report commands referencing
`venv/evidence-completeness-runtime/...ps1` are historical local launchers, not portable
dependencies. The old preview export CLIs still require a caller-supplied protection
ledger; focused tests regenerate in memory and do not require those CLI exports.

The initial file-only materialization contained 922 tracked/proposed files and excluded
all diagnostic JSON, `.env`, virtual environments and runtime outputs. It ran 118 tests:
117 passed, one source-export test correctly rejected the absence of Git tracking metadata.
The test was not skipped or weakened. A subsequent local clone supplies normal Git
metadata, with the same exact proposed overlay and LF files (892 CRLF files normalized).
The original repository's branch, HEAD and index remain untouched.

Windows sandbox signal-pipe restrictions blocked two local clone attempts before they
could run Git's local transport. A narrow owner-context local-only clone succeeded; no
remote/network clone, commit, push or checkout/reset of the resolver was performed.
The disposable clone index was populated from its existing HEAD solely for source-tracking
checks. No `git add` was used, including in the disposable clone.

Validation uses Python 3.13.12 with installed `litellm` 1.105.1, `python-dotenv` 1.2.4,
`jsonschema` 4.26.0, `streamlit` 1.66.0, `pandas` 3.0.6 and `chromadb` 1.5.9. No dependency
was missing in that environment. `jsonschema` is transitively declared by both litellm
and chromadb in the existing requirements; no requirements changes were necessary.
Git is required by the existing tracked-fixture check. A fresh dependency installation
and Linux/macOS execution were not attempted: no network/install was authorized. The
test is a fresh **source/Git checkout** using an already provisioned interpreter, with
LF checkout semantics on Windows; it is not a claim of cross-OS CI execution.

## Validation and protected versions

**PASS: all 118 focused tests passed in the LF Git clone in 154.550 seconds.**
The first narrow portability selection also passed all 11 tests, including independent
full-result comparisons (overlapping cases, not an additional unique count). No complete
or quick suite was run. The full LF run retained the Stage 2B/2C oracle, scoring-safety,
source/export-security, decomposition, API, DSA, historical synthetic snapshot and
currentness assertions. There are no remaining focused failures.

Executed portable commands (the installed interpreter's absolute path was used at
execution, not a dependency encoded in source):

```text
python -B scripts/run_coordinated_preview_checks.py --scratch-root LOCAL_SCRATCH tests.test_coordinated_ownership_preview.TextOwnershipUnitTests tests.test_coordinated_ownership_preview.OwnershipIntegrationPreviewTests.test_full_preview_matches_frozen_reviewed_baseline tests.test_coordinated_evidence_preview.CoordinatedEvidencePreviewTests.test_full_preview_matches_frozen_reviewed_baseline
python -B scripts/run_coordinated_preview_checks.py --scratch-root LOCAL_SCRATCH
git diff --check
git diff --cached --check
git check-ignore -v bulk_unresolved_stage2_preview.json bulk_unresolved_stage2b_preview.json bulk_unresolved_stage2c_preview.json
```

The full run is from the disposable Git clone. `PYTHONPATH` and `EVIDENCE_TEST_SCRATCH`
were explicitly absent. The 118 tests are exactly the ten modules in the tracked
runner's `FOCUSED_MODULES`. No original-checkout project module imports were detected.
Logs are `portable_small.log`, `fresh_tests.log` (the intentionally file-only experiment
with its Git metadata error), and `fresh_lf_git_tests.log` (118 passed).

Both Git whitespace checks pass. Untracked proposed files are checked with
`git diff --no-index --check -- NUL FILE` without staging; ordinary difference exit
status for a new file is not a whitespace error.

All 922 entry-state files were hashed. Exactly five authorized portability/configuration
edits differ, as listed above; all other entry files, all three diagnostic exports, all
original reports and the existing security integration are byte-identical. Protected
scoring/parser sources, seven LF-normalized source pins, published taxonomy/registry
and historical fixtures are unchanged. Production identities remain:

```text
stable-evidence-v1.17-phase6d21
jd-atomic-requirement-decomposition-v1.1
phase6d-capability-taxonomy-v1.6
technology-registry-v1.3
api-evidence-completeness-v1.1
```

Local evidence is under ignored
`venv/evidence-completeness-runtime/tmp/checkpoint_stage2_2c/`: entry ledger,
artifact review, ignored-path inventory, clone/materialization manifests and test logs.
These files and disposable clones are not proposed staging candidates. No live DB,
actual résumé, published snapshot or saved Job Match was touched.

## Proposed commit message and decision

```text
test: checkpoint Stage 2-2C research with portable offline checks
```

**PASS for the exact file-scoped research checkpoint's commit/push content readiness.**
The three large diagnostics must remain excluded. Readiness is separate from
authorization: no commit or push is authorized or performed. Remote credentials,
branch protection and operational pushability are unverified, because no remote
operation was requested. This audit's PASS covers content, privacy and offline
reproducibility, not a guarantee that a future remote push will be accepted.
Production Option A implementation remains **BLOCKED** under the preserved Stage 2C
recommendation. Stop for review.
