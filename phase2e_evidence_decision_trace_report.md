# Phase 2E — Evidence Decision Trace

## Pre-implementation dependency map

Verified before implementation: branch `feat/job-match-evidence-decision-trace-v1`
at `9d539af`, also the parent branch checkpoint. Phase 2–2D.1 is tracked and
committed. Only unrelated `coordinated_batch_dashboard_review.md` is untracked.

| Native decision | Location and retained evidence |
|---|---|
| Input admission/currentness | `developer_real_comparison.load/load_retrospective/require_current/evaluate`; sealed original handoff, current report excluded, strict/retrospective isolated. |
| Projection/ownership | `coordinated_sources.build_library_projection/verified_projection_ledger`; original fields, occurrence identities, structured/raw aliases and unindexed coverage. |
| Canonical geometry | `stable_evidence_scoring.canonicalise_requirements`; importance, parent fractions and capability identities in canonical rows. Gated geometry uses `coordinated_integration.canonicalise_coordinated_requirements`. |
| Index and lexical proposal | `build_resume_evidence_index/build_deterministic_keyword_match`; deterministic keyword selection is invoked by `coordinated_preview.run_comparison`. Ordinary rejected-candidate history is not retained. |
| Linking/validation | `link_requirement_matches/apply_structured_requirement_matches/validate_linked_matches`; final row metrics/warnings are partial observations, not an all-candidate trace. |
| Reselection | `_apply_capability_single_row_reselection`; only successful stronger-single-row selection receipts retained, including coverage/overlap and original/selected evidence. Missing audit does not mean no attempt. |
| Taxonomy ceiling | `apply_taxonomy_caps_to_requirements`; existing row validation fields/receipts, not an inferred ceiling from final NONE. |
| NONE recovery | `_apply_capability_none_recovery`; successful single-original recovery receipt with metrics and taxonomy reason; unsuccessful candidates are not retained. |
| Coordinated completeness | `coordinated_integration.build_coordinated_analysis/_evaluate_row`; original-index proofs, compatibility events, capped stage labels, R1 exclusion and scoped conflict receipt. |
| Null aggregates | `coordinated_preview_model.analysis_view` validates REVIEW_REQUIRED null credit and whole-JD withholding. Trace must only read these outputs. |

The taxonomy ceiling adapter is
`tailoring.phase6d_stable_scoring_adapter.cap_requirement_with_taxonomy`, called
through `apply_taxonomy_caps_to_requirements`. The trace reads retained outcomes;
it never invokes that evaluator again.

## Implementation and observability

`job_discovery/evidence_decision_trace.py` is a pure diagnostic projection of a
current comparison request and its retained outputs. It replays the existing
verified source projection and rebuilds the existing native **index only** to
map exact source/section/text/evidence-ID occurrences to original library owners.
It does not run keyword matching, source eligibility, a taxonomy evaluator,
recovery, reselection or either scorer. It does not mutate caller objects.

The explicit UI Build action retains one trace per input in session memory.
Requirement selection follows the existing checkbox IDs; a record selector shows
each original record's stages. A local reviewer can explicitly annotate an
attributable requirement/record pair using the requested review categories.
Annotations are not approvals, scoring expectations or policy changes and are
never written to application tables or included in the default bundle.
Real and synthetic traces have separate widget/state namespaces. No batch
scoring or independent expectations changed.

**Native instrumentation added: none.** Existing successful recovery/reselection
receipts and coordinated proof/event objects are reused. The index projection is
labeled reconstructed source coverage, not a historical log of every matching
iteration. The trace is intentionally **PARTIAL**. Ordinary unsuccessful native
candidate histories, failed thresholds and unsuccessful recovery/reselection
attempts were not retained, so they remain `NOT_OBSERVABLE`.

Known statuses are `SOURCE_AVAILABLE`, `SOURCE_NOT_PROJECTED`,
`SOURCE_NOT_INDEXED`, `CANDIDATE_CONSIDERED`,
`NATIVE_COMPATIBILITY_FILTER_REJECTED`, `EVIDENCE_ACCEPTED`,
`ACTION_PROOF_EVALUATED`, `ACTION_PROOF_INCOMPLETE`,
`ADMISSION_REVIEW_REQUIRED`, `RECOVERY_ATTEMPTED`, `RESELECTION_ATTEMPTED`
and `NOT_OBSERVABLE`. A compatibility rejection means an observed native filter
event for an attributable occurrence/stage. It does not mean every occurrence in
that library record was rejected or that the whole record cannot be selected.

