# v1.27 activation regression diagnosis

Branch: `feat/unresolved-review-workflow-v1`. Starting commit:
`557db892648f8fa3bdd1fd35bd9a29862669f374`.

## Baseline and reproduction

The source switch was OFF at entry and remains **`PRODUCTION_ENABLED = False`**.
The user confirmed the original terminal output was not saved locally. Nothing
was deleted or overwritten to reconstruct it. On unchanged starting code:

| Run | Result | Preserved local log |
|---|---|---|
| Exact original five modules, OFF | 68 passed | `reports/v127_activation_off_baseline.log` |
| Same five modules, isolated global ON | 68 run: 47 passed, 13 failures, 8 errors | `reports/v127_activation_on_reproduction.log` |

The ON reproduction temporarily sets the global switch in the disposable test
process, including module loading. It does not use a request-local release scope
or edit the source flag. Its counts and reported failures match the user's original
run. The following table classifies all 21 reproduced failures/errors, as authorized
by the user's clarification.

## All 21 causes

Module abbreviations: **R** = `test_requirement_context_release`, **C** =
`test_requirement_context_correction`, **J** = `test_job_discovery_job_match`,
**D** = `test_document_grounded_analysis`, **P** = `test_phase8_verification`.
All are under `tests`. F = assertion failure; E = exception.

| # | Outcome and exact test method | Cause and correction |
|---|---|---|
| 1 | F R.`test_context_only_document_persists_as_null_without_rebinding_archived_initial` | The supposedly archived v1.17 document was constructed while ON, so it was v1.27. Explicitly construct this transition control in OFF mode; retain the stale-history assertion. |
| 2 | F R.`test_job_finder_archive_currentness_cache_hit_recompute_and_rollback` | Both the old snapshot and requested old versions were already v1.27. Explicit OFF setup restores a real version transition, rejection and rollback test. |
| 3 | F R.`test_actual_30_jd_geometry_and_exact_affected_denominators` | Both before/after views were enabled, so no changed jobs remained. Explicit OFF setup retains the independently expected changes at Jobs 15/158. |
| 4 | F R.`test_disabled_production_switch_and_disposable_activation_simulation` | Asserted an ambient OFF switch while launched ON. The transition test now selects OFF itself before simulating ON and rollback. |
| 5 | F R.`test_explicit_document_phase8_recompute_keeps_archived_scores_separate` | Its “old” document was already current, so automatic historical-transition rejection was inapplicable. Construct the original in OFF mode; preserve rejection and explicit-recompute assertions. |
| 6 | F R.`test_explicit_legacy_report_refresh_keeps_own_sources_and_overrides` | Its “old” report was already current, bypassing the historical-transition missing-source guard by design. Explicit OFF setup tests the intended stale input and preserves the missing-evidence rejection. |
| 7 | F R.`test_independent_synthetic_numeric_effect_and_supporting_behavior` | Enabled baseline already scored 100 rather than the OFF expectation of 55. Explicit OFF setup preserves both numeric expectations and Supporting checks. |
| 8 | F R.`test_release_identity_cache_fingerprint_and_default_rollback` | Old and new fingerprints were both generated ON. Explicit OFF setup restores distinct identities and exact rollback assertions. |
| 9 | F R.`test_stale_document_is_retained_until_explicit_original_input_recompute` | Document constructed ON was not stale. Explicit OFF setup preserves passive-read, explicit-recompute and corrupted-original checks. |
| 10 | F C.`test_gate_off_corpus_geometry_and_saved_inputs_unchanged` | Ambient ON correctly produced 714 rather than OFF's 716 rows. Explicit OFF baseline retained; a separate global-ON test verifies 716 → 714 and exact removed IDs. |
| 11 | F C.`test_other_preview_policies_cannot_be_silently_composed` | Cleanup restored ambient ON, where learning is Supporting, rather than its assumed OFF Core. The developer-preview control now explicitly selects OFF. |
| 12 | F J.`test_default_builder_uses_current_master_scoring` | Fresh current output was compared with the native v1.17 constant. Compare with the effective production version helper; exercise both modes. |
| 13 | F D.`test_absent_profile_evidence_has_no_document_credit` | Same stale version assertion. Use effective current identity; retain NONE/source-bounding assertions. |
| 14 | E J.`test_analyze_match_caches_by_job_and_evidence_identity` | Stub requested `test-scoring-v1` under global ON. The production guard correctly rejected it. Give the stub the current scorer identity; retain cache/call-count assertions. |
| 15 | E J.`test_evidence_change_marks_previous_snapshot_stale` | Same incompatible stub identity. Use the current identity; retain stale-evidence assertions. |
| 16 | E J.`test_job_hash_change_marks_previous_snapshot_stale` | Same incompatible stub identity. Use the current identity; retain changed-JD assertions. |
| 17 | E D.`test_document_decision_integrity_and_legacy_blueprint_exclusion` | The synthetic **current** Phase 9C fixture adapter canonicalised current rows but stamped captured v1.17 metadata. Use the effective version in that test-only adapter. The historical JSON and rejection rules remain unchanged. |
| 18 | E P.`test_complete_verification_can_be_blueprint_ready` | The mocked fresh baseline helper emitted v1.17 while ON. Make fresh mocks use current identity; do not bypass transition validation. |
| 19 | E P.`test_fitted_draft_can_pass_preapproval_gate_without_being_blueprint_ready` | Same obsolete fresh-mock identity; same correction, retaining readiness assertions. |
| 20 | E P.`test_initial_uses_saved_pre_tailoring_profile_only` | Its explicitly `legacy-scorer` input requires an explicit recomputation request when ON. Request it; retain independent initial/tailored evidence and no-mutation assertions. |
| 21 | E P.`test_stale_stored_baseline_is_rebuilt_with_current_scorer` | Its v1.3 baseline requires explicit transition under ON. First assert automatic rejection and zero builder calls, then request recomputation; retain old baseline/version and source assertions. |

