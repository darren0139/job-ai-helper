# Phase 2D.1 — debug export importance accuracy

## Finding and bounded correction

Verified repository: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch remains `feat/job-match-real-evidence-comparison-v1`. Existing uncommitted
Phase 2–2D changes and unrelated files were preserved.

The reported defect is confirmed by source inspection. In
`job_discovery/developer_debug_export.py`, `_side()` used a separately duplicated
importance allowlist containing `required`, `core`, `deal_breaker`, `preferred`
and `optional`. It omitted **supporting**. The authoritative published scorer's
`analysis_stability/stable_evidence_scoring.py:IMPORTANCE_WEIGHTS` defines exactly
`deal_breaker`, `required`, `core`, `supporting` and `preferred`. `optional` is not
one of those canonical importance identities.

The native review table previously displayed the raw canonical receipt value;
the JSON diagnostic filtered it through that incorrect list. This explains how
a legitimate `supporting` value could display correctly in the UI and become
`UNRECOGNIZED` in the ZIP. It is an export representation defect, not evidence of
a scoring or weight defect. The reported six occurrences and example
`req_d8a925b5b34e` come from the user's independent inspection; this task did not
open application #152's database or private ZIP.

The new `_importance()` presentation helper accepts exact keys from the existing
`IMPORTANCE_WEIGHTS` contract. Both the main table projection and both diagnostic
sides use it. All five legitimate values survive unchanged. Missing values,
`optional`, case variants such as `Supporting`, unknown strings and private
arbitrary strings become `UNRECOGNIZED`. There is no lowercasing, fallback to a
guessed category, inference from wording or derivation from numeric weight.
Original receipt values remain untouched and available in local raw inspection.

The CSV's existing identity/label/credit schema remains unchanged; importance is
in per-side JSON diagnostics. Bundle membership and schema identity remain
`developer-comparison-debug-v1`; this corrects an existing field without changing
scorer, cache or input-admission identities. The existing implementation revision
fingerprint naturally changes, so reload and compare explicitly after restarting
or updating the running app before exporting again. The previous ZIP is not
rewritten.

## Exact files changed in this phase

| File | Change |
|---|---|
| `job_discovery/developer_debug_export.py` | Reuse authoritative importance keys for JSON diagnostics and the native table projection. |
| `tests/test_comparison_debug_dashboard.py` | Add independent expected-category and unknown-category controls across receipts, table projection, actual native table and serialized bundle. |
| `phase2d1_debug_export_accuracy_report.md` | This report. |

No scorer, taxonomy, parser, weights, evidence selection, Job Finder, Application
Sessions, Phase 8, database, gate default or saved data was modified. No new
matching algorithm or rejected-evidence instrumentation was implemented.

## Focused verification

New presentation fixtures independently specify core, preferred, supporting,
required, deal_breaker and genuinely unknown results. They deliberately vary
receipt importance without rerunning a scorer; they are representation tests,
not synthetic scoring expectations. They verify:

- Exact category preservation and safe unknowns on both implementation sides.
- Actual native editor importance cells and read-only column configuration.
- No changes to authoritative receipt objects and no automatic scoring.
- CSV/JSON ID ordering, labels and credits; whole-report/ZIP diagnostics equality.
- Deterministic serialized bytes, all payload SHA-256 seals and byte lengths.
- Unknown private strings absent from all exported ZIP members.

The existing focused module also covers arbitrary private payload exclusion,
explicit private excerpt consent/preview, receipt identity rejection, null versus
NONE, geometry withholding, source invalidation, checkbox retention, explicit
exports, zero-difference counts and no database writers during export.

