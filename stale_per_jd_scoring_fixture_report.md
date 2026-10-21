# Stale Per-JD scoring fixture compatibility

Date: 2026-10-21, Asia/Singapore.
Repository: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch remains `fix/stale-per-jd-scoring-fixtures`; HEAD remains `232d9838d898c2376ffc27fae1d975f9ea474fb5`.

## Decision

The Per-JD failures were stale **test input/context** defects. Production correctly rejected historical v1.16 results at a current-analysis boundary. The repair separates explicit historical accounting replay from actual current v1.17 synthetic analysis. It changes only tests and test helpers; no scoring, accounting, cache, currentness, publication or persistence algorithm was changed.

| Verdict | Result |
|---|---|
| Original failures | PASS — full original Per-JD module: 23/23 |
| Historical v1.16 preserved | PASS — exact original bytes, identities, labels, weights and assertions |
| Current v1.17 accounting | PASS — actual scorer on independently authored synthetic inputs |
| Stale-analysis rejection | PASS — including positive evidence, aggregation, cache identity and pre-storage binding rejection |
| Related regressions | PARTIAL — 143/149 pass; six separate frozen-adjudication prerequisite errors remain |
| Production behavior unchanged | PASS — no production or existing fixture file modified |
| Ready for isolated checkpoint | YES — the four test/helper files and this report; this is not a green full-CI claim |
| Full CI | NOT RERUN |

No staged changes, commits, pushes, merges, branch switches, resets or cleanups. The unrelated untracked dashboard review is unchanged. Other worktrees were listed through Git metadata only, never opened or modified.

## Root cause and integration path

`tests/test_per_jd_taxonomy_status.py` loads `per_jd_scoring_audit.json`. `view` originally passed a frozen v1.16 `baseline_stable_analysis` to `coverage_presentation.jd_coverage`. That function validates current scoring, taxonomy and registry identities before consuming native positives or reviewed gap proofs. At `coverage_presentation.py:198`, it raises `ValueError: Stale/incompatible analysis: scoring_version` because the current published scorer is v1.17. The original `maintenance.currentness` mock applies to the reviewed audit, not the saved analysis's independent version check; it cannot make old analysis current.

`live_analysis` also copied Job 566's historical rows and header. It changed requirement IDs and recomputed JD/scope fingerprints, but retained the v1.16 scoring identity. This was not a current-source fixture. `analyzed_jobs_coverage` catches the rejection and records each job as pending. Its `(numerator, denominator, percentage)` becomes `(0, 0, None)`: an empty set of eligible accounting occurrences with **unavailable percentage**, not an actual zero score. UI rendering likewise shows the unavailable caption and no successful coverage metrics. A bound-JD rejection test failed its regex because the earlier scoring-version check prevented it reaching the intended join validation.

The same defect affected historical summary/calibration tests in `tests/test_scoring_eligibility_calibration.py`: five assertions failed after all old records became pending, and two class setups failed through `audit_jd_scoring_eligibility.build_audit` -> `jd_coverage`. The latter prevented 14 test methods from executing. The six unresolved-adjudication failures have a different boundary and remain separate below.

No valid current v1.17 accounting defect was found. Positive evidence must not bypass version checks; rejection of the old fixture in the real current environment remains correct.

## Historical fixture provenance and meaning

The fixture was added at `edb115d4a8d196fd917566eb1d06f0476d1af757` (2026-10-11, complete governed taxonomy coverage and application analysis workflow). `git log --follow` finds no subsequent fixture content revisions. Its manifest records source HEAD `421ad429b0073863c59602aebba89e7231d6a087`, timestamp `2026-10-10T10:57:22.301968+00:00`, scorer `stable-evidence-v1.16-phase6d20`, taxonomy v1.5 and registry v1.3. It predates published v1.17 and is a frozen accounting/evaluability oracle, not a currently publishable analysis.

