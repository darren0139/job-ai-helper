# Coordinated Job Match developer UI integration — Phase 1

## Architecture audit (before implementation)

Verified branch `feat/coordinated-job-match-ui-integration`, starting HEAD
`2a0bf28916e338daf8a64e18df278e6e5c9dcc0a`. Only the unrelated untracked
`coordinated_batch_dashboard_review.md` was present; preserve it.

`app.py` uses the sidebar `navigation_page` radio and a page dispatch chain.
Job Finder delegates to `job_discovery.ui.render_job_finder`;
`job_discovery.matching.inspect_job_match` checks saved identities and
`analyze_job_match` builds/persists published analysis. Application Session
initial analysis uses `tailoring.initial_analysis_explainer_ui` and its
currentness-aware loader. Phase 8 uses document A/B snapshots from
`tailoring.job_match_ab_analysis`; these are document-authority comparisons,
not interchangeable with library-authority previews. Cache and saved analysis
writers reject preview identities before persistence.

The standalone `coordinated_job_match_preview.py` uses
`job_discovery.coordinated_preview.prepare_comparison` and `run_comparison`.
These validate a library projection and evaluate published v1.17 with the gate
OFF alongside source-aware v1.21 (built on coordinated v1.20). The nullable
`coordinated_preview_model` validates contributions and whole-JD withholding.
The production Initial Analysis renderer assumes a different saved schema;
reuse its native table convention, not its numeric summary implementation.
Existing diagnostics exports include complete raw analyses and are unsuitable
as the default sanitized export.

Chosen boundary: one lazy main-app Developer Diagnostics page, configuration
gate plus per-session opt-in and explicit run. Use only the existing synthetic
profile fixtures and frozen source JDs. No current application/library loader
is invoked: application-local comparison is unavailable because this page has
no verified application-to-library projection contract. v1.22/v1.23 `classify`
receipts are separate parser diagnostics, not additional comparable scores;
both experiments remain NO-GO. No production API change is required.

## Implementation

Files changed/added for this task:

| File | Change |
|---|---|
| `app.py` | Conditional final navigation entry, lazy page dispatch, isolated error boundary, fallback when configuration is disabled. Existing page names and widget keys retained. |
| `job_discovery/developer_comparison.py` | Small synthetic-only adapter around the existing verified comparison API; execution gate, byte/source fingerprint, exact-ID table projection and allowlisted JSON export. |
| `job_discovery/developer_comparison_ui.py` | Session opt-in, explicit Run, side-by-side results, requirement filter/details, metadata classifications and in-memory download. |
| `tests/developer_comparison_harness.py` | Actual page renderer isolated from unrelated application startup. |
| `tests/test_developer_comparison.py` | Adapter contracts, independent E04 conflict/E02 partial/E01 complete expectations, real evaluator AppTests, actual `app.py` navigation/evaluation test. |
| `coordinated_job_match_ui_integration_report.md` | Architecture audit, operating instructions, boundaries and verification. |

The pre-existing untracked `coordinated_batch_dashboard_review.md` is unrelated
and untouched. Test logs and disposable runtime outputs are under ignored
`reports/coordinated_ui_*`; they are not checkpoint source files.

## Enable and disable

In PowerShell, from this checkout:

```powershell
$env:JOB_AI_DEVELOPER_COMPARISON = '1'
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -m streamlit run app.py
```

Choose **Developer Diagnostics**, enable **Enable this session comparison**,
select a synthetic example and click **Run comparison**. The environment value
must be exactly `1`; the adapter separately checks both configuration and session
consent. Normal startup/navigation never invokes the experimental evaluator.

To disable, stop the server, remove the setting and relaunch:

```powershell
Remove-Item Env:JOB_AI_DEVELOPER_COMPARISON -ErrorAction SilentlyContinue
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -m streamlit run app.py
```

No setting is stored in SQLite. Neither the gate nor any published scoring
identity is changed by a preview run. The ordinary app's existing startup
initializers are unchanged; the comparison adapter itself has no database route.

## Supported comparison and limitations