Commands (supported Python 3.13, strict offline launcher and disposable SQLite):

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2d1_importance tests.test_comparison_debug_dashboard
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2d1_final tests.test_comparison_debug_dashboard tests.test_developer_real_comparison.RealUITests tests.test_retrospective_comparison.RetrospectiveTests.test_ui_explicit_retrospective_compare_retains_result_and_strict_mode
git diff --check
git diff --cached --check
```

The initial run passed the 13 existing module tests but the two new tests failed
in setup: they incorrectly assumed the coordinated scorer shared every published
requirement ID. They now use the existing explicit identical-geometry presentation
fixture, without changing any assertions or production geometry safeguards.
Final focused results: **19/19 PASS** (85.938 s): all 15 export/dashboard controls,
three existing real UI regressions and the existing strict/retrospective UI
regression. Working and staged Git whitespace checks passed; the changed untracked
files also passed a direct trailing-whitespace scan. No full CI was run.

Protected production directories and historical fixtures have no Git diff from
HEAD. The pre-existing real comparison controller retains SHA-256
`b9c8239c1192faa5ed7b0eb34cd0f7a6f5340ff62e5ec6afee947cf68641d190`;
the unrelated dashboard review retains SHA-256
`5a17ea791dbb78c7b21ea52bce6a8978f4553b4adb2c43fb5c3a0a150778d0bf`.
No real/copied application database or private ZIP was opened in this phase.

## What is still missing for the 14 no-accepted-evidence requirements

The importance correction does **not** explain their evidence labels. Matching
v1.17/v1.21 results only show agreement for the same input. A final NONE label or
`NO_ACCEPTED_SOURCE_SELECTED` does not demonstrate absence of candidate experience.

The default bundle deliberately exports accepted-reference identities, limited
disposition/action summaries and receipt hashes. A hash authenticates an object
but cannot explain its contents. For each of the 14 requirement IDs, an actual
diagnosis still needs the following, under the same frozen source authority:

1. **Grounded requirement semantics:** the original requirement wording and source
   span, canonical focus/capability and technology IDs, mandatory actions and
   importance/allocation. Safe exports currently omit wording and much of the
   capability-resolution reasoning.
2. **Original evidence coverage:** which of the five frozen library records and
   individual original occurrences were actually projected/indexed, their owned
   sections/metadata, and relevant original claim excerpts. The ZIP does not
   contain the full frozen evidence or indexed candidate universe. The frozen
   library is not automatically the current résumé or full Application Session.
3. **Per-record eligibility and rejection reasons:** which original records were
   considered for each requirement, which source/ownership/scope checks excluded
   them, and whether a relevant record was absent, unindexed or rejected. Empty
   accepted references do not distinguish these paths. The optional selected
   excerpt export only includes accepted references, so it cannot expose a
   rejected candidate for a NONE row.
4. **Native decision trace:** initial match source, matched terms, overlap and
   coverage metrics, the applicable existing thresholds and validation warnings,
   plus capability taxonomy ceilings/reasons. The export's receipt fingerprint
   and final label are not a complete trace of these decisions.
5. **Recovery and reselection details:** whether the existing capability NONE
   recovery and single-row reselection paths ran, their eligibility conditions,
   attempted originals and rejection/acceptance reasons. Some successful-path
   audits exist in retained analyses; the share-safe bundle does not project
   those full audits, and successful-only audits do not establish why every
   rejected candidate failed.
6. **Experimental completeness decisions where applicable:** original-record
   action proofs, missing technical modifiers, API authorship/design protections,
   contradiction scope and native-NONE/P3 ceilings. Counts and fingerprints alone
   do not identify the substantive missing or contradicted claim.
7. **Independent reviewed counterexamples:** for a suspected false negative,
   identify the exact requirement and qualifying original claim in one attributable
   frozen record, with a human-justified expected disposition. If the claim exists
   only in a later résumé, current application report or another record, it cannot
   silently replace or combine with the original library evidence.

Smallest next diagnostic step: deliberately inspect the relevant original frozen
records and existing per-row/native recovery/reselection receipts locally, then
produce an explicit per-requirement considered/accepted/rejected evidence matrix
with bounded reason codes and independently reviewed examples. Any additional
trace instrumentation or private rejected excerpts would require a separately
scoped change and explicit privacy controls. Do not infer new labels from this
export defect or increase matching permissiveness. The current task neither
determines which of the 14 are false negatives nor claims the 14 prove absence of
experience.

## Verdict

**PASS — ready to regenerate the diagnostic bundle.** Explicitly reload the
frozen application inputs and compare after the implementation revision changes,
then choose Export Comparison Debug. Verify the previously reported supporting
rows now export their authoritative `supporting` values. This task does not claim
to have regenerated or independently inspected application #152's private output.

Published v1.17 and experimental v1.21 scoring implementations and saved results
remain unchanged. The remaining no-accepted-evidence diagnosis is not resolved by
this display fix. No staging, commit, push or merge was performed.
