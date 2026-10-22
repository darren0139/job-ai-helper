# Phase 2F — unresolved requirements and evidence relevance

## Outcome

One independently supported bounded semantic recovery gap was reproduced and
corrected **only in a separate opt-in experimental v1.24 preview**. The existing
approved attention-to-detail WEAK quality proxy is discarded by native recovery
when lexical overlap is zero, even for an original authored quality activity.
Published v1.17 and existing experimental v1.21 remain unchanged.

For application #152, only `req_193aa89d8bb0` changes NONE → WEAK. Overall alignment
remains **12%**. Thirteen other NONE decisions remain unchanged: six requirements
are unsupported within this frozen packet, seven require scope/policy review.
No claim is made that unresolved identities imply false negatives or that the
candidate lacks experience outside the authorized snapshot.

**Scoring promotion: NO-GO.** This is a reviewable bounded experimental correction,
not production activation, automatic taxonomy expansion or a new dashboard.

## 1. Verified baseline and source authority

Repository: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `feat/job-match-unresolved-relevance-v1`.
Initial HEAD: `788db03b90c55241cd43a54604f94205bccc6452` (committed Phase 2E checkpoint); parent `9d539af` includes
Phases 2–2D.1. Initial working tree had only unrelated untracked
`coordinated_batch_dashboard_review.md`, preserved unchanged.

The existing `developer_real_comparison.load_retrospective` admitted #152's sealed
original Job Finder handoff: source job **493**, snapshot **44**, five original
library records, 17 canonical requirements. Original v1.16/taxonomy v1.5 output
remains an archived reference; fresh v1.17/taxonomy v1.6 and v1.21 are evaluated
against the same frozen source. The modified current application report is not
used. No current evidence-library query or document-authority substitution occurs.

Read-only inspection used only this worktree's copied `data/applications.db`,
through `mode=ro`, `PRAGMA query_only=ON` and read transactions. Process audit
guards denied other database connections, filesystem writes, network/socket
operations, subprocesses and private configuration reads. Complete database
SHA-256 was identical before/after each diagnostic. The separate production
repository/database was never opened. Automated tests use disposable synthetic
inputs only. Private original claims were inspected locally as necessary; this
report does not reproduce résumé text, titles, contact details or documents.

Verified baseline on these inputs: published v1.17 and experimental v1.21 each
12%, DIRECT 1, TRANSFERABLE 1, WEAK 1, NONE 14, REVIEW_REQUIRED 0. Thirteen NONE rows
have unresolved capability identities; the attention-to-detail row is resolved.
All five original library records have indexed/projected content. The old 164/170
unobservable pair histories were a limitation of retained receipts, not proof
that the matcher had skipped those records.

## 2. Existing fixtures, provenance and historical expectations

| Artifact | Availability and interpretation |
|---|---|
| `reports/unresolved_independent_review_packet_v5.json` | Present, ignored, 38 cases, native seal valid; prior immutable tracked manifest pins its complete bytes. Blinded pending review material, not 38 approved gold decisions. |
| `reports/unresolved_semantic_layer1_evidence_relevance_v1.json` | Present, ignored, four cases, native seal valid; bytes match prior tracked pin. Report-only relevance candidates, explicitly not claim/scoring authorization. |
| `reports/unresolved_gold_review_packet_v4.json` and local preparation companions | Available; the frozen semantic tests load their exact cases successfully. No missing local prerequisite blocked those checks. |
| `tests/fixtures/unresolved_adjudication_benchmark_v1.json`, `v2.json` | Tracked reviewed accounting/validator fixtures, preserved; no new human decisions imported. |
| `tests/fixtures/predicate_investigation_v2/{report,manifest,provenance}.json` | Tracked authenticated historical artifact pair/provenance, preserved; pins include the two reports above. |
| `tests/test_unresolved_independent_review_v5.py` | Current-source tests use explicit disposable authored unit artifacts. They test real review validators, not newly recovered historical results or human gold. |
| `tests/test_unresolved_semantic_evidence.py` | Pure semantic controls and historical frozen report tests. One historical protected-source assertion is stale against today's tree; see below. |

Complete report hashes, unchanged:

- V5 packet: `ee08555df22ef5f29d0e103cb1dba78efec92beb719a252f5e71ecab4069bf7c`.
- Semantic report: `d8d5327ed93d05cc215b3ea263684ee66a6ab88db2f905d80d9cb2bd58d1493d`.