No exhaustive considered/rejected/not-evaluated totals are invented. Observed
counts are lower bounds, separately labeled. Final unselected records are not
called rejected. Proof evaluation is distinguished from matching consideration.
Successful selected references prove consideration; a missing audit does not
prove an attempt was skipped. Ambiguous multi-owner aliases are left unattributed,
rather than assigning acceptance to every text-identical original record.
An unresolved accepted owner makes total admitted/unselected record counts null;
the number of independently attributed owners remains a separately named count.
It never becomes zero admissions or multiple invented acceptances.

Retained native validation-warning codes use a fixed allowlist, with unknown
codes masked. The native link-source enum is separate from final disposition.
A recovery identity reference uses retained final NONE fields and the existing
native identity guard, without rerunning eligibility or claiming an attempt. It
is not applied to coordinated receipts or positive rows whose prior state cannot
be safely reconstructed.

The actual configured native weak thresholds are exposed as a separate reference
(`0.28` score, `0.25` coverage, `2` overlap), read from existing constants.
Their role explicitly says **CONFIGURED_ONLY_NOT_PROOF_OF_EVALUATION**.
Pair-level evaluated thresholds and candidate scores remain null when no native
decision retained them. Recovery/reselection coverage and overlap are copied only
from their successful receipts. Final row `match_coverage`/`match_overlap_count`
are not candidate scores: lexical linking stores coverage against a selected
keyword row, which may itself be a **missing** JD keyword. A value of `1.0` does
not demonstrate matching résumé evidence.

The main and record tables use native Streamlit controls and explicit unknown
states. Large native details stay collapsed. Scorer-null contributions remain
null; incompatible decompositions retain absent-side statuses and do not acquire
invented row counterparts. Standalone receipt contributions are labeled as such,
not cross-geometry score deltas. The existing score withholding UI is unchanged.

## Source authority and privacy

The real loader remains the existing strict or retrospective handoff loader.
Trace input identities are current request identities, never application-ID-only
cache keys. A stale/mutated projection, incompatible authority/version or altered
receipt view is rejected. No newer library, current application report, document
authority or Phase 8 adapter was introduced. Source changes clear retained real
trace/review/private state through the existing invalidation path.

Default exports retain only original numeric library IDs, hashed occurrence and
source-reference identities, canonical IDs, allowlisted native capability IDs,
bounded reason/status enums, numeric metrics and receipt hashes. No raw JD,
evidence, source paths, names, arbitrary metadata, contact fields, environment or
exception payloads are included. Native free-text reason identities are hashed;
local native explanations remain inside collapsed inspection. IDs/hashes are
linkable integrity references, not an anonymity guarantee.

A **separate** original-candidate consent checkbox and Preview action expose one
chosen original record's excerpts and selected requirement wording locally. The
preview explicitly distinguishes original candidates from accepted-only excerpts:
not selected does not mean rejected. It requires exact IDs and current source
verification and clears on pair/source/consent changes. Nothing automatically
exports all original wording. There is no guaranteed redaction claim.

The share-safe ZIP preserves the original eight members and adds:

- `evidence_decision_matrix.csv`: exact requirement/side/library-ID join keys,
  source-reference hashes, coverage and observable decisions.
- `evidence_decision_trace.json`: input and implementation identities, native
  row/record observations, action events, successful audits, nullable summaries
  and explicit limitations.
- `trace_coverage.json`: partial coverage counts and unavailable-stage flags.

All ten payloads are covered by manifest byte counts and SHA-256; ZIP ordering and
timestamps remain deterministic. The existing 16 MiB export bound remains.
The trace has a 20,000 requirement/record/side pair bound. Exceeding that bound
reports trace UNAVAILABLE while preserving the original debug export. Safe
comparison-failure bundles still contain the original eight members because no
evaluated trace exists; no fake empty-JD result is introduced.

## Actual #152 copied-development-database check

An explicit agent diagnostic used only
`C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver\data\applications.db`.
The existing loader used `mode=ro`, `PRAGMA query_only=ON` and read transactions.
An additional process-local SQLite authorizer denied writes/DDL/attach, and audit
hooks denied all other database connections, filesystem writes, network/socket
access, subprocesses and private configuration reads. No automated test used
this database. Its complete SHA-256 was equal before and after the diagnostic.
No private text or raw exception was printed or persisted.

Verified source job **493**, snapshot **44**, current application report excluded,
five original records and 17 comparable requirements. Both fresh implementations
again return **12%** with DIRECT 1, TRANSFERABLE 1, WEAK 1, NONE 14 and
REVIEW_REQUIRED 0; required/core 5, preferred 18 and evidence strength 67.
No whole-JD score is withheld. These are fresh frozen-input diagnostics, not a
historical score replay or current Application Session result.

All five records have at least one projected/indexed original occurrence. This
rules out wholesale loss of a library record in this input; it does **not** prove
every original field is indexed, or every indexed record was reached for every
requirement. There are 170 requirement/side/record pairs. Only six pair
considerations are proved by final acceptance (three positive requirements on
two sides); 164 pair consideration histories remain unobservable.

