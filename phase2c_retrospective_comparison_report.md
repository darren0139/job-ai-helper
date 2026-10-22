# Phase 2C — retrospective frozen evidence comparison

Implemented a separate **Retrospective Frozen Evidence Comparison** in the existing
developer page. Strict current-version comparison remains the default and retains
its original admission/rejection behavior. This phase explicitly authorizes fresh
evaluation of verified older input packets; it does not change the Phase 2B finding
that their saved outputs are incompatible with current saved-result admission.

Branch: `feat/job-match-real-evidence-comparison-v1`, worktree
`C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
No staging, commit, push, merge, database write, migration or production activation.

## Scope decision before implementation

The existing `coordinated_preview.prepare_comparison` accepts explicit original
library records and a raw JD with a parser seed. The current native canonicalizer
can construct requirements from that raw JD with an empty profile. The existing
`run_comparison` then builds deterministic keywords and gives both published v1.17
and source-aware v1.21 the same projected résumé/profile/JD inputs. It revalidates
the request identity, preserves library occurrence ownership, disables retrieval,
and runs the existing guarded comparator. No validator or scorer needed changing.

Chosen bounded admission: independently verify the archived packet against its
separately persisted source snapshot and application-owned Initial Analysis, then
construct a **new** request with `jd_profile={}` and the original raw JD/evidence.
The old extraction and old taxonomy/capability labels never enter either fresh
scorer. Exact requirement identity/importance/parent allocation must reconcile;
there is no semantic-text join or guessed weight mapping.

## Identity contracts

### Historical authority

The existing read-only transaction, gate and provenance checks remain shared:

* Explicit single application, sealed `job_finder` entry binding and exact source
  job/snapshot IDs; the separately persisted snapshot must equal the bound snapshot.
* Exact original raw JD and generation hash; stripped-JD SHA-256 verifies under the
  existing handoff contract. No newest JD/document fallback.
* Exactly one application-owned original analysis for the bound initial ID; its
  input fingerprint and complete initial-reference metadata must match the entry.
* The original report's JD/profile/raw résumé/projected profile/stable result must
  equal the frozen handoff inputs, not the current application report.
* Nonempty original library records, native evidence fingerprint, unique positive
  item IDs, and replay-verifiable field/occurrence ownership. No current library
  lookup or cross-record ownership fabrication.
* Archived canonical rows must match their sealed historical scope. Conflicting
  original pointers, configured/document-session authorities and corrupt packets
  remain blocked; this is not document-based session support.

Recognized historical source schemas are bounded to the verified v1.16/v1.5 pair
and the current published scorer/taxonomy pair. Their match schema and registry
must agree with the supported current library input contract (currently match
v2.3.0 and registry v1.3), and archived stable-result identities must agree with
the snapshot. Unknown/inconsistent historical schemas are explicitly rejected.
There is no application-ID or private-content special case.

The current application report may differ only because it is excluded from this
mode's evidence authority. A boolean warning displays that difference; it is never
merged, cleared, refreshed or presented as original evidence. Its bytes still
participate in the loaded identity, so later changes invalidate retained results.
Malformed current report data still fails closed rather than being repaired.

### Fresh authority and reconciliation

`load_retrospective` creates `RETROSPECTIVE_FROZEN_INPUTS_V1`, distinct from strict
admission. Its identity includes the mode, selected application, exact archived
snapshot and owned receipt, source job, fresh request identity, implementation
source revision and current policy/knowledge identities. The existing comparison
adapter still uses its own independently replay-validated current request identity.

Fresh input is `{raw_jd_text: original, jd_profile: {}, evidence_items: originals}`.
The current native raw-JD parser/canonicalizer and taxonomy explicitly reinterpret
the source text. The historical extraction is used only to authenticate the
original receipt; no v1.5 capability ID is renamed or promoted into v1.6.

Admission requires exact ordered reconciliation of requirement IDs, text,
importance, parent IDs and allocation fractions between archived scope and fresh
published parsing. A changed ID, missing/added requirement, weight or importance
blocks with a current-parser geometry explanation. This conservative condition
can reject otherwise meaningful historical JDs; no approximation is attempted.

At Compare, the shared adapter runs once. Returned identities must be v1.17 and
v1.21, the same admitted input/authority, and the current taxonomy/registry. Fresh
published requirements must still match admitted parser geometry. The adapter's
unchanged library projection/alias validators establish identical source evidence
and guard all current evidence eligibility rules for both implementations.

The experimental implementation may change coordinated-action decomposition. Its
geometry is compared with the fresh published scope using the same exact fields.
If that geometry differs, **comparative percentages and table/export credits are
withheld**, with an explicit warning. Labels and standalone implementation receipts
remain inspectable; no implied row mapping or numeric delta is calculated. If
geometry agrees, each fresh score is shown only when its own nullable model allows
it. REVIEW_REQUIRED remains null, never zero. A historical-to-fresh numeric delta
is never computed, regardless of geometry.

## What is and is not replayed

Reused: original raw JD, original library record content and ownership, immutable
source/receipt identities, and exact reconciled requirement scope.

Evaluated afresh: deterministic keyword matching, current taxonomy/registry
recognition, v1.17 scoring, and the v1.21 source-aware coordinated evaluator.

Not reproduced: historical v1.16 scoring decisions, historical taxonomy behavior,
model/extraction runs, retrieval configuration, current Application Session or
Phase 8 results, historical aggregate parity, or saved-analysis lifecycle actions.
No old numeric output is relabeled as a new scorer result.

The saved result stays in **Archived historical reference — not reproduced**, with
its original version and identity. The page displays the requested exact label:

> Retrospective diagnostic — original frozen inputs evaluated using current scoring implementations. Does not reproduce or update the saved historical analysis.

v1.22/v1.23 metadata diagnostics remain classification-only **NO-GO**. They do not
filter this request, change eligibility or add scores. Existing native parsing
limitations, including potential footer contamination, remain disclosed rather
than being silently repaired here.

## Files changed in Phase 2C

| File | Change |
|---|---|
| `job_discovery/developer_real_comparison.py` | Explicit retrospective loader around shared authentication; separate current raw-parser request; historical/current geometry and output-identity checks; mode-aware stale validation and sanitized selected export. Strict loader remains the default with its original checks. |
| `job_discovery/developer_comparison_ui.py` | Admission selector, explicit retrospective label and current-report warning, archived reference, comparative withholding for different geometry. Existing explicit Browse/Load/Compare and native filter/multiselect/details retained. |
| `tests/test_retrospective_comparison.py` | Synthetic historical packet admission, actual pipeline/source equality and null controls, geometry/schema/identity corruption, mode separation, read-only AppTest and explicit rerender behavior. |
| This report | Contracts, limitations, copied-database admission check, test results and manual procedure. |

Existing Phase 2/2B changes, tests and reports are preserved. `app.py` and the
unrelated `coordinated_batch_dashboard_review.md` retain their Phase 2B hashes.
Production scorer/parser/policy, version constants, taxonomy/registry, database
managers, shared comparison/projection adapters, synthetic controller/batch UI and
historical fixture/oracle files were not edited.

## Copied development database admission check

Only the explicitly authorized copy at
`C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver\data\applications.db`
was inspected with `mode=ro`, `query_only=ON` and a read transaction. The separate
original production database and backup files were not opened.

For application **#152**, actual retrospective **Load** succeeded:

* Five original library records, 17 archived rows.
* Original versions retained as v1.16 / taxonomy v1.5 / registry v1.3.
* Fresh request uses an empty raw-parser seed, current v1.17 / taxonomy v1.6 /
  registry v1.3 identities, with v1.21 selected by the unchanged comparator.
* Exact requirement identities, importance and allocation reconcile.
* The changed current application report is detected and excluded.
* Copied-database size and modification time remain unchanged.

Only counts, booleans, version identifiers and admission status were emitted. No
raw JD/résumé/evidence/contact data was printed, exported or added to tests. The
copied database was **not scored** during this check: the user must explicitly
press Compare in the UI. No claim is made yet about #152's fresh labels, numeric
scores, experimental geometry or agreement with its historical result.

## Privacy, state and persistence

Both modes retain the existing default-OFF environment flag, per-session consent,
explicit browsing, selected application, Load and Compare actions. Mode/application
changes clear the prior loaded/result pair. Source/code changes, including later
current-report edits, force explicit reload. Before and after scoring, source
identity is rechecked. Filtering, selection, details and downloads do not score.
One loaded/result pair is retained in session memory; no shared real-data cache
or persistence route is introduced. The early read-only developer entry still
bypasses ordinary application startup/migrations and document/sidebar loading.

Selected real summary exports remain allowlisted: IDs, labels, allocations,
eligible credits, version/fingerprint identity and retrospective semantics. They
exclude raw wording, current/private reports, evidence text, source URLs, contacts,
environment and full database/receipts. Historical numeric delta is explicitly
null; geometry-incompatible comparative credits are null and clearly marked as
withheld. Full standalone receipts are local on-demand UI details, not exports.

## Focused tests

Initial 14 retrospective tests passed in 57.041 seconds. Final verification adds
three output/mode guards and reruns all 173 existing focused regressions. The tests
use synthetic disposable historical handoffs only; old-version labels in admission
fixtures are not reconstructed v1.16 numeric oracles. An independent E04 conflict
control checks actual current pipeline quarantine and null aggregate behavior.
The compatible-geometry presentation control is explicitly a test double, not a
claim about independent v1.21 scoring correctness.

**Final result: 190 focused tests passed**, zero failures/errors/skips. All 173
existing controls were retained and rerun alongside 17 new retrospective controls.

| Final run | Result | Time |
|---|---|---|
| Retrospective, Phase 2B, real/synthetic comparison and batch UI | 83/83 PASS | 270.362 s |
| Related application, cache, source, persistence and historical fixture contracts | 107/107 PASS | 138.381 s |

Git working/staged whitespace checks passed, as did trailing-whitespace checks for
the new files. Protected paths show no Git diff. Existing app-entry and unrelated
review-file hashes remain unchanged. No existing oracle or assertion was edited.

Commands, using the supported Python 3.13 runtime and strict offline launcher:

```powershell
$testPython = 'venv/evidence-completeness-runtime/environment/Scripts/python.exe'
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2c_retrospective tests.test_retrospective_comparison
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2c_ui_regression tests.test_retrospective_comparison tests.test_frozen_handoff_compatibility tests.test_developer_real_comparison tests.test_developer_comparison tests.test_developer_batch_audit
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2c_contract_regression tests.test_application_session_first_analysis_binding tests.test_application_session_analysis_currentness tests.test_initial_analysis_explainer tests.test_shared_application_session_identity tests.test_job_finder_v17_batch_ui tests.test_job_match_batch_matching tests.test_analysis_cache_manager tests.test_phase8_score_explainability tests.test_coordinated_job_match_preview tests.test_coordinated_library_sources tests.test_historical_source_fixtures tests.test_predicate_historical_fixtures
git diff --check
git diff --cached --check
```

No full CI or quick/full project suite was run. Offline guards remain unchanged.

## Manual verification with #152

1. Use the copied development database only. Pause other local writers so a
   before/after check is meaningful; record local database hashes/counts and saved
   analysis IDs/scores through read-only tooling. Do not upload those private data.
2. Restart the existing local Streamlit process from this worktree with
   `JOB_AI_DEVELOPER_COMPARISON=1`, using the existing supported interpreter and
   `-m streamlit run app.py --server.port 8503` (or a free local port). Enter directly
   at `http://127.0.0.1:8503/?developer_comparison=1` to bypass normal startup.