**Finding:** these 21 outcomes expose mode-dependent test inputs/assertions and a
test-only fresh-fixture identity defect. They do not justify weakening a production
guard. No production scoring, currentness, provenance or persistence defect has been
demonstrated by them. The activated acceptance checks below independently exercise
the real paths; their results determine readiness rather than this classification alone.

## Changes and boundaries

| Exact file | Change |
|---|---|
| `scripts/run_offline_release_checks.py` | Add `--requirement-context-mode off/on`. The existing guarded child-process bootstrap sets only that child's policy switch after installing containment. It prints the mode. No application environment switch or production activation path is added. |
| `tests/test_requirement_context_release.py` | Explicit OFF setup for historical-to-release transition classes. Existing expected scores, IDs, cache differences and rejections remain. |
| `tests/test_requirement_context_correction.py` | Explicit OFF setup for native-versus-developer-preview controls. |
| `tests/test_job_discovery_job_match.py` | Current-version assertion and cache-stub identity use the effective helper. |
| `tests/test_document_grounded_analysis.py` | Current-version assertions, including the actual `app.run_resume_analysis` function exercised with fake provider results. |
| `tests/phase9c_fixture_support.py` | Fresh synthetic projection uses effective scorer identity; historical bytes, evidence seeds and unknown-ID rejection unchanged. |
| `tests/test_phase8_verification.py` | Fresh mock identity uses effective helper; deliberate stale-baseline tests explicitly request transition and retain source/readiness assertions. |
| `tests/test_requirement_context_activation.py` | Separate global-ON acceptance and process-mode restoration tests. |
| `requirement_context_v127_activation_regression_report.md` | This report. |

Transition tests select their own OFF input state. Fresh Job Finder, document and
Phase 8 tests remain in the selected process mode; they are not all forced OFF to
obtain green results. The new acceptance class explicitly selects global ON without
calling `requirement_context_release()`. A separate test verifies the launcher's
requested process mode is in force after individual test overrides are restored.

Activated coverage includes:

- Actual Job Finder Analyze Match, compatible persisted v1.27 receipts, repeated
  cache hit, rejection of an explicit old cache identity, archived v1.17 readability,
  rollback to the original snapshot and restoration of the v1.27 cache afterward.
- The real Initial Analysis entry function with fake provider results, explicit
  recomputation from sealed original document evidence, no write during passive
  load/recomputation, explicit disposable persistence and unchanged frozen Initial.
- Actual Phase 8 automatic-transition rejection and successful explicit document
  transition. A Streamlit AppTest clicks the real Re-run button, executes the real
  scorer, and proves passive rerender causes no scoring. Its retrieval/save boundaries
  are in-memory test doubles; it does not claim a live database UI acceptance test.
- Current Phase 9C evaluation and fresh disposable blueprint admission, with original
  v1.17 candidate/blueprint provenance still rejected under v1.27. Historical fixture
  identities are not promoted in place.
