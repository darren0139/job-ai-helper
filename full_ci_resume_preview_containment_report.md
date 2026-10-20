# Full-CI résumé preview containment report

## Scope and repository

Worktree: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `fix/full-ci-resume-preview-containment`.
Entry HEAD: `299c09dd1084a6fc67724b5244e46dbe77c8d322`.
Entry status contained only the unrelated, untracked `coordinated_batch_dashboard_review.md`.
No staging, commits, pushes, branch changes, production changes or live-data operations were performed.

## Reproduced cause

The original blocked test failed under the unchanged offline release guard: one test, one error, 0.099 seconds.
Its full traceback is retained in `reports/full_ci_resume_preview_runtime/reproduce.log`.

Call chain before correction:

1. `AllCanonicalFitHandoffTests._run_fitter` creates synthetic source, candidate DOCX and PDF files in `TemporaryDirectory`.
2. The actual `generate_tailored_resume_copy_fit_one_page` receives the full 16-bullet payload. Existing test doubles report two pages for that full render.
3. The actual fitter calls `_snapshot_before_fitting_pdf` at production line 4556 before reduction.
4. The snapshot helper uses module-global `PREVIEW_DIR`, initialized at line 98 to `Path("outputs/resume_previews")`. This helper has no environment-variable or output-directory argument override; the test had not patched this dependency.
5. `_snapshot_before_fitting_pdf`, line 850, calls `PREVIEW_DIR.mkdir`. The relative path resolves beneath the checkout, outside disposable scratch.
6. `scripts/offline_release_guard.py`, line 41, raises:

```text
RuntimeError: Offline checks prohibit filesystem mutation outside disposable scratch: outputs\resume_previews
```

The synthetic candidate files were isolated, but their preserved overflow snapshot was not. This is a test-fixture isolation defect. The production output default is intentional and remains unchanged. The active PDF converter also uses the same global directory, including its LibreOffice profiles; changing only the candidate PDF filename would leave that alias unisolated.

## Test-only correction

Each affected fixture now patches the correct production module's `PREVIEW_DIR` to its existing temporary root's `previews` subdirectory. The original launcher makes `TemporaryDirectory` use disposable scratch. Scoped `unittest.mock.patch` restores configuration, including on exceptions; the enclosing temporary-directory context cleans artifacts.

No snapshot helper, fitting/reduction algorithm, production renderer, guard, runner, default output path, historical oracle or expected scoring label was changed. The original overflow assertions remain intact: the first render is full, has 16 bullets and two pages, and reduction appears only in later attempts.

Changed files:

| File | Change |
| --- | --- |
| `tests/test_all_canonical_sequence_regressions_v1.py` | Scope preview output in the canonical fitter fixture; verify the actual snapshot bytes/path and cleanup; add three independent isolation controls. |
| `tests/test_fitting_input_snapshot.py` | Scope preview output for the non-one-page result fixture. |
| `tests/test_phase6c_bounded_fitting.py` | Scope preview output in the bounded-fitting fixture and mocked LibreOffice timeout test. |
| `full_ci_resume_preview_containment_report.md` | This report. |

The two related modules were run before correction: 16 tests, seven errors, 1.117 seconds. All seven traceback paths reached the same global directory (six overflow snapshot failures and one converter mkdir failure). Evidence: `related_before.log`. Other tests were left unchanged.

## Independent controls

- The original real fitter now verifies the copied snapshot exists within its disposable root and contains the synthetic PDF bytes; the root is absent after cleanup.
- `test_real_snapshots_are_unique_contained_and_cleaned_after_success` calls the real snapshot helper twice in each of two independent temporary roots. All four copies have distinct paths and original bytes; configuration restores and all files/roots disappear.
- `test_preview_configuration_and_files_restore_after_exception` creates a real snapshot, raises an explicit synthetic failure, and verifies both restoration and cleanup.
- `test_guard_rejects_unexpected_write_without_redirecting_it` attempts a unique unauthorized checkout write while preview output is scoped. The original guard raises its specific RuntimeError; neither the outside file nor a redirected file is created. This control runs under the containment launcher and is explicitly skipped when that launcher is absent.

All three controls passed under both focused execution and full discovery. No unauthorized production output write was admitted.