The 13 unresolved NONE rows do not meet the current native recovery identity
precondition: a nonempty capability ID resolved through canonical taxonomy. This
restricts the available recovery path; it does not prove recognition was wrong
or qualifying evidence exists. The attention-to-detail row meets that identity
precondition, which alone establishes neither full eligibility nor its missing
attempt/rejection history.

The 14 NONE rows agree on both sides. Every one has zero accepted records,
no successful recovery/reselection receipt and no observed applied taxonomy
ceiling. Each has all five records represented by source coverage:

| Requirement ID | Importance | Capability resolution | Applied cap |
|---|---|---|---|
| `req_193aa89d8bb0` | preferred | `quality.attention_detail` | No (`not_needed`) |
| `req_26d895b9a27f` | core | unresolved | No (`unrecognised`) |
| `req_30482086845a` | supporting | unresolved | No (`unrecognised`) |
| `req_4731e7fdb9f1` | supporting | unresolved | No (`unrecognised`) |
| `req_52969cf18afc` | core | unresolved | No (`unrecognised`) |
| `req_67c5d07c55c1` | preferred | unresolved | No (`unrecognised`) |
| `req_73ffb410c613` | preferred | unresolved | No (`unrecognised`) |
| `req_74e080b49b36` | supporting | unresolved | No (`unrecognised`) |
| `req_b57c19e5162c` | preferred | unresolved | No (`unrecognised`) |
| `req_ba468f2924d8` | supporting | unresolved | No (`unrecognised`) |
| `req_c3b362e0255b` | preferred | unresolved | No (`unrecognised`) |
| `req_d8a925b5b34e` | supporting | unresolved | No (`unrecognised`) |
| `req_dbfa330d23eb` | core | unresolved | No (`unrecognised`) |
| `req_ff55125c928e` | supporting | unresolved | No (`unrecognised`) |

Positive controls: `req_09f08d68e520` DIRECT (`fullstack.integration`) and
`req_3f3b3d88b57d` WEAK (`quality.qa_testing`) each have an authentic successful
NONE recovery receipt. Their retained earlier cap status is `applied`; it must
not be interpreted as their terminal recovery label. `req_cfc6614dce69` is
TRANSFERABLE with an accepted original reference despite unresolved capability
identity. Thus unresolved capability alone is not proof of rejection.
All positive source references mapped to single verified owners, with no
unattributed accepted references.

**Independent false-negative verdict: insufficient trace to determine for all
14.** The known outputs narrow the issue to native selection/eligibility and
possibly recognition/coverage, but cannot distinguish a legitimate unsupported
claim from a missed candidate or overly restrictive threshold. No classification
was changed. Collaboration, troubleshooting, documentation and SQL/NoSQL remain
review candidates only. The original frozen records and retained local reasons
must be independently inspected pair by pair; evidence from current résumé or
Application Session must not be substituted.

## Exact files changed

| File | Change |
|---|---|
| `job_discovery/evidence_decision_trace.py` | New bounded pure trace and explicit private original-pair projection. |
| `job_discovery/evidence_trace_ui.py` | New native explicit trace, cached record inspection, local pair annotation and separate private preview. |
| `job_discovery/developer_review_ui.py` | Render real trace below selected requirement review; clear its state on invalidation. |
| `job_discovery/developer_comparison_ui.py` | Render trace for authorized synthetic inputs with isolated keys; clear synthetic state when unavailable/OFF. |
| `job_discovery/developer_debug_export.py` | Add trace projections to explicit report/ZIP; preserve existing payloads and failure behavior. |
| `app.py` | Clear both trace namespaces in the existing default-OFF branch. |
| `tests/test_evidence_decision_trace.py` | New parity, ownership, observability, audit, threshold, privacy, bounds, UI and ZIP controls. |
| `tests/test_comparison_debug_dashboard.py` | Update only bundle-member expectation from eight to the authorized eleven; existing integrity assertions retained. |
| This report | Dependency map, observed #152 results, verification and limitations. |

Production scoring, all policies/constants/taxonomy/parsers, admission controller,
Job Finder/Application Session/Phase 8 algorithms, persistence and independent
scoring oracles are unchanged. Unrelated untracked review is preserved.

## Verification

Initial 24 trace/export controls passed (120.082 s). That run exposed automatic
Arrow conversion warnings from mixed boolean/status columns; the native display
now formats those status columns consistently as strings. No assertions were
weakened. A final bounded-export preservation control was added afterward.