Both match the existing committed `predicate_investigation_v2/manifest.json`
protected hash references. Native canonical sealing uses the existing fingerprint
function with compact sorted JSON; neither artifact was resealed/regenerated.

**Pre-existing failure:** before the scoring correction, 31/32 unresolved/semantic
checks passed. The one failure was
`FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged`:
it compares an old v1.16-era protected source map with the current repository.
It is an obsolete current-source equality expectation, not evidence that this
phase corrupted the historical report. Report bytes and its native seal remain
valid. The assertion was not disabled, rewritten, regenerated or weakened. Its
historical/current test separation needs a separate deliberate repair; no full-CI
success is claimed here.

## 3. Native root-cause observation

Existing entry points remain:

- `stable_evidence_scoring.canonicalise_requirements`: IDs, importance, provenance,
  parent geometry; production resolver and technology registry provide identities.
- `build_resume_evidence_index`, `_best_resume_evidence`,
  `build_deterministic_keyword_match`, `link_requirement_matches`: indexed
  candidates, actual comparisons and lexical weak gates.
- `_evidence_source_is_requirement_compatible`: native source restrictions.
- `capability_taxonomy._evaluate_capability_record`: approved capability tiers.
- `_apply_capability_single_row_reselection`, taxonomy caps and
  `_apply_capability_none_recovery`: final native ceilings/recovery.
- `coordinated_integration`: original-record P3/AND ownership, conflict quarantine
  and null aggregate behavior. These remain untouched.

The new `native_evidence_observation.observe` is a small explicit current-thread
observer around the existing comparison. It uses Python tracing at checked native
function/branch locations, without replacing functions, modifying frame locals,
changing caller inputs or inserting candidate decisions. It captures actual
candidate comparison values, native weak-gate results, capability evaluations and
the executed zero-overlap recovery rejection branch. It restores tracing even
on failure and refuses to replace an existing debugger/coverage tracer.

Observation is developer-gated, deterministic, bounded to 20,000 retained events,
and carries dropped-event/error counts, input and implementation identities.
Source/text are represented by fingerprints; exact single-original ownership is
attached from the replay-verified projection. Ambiguous owners remain unattributed.
These are **fresh observed executions**, not reconstruction of historical events.
No UI, model, network, database writer or general research framework was added.

On #152 the observer captured **11,376 events**, zero errors and zero drops.
Every NONE requirement had **81 distinct indexed candidate occurrences actually
compared**, across the five original library records. This is not 81 projects or
81 independent supporting claims. It disproves whole-record candidate omission
for those indexed occurrences; unsupported metadata is not silently promoted.

For the priority cases:

| Requirement | Actual native observation | Independent relevance judgment |
|---|---|---|
| `req_26d895b9a27f` | Best observed candidate owner 4; score 0.521333, focus coverage 0.20, overlap 2. Actual WEAK gate rejects coverage below 0.25. | Requirement explicitly includes collaboration **and** specifying/designing/building/maintaining applications. A collaboration/integration claim is relevant but does not prove that complete lifecycle. Do not relax coverage or collapse the obligation to generic teamwork. |
| `req_dbfa330d23eb` | All indexed comparisons have zero score/overlap; no positive lexical candidate and no weak gate evaluation. | Frozen records do not explicitly establish diagnosing/troubleshooting issues. Building software or applying security policies is not troubleshooting proof. |
| `req_52969cf18afc` | Best observed owner 6; score 0.18, coverage 0.20, overlap 1; actual weak gate fails. | An application storing/generating reports or letters does not establish the developer personally authored engineering documentation. |
| `req_c3b362e0255b` | Indexed comparisons zero; identity unresolved and no native semantic recovery route. | Original database-backed implementation is relevant to basic knowledge. Broad SQL/NoSQL scope and credit policy are not resolved by mapping it to database **design** or guessing an OR. Relevant activity is not automatically full claim support. |
| `req_193aa89d8bb0` | Native capability evaluation returns WEAK / `deterministic_quality_proxy_capped_at_weak` for original owner 2, then the actual zero-overlap branch rejects it (coverage 0, overlap 0). | Existing approved quality proxy applies to an authored technical quality activity, with a WEAK ceiling. This is the one confirmed bounded semantic-recovery gap. |

