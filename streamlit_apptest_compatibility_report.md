# Streamlit AppTest compatibility — governed review recovery

## Repository and decision

Worktree: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `fix/streamlit-apptest-compatibility`.
HEAD: `bedaa8ea7946c91c2f7486c2209869fa2dd6cc4f`, unchanged.
Entry status contained only the unrelated untracked `coordinated_batch_dashboard_review.md`.

**Test compatibility defect confirmed; production recovery logic is unchanged.** The fix uses installed AppTest public mapping methods. All 104 focused tests passed. Ready for an isolated checkpoint; full CI was not rerun and remains unverified beyond these checks.

## Exact root cause and runtime observations

Supported interpreter: `venv/evidence-completeness-runtime/environment/Scripts/python.exe`, CPython 3.13.12. Installed Streamlit: **1.66.0**. The project requirement is unpinned `streamlit`; no dependency was installed, upgraded or changed.

The installed `streamlit/testing/v1/app_test.py` exposes `_AppTestSessionState` through `app.session_state`. Its public `keys()`, `items()`, `values()`, `get()`, `to_dict()`, iteration and keyed access expose user state. Its `__getattr__` treats an unknown attribute as a user-state key. Therefore:

```python
app.session_state.filtered_state
```

attempts to retrieve the user key `"filtered_state"`. That key does not exist, producing a KeyError which AppTest converts to:

```text
AttributeError: filtered_state not found in session_state.
```

`filtered_state` is an underlying framework property, not a public property of this AppTest wrapper. Reaching into `_state` is unnecessary. The installed package's bundled Streamlit skill/testing reference and actual runtime source were inspected; no API behavior was guessed or inferred from an unrelated environment.

The contained runtime observation (`api_observation.log`) ran the real static harness and real disposable review store. It found the actual existing key `unresolved_review_32106c5b0500512a_packet`, containing `action_context`, `approval`, `context`, `governed_regression`, `readiness`, `recovery`, `recovery_key` and `saved_governed`. Recovery status was `ready`, readiness was true, and public state inspection left the snapshot unchanged. The observed key is diagnostic evidence, not a constant added to tests.

Failure timing before correction:

- Reopen/code reload test: the page has already shown the legitimate recovered approval, but original line 73 fails before the draft/regression fingerprint, blocker and final unchanged-bytes assertions.
- Legacy session test: original line 167 fails immediately after the first page run, before removing the recovery key, rejecting the stored review and asserting that stale session approval is untrusted.

Thus the errors do not mean the packet, approval or recovery key is missing. They prevent the important later assertions from executing.

## Minimal test-only correction

| File | Changes |
| --- | --- |
| `tests/test_governed_review_recovery_v1_2_1.py` | Use `reopened.session_state.items()` and `app.session_state.keys()` in the two original tests; add `test_public_packet_inspection_is_read_only_and_reruns_do_not_approve`. |
| `tests/test_unresolved_requirement_review_ui.py` | Replace the same unsupported access with `.keys()` in `test_changed_draft_receipt_invalidates_approval_readiness`. |
| `streamlit_apptest_compatibility_report.md` | This report. |

The neighboring test independently reproduced the identical exception before editing: 13 tests, 12 passed and one error. Correcting that one access is part of this same API compatibility defect, not a production refactor or a network/Ollama fix.

No existing project state-inspection helper was found that was needed here. Public enumeration retains the original `_packet` suffix selection without duplicating the controller's dynamic identity/provenance hash or introducing a fabricated key. The code then reads the selected existing key directly. No private API, fallback shim, exception suppression or production compatibility layer was added. This validates the installed 1.66.0 API; it does not promise compatibility with every historical Streamlit version.

Every original assertion remains. The real controller, read-only recovery path, SQLite approval receipts, source identities and fingerprint checks still execute. The original intentional invalid-packet injections remain unchanged. The new test does not inject an approval: it recovers the existing legitimate fixture approval, asserts exactly one packet, reads it through public mapping methods, compares state before/after inspection, and reruns twice while checking unchanged approval/database/taxonomy bytes. Existing forbidden-writer controls remain active; the real `recover` function is not replaced.

## Security and recovery controls exercised

- Legitimate approval survives a new AppTest session and UI module reload, with exact draft/regression fingerprints and no publication blockers.
- Legacy session approval lacking its recovery key cannot override a persisted rejection.
- Wrong job, snapshot, source hash or requirement identity cannot reuse the receipt; changed source text is stale.
- A different draft, stale taxonomy/knowledge, missing approval, missing store and incomplete/unvalidated draft remain non-actionable.
- Store changes invalidate cached approval on rerun. Repeated rendering does not approve, publish or replay validation.
- SQL authorizer rejects writes during recovery; readonly connection mode and unchanged synthetic database/taxonomy bytes are asserted.
- The neighboring draft-tampering test again reaches its original assertions rejecting readiness and publication after a mismatched draft receipt.
- Isolated preview UI, Phase 8 reconciliation/canonical identities, browser authentication/loopback restrictions and résumé overflow containment passed their existing checks.