Commands:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2e_initial tests.test_evidence_decision_trace tests.test_comparison_debug_dashboard
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2e_final_ui tests.test_evidence_decision_trace tests.test_comparison_debug_dashboard tests.test_developer_real_comparison tests.test_retrospective_comparison tests.test_frozen_handoff_compatibility tests.test_developer_comparison tests.test_developer_batch_audit
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2e_final_policies tests.test_coordinated_library_sources tests.test_coordinated_job_match_preview tests.test_capability_none_recovery tests.test_capability_taxonomy_v1_4_single_row_reselection tests.test_api_evidence_completeness
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2e_receipt_followup tests.test_evidence_decision_trace tests.test_comparison_debug_dashboard.DebugDashboardTests.test_share_safe_report_omits_arbitrary_private_payloads tests.test_comparison_debug_dashboard.DebugDashboardTests.test_zip_files_csv_json_hashes_and_determinism
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2e_attribution_followup tests.test_evidence_decision_trace.TraceTests.test_ambiguous_original_owner_is_unknown_not_zero_or_multiple_acceptances tests.test_evidence_decision_trace.TraceTests.test_pure_trace_preserves_both_scorers_and_all_identities tests.test_evidence_decision_trace.TraceTests.test_explicit_ui_cached_inspection_review_and_private_consent
git diff --check
git diff --cached --check
```

Policy/provenance regression result: **43/43 PASS** (63.886 s).
UI/admission/export regression result: **108/108 PASS** (423.690 s).
After adding native warning/identity-reference fields, focused follow-up:
**13/13 PASS** (51.447 s). Final ambiguous-ownership/null-count, scorer parity and
native UI follow-up: **3/3 PASS** (37.615 s). Across those runs, **153 distinct
focused tests passed**; follow-ups repeat relevant prior controls after changes.
No full CI was run.

Working and staged Git whitespace checks passed; new files passed a direct
trailing-whitespace scan. Protected production directories, native scorers,
taxonomy/registry, historical fixtures and original-source controller have no
diff from HEAD. The controller retains SHA-256
`b9c8239c1192faa5ed7b0eb34cd0f7a6f5340ff62e5ec6afee947cf68641d190`.
Unrelated dashboard review retains SHA-256
`5a17ea791dbb78c7b21ea52bce6a8978f4553b4adb2c43fb5c3a0a150778d0bf`.

## Manual smoke test

1. Restart the development app with the existing developer flag explicitly set.
   Open its read-only developer entry; select retrospective mode and #152.
2. Explicitly Load and Compare. Verify 12%/12%, 17 rows and unchanged five-record
   frozen authority. Current report and historical archived output stay separate.
3. Tick one NONE row. Build retained evidence trace explicitly. Inspect all five
   original records and compare observed versus unknown stages. Native final
   keyword metrics must not be read as candidate evidence scores.
4. Inspect the DIRECT, TRANSFERABLE and WEAK controls above. For the recovered
   controls inspect successful recovery metrics. Missing reselection audit stays
   NOT_OBSERVABLE, not false.
5. Change selected requirement/record/filter. No scorer or trace rebuild runs.
   Save a local review only deliberately; this cannot relabel evidence or save an
   application. Source/mode changes invalidate state.
6. If wording is needed, use the separate original-candidate consent and Preview
   for one attributable record. Accepted-only and original-candidate excerpts are
   distinctly labeled. Opt out and verify the preview disappears.
7. Export Comparison Debug. Inspect all eleven members and all ten payload hashes;
   CSV/JSON trace joins and source identities must agree. No private excerpt or
   review annotation belongs in the share-safe ZIP.
8. Verify the synthetic trace and batch functionality still work independently.
   Disable developer consent/flag and verify cached trace/private state clears.
   Confirm development database bytes and saved scores are unchanged.

## Verdict and limitations

| Check | Verdict |
|---|---|
| Source integrity | **PASS** |
| Native scorer parity | **PASS** |
| Per-requirement decision trace | **PARTIAL** — authenticated observations, not exhaustive native candidate history. |
| Rejected-evidence attribution | **PARTIAL** — attributable native filter events where retained; ordinary unsuccessful candidates unknown. |
| Recovery/reselection visibility | **PARTIAL** — authentic successful receipts, identity precondition references; unsuccessful attempts unknown. |
| Debug ZIP integrity | **PASS** |
| No automatic rescoring | **PASS** |
| No database writes | **PASS** |
| Ready for manual application #152 review | **YES** |
| Ready for production scorer promotion | **NO** |

This delivers a usable trustworthy partial trace, not a complete explanation of
all fourteen NONE decisions or an independent certification of their correctness.
The next review should use the new local pair inspector and original-candidate
preview to identify independently justified suspected misses. If unsuccessful
candidate metrics are needed, a separate bounded opt-in observer at native
decision points is still required; it must preserve parity and original-record
ownership. Do not infer or promote labels from missing traces.

No stage, commit, push, merge, branch switch, reset or cleanup was performed.