There are 30 historical jobs and 727 canonical/audit source rows. The existing report interpretation selects 474 meaningful rows. Historical Job 163 retains score 14, six capability occurrences and two independently typed NAC gap proofs; Job 566 retains score 23 and eleven capability occurrences. These saved scores are **historical receipt values**; no old candidate profile was rerun through current matching to create a new result.

Frozen SHA-256, unchanged before/after and equal to the tracked Git blob:

`a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`

The source NAC identities remain `(163, req_2f6aedb603aa)` and `(163, req_6677d37f660c)`. Job 566's gRPC control `req_86d57d2e033d` retains its original NONE in historical calibration. All other canonical identities, weights, source joins, labels and review records remain byte-protected by that same checksum. Historical global coverage `(192, 194)`, weighted coverage, parent allocation and all 30 arithmetic receipt parity assertions remain intact.

## Before-fix inventory

Complete tracebacks and verbose case outcomes are retained in the [original Per-JD log](C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver/reports/per_jd_fixture_runtime/before_per_jd.log) and [original related-module log](C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver/reports/per_jd_fixture_runtime/before_related.log). Machine-readable case signatures are in local `reports/per_jd_fixture_runtime/audit_metadata.json`.

Original Per-JD run: **23 tests; 6 passed; 3 assertion failures; 14 errored test methods producing 18 error records** (four live-input subtests and two corrupt-review subtests account for repeated records). No skips. Test names below are unchanged; full module/class identities and traceback frames are in the logs.

| Error/failure case (including subtests) | Signature / observed cause |
|---|---|
| `test_all_dependency_noise_and_deferred_classes_stay_outside_denominator (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_all_dependency_noise_and_deferred_classes_stay_outside_denominator)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_corrupt_review_cannot_supply_gaps_or_hide_native_resolutions (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_corrupt_review_cannot_supply_gaps_or_hide_native_resolutions) (corrupt='row')` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_corrupt_review_cannot_supply_gaps_or_hide_native_resolutions (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_corrupt_review_cannot_supply_gaps_or_hide_native_resolutions) (corrupt='proof')` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_deferred_and_identity_not_denominator (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_deferred_and_identity_not_denominator)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_incomplete_accounting_keeps_positive_proofs_without_requiring_all_rows (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_incomplete_accounting_keeps_positive_proofs_without_requiring_all_rows)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_invalid_gap_proof_does_not_invent_a_gap_or_hide_native_resolutions (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_invalid_gap_proof_does_not_invent_a_gap_or_hide_native_resolutions)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_job163_only_own_proved_gaps (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_job163_only_own_proved_gaps)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_live_without_review_is_available_and_occurrences_exclude_unknowns (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_without_review_is_available_and_occurrences_exclude_unknowns) (resolved=8)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_live_without_review_is_available_and_occurrences_exclude_unknowns (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_without_review_is_available_and_occurrences_exclude_unknowns) (resolved=11)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_live_without_review_is_available_and_occurrences_exclude_unknowns (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_without_review_is_available_and_occurrences_exclude_unknowns) (resolved=7)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_live_without_review_is_available_and_occurrences_exclude_unknowns (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_without_review_is_available_and_occurrences_exclude_unknowns) (resolved=5)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_other_job_gap_cannot_affect_job566 (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_other_job_gap_cannot_affect_job566)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_same_application_status_survives_resume_and_tailoring (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_same_application_status_survives_resume_and_tailoring)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_stale_review_cannot_supply_gaps_but_native_resolutions_remain_available (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_stale_review_cannot_supply_gaps_but_native_resolutions_remain_available)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_ui_scope_and_no_execution_on_rerender (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_ui_scope_and_no_execution_on_rerender)` | KeyError: "This JD's confirmed taxonomy coverage" |
| `test_zero_denominator_is_not_fabricated_100 (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_zero_denominator_is_not_fabricated_100)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_proven_gap_does_not_automatically_mean_unscoreable (tests.test_per_jd_taxonomy_status.ScoringEligibilityAuditTests.test_proven_gap_does_not_automatically_mean_unscoreable)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_receipts_reproduce_every_production_score_and_do_not_mutate (tests.test_per_jd_taxonomy_status.ScoringEligibilityAuditTests.test_receipts_reproduce_every_production_score_and_do_not_mutate)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_bound_jd_and_generation_must_match (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_bound_jd_and_generation_must_match)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_live_aggregate_without_review_sums_occurrences_and_additional_items (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_aggregate_without_review_sums_occurrences_and_additional_items)` | AssertionError: Tuples differ: (0, 0, None) != (23, 23, 100) |
| `test_live_ui_without_review_is_passive_and_zero_denominator_is_explained (tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_ui_without_review_is_passive_and_zero_denominator_is_explained)` | AssertionError: Lists differ: [] != ['100.00%', '0 currently established'] |

