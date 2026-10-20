# Coordinated-action Job Match developer comparison implementation

## Result and boundary

Implemented the bounded developer-only comparison. Published scorer v1.17 and the normal Job Match workflow remain authoritative. The existing unprojected gated v1.20 entry point and its historical references remain intact. No production feature is activated and no gated persistence is enabled.

Open the standalone page with:

```powershell
streamlit run coordinated_job_match_preview.py
```

The developer toggle defaults OFF. Choose an existing synthetic profile, enable the comparison and click **Run developer comparison**. It uses frozen JDs and supplied synthetic library records, not live candidates, databases or model extraction. It displays separate published and gated receipts, a filterable native requirement table, row selection, per-original action/scope/conflict receipts and a separate JSON export. Results occupy one dedicated session entry; filters, receipt switching and selection do not rerun analyses. No normal Application Session state or frozen Initial Analysis is replaced.

Repository/branch: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`, `feat/coordinated-final-integration-v1`; entry HEAD `a359cfc5c328aa407421580903925e4e1683cb39`. Both pre-existing untracked reports are preserved.

## Fixed integration blockers

| Blocker | Implementation |
|---|---|
| Null review credit became zero | Separate typed `AnalysisView` / `RequirementView` / `Label` model. DIRECT, TRANSFERABLE, WEAK, NONE and REVIEW_REQUIRED remain distinct. Review credit and all withheld aggregate fields stay null; forged zero-valued review fields raise rather than silently converting. |
| Misleading score/rank/export | Whole-JD percentage and rating band are suppressed when unavailable. No partial normalization is computed. All developer results are ranking-ineligible, including fully numeric comparisons. JSON preserves null and carries preview/schema identity plus the gated receipt. The published numeric-only summary and ranking functions now explicitly reject preview payloads; ordinary v1.17 behavior is unchanged. |
| E23 raw projection lost source scope | New replay-verified library sidecar records canonical item ID, original field/line occurrence, original text, projected path/container and every raw emission origin. Only a raw alias whose **every** origin is a verified structured original avoids being treated as a new unscoped statement. The originals themselves are still evaluated independently, including denials and duplicates. |
| Raw-only/unindexed evidence could be misattributed | Explicit raw-only input is never linked by a text match, even if identical to a known bullet. Unknown-category records and unindexed metadata remain visible with unscoped/unindexed coverage. They do not become admitted ownership or fabricated project associations. Forged sidecars fail deterministic replay verification before scoring. |
| Preview could rebuild through OFF/currentness | Separate request/receipt/cache namespace and dedicated session key. Frozen JD extraction or an explicit injected extractor is mandatory; there is no default model extractor. Stale previews require a new explicit run. Normal application refresh rejects preview receipts instead of rebuilding them as v1.17. |
| Saved pipeline coupling | The controller never invokes `analyze_job_match`, candidate/database loading, saved-match writers, application binding, normal summary or ranking. OFF and gated builds receive separate copies of the same original JD and projected evidence. OFF uses native canonicalisation/keyword matching; the gated path uses the existing coordinated native pipeline with verified source receipts. |
| Gated persistence escape boundary | The publication guard additionally recognizes v1.21. The connection-based insertion helper now checks publishability before executing SQL, alongside the existing public writer guards. v1.18/v1.19/v1.20/v1.21 and exported comparisons remain rejected. |

No ownership grammar, R1 packet recognition, P3 ceiling, API V1.1 rule, taxonomy, published scoring constant, native source ranking/deduplication or parent allocation was expanded. There is no duplicate fallback selector and no cross-bullet ownership union.

## Version identities and compatibility

| Identity | Value |
|---|---|
| Published/default OFF | `stable-evidence-v1.17-phase6d21` — unchanged |
| Original Stage 2I gate | `stable-evidence-v1.20-phase6d24` — unchanged for calls without a source projection |
| Explicit source-aware gated comparison | `stable-evidence-v1.21-phase6d25` |
| Source projection | `job-match-source-projection-v1` |
| Verified raw alias policy | `coordinated-verified-raw-alias-scope-v1` |
| Comparison/session namespace | `developer-job-match-comparison-v1` / `developer_coordinated_job_match_comparison_v1` |
| Nullable view/export | `coordinated-comparison-view-v1` |

The v1.21 analysis fingerprint includes the full verified occurrence ledger, original library provenance and new policy identities. The comparison request also includes original raw JD, frozen extraction, evidence authority, supplied originals, explicit raw-only coverage, published/gated versions, existing policy identities and relevant implementation/knowledge revisions. Published v1.17 cache hits cannot stand in for gated results. Selection/filter state is not an analysis input.

The source-aware scorer is only chosen by the explicitly invoked controller. The native default-false gate still dispatches ordinary gated calls to the frozen v1.20 behavior. No saved snapshots or prior oracle expectations are relabeled as v1.21.

## Actual application-adapter results

The new independent fixture `coordinated_library_projection_v1.json` defines the application-adapter expectations separately from prior Stage 2H/2I references. Source records come from original synthetic project/experience bullets. Résumé-wide metadata is retained as unindexed input, not assigned as responsibility ownership to an invented project.

| Case | Old v1.20 flattened adapter | New verified v1.21 adapter | Receipt/aggregate result |
|---|---|---|---|
| E01 | DIRECT | DIRECT | Complete original preserved. |
| E02 | WEAK | WEAK | Existing P3 weak ceiling preserved. |
| E03 | REVIEW_REQUIRED | REVIEW_REQUIRED | No ownership union across atomic bullets. |
| E04/E05 | REVIEW_REQUIRED | REVIEW_REQUIRED | Same-project denial quarantines in either bullet order; credit and whole-JD metrics null. |
| E23 | REVIEW_REQUIRED despite valid different-project ownership | **DIRECT** | Raw text and the other project's denial remain present; the verified alias points to that original container. No global denial veto. |
| E24 | REVIEW_REQUIRED | REVIEW_REQUIRED | Both duplicate original origins remain traceable. The conflicted native-selected project is not replaced with an unproved fallback. |
| B01 | DIRECT | DIRECT | Genuine authored endpoint evidence remains recognized. |
| B02 | REVIEW_REQUIRED | REVIEW_REQUIRED | Family ownership and API authorship from separate originals are not combined. |
| B05 | REVIEW_REQUIRED | REVIEW_REQUIRED | Same-project REST endpoint denial quarantines; API consumption does not become authorship. |
| C01 | DIRECT cloud | DIRECT cloud | Independent complete cloud evidence preserved. |
| C03 | DIRECT cloud, REVIEW backend | DIRECT cloud, REVIEW backend | Backend contradiction withholds whole-JD alignment without suppressing valid cloud evidence. |
| F01 | NONE | NONE | Native NONE ceiling preserved. |

The original unprojected v1.20 fixture suites still report 60 cases: 12 DIRECT / 3 WEAK / 19 NONE / 26 REVIEW, 31 whole-JD withheld; and 38 cases: 12 DIRECT / 2 WEAK / 2 NONE / 22 REVIEW, 26 whole-JD withheld. These references are not the same inputs as a reconstructed library projection; do not infer historical/live candidate score changes from the adapter examples. R1 remains deliberately restrictive for richer library inputs with raw text and metadata.

## Historical formatter test correction

The previously failing two-gap/direct-evidence UI test uses a frozen v1.16 scorer receipt and taxonomy v1.5. Its assertion was evaluated under current v1.17 identity, so the production stale gate correctly refused the old receipt. The test now explicitly isolates the historical **formatter version context** using the version recorded in the untouched fixture. The original two-gap/direct assertions remain unchanged. An additional test proves the same historical receipt is still rejected under today's published currentness. No historical fixture or production scorer constant was changed to pretend the receipt is current.

## Validation

All checks use synthetic/disposable inputs. No model, embedding, network, live candidate or live database access is permitted. The task-owned scratch tree is already ignored: `reports/coordinated_integration_fix_runtime/`.

| Check | Result |
|---|---|
| Independent source contract before scoring hook | 5 tests PASS: exact aliases/origins, duplicates, explicit raw-only identity, unindexed coverage and forged/document authority rejection. |
| Initial source/controller contract | 17 tests PASS. |
| Original combined coordinated suite | **72 tests PASS**, including original 60 and 38, R1/P3/API protections, conflict controls, persistence rejection, source invariants and all 30 historical default-OFF comparisons. |
| Final preview/UI/historical formatter checks | **38 tests PASS**: nullable summary/table/export, ranking rejection, all four gated versions rejected, no database/model routes, authority separation, stale preview invalidation, refresh rejection, retained UI interaction, native row selection, default OFF and historical formatter/currentness controls. |
| Identical-input before/after adapter check | 13 independent cases PASS; E23 changes from REVIEW_REQUIRED/null to DIRECT/1.0 parent credit. Other listed outcomes and C03's independent cloud credit/whole-JD withholding are preserved. |
| Full project runner | **BLOCKED / incomplete**, not green. Compiled 672 Python files and passed the configured smoke stage. During discovery, 72 tests reported success and one unrelated résumé-output test hit the containment boundary. The run was explicitly interrupted after that boundary was independently reproduced; remaining discovered tests were not assessed. |
| Protected files/whitespace | 949 of 957 entry files remain byte-identical; exactly eight existing files changed as listed below. All prior references, protected scoring/taxonomy/registry files and both pre-existing untracked reports are unchanged. Tracked, staged and new-file whitespace checks pass; index is empty and branch/HEAD unchanged. |

The first new UI test attempt contained a test-only attribute named `run`, colliding with `unittest.TestCase.run`; it was corrected to `compare_call` and the complete focused set reran green. No assertion was weakened to resolve that harness error.

### Reproducible commands

Use Python 3.13 with normal project dependencies. The interpreter used here is `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B`.

```powershell
python -B scripts/run_coordinated_preview_checks.py --scratch-root reports/coordinated_integration_fix_runtime tests.test_coordinated_library_sources