Observed score/coverage here are actual candidate comparison values, unlike the
retained keyword-link coverage of 1.0 discussed in Phase 2E. A maximum of zero
does not identify a selected best record; zero-score ties are not presented as
native accepted choices. Threshold absence is not reported as threshold failure.

## 4. All fourteen verdicts

Verdicts concern this exact frozen packet and exact obligation, not the
candidate's overall competence. AMBIGUOUS means relevant evidence or unresolved
scope/credit contracts require review; it does not relabel NONE as numeric WEAK.

| Requirement ID / verified scope | Verdict | Root classification and disposition |
|---|---|---|
| `req_d8a925b5b34e` — project objectives/role | AMBIGUOUS_REQUIRES_REVIEW | Relevant delivered team projects, but broad role/training scope and generic collaboration identity are not governed. Native lexical coverage 0.1111, overlap 1; unchanged NONE. |
| `req_4731e7fdb9f1` — project manager, technical lead, architect | CONFIRMED_UNSUPPORTED | Named-role collaboration is absent; generic teamwork is not those specific counterparties. Unchanged NONE. |
| `req_26d895b9a27f` — collaboration plus full lifecycle | AMBIGUOUS_REQUIRES_REVIEW | Relevant collaboration, incomplete specified lifecycle; actual coverage gate failure, not retrieval omission. Unchanged NONE. |
| `req_dbfa330d23eb` — analysis/troubleshooting | CONFIRMED_UNSUPPORTED | No original troubleshooting claim; no inference from programming or RLS. Unchanged NONE. |
| `req_52969cf18afc` — documentation/reporting | CONFIRMED_UNSUPPORTED | App functionality versus the candidate's engineering-document authorship are different activities. Unchanged NONE. |
| `req_30482086845a` — continuous improvement/best practices | AMBIGUOUS_REQUIRES_REVIEW | CI/workflow improvements are relevant, but broad ongoing-practice claim lacks an approved scope/credit rule. Unchanged NONE. |
| `req_ff55125c928e` — staying current with industry | CONFIRMED_UNSUPPORTED | Tool use does not establish ongoing industry monitoring. Unchanged NONE. |
| `req_c3b362e0255b` — database knowledge, SQL/NoSQL | AMBIGUOUS_REQUIRES_REVIEW | Real relational database activity; unresolved broad/alternative scope and knowledge contract. No automatic database-design identity or aggregation of separate claims. Unchanged NONE. |
| `req_67c5d07c55c1` — named frameworks | AMBIGUOUS_REQUIRES_REVIEW | React activity is relevant; Angular/Node and list scope are not established. ReactJS is already an approved React alias, so adding another alias is not a justified fix for the complete requirement. Unchanged NONE. |
| `req_73ffb410c613` — engineering concepts and Agile | AMBIGUOUS_REQUIRES_REVIEW | Software work does not independently prove Agile; GitHub/CI is not Agile ownership. Unchanged NONE. |
| `req_74e080b49b36` — learning quickly | CONFIRMED_UNSUPPORTED | Several technologies do not establish speed of learning. Unchanged NONE. |
| `req_ba468f2924d8` — effective team player | AMBIGUOUS_REQUIRES_REVIEW | Concrete teamwork exists, but generic teamwork/effectiveness credit lacks a governed identity; do not map same-function collaboration to cross-functional/stakeholder capability. Unchanged NONE. |
| `req_b57c19e5162c` — critical/analytical/creative problem solving | CONFIRMED_UNSUPPORTED | No explicit grounded trait claim; technical project descriptions alone do not prove all these attributes. Unchanged NONE. |
| `req_193aa89d8bb0` — attention to detail/quality | CONFIRMED_FALSE_NEGATIVE | Approved WEAK quality activity blocked by lexical zero-overlap recovery guard. Corrected only in opt-in v1.24. |

Totals: **1 confirmed bounded false negative, 6 unsupported, 7 ambiguous, 0 left
solely NOT_OBSERVABLE** in this fresh review. These are agent review findings,
not newly imported independent-human gold. Canonical identity resolution itself
was not shown to misclassify any of the 13 unresolved rows. Several need a
legitimate missing scope contract; that does not authorize taxonomy expansion.