There are 38 existing realistic synthetic examples, using the existing source
JDs and `preview_inputs` helper. They are explicitly simulations of library
authority. No current application, résumé library, saved analysis or unrelated
session is loaded. Live application comparison, stale saved-result rendering
and document/library authority conversion remain unsupported in Phase 1.
The page states this limitation rather than implying that it inspected the
selected Application Session. Existing production currentness validation is
unchanged and covered separately by its regression tests.

Published v1.17 and source-aware v1.21 execute through the existing pipeline.
v1.21 builds on coordinated v1.20; it is not a renamed published result.
Requirement tables join **only exact canonical IDs**. A row that exists only in
one decomposition is unavailable on the other side; no similar-text join,
invented child mapping or parent-credit delta is created. Differences state
observable label/allocation changes without inventing causal explanations.
Details expose selected originals, evidence IDs, source provenance, actions,
technical scope, native/effective labels, conflict findings and complete scoring
receipts. Canonical capability/eligibility fields remain accessible in receipts;
the UI does not reinterpret an unrecognized capability as candidate absence.

REVIEW_REQUIRED contributions remain null and whole-JD scores/bands unavailable.
Governed numeric zero stays numeric zero. DIRECT, WEAK, NONE and TRANSFERABLE
retain their existing meanings. Filtering and inspection use retained results.
No stable ranking, persistence, cache currentness, evidence allocation or policy
code was modified.

The two metadata tables call the existing v1.22/v1.23 **classifiers** on the same
original JD. They show line/source, wording, classification, admission and reason.
Ambiguous classifications remain visibly unresolved. They are not extra scored
analyses, and no metadata exclusion is applied to v1.17 or v1.21 here. Both
metadata scoring experiments remain NO-GO; their whole-JD scored comparison is
outside this bounded integration.

All tables use native `st.dataframe`, stretch width and native column controls;
full wording remains in details. No custom CSS/HTML table, new dependency or
unrelated styling change was introduced.

## Session lifecycle and performance

One comparison is retained under `developer_job_match_ui_v1_result`. All new
widget keys use the `developer_job_match_ui_v1_` prefix. Production analysis,
application-selection and ranking keys are not reused. Evaluation is explicit
and synchronous, with a spinner; inputs are limited to known fixtures and a
250 KB serialized input bound. There is no arbitrary pasted or live input route,
model call, background job, global candidate-result cache or persistence.

Reruns compare implementation/knowledge/source bytes and fixture fingerprints,
without calling extraction, canonicalization or scoring. The identity includes
all existing preview source/policy revisions, taxonomy bytes, the realistic
profile fixture, frozen JD corpus, ownership oracle and input factory scripts.
Changing the selection or fingerprint clears the old result and download.
Turning session consent off clears its retained result. Evaluation failures
clear previous output and show EVALUATION_FAILED; raw exception strings are not
rendered because they could contain sensitive local paths.

AppTest verified one evaluator call through filtering, requirement inspection,
export controls and ordinary reruns. The independent main-app navigation/run
check took 103.938 seconds including cold heavyweight application imports,
navigation reruns and actual scoring. This is not a per-evaluation benchmark;
cold app startup remains a performance limitation worth measuring separately.
No scoring performance rewrite or normalization change was attempted.

## Diagnostic export

`developer-job-match-ui-v1` is a separate preview-only schema. The in-memory
download includes stable/experimental identities, knowledge versions, source
authority, selected synthetic case, input and implementation fingerprints,
numeric/null summaries, exact-ID requirement differences, supported/missing
actions, technical scope, conflict quarantine, evidence/source IDs and metadata
classifications. Ranking and persistence eligibility are explicitly false.
`errors` is empty for a successful export; failures are visibly unavailable,
not exported as successful empty results.

Export uses an allowlist; it never copies session dictionaries, raw analyses,
environment, credentials, filesystem paths, unrelated applications or résumé
contents. Default export omits requirement/JD text and all raw evidence text.
A clearly labeled checkbox can include the selected synthetic requirement/JD
wording. Full raw receipts remain inspection-only. The selected input identity
and nullable receipt model are checked again before export. Fixed-input exports
have no timestamp and are deterministic. The download test intercepts the
actual Streamlit download argument and compares its summaries and identity to
the displayed retained result.

## Verification