3. Opt in, **Browse saved applications**, select #152. The default **Strict
   current-version comparison** must still block its changed/legacy report.
4. Select **Retrospective Frozen Evidence Comparison**, then explicitly **Load
   saved comparison inputs**. Verify five originals, 17 rows, old and fresh
   versions, reconciled geometry and the current-report exclusion warning.
   Expand the archived reference; its v1.16/v1.5 result must remain separately labeled.
5. Click **Compare loaded application**. Verify fresh v1.17 and v1.21 identities.
   Inspect a selected requirement's current capability/source/action receipts.
   Do not infer a numeric improvement over the old result. If the fresh
   decomposition differs, comparative metrics and credits must be unavailable.
   If REVIEW_REQUIRED occurs, its contribution/aggregate remains null, not zero.
6. Filter/select/expand/rerender without pressing Compare. Retained results must
   remain unchanged and must not rescore. Optional selected summary export must
   omit private wording and all historical numeric deltas. Switching back to strict
   mode clears the retrospective pair; disabling consent clears loaded state.
7. Recheck the copied database and saved IDs/scores before leaving Diagnostics.
   No refresh, Save, cache activation, override clearing, new analysis history or
   Phase 8 action should have occurred. Normal application pages retain their
   original behavior; do not run their write actions as part of this smoke check.

## Verdict

Input admission for #152: **PASS**. Strict legacy rejection remains intact.
Retrospective mode: **READY for user-run manual comparison**. Fresh numeric results
are not claimed before explicit Compare.
Production scorer promotion, ranking/persistence activation, historical score
reproduction and broader document-session support: **NO**.