python -B scripts/run_coordinated_preview_checks.py --scratch-root reports/coordinated_integration_fix_runtime tests.test_coordinated_batch_dashboard tests.test_coordinated_action_implementation tests.test_coordinated_r1_disposition tests.test_coordinated_conflicts tests.test_coordinated_conflict_acceptance tests.test_coordinated_realistic_evidence_audit tests.test_api_evidence_completeness

python -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_integration_fix_runtime tests.test_coordinated_library_sources tests.test_coordinated_job_match_preview tests.test_coordinated_job_match_preview_ui tests.test_initial_analysis_explainer

python -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_integration_fix_runtime --full-project

git diff --check
git diff --cached --check
```

The new offline launcher is portable source, not a private runtime dependency. It runs the unchanged full project runner with normal compilation/smokes/discovery, propagating containment to Python children. Explicit compilation output is redirected to a scratch bytecode prefix. Windows temporary folders inherit the disposable parent's ACL. Optional Chroma dotenv loading is disabled only in the test harness. Candidate/database artifacts and secret reads outside scratch remain blocked; only the installed `python-docx` default template is admitted as a known noncandidate resource. Uncontained external tools are not broadly permitted.

### Unsafe artifact boundary

The old Phase 9D smoke blocked because `BLUEPRINT_ARTIFACT_ROOT` defaulted to repository data storage. The isolated runner now supplies the already-supported `PHASE9F_BLUEPRINT_ARTIFACT_ROOT` setting under its disposable root. The previously blocked Phase 9D smoke and blueprint availability checks pass without changing blueprint semantics, production configuration or safety guards.

Full discovery then encountered `test_all_canonical_sequence_regressions_v1.AllCanonicalFitHandoffTests.test_reduction_occurs_only_after_recorded_overflowing_full_render`. Its mocked two-page render calls `_snapshot_before_fitting_pdf`, which tries to create the hard-coded `outputs/resume_previews` directory. The audit hook rejected that repository output write before it occurred. A separate single-test rerun reproduced the exact exception in 0.045 seconds of test execution. This is an unrelated existing test-isolation defect under the requested output boundary, not evidence of a coordinated-scoring regression. No rendering assertion, production output constant or filesystem guard was weakened. That test cannot complete safely **as currently written under this launcher**. A future test-only patch should redirect its preview directory into its existing temporary fixture. The remaining broad suite is unverified, so there is no full-CI clearance.

Ignored evidence is retained locally in `reports/coordinated_integration_fix_runtime/`: `legacy72.log`, `preview_final.log`, `adapter_before_after.log`, `full_project_final.log`, `canonical_boundary.log`, `entry_hashes.json` and `protection.json`. The full runner and its owned child processes were stopped; no background acceptance run is left active.

## Changed files

| File | Change |
|---|---|
| `job_discovery/coordinated_sources.py` | New pure original-occurrence projection/replay and raw alias provenance. |
| `job_discovery/coordinated_preview_model.py` | New typed nullable requirement/summary/export contract and ranking rejection. |
| `job_discovery/coordinated_preview.py` | New explicit OFF/gated controller, versioned request identity and retained-state validation. |
| `analysis_stability/coordinated_integration.py` | Optional verified projection path with local v1.21 identities; unprojected v1.20 preserved. |
| `analysis_stability/coordinated_conflicts.py` | Only replay-verified raw aliases avoid a duplicate unscoped re-evaluation; original scoped records remain checked. |
| `analysis_stability/coordinated_runtime.py` | Shared preview detection; v1.21 rejection and preview namespace protection. |
| `job_discovery/matching.py` | Published numeric-only summary rejects previews; normal v1.17 arithmetic unchanged. |
| `job_discovery/match_ranking.py` | Reject preview envelopes, summaries and nested gated receipts. |
| `tailoring/jd_user_input_overrides.py` | Reject preview reports from ordinary Application Session refresh. |
| `database/analysis_cache_manager.py` | Low-level connection insertion rejects gated receipts before SQL. |
| `scripts/coordinated_job_match_preview_inputs.py` | Frozen/synthetic-only page inputs, preserving unscoped metadata separately. |
| `coordinated_job_match_preview.py` | Minimal standalone native Streamlit page, dedicated session state and no save/bind route. |
| `tests/fixtures/coordinated_library_projection_v1.json` | New independent application-adapter expectations, not rewritten old references. |
| `tests/test_coordinated_library_sources.py` | Independent provenance, duplicate, coverage and replay controls. |
| `tests/test_coordinated_job_match_preview.py` | Actual pipeline application-adapter, null, cap, isolation, identity and persistence controls. |
| `tests/test_coordinated_job_match_preview_ui.py` | Actual AppTest page behavior, selection/filter performance, scope receipts and initial-state protection. |
| `tests/test_initial_analysis_explainer.py` | Correct historical formatter context; retain two-gap assertion and add current stale rejection. |
| `scripts/offline_release_guard.py` | Test-only child-process/secret/network/file/SQLite containment and temporary ACL handling. |
| `scripts/run_offline_release_checks.py` | Reproducible disposable launcher with artifact redirection for focused/full checks. |
| `coordinated_final_integration_implementation.md` | This implementation and verification report. |

The normal Job Finder UI, uploaded-document scorer, published scoring/taxonomy/registry, saved references, research diagnostics and the pre-existing readiness reports are preserved. No normal cached match or Application Session is migrated or refreshed by the new page.

## Remaining compatibility and readiness

This is a developer-only library comparison, not production activation or a document-scoring replacement. Finite positive/negative language recognition, P01/P02 conservative review, strict R1 packet conditions, native NONE ceilings and E24's lack of a new fallback selector remain intentional disclosed limits. There is no general contradiction/chronology resolver. Unknown provenance remains reviewable, not evidence of absence.

The old Job Match/Phase 8 presentation remains published-numeric-only; it is protected from preview receipts rather than repurposed as a nullable renderer. The preview has no saved-analysis retrieval, application binding, production ranking or document authority route. Any later production activation and persistence/migration need separate explicit approval and compatibility design.

**Recommendation: CONDITIONAL GO for developer-only review.** The bounded preview implementation and all 110 combined focused checks pass. Full CI is BLOCKED/incomplete at the independently confirmed unrelated output-write boundary; this is not a general release clearance. Production activation and gated persistence remain OFF and unauthorized. No staging, commit, push or merge was performed. Stop for review.