Use the supported Python 3.13 interpreter and containment launcher for every
project-importing test. No full or quick project-wide suite was run.

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_ui_final tests.test_developer_comparison

& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_ui_regressions tests.test_coordinated_job_match_preview tests.test_coordinated_job_match_preview_ui tests.test_coordinated_library_sources tests.test_jd_metadata_v123 tests.test_application_session_analysis_currentness tests.test_application_session_first_analysis_binding tests.test_initial_analysis_explainer tests.test_job_finder_v17_batch_ui tests.test_analysis_cache_manager tests.test_stable_evidence_scoring tests.test_ollama_test_lanes

& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_ui_workflows tests.test_job_match_batch_matching tests.test_phase8_verification tests.test_phase8_score_explainability

git diff --check
git diff --cached --check
```

| Run | Passed | Failed | Errors | Skipped |
|---|---:|---:|---:|---:|
| New Phase 1 tests, final run (172.545 seconds) | 17 | 0 | 0 | 0 |
| Existing focused regressions | 130 | 0 | 0 | 0 |
| Existing workflow regressions | 22 | 0 | 0 | 0 |
| Separate corrected main-app AppTest | 1 | 0 | 0 | 0 |

The initial new-test run had 15 passes and one failure: the test had not
redirected the ordinary main app's startup DB paths. The guard blocked a mkdir
outside scratch **before database access**. The repair is test-only: redirect
all startup DB constants to disposable storage and suppress the unrelated
browser bridge. Production paths, assertions and guards remain unchanged. The
corrected main-app test then executed the real E01 adapter and asserted DIRECT,
default-OFF navigation, explicit action, no repeated scoring and gate disable.

The adapter's E04 assertions independently require conflict quarantine and
null credit; E02 independently requires the existing P3 WEAK ceiling. Existing
preview regressions verify the independent library-projection oracle, source
occurrences, raw-only/unsupported evidence, native NONE ceiling, API ownership,
all gated persistence denials and library/document-authority separation.
Currentness, cache, Application Session initial binding, Initial Analysis,
stable evidence, Job Finder batch selection and Phase 8 tests passed separately.

Integrity checks:

- The only tracked diff is `app.py`; scoring, parser, taxonomy, registry,
  ranking, persistence, cache, CI workflows and existing fixtures are unchanged.
- Published identity remains `stable-evidence-v1.17-phase6d21`; experimental
  entry points still require explicit invocation. No v1.24 identity was added.
- Frozen v1.16 accounting fixture SHA-256 remains
  `a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.
- Historical lane registration/byte checks passed: 169 current assertions
  registered and 143 archived assertions registered, with original archive
  hashes intact. This is registration/integrity checking, not historical execution.
- Eight pinned historical artifact/preservation-map files also match the
  existing pre-isolation byte ledger. Historical reproduction remains unrun;
  known prerequisite deficiencies were not restamped or repaired in this phase.
- Both Git whitespace checks passed. Nothing was staged, committed or pushed;
  the branch and HEAD remain unchanged. No production database, candidate data,
  model download or external service was accessed by this task.

## Final verdict

The final run passed all 17 new tests. Together with 152 existing regressions,
169 distinct focused tests passed with zero failures, errors or skips. The
separate one-test main-app rerun is additional execution of a test included in
the final 17; it is not counted twice in that total.

| Criterion | Verdict |
|---|---|
| Main `app.py` developer entry point | PASS |
| Feature default OFF | PASS |
| Stable v1.17 unchanged | PASS |
| Experimental persistence isolation | PASS |
| Requirement comparison | PASS for verified synthetic examples; live application comparison unavailable |
| Metadata diagnostics | PARTIAL: authentic classifiers exposed; v1.22/v1.23 scored comparisons deliberately unavailable, both still NO-GO |
| Diagnostic export | PASS |
| Streamlit integration tests | PASS, including actual main-app navigation and evaluator execution |
| Existing regression tests | PASS, 152 focused tests |
| Ready for isolated checkpoint | YES, for this bounded synthetic developer UI |
| Full CI | NOT RERUN |

The separate manually dispatched GitHub Actions execution has not been queried
or certified by this task. This verdict does not approve experimental scoring
for production. No staging, commit, push, merge, branch change or production
activation was performed.