## Validation commands and focused results

Interpreter: `venv/evidence-completeness-runtime/environment/Scripts/python.exe`, CPython **3.13.12**, Windows x64, `-B`.
All test commands use the existing containment launcher:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/full_ci_resume_preview_runtime tests.test_all_canonical_sequence_regressions_v1.AllCanonicalFitHandoffTests.test_reduction_occurs_only_after_recorded_overflowing_full_render
```

Before fix: one error / one test. After fix: **one passed / one test, 0.799 seconds**, no failures, errors or skips (`original_after.log`). The real fitter recorded full 16 bullets / two pages, then a verified one-page result with 15 bullets.

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/full_ci_resume_preview_runtime tests.test_all_canonical_sequence_regressions_v1 tests.test_fitting_input_snapshot tests.test_phase6c_bounded_fitting tests.test_all_canonical_before_fitting_v1 tests.test_all_canonical_followup_fixes_v1 tests.test_fitting_render_optimizer tests.test_evidence_aware_fitting tests.test_docx_project_bullet_preservation tests.test_phase6c_bullet_fusion_controls_preview tests.test_shared_resume_pdf_preview_v1 tests.test_phase9e_tailoring_base_visual_preview tests.test_phase9e_tailoring_base_original_docx_preview
```

**81 passed / 81 tests, 55.838 seconds**, no failures, errors or skips (`related_after.log`). Includes canonical capacity/sequence, full rendering, overflow/reduction/restoration, render budgets, snapshot identity, bullet preservation and rasterized PDF preview regressions. Existing converter and page-count doubles remain; these tests do not claim an installed LibreOffice end-to-end render.

## Full offline CI

The CI workflow uses Python 3.13 on Ubuntu/Windows and runs `python scripts/run_project_checks.py --mode full --ci`. Its separate Streamlit startup/HTTP health job was not launched locally: this task prohibits network and live application data access.

The existing offline wrapper invokes the same full runner with `--mode full`; `--ci` changes the printed environment label only, not checks or discovery. Exact command executed:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/full_ci_resume_preview_runtime --full-project
```

Output: `reports/full_ci_resume_preview_runtime/full_project.log`.
The wrapper generated `reports/full_ci_resume_preview_runtime/offline-release-<uuid>` and propagated its original guard to Python children. SQLite, bytecode, blueprint artifacts and temporary files were redirected by the existing launcher, unchanged.

- Python compilation: **678 files**, completed before smoke execution.
- Configured zero-cost smoke checks: **43**, completed before discovery. Includes Phase 8/9 aggregation parity, immutable source/cache reuse and Application Session/execution contracts. All passed; no actual model/embedding calls or network access were admitted.
- Original overflow regression: **PASS in full discovery**, as were all three new isolation controls.
- Completed, logged unittest outcomes before interruption: **489 = 488 passed, 1 error, 0 assertion failures, 0 skips**. Counts include tests whose docstrings/logging put the completion status on another line; counting only single-line `... ok` records would incorrectly report 481 passes.
- Full discovery was **interrupted at the user's requested unrelated-blocker boundary**. The runner has no fail-fast setting; additional tests completed between the first error and its detection. These are observed completed counts, not a final unittest summary or the total suite size. Any in-flight work at termination is uncounted.
- Runtime: approximately **26 minutes**. The retained full log's creation-to-last-write span is **1569.832 seconds** (23:17:06–23:43:15, local time). The process tree was interrupted immediately after detecting the error; no normal runner elapsed-time/final summary was produced. This log span is not presented as an exact successful-suite duration.
- Full offline CI: **BLOCKED / incomplete**, not PASS.

### Next unrelated blocker

First error:
`test_browser_bridge_runtime.BrowserBridgeRuntimeTests.test_runtime_starts_on_loopback_and_answers_health`.

Independent reproduction:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/full_ci_resume_preview_runtime tests.test_browser_bridge_runtime.BrowserBridgeRuntimeTests.test_runtime_starts_on_loopback_and_answers_health
```

Result: **one test, one error, 0.044 seconds**. Complete exact traceback: `reports/full_ci_resume_preview_runtime/next_blocker.log`.