## Test commands and results

All behavioral tests used the unchanged launcher and disposable scratch contract. Common prefix:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/apptest_compat_runtime
```

Original pair, selected by full test names:

```text
tests.test_governed_review_recovery_v1_2_1.RecoveryTests.test_legacy_session_approval_without_recovery_key_is_not_trusted
tests.test_governed_review_recovery_v1_2_1.RecoveryTests.test_reopen_and_code_reload_recovers_exact_real_approval_without_writes
```

| Run | Result | Unittest runtime |
| --- | --- | ---: |
| Original pair before correction | 2 errors / 2 tests | 17.437 s |
| Actual API/packet observation | 1 passed / 1 test | 8.185 s |
| Neighboring review UI before correction | 12 passed, 1 error / 13 tests | 70.851 s |
| Original pair after correction | 2 passed / 2 tests | 6.579 s |
| Legacy test alone, fresh guarded process | 1 passed / 1 test | 5.277 s |
| Reopen test alone, fresh guarded process | 1 passed / 1 test | 6.839 s |
| Combined focused regressions | **104 passed / 104 tests**, no failures/errors/skips | **142.858 s** |

The individual process runs used the common prefix followed by one original full test name each. The combined focused command was:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/apptest_compat_runtime tests.test_governed_review_recovery_v1_2_1 tests.test_unresolved_requirement_review_ui tests.test_governed_requirement_activation_v1_1 tests.test_governed_review_post_publication_v1_2_2 tests.test_governed_requirement_resolution tests.test_phase8_requirement_reconciliation tests.test_phase8_verification tests.test_phase8_canonical_guard tests.test_coordinated_job_match_preview_ui tests.test_browser_bridge_runtime tests.test_offline_loopback_security tests.test_all_canonical_sequence_regressions_v1
```

Coverage by group: recovery/review UI **26**; activation/publication/resolution **28**; Phase 8 **24**; isolated preview UI **5**; browser/loopback security **7**; canonical résumé sequence/containment **14**. These total 104 distinct tests; the separate pair/process runs repeat tests from that set. Source files were held stable throughout post-fix validation.

Evidence is retained locally under ignored `reports/apptest_compat_runtime/`: `before.log`, `api_observation.log`, `neighbor_before.log`, `original_after.log`, `legacy_independent.log`, `reopen_independent.log`, `focused.log` and `integrity.json`. The disposable observation script is not imported by committed tests and is not a test dependency.

## Integrity, compatibility and local runtime note

The entry SHA-256 ledger covers **984 tracked files plus the existing dashboard report**. Final comparison: **983 unchanged and exactly the two intended test files changed**. The requested report is new. Production recovery/controller code, offline guards, loopback infrastructure, historical fixtures, taxonomy/registry and all scorer/version files match entry bytes. Published v1.17, coordinated v1.20/v1.21 and metadata v1.22/v1.23 remain unchanged. No application route, Job Finder, Application Session, database/cache contract, résumé implementation or experimental gate was modified.

Changed Python syntax checks passed; focused imports and execution passed. `git diff --check` and `git diff --cached --check` passed; staged diff is empty. Branch and HEAD remain as recorded above. The unrelated dashboard report remains byte-for-byte unchanged. No live candidate or production-database access, model/embedding calls, Ollama/Tavily requests or external service calls were performed. Browser checks use the existing explicitly scoped synthetic local HTTP fixture. All actual AppTest executions and the successful runtime observation used the original contained launcher.

A preliminary uncontained API-import attempt failed while naming a nonexistent exported wrapper class. Importing AppTest had created its framework-global empty temporary directory at `C:\Users\Admin\AppData\Local\Temp\tmp5deg_6ny`; Windows denied its automatic cleanup and a later verified, nonrecursive removal attempt. No ACL change, recursive cleanup or escalation was attempted. This local empty framework-temp residue is not a test dependency or production artifact. Subsequent inspection was moved into the contained probe; all validation output and disposable fixtures are under task scratch. Launcher scratch/logs are retained for review and remain ignored; no user artifact was deleted or uploaded.

## Remaining full-CI blockers and verdicts

Full CI was **NOT RERUN**, as explicitly requested for this bounded fix. The previous run's separate six network-fixture errors and 35 Ollama diagnostic prerequisite errors remain outside scope. Their current full-suite counts are not remeasured here; focused success does not establish a green full suite. No missing diagnostic document, frozen expected hash or unrelated network permission was changed.

| Decision | Verdict |
| --- | --- |
| Original two tests | **PASS** |
| Recovery security behavior preserved | **PASS** |
| Related AppTest tests | **PASS**, within 104/104 focused regressions |
| Production behavior unchanged | **PASS** |
| Ready for isolated checkpoint | **YES**, the two test files and this report |
| Full CI | **NOT RERUN**; unrelated blocker groups remain |

Nothing was staged, committed, pushed, merged or switched. Stop for review.