## 5. Minimal experimental correction

New identity: `stable-evidence-v1.24-phase6d28`.
Policy: `owned-quality-proxy-semantic-recovery-v1`.
Namespace: `developer-evidence-relevance-v1`.
Base: unchanged explicitly evaluated v1.21.

`evidence_relevance_preview.evaluate` requires explicit developer consent and a
current original-source request. It clones a validated v1.21 result; it never
mutates the published/base outputs. It changes only a NONE row that:

1. Resolves through the existing canonical `quality.attention_detail` definition,
   has no accepted evidence, no coordinated receipt and no applied taxonomy cap.
2. Is a complete, finite attention-to-detail trait requirement, including every
   contributing original parent. No lost mandatory action or compound obligation
   can be recovered as a generic quality trait.
3. Has one indexed original project/experience **bullet**, with exactly one
   verified library owner and an affirmative authored technical quality activity.
4. Satisfies the existing taxonomy WEAK tier/reason. Only its approved specific
   goals (RLS, access control, data integrity, pipeline consistency) are eligible;
   generic review/audit/tool listings are not enough.
   The quality goal must be the affirmative action's immediate object in the
   same clause; unrelated implementation verbs cannot borrow later quality words.
5. Has no scoped contradictory/uncertain source, third-party claim or unscoped
   extra raw input. Other records may veto, never supply missing positive proof.

The new label cannot exceed WEAK (existing 0.2 / strength 2). No lexical threshold
is lowered. This is a versioned semantic exception to the zero-overlap gate,
requiring an already-approved named proxy plus stricter ownership/activity proof.
It is a policy choice for review, not a claim the old guard failed to execute its
code. The original guard remains intact, including the unrelated configuration/
troubleshooting zero-overlap regression.

All identities, importance, parents and fractions are conserved. Existing native
alignment arithmetic recalculates the preview; any other REVIEW_REQUIRED parent
keeps whole-JD scores null. New fingerprint material includes request, base,
policy, version and exact changed source receipts. v1.22/v1.23 stay classification-
only NO-GO. The existing preview persistence guard additionally rejects v1.24,
including bare version-only packets whose development flags were stripped.

## 6. Identical-input before/after

| Metric | Published v1.17 | Existing v1.21 | Separate v1.24 |
|---|---:|---:|---:|
| Alignment | 12% | 12% | 12% |
| DIRECT | 1 | 1 | 1 |
| TRANSFERABLE | 1 | 1 | 1 |
| WEAK | 1 | 1 | 2 |
| NONE | 14 | 14 | 13 |
| REVIEW_REQUIRED | 0 | 0 | 0 |
| Required/core coverage | 5 | 5 | 5 |
| Preferred coverage | 18 | 18 | 21 |
| Evidence strength | 67 | 67 | 60 |

The sole changed requirement is `req_193aa89d8bb0`, NONE → WEAK, citing original
library record **2**, `description.lines[1]`, structured source
`resume_profile.projects[1].bullets[1]`. Its actual source-reference fingerprint:
`67d453a10b5f0b152a1088121bfef366d18eef1530749ef35bfb2e3040a4e028`.
The verified original occurrence is `libocc_6bff6d1164176901f603`; its receipt hash
is `018d6e76317c57324b34c3af2f0c5585061ba8da2241ff121603e06a1a622123`.
No other record is combined to prove this trait proxy. The evidence supports an
authored access-security quality activity, not custom API authorship or a DIRECT
personality claim. No raw private claim text is copied into this report.
This matches an attributable saved assertion under the existing evidence policy;
it is not an independent audit of SQL policies or the real implementation.

All other requirement labels and accepted sources remain unchanged; all 17 row
identities/weights reconcile exactly. Evidence strength decreases because the
existing arithmetic averages strength over positive matches, now including an
additional WEAK match. The unchanged rounded 12% is not a failure or success
metric; the individually justified disposition is what changed.

## 7. Exact file changes

| File | Change |
|---|---|
| `job_discovery/native_evidence_observation.py` | New bounded opt-in observer at actual native comparison, threshold and recovery decision points. |
| `job_discovery/evidence_relevance_preview.py` | New separate gated v1.24 quality-proxy correction with original-source and full-scope guards. |
| `analysis_stability/coordinated_runtime.py` | Add v1.24 to existing preview persistence rejection identities; no default gate or scoring behavior changes. |
| `tests/test_evidence_relevance_preview.py` | Independent authored positives/negatives, parity, scope/ownership, observation, deterministic identity, withholding and persistence tests. |
| This report | Baseline, fixture inventory, actual root causes, verdicts, before/after and release decision. |