```text
tests/test_browser_bridge_runtime.py:24
    runtime = start_browser_bridge_runtime(port=0)
browser_integration/bridge_runtime.py:57
    server = JobAIBridgeServer((host, int(port)), effective_token)
browser_integration/bridge_server.py:37
    super().__init__(server_address, JobAIBridgeHandler)
socketserver.py:457 -> http/server.py:140 -> socketserver.py:478
    self.socket.bind(self.server_address)
scripts/offline_release_guard.py:51
    raise RuntimeError('Offline checks prohibit network access')
RuntimeError: Offline checks prohibit network access
```

This test explicitly requires a real loopback HTTP server and then a `/health` request. Its SQLite fixture already uses a temporary directory; the error is a **socket bind prohibition**, not the résumé filesystem root. The denial occurs before the HTTP server starts or its request runs. It independently reproduces without importing the modified résumé test modules. Its test, browser implementation and guard all match entry hashes: this is newly exposed offline-harness incompatibility, not a regression introduced by this patch, and does not establish a production browser defect.

No network exception, skip, mock replacement, browser change or guard change was introduced. A separately reviewed validation-boundary decision is needed for tests whose actual contract requires loopback networking; this task does not authorize one. No further full-suite rerun was attempted after confirming this blocker.

## Integrity and compatibility

An entry SHA-256 ledger covered **980 tracked files plus the existing untracked dashboard report**. Final comparison: **978 unchanged, exactly three changed**, all the test modules listed above. The new report is additional. The dashboard report remains byte-for-byte identical. No historical expected-result fixture was rewritten.

In particular, production résumé rendering, parsing, taxonomy/registry, scoring, application routes, cache/persistence and Phase 8/Application Session modules are unchanged. Published `stable-evidence-v1.17-phase6d21`, development v1.20/v1.21 and metadata v1.22/v1.23 identities remain unchanged; metadata namespaces remain `jd-metadata-comparison-v1` / `jd-metadata-comparison-v2`. No experimental gate was enabled. No changed production dependency calls for additional scoring-specific reruns; hash equivalence and the applicable full-run smoke checks are the compatibility evidence here. This report does not re-label prior 157/15-test results as newly executed, nor claim all later scoring regression modules completed in the interrupted run.

The two existing files beneath `outputs/` were checked by metadata only, without reading résumé contents: file sizes and nanosecond modification times remained identical across the full run. All test execution used the original write guard; no output escaped disposable scratch. The independent unauthorized-write control passed. Production directories, live databases and user outputs were not cleaned or modified.

`reports/full_ci_resume_preview_runtime/` is ignored by the existing rules (`git check-ignore` confirmed). It retains task-owned diagnostic logs, hash/count ledgers and launcher scratch for local review; it must not be staged. Per-test temporary directories and snapshot files were cleaned, as asserted. No existing local data was deleted. No `.gitignore` or containment configuration change was necessary.

Final verification:

- AST syntax checks for all three changed Python files: **PASS**; focused imports and full-run compilation: **PASS**.
- `git diff --check`: **PASS**.
- `git diff --cached --check`: **PASS**, with an empty staged diff.
- Final branch and HEAD equal entry values.
- Final tracked diff: only the three test modules in the inventory.
- Final untracked files: the preserved `coordinated_batch_dashboard_review.md` and requested `full_ci_resume_preview_containment_report.md`.
- Evidence ledgers: `baseline.json`, `final_integrity_and_counts.json`, `output_metadata.json` under the ignored task runtime directory.

Backlog outside this fix: resolve the browser HTTP integration test's compatibility with a strict no-network validation lane; assess later full-discovery results only after that decision. The existing `fitz` deprecation warning is informational and unrelated; no PDF-library migration was attempted.

## Verdicts

| Decision | Verdict |
| --- | --- |
| Original blocker fixed | **PASS** |
| Related résumé regressions | **PASS — 81/81** |
| Full offline CI | **BLOCKED — interrupted after unrelated loopback bind error** |
| Production behavior unchanged | **PASS — production/guard/fixture hashes unchanged** |
| Ready for checkpoint | **NO for a full-CI-cleared checkpoint** |

The bounded résumé test fix is reviewable and verified. Full-project readiness remains blocked by the separately identified browser-runtime test. No commit or push was performed.