The six originally passing methods were `test_global_is_global_and_preserved`, `test_live_identity_corruption_and_stale_analysis_fail_closed`, `test_render_unanalyzed_and_missing_never_falls_back_global`, and the scoring-audit controls `test_counterfactual_preserves_original_sibling_allocation`, `test_supporting_evidence_stays_in_native_strength_component`, `test_unresolved_alone_never_proves_evaluation_limit`. The live corruption test previously passed before reaching some intended corruption checks because every input was already stale; fresh current inputs now make those assertions meaningful.

Related baseline: **135 executed, 124 passed, 5 failures, 6 test errors, plus 2 class-setup errors**. unittest does not add class-setup errors to its executed-test count. The two setup failures blocked 14 additional methods.

| Related before-fix case | Signature / classification |
|---|---|
| `setUpClass (tests.test_scoring_eligibility_calibration.CalibrationTests)` | ValueError: Stale/incompatible analysis: scoring_version |
| `setUpClass (tests.test_scoring_eligibility_calibration.FinalAdjudicationTests)` | ValueError: Stale/incompatible analysis: scoring_version |
| `test_cli_default_no_transport_init_or_network (tests.test_unresolved_adjudication.NativeInputTests.test_cli_default_no_transport_init_or_network)` | ValueError: Frozen input/current knowledge changed; benchmark needs review |
| `test_cloud_preflight_with_key_zero_calls (tests.test_unresolved_adjudication.NativeInputTests.test_cloud_preflight_with_key_zero_calls)` | ValueError: Frozen input/current knowledge changed; benchmark needs review |
| `test_frozen_manifest_labels_not_bucket_conversion (tests.test_unresolved_adjudication.NativeInputTests.test_frozen_manifest_labels_not_bucket_conversion)` | ValueError: Frozen input/current knowledge changed; benchmark needs review |
| `test_no_auto_all_corpus_expansion (tests.test_unresolved_adjudication.NativeInputTests.test_no_auto_all_corpus_expansion)` | ValueError: Frozen input/current knowledge changed; benchmark needs review |
| `test_paid_execution_requires_prior_qwen_and_confirmation (tests.test_unresolved_adjudication.NativeInputTests.test_paid_execution_requires_prior_qwen_and_confirmation)` | ValueError: Frozen input/current knowledge changed; benchmark needs review |
| `test_whole_paid_plan_over_budget_never_initializes_transport (tests.test_unresolved_adjudication.NativeInputTests.test_whole_paid_plan_over_budget_never_initializes_transport)` | ValueError: Frozen input/current knowledge changed; benchmark needs review |
| `test_full_receipt_identity_and_snapshot_must_match (tests.test_scoring_eligibility_calibration.AnalyzedJobsSummaryTests.test_full_receipt_identity_and_snapshot_must_match)` | AssertionError: 0 != 1 |
| `test_global_and_per_jd_preserved (tests.test_scoring_eligibility_calibration.AnalyzedJobsSummaryTests.test_global_and_per_jd_preserved)` | AssertionError: Tuples differ: (0, 0) != (29, 31) |
| `test_occurrences_not_percentage_average_and_native_gap_identity (tests.test_scoring_eligibility_calibration.AnalyzedJobsSummaryTests.test_occurrences_not_percentage_average_and_native_gap_identity)` | AssertionError: Tuples differ: (0, 0) != (17, 19) |
| `test_stale_unavailable_summary_only_and_unanalyzed_are_separate (tests.test_scoring_eligibility_calibration.AnalyzedJobsSummaryTests.test_stale_unavailable_summary_only_and_unanalyzed_are_separate)` | AssertionError: Tuples differ: (0, 4, 1) != (1, 3, 1) |
| `test_summary_ui_shows_own_occurrences_and_rerenders_without_execution (tests.test_scoring_eligibility_calibration.AnalyzedJobsSummaryTests.test_summary_ui_shows_own_occurrences_and_rerenders_without_execution)` | AssertionError: Lists differ: ['Not enough classified capability requirem[37 chars] '0'] != ['89.47%', '2 currently established', '1'] |

The five summary failures and two calibration setup errors share the proven stale accounting-context defect. The six `NativeInputTests` errors are frozen benchmark/current-knowledge incompatibility, not Per-JD saved-analysis validation or a network-guard regression.

## Implementation and independently justified expectations

### Historical accounting only

New `tests/per_jd_accounting_fixtures.py` loads the historical file only if its exact checksum matches. `historical_accounting_context` verifies the v1.16 manifest, v1.5 taxonomy and every job's original scorer identity. It supplies those declared historical versions to the **consumer's** lookup inside an isolated test-only taxonomy context, using the existing explicit historical-presentation pattern already present in `test_post_publication_accounting.py`.

This is a frozen accounting/presentation and arithmetic replay, **not re-execution or certification of the historical evidence evaluator**. No old row is given a v1.17 header. No production scoring constant or code is patched. The scoped consumer adapter must not be used for current-source scoring, production cache reads, ranking, persistence or publication. Independent tests show it restores the real current lookup even on exception, refuses current bundles, and leaves historical positive evidence rejected outside that context.

`test_per_jd_taxonomy_status.py` explicitly separates its six current-input methods from historical receipt cases. Its scoring-audit class replays historical arithmetic, allocation and evaluability. `test_scoring_eligibility_calibration.py` uses the historical context for its original summary/report contracts. Its two native replay-observation tests retain their actual current scorer environment. Existing assertions and expected totals were not edited: AST comparison confirms **every pre-existing `test_*` method body in both edited modules is identical** to HEAD.

### Actual current source

The live helper now calls `build_stable_analysis` with an authored Requirements section, empty synthetic résumé/keyword evidence, retrieval OFF and the default-OFF scorer. It does not copy historical results. Its independently specified count controls use:

- `Perform regression testing for module i`: a literal `quality.qa_testing` requirement predicate in the published-equivalent v1.6 isolated taxonomy.
- `Perform quuxscope obligation i`: a deliberately unrecognized requirement.
- `C#`: a registry identity-only control, not capability development.

An initial scratch control using unheaded raw text produced no admitted rows; another using “unit tests” did not match the taxonomy's literal testing terms. The final authored controls use an explicit Requirements section and the documented `regression testing` predicate. These were input-design checks, not changes to scorer policy or expected totals. Intermediate logs remain local and are not substituted for final results.

Thus `(23, 23, 100)` is independently derived from **11 + 7 + 5 capability occurrences** across three synthetic JDs, and 45 additional items from **11 + 14 + 20** unclassified rows. It is not copied from Job 566's coincidentally equal saved alignment score of 23 and does not depend on old candidate scoring geometry. Individual job and aggregate counts agree. Another actual current control has eight rows: three capabilities, one identity and four unknowns -> denominator 3, additional items 5, taxonomy coverage 100%. Empty candidate evidence gives all NONE and a legitimate alignment score 0. **Taxonomy coverage is not candidate match percentage.**

The new compatibility tests separately verify current/stale mixed aggregation, all-stale null presentation, version-keyed cache lookup, stale application-binding rejection before DB initialization, checksum preservation and deterministic canonical identities. New current results retain the actual `SCORING_VERSION` constant rather than a duplicated current-version string.

### Labels, allocation and withholding

The independent DIRECT/WEAK/NONE arithmetic control retains values 1/.20/0 from the established match contract. Two required children share a parent of weight 4 (allocation 2 each); a second required parent retains weight 4. Coverage is `(2*1 + 2*.20 + 4*0)/8 = 30%`; strength is 60%; the established .9/.1 composition yields 33. Phase 8 parity and source rows are preserved. No policy or credit rule was invented.

A separately authored REVIEW_REQUIRED unit control keeps `match_value=None`, produces null whole-JD alignment and `WITHHELD_PENDING_POLICY_REVIEW`, and remains unpublishable even if given a published scorer header. Existing preview regressions also verify actual synthetic pipeline withholding, forged-zero rejection, scoped ownership, native NONE/P3 ceilings, cache/source identities and rejection of all gated persistence identities. No production gate was activated; explicitly gated runs occur only inside existing isolated synthetic regression tests.

## Cache, saved analyses and persistence

`matching.inspect_job_match` queries using the current scorer identity; a historical latest snapshot remains status `stale` with reason `stable scoring version changed`, never a current cache hit. Application binding's `persist_explicit_application_analysis` compares stable scoring/taxonomy/registry identity to `current_ab_identity` before initializing storage. The new test checks the actual stale rejection and that DB initialization/connection are never called. No database, schema, saved analysis or Application Session was migrated or updated.

`coverage.analyzed_job_records` still requires matching lightweight/full receipt identities and snapshot IDs. Existing aggregate tests preserve those constraints. Rejected analyses contribute no eligible rows; bookkeeping empty counts may be zero while public percentages remain null. Real REVIEW_REQUIRED contributions and aggregate match scores remain null, not invented zeros. Currentness, cache, source/evidence and preview-persistence safeguards are unchanged.

## Verification

All runs used the supported Python 3.13 interpreter and existing disposable containment:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/per_jd_fixture_runtime <test modules or method>
```

The two representative original failures were rerun as separate independent invocations:

```text
tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_incomplete_accounting_keeps_positive_proofs_without_requiring_all_rows
tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_aggregate_without_review_sums_occurrences_and_additional_items
```

Both pass (1/1 each). A prior three-method focused run also passed, including live identity-only/count controls.

| Final selection | Run / pass / failure / error / skip |
|---|---|
| `tests.test_per_jd_taxonomy_status` | 23 / 23 / 0 / 0 / 0 |
| `tests.test_per_jd_scoring_compatibility` (new independent controls) | 12 / 12 / 0 / 0 / 0 |
| Related six modules below | 149 / 143 / 0 / 6 / 0 |
| Cache/currentness/stable/evidence seven modules below | 85 / 85 / 0 / 0 / 0 |

The related selection:

| Module | Final result |
|---|---|
| `tests.test_post_publication_accounting` | 10/10 pass; unchanged existing historical/current-presentation context |
| `tests.test_scoring_eligibility_calibration` | 22/22 pass; formerly two classes did not run |
| `tests.test_technology_maintenance_batch` | 27/27 pass |
| `tests.test_tqd3_production_resolver_inspector` | 9/9 pass |
| `tests.test_tqd3_research_readiness` | 23/23 pass |
| `tests.test_unresolved_adjudication` | 52/58 pass; six separate existing frozen-input errors |

The additional 85 passing regressions comprise `tests.test_analysis_cache_manager`, `tests.test_application_session_analysis_currentness`, `tests.test_job_match_session_ab`, `tests.test_stable_evidence_scoring`, `tests.test_frozen_evidence_contract`, `tests.test_api_evidence_completeness`, and `tests.test_coordinated_job_match_preview`. They cover actual cache reuse and invalidation, historical comparability, application refresh, independent source attribution, API consumption/authorship separation, allocation, unavailable scores and gated persistence denial.

Logs: `after_per_jd.log`, `compatibility.log`, `after_related.log`, `regressions.log`, `final_individual_partial.log` and `final_individual_aggregate.log`, all under ignored `reports/per_jd_fixture_runtime/`. No full or quick project-wide runner was used. Passing focused tests do not establish full-CI success.

In-memory Python `compile` checks pass for all four added/edited Python files; no repository bytecode was produced. `git diff --check` and `git diff --cached --check` pass. New untracked files are checked separately for trailing whitespace. The Streamlit skill and installed testing reference were read; UI checks use the existing headless AppTest framework and existing network containment helpers, with no browser/server launch or guard edits.

## Remaining failures and limits

The six remaining errors are all in `tests.test_unresolved_adjudication.NativeInputTests`:

1. `test_cli_default_no_transport_init_or_network`
2. `test_cloud_preflight_with_key_zero_calls`
3. `test_frozen_manifest_labels_not_bucket_conversion`
4. `test_no_auto_all_corpus_expansion`
5. `test_paid_execution_requires_prior_qwen_and_confirmation`
6. `test_whole_paid_plan_over_budget_never_initializes_transport`

Each traceback reaches `scripts/adjudicate_unresolved_requirements.py:33`, function `prepare`, and raises `Frozen input/current knowledge changed; benchmark needs review`. That contract reconstructs model inputs using current resolver/taxonomy/version identity and compares against a distinct frozen benchmark. It is not the Per-JD coverage API or aggregate accounting. These errors were present in the baseline and match the separately documented Ollama historical-runtime prerequisite issue. No adjudication expectations, labels, preservation maps or algorithms were edited. Full tracebacks remain in `after_related.log`.

The historical adapter is intentionally a test boundary. It does not authorize publishing v1.16 results, prove a v1.16 evidence-evaluator runtime was rebuilt, or make historical data current. A future scorer/taxonomy migration must keep those distinctions. Current synthetic accounting assertions do not claim historical/live candidate scores changed.

## Exact file inventory and integrity

| Reviewable file | Change |
|---|---|
| `tests/test_per_jd_taxonomy_status.py` | Historical context versus real current helper; all original test method bodies/assertions unchanged |
| `tests/test_scoring_eligibility_calibration.py` | Explicit historical report/summary contexts; native current replay observations stay separate; assertions unchanged |
| `tests/per_jd_accounting_fixtures.py` | New strict historical loader/context and fresh current synthetic analysis builder |
| `tests/test_per_jd_scoring_compatibility.py` | Twelve independent compatibility/safety controls |
| `stale_per_jd_scoring_fixture_report.md` | This report |

The entry ledger covered 991 existing files, including `coordinated_batch_dashboard_review.md`. Exactly the two test modules above differ. Every other entry is byte-identical, including the historical v1.16 fixture, all production/scorer/version sources, taxonomy, registry, cache/persistence, application/session sources, browser/network/resume containment and prior Ollama test/report sources. The two edited test modules are not members of the four previously audited Ollama preservation maps; those maps were neither restamped nor edited. Published v1.17 and experimental v1.20–v1.23 constants/defaults remain unchanged.

All additional diagnostic logs, probe scripts, baseline and audit metadata are local-only under ignored `reports/per_jd_fixture_runtime/`, including launcher-created disposable runtime/database trees. No ignored data is required by the new tests, and no large fixture or diagnostic export was added to Git. Only committed safe test fixtures and normal project dependencies are required. The historical checksum equals the actual Git blob bytes, so it is not a Windows-only line-ending identity. The unrelated untracked dashboard report remains outside the checkpoint scope.

No Ollama, Tavily, external-network, model or embedding operation was performed. Test dependencies and AppTest use the existing offline launcher; application/cache tests use injected transports or disposable test-owned storage, not live data. No résumé/candidate source was imported for new scoring controls. Historical fixtures were read as frozen evidence/accounting records only. No approval or weakening of production currentness was needed.

Recommended next action: review this bounded test-only checkpoint. Keep the separate unresolved-adjudication/Ollama historical-runtime work explicit; do not restamp its benchmark to claim full CI is green. Stop for review.