No published scorer, canonical parser, taxonomy/registry, numerical threshold,
Job Finder/Application Session/Phase 8 UI, saved data, historical report, review
oracle or existing test assertion was changed. No staging, commit, push, merge,
reset, cleanup or branch switch.

## 8. Verification

Supported Python 3.13, strict offline launcher, disposable synthetic test inputs:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2f_baseline_benchmarks tests.test_unresolved_semantic_evidence tests.test_unresolved_independent_review_v5
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2f_targeted tests.test_evidence_relevance_preview
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2f_regressions tests.test_evidence_relevance_preview tests.test_capability_none_recovery tests.test_capability_taxonomy_v1_4_single_row_reselection tests.test_api_evidence_completeness tests.test_coordinated_library_sources tests.test_coordinated_job_match_preview tests.test_technology_identity_remediation tests.test_unresolved_independent_review_v5 tests.test_unresolved_semantic_evidence.SemanticEvidenceTests tests.test_predicate_historical_fixtures
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2f_integration tests.test_developer_real_comparison tests.test_retrospective_comparison tests.test_frozen_handoff_compatibility tests.test_comparison_debug_dashboard tests.test_evidence_decision_trace tests.test_coordinated_action_implementation tests.test_evidence_relevance_preview.RelevancePreviewTests.test_other_review_required_parent_keeps_whole_jd_unavailable
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/phase2f_final_predicate tests.test_evidence_relevance_preview
git diff --check
git diff --cached --check
```

- Baseline research checks: **31 passed, 1 pre-existing historical hash assertion
  failed** (32 total, 30.833 s), before the correction. See section 2.
- Initial new correction/observer controls: **9/9 PASS**, 27.132 s.
- Relevance, recovery/reselection, API, source ownership, knowledge identity,
  current-source review and historical-byte validators: **98/98 PASS**, 119.145 s.
- Existing real/retrospective UI, source admission, export, trace, coordinated
  constraints and new cross-parent withholding: **97/97 PASS**, 362.746 s,
  including hash-pinned published parity on all 30 historical JDs.
- After tightening direct action/goal ownership and adding unrelated-verb and
  third-party controls: **10/10 PASS**, 36.086 s. These repeat the new correction
  tests against the final predicate, including the added REVIEW_REQUIRED case.
- The copied-database comparison was repeated after that final predicate change:
  the same sole NONE → WEAK result, 12%/12%/12%, unchanged database bytes.
- Working and staged Git whitespace checks passed; new files also passed a direct
  trailing-whitespace scan. The staging area remains empty.

The original QueryAI generic `data` → DSA false-positive regression and the
unrelated zero-overlap configuration proxy stay rejected. New tests also reject
language-only evidence, generated-report functionality, bare quality listings,
plans, negation, third-party work and cross-bullet fabricated support. No full
project CI was run; the known historical failure remains visible.

## 9. Release decision and next integration steps

**NO-GO for scoring promotion or persistence.** The experimental correction is
ready for bounded review with the focused checks above; production remains v1.17,
developer comparison remains v1.21. No application UI automatically selects v1.24.

The smallest next decision is to independently approve or reject this one
WEAK-ceiling quality exception, including ownership/negation/compound controls.
Other ambiguous claims require explicit scope/credit contracts; do not map them
to unrelated existing capabilities merely to resolve identity counts. The stale
historical/current protected-hash assertion needs a separate compatibility repair
without altering original report bytes or expectations.

For Job Finder, integrate only an approved version with a distinct cache/current-
ness identity and migration decision. For Initial Analysis, require the existing
authoritative document/JD adapter; a frozen Job Finder library comparison is not
an Application Session result. For Phase 8, preserve independently verified before/
after evidence and its existing score explanations. Reuse the current requirement
and source receipts; no new dashboard or cross-authority numeric comparison is
needed. Until those approvals, rollback is simply using unchanged v1.17/v1.21
and discarding the nonpersistent v1.24 packet.