- Enabled 30-JD geometry (716 → 714; only the two approved exclusions), unchanged
  surviving importance/allocations/provenance, mandatory/Supporting/role labels,
  null alignment and unavailable presentation, and no automatic approval from nulls.
- Existing independently expected API authorship/protocol and NONE-recovery controls
  under both modes. OFF-only historical version-mutation/pin tests remain OFF controls.

During construction, one new Job Finder test supplied an empty extractor profile.
The existing admission guard correctly rejected it. The test now supplies a non-empty
synthetic job-title profile and passes; production admission was not relaxed. The
intermediate failed log is retained as `reports/v127_activation_new_tests.log` and
the focused passing rerun as `reports/v127_activation_job_finder_recheck.log`.

## Frozen final verification

Python 3.13, strict offline launcher, disposable SQLite/DOCX only. No real databases,
network, model, embedding or secret inputs. Original baseline/reproduction logs remain
unchanged. Final selections and results:

| Lane | Result | Local log |
|---|---|---|
| Complete OFF application suite: original five modules plus activation module | **75 passed**, 231.332 s | `reports/v127_activation_final_off.log` |
| Complete ON application suite: identical six modules | **75 passed**, 225.198 s | `reports/v127_activation_final_on.log` |
| OFF: complete API completeness, NONE recovery, Phase 9C fixture-support modules | 21 passed | `reports/v127_activation_guard_off.log` |
| ON: seven API semantic methods, eight NONE semantic methods, complete fixture-support module | 19 passed | `reports/v127_activation_guard_on.log` |

Commands for the two complete application suites (run once with each mode):

```text
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/v127_activation_final_<mode> --requirement-context-mode <off|on> tests.test_requirement_context_release tests.test_requirement_context_correction tests.test_job_discovery_job_match tests.test_document_grounded_analysis tests.test_phase8_verification tests.test_requirement_context_activation
```

The guard OFF lane additionally runs
`tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_phase9c_fixture_support`.
The ON guard lane runs every semantic method in the first two modules, excluding
only `test_scoring_identity_changes_without_changing_candidate_or_taxonomy` and
`test_policy_and_scoring_versions_are_pinned`, plus the complete fixture-support
module. Those two tests specifically exercise/pin historical native identities;
both remain active and pass in the OFF guard lane. No test was disabled or expectation
silently replaced.

The source/test freeze and protected-input receipts are local under
`reports/v127_activation_frozen_code.json` and `reports/v127_activation_protection.json`.
Final results: all **850 captured Python source/test files remained byte-identical
during the final runs**. All **72 protected inputs**, including the historical
fixtures/reports, both unrelated Markdown documents and original captured baseline/
reproduction logs, remained byte-identical. All eight changed/new Python files parse.
Both `git diff --check` and `git diff --cached --check` pass. There are no staged
changes. Git diff for production matching/scoring, database, taxonomy, historical
fixtures and the accepted legacy assertion is empty.

Exact executed test identities, log hashes, timings and final integrity results are
retained in `reports/v127_activation_verification.json`. No full project CI result
is claimed; earlier iterations and focused reruns are not represented as complete
passing suites. Both final 75-test lanes are complete passing runs on the same frozen
code. In addition to the new-test setup error noted above, the first targeted
iteration exposed the deliberate `legacy-scorer` lineage test's missing explicit
request; that request was corrected before freezing. Its original no-cross-source
and no-mutation assertions remain.

## Release decision

**GO: safe local Streamlit activation can resume as the next controlled step.**
There is no outstanding activation blocker found in the reproduced failure cohort,
final application suites or protection regressions. No production-policy correction
or validation relaxation was needed. The changes repair test-mode compatibility and
provide reproducible OFF/ON acceptance; they do not change v1.27 scoring semantics.

The user's prior controlled-activation approval and single historical CI exception
remain recorded; this task does not activate the running application. Source is
still **OFF**, and no new scorer, parser, alias or taxonomy identity was introduced.
For the next controlled activation, use the previously reviewed switch/deployment
procedure, restart Streamlit, and use explicit original-input recomputation where
historical analyses are stale. Existing incompatible blueprint bindings must remain
blocked; do not relabel them. Rollback selects OFF and its original cache identity,
as verified against retained history.

The separately accepted single historical source-ledger assertion is unchanged;
its hashes/oracle were not rewritten and its exception is not broadened. Both
unrelated untracked files,
`coordinated_batch_dashboard_review.md` and `unresolved_review_workflow_audit.md`,
remain preserved. No stage, commit, push, merge or activation has occurred.
