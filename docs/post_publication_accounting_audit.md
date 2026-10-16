# Post-publication Job Match accounting audit

Target: EDB discovered job 146, historical snapshot 40, current saved snapshot
56, `req_9270e95898c8`, **Design and develop RESTful APIs**. Offline audit;
no Job Match refresh or live snapshot repair was performed.

## A. The empty table was a different subset, not missing identities

`taxonomy_discovery/coverage_presentation.py::render_jd_taxonomy_status` rendered
three independent fields consecutively: the `technology_identity_resolved`
counter, `st.write(view['breakdown'])`, then `st.dataframe(view['routes'])`.
`jd_coverage` derives the native counter from saved canonical `knowledge_status`.
But `breakdown` and `routes` belong to reviewed **unresolved-remediation
destinations**, supplied by a compatible maintenance audit/addressability plan.
They are not the technology-identity ledger.

The native-only path intentionally returns `breakdown={}`, `routes=[]` and
`reviewed_accounting=False`. A partial compatible positive-proof review can
also have zero route rows. Rendering those values without a category or empty
state produced the observed `{}` and `empty` table. There was no serialization
failure or lost C#/JavaScript identity. The exact live browser-session review
receipt was not captured; the read-only snapshot/native path reproduces the
reported 7/7, two identities and zero review routes exactly.

The persisted identity sources are:

| Requirement ID | Text | Native state | Saved technology ID |
|---|---|---|---|
| `req_951a4d36e0a9` | C# | TECHNOLOGY_IDENTITY_RESOLVED | `csharp` |
| `req_eda71746c01c` | JavaScript | TECHNOLOGY_IDENTITY_RESOLVED | `javascript` |

Their IDs, labels and matched aliases are recorded in `knowledge_resolution`
and `technology_registry_resolution`. No registry re-query is needed.

The renamed **Advanced / this JD's knowledge accounting** expander now shows
separate readable identity and capability ledgers. Reviewed unresolved routes
have their own heading, explanation and destination/count columns. Zero route
rows produce an explicit message, not an empty dataframe. No reviewed route,
proof or capability relationship is invented to fill an empty category.

## B. The summary reclassified final rows with an older classifier

Execution order is:

1. `job_discovery.matching::_default_stable_builder` invokes the shared
   deterministic `build_stable_analysis` after JD extraction.
2. The scorer applies `apply_taxonomy_caps_to_requirements`. The production
   resolver exhausts ordinary knowledge and then the approved bounded fallback.
   The adapter pins `capability_recognition_rule`, native taxonomy version,
   capability and knowledge resolution into the canonical row.
3. `_apply_capability_none_recovery` evaluates evidence for that resolved
   capability; the final canonical row is DIRECT.
4. `matching::summarize_stable_match` calls
   `observations::build_taxonomy_resolution_diagnostics` on the **completed**
   stable analysis, derives ranking quality, then persists both structures via
   `save_job_match_snapshot`.

The diagnostics builder called `classify_requirement_record`, an older
canonical classifier that intentionally does not implement the new fallback.
It honored pinned registry resolutions but omitted the final native bounded
fallback. Thus it reclassified the API row as unresolved after the scorer had
already resolved it. The summary row's existing `match_label=direct` confirms
that this was not an earlier execution stage or stale pre-scoring intermediate.

The correction reuses `classify_requirement_fallback_diagnostics` only when
the final native row pins the matching rule, capability, canonical source,
resolved knowledge status, and matching analysis/row/native taxonomy versions.
It rechecks the same bounded scope. Arbitrary capability hints, missing or
edited rule receipts, old knowledge versions and compound/negative scope do
not obtain new resolution. The summary now includes an explicit accounting
stage marker. Registry behavior, requirement recognition and evidence rules
are unchanged.

Only `req_9270e95898c8` changes resolution in the read-only snapshot-56 summary
derivation. The original canonical rows, source provenance, eligibility flags,
parent allocations, evidence and score are unchanged.

| Accounting | Saved snapshot 56 | Corrected derivation |
|---|---:|---:|
| Eligible canonical items | 43 | 43 |
| Capability resolved | 6 | 7 |
| Not capability resolved | 37 | 36 |
| Overall ranking coverage | 18/128 = 14.0625% | 21/128 = 16.40625% |
| Required/core ranking coverage | 18/127 = 14.173228% | 21/127 = 16.535433% |
| Rounded ranking display | 14% / 14% | 16% / 17% |
| Ranking eligible | false | false |
| Deterministic alignment score | 20 | 20 |

The approved fallback should contribute: it is a final, native,
score-eligible capability resolution, the same classification the existing
ranking contract counts. The ranking engine, importance weights, 65% overall
and 75% important thresholds, minimum count and denominator logic were not
changed. It already sums importance weights over canonical eligible rows;
this ranking denominator is distinct from scorer parent-allocation weighting.

The corrected numerator can affect future generated ranking quality, including
its existing provisional-sort tie-breaker. Other near-threshold jobs could also
change eligibility after authorized regeneration. No live jobs were refreshed,
no new ranking was persisted, and no corpus-wide rank change is claimed.

**Snapshots 40 and 56 were not rewritten.** Snapshot 56 still contains its old
6/37 summary. Newly constructed summaries use the correction. Job Finder now
explains the saved ranking denominator and flags disagreements with final
canonical decisions without silently recalculating the historical receipt.
No cache invalidation, version migration or automatic refresh was introduced.

## C. DIRECT is allowed by the existing policy, but is stronger than the text

Selected evidence `ev_3e06933c2432`,
`resume_profile.projects[1].bullets[1]`:

> Implemented backend data access through PostgREST and applied Row-Level Security policies to secure database operations.

The native evaluator follows this unchanged chain:

- `backend.api_development`'s named-protocol completeness guard accepts
  `postgrest` as supporting the requested REST protocol. It does not imply gRPC.
- Its DIRECT evidence tier accepts one action from **built, implemented,
  developed, created, integrated**, together with an API term such as
  **api, endpoint, web service, fastapi, postgrest**. This row matches
  **implemented + postgrest**, yielding `explicit_backend_api_implementation`.
- The none-recovery selector ranks a DIRECT decision above `none` even with
  zero lexical overlap. Positive overlap is required for WEAK recovery, not
  DIRECT. It selects one source row and does not combine evidence rows.

The source explicitly supports backend data-access implementation through
PostgREST and RLS. It does **not explicitly establish authored API endpoints,
API design, request validation, interface contracts or endpoint testing**.
Thus DIRECT is mechanically consistent with the current broad capability tier,
but potentially over-credits the more specific design/develop requirement.
This is a requirement/evidence-policy granularity concern, not proof that the
candidate lacks API ability or that other project evidence was omitted.
The statement is source-recorded implementation evidence, not independently
verified implementation or a fresh project/code audit.

Offline hypothetical probes (not candidate evidence or human gold) demonstrate
the boundary: **Integrated an existing PostgREST interface for data retrieval;
no API endpoints were designed or developed** also receives DIRECT. An explicit
authored-endpoint statement receives DIRECT, while a bare PostgREST skills
listing receives NONE. Exact probe outputs are in the JSON audit.

The current contribution is **3.536296** overall points: 2.823530 coverage plus
0.712766 evidence points. No label/value, source, eligibility or contribution
was changed. v1.6 only enabled requirement recognition; it did not publish a
new evidence tier. Recognition made this existing broad evidence rule reachable.

Recommendation for **separate approval**: a bounded requirement-specific
evidence-completeness review distinguishing API authoring from consumption or
integration of an existing interface, including explicit non-authoring
negatives. Decide the appropriate weaker label only after that review; retain
legitimate API-only recoveries and the REST/gRPC completeness controls. Do not
globally disable capability-none recovery or require token overlap for all
semantically valid evidence. No such policy change was implemented here.

## D. Coverage scope

Snapshot 56 has **43 canonical items: 7 capability resolved, 2 identity-only,
34 unresolved**. Confirmed coverage is **7 / (7 + 0 currently proven gaps)**,
not 43/43. The other **36** items include both identity-only and unresolved
items; they are not 36 proven taxonomy gaps. The UI explicitly states that
the confirmed subset covers **7 of 43** saved analysis items, keeps native
identities separate, and labels independent reviewed destinations separately.

Ranking retains all 43 score-eligible rows and its existing importance-weighted
capability denominator. Its 36 corrected not-capability-resolved rows include
the two identity-only requirements. It is a different metric from confirmed
taxonomy coverage, not a contradiction of 7/7.

## Validation, files and safety

Changed production files:

- `taxonomy_discovery/observations.py`: pinned fallback accounting reconciliation.
- `taxonomy_discovery/coverage_presentation.py`: native detail ledgers, distinct
  reviewed-route category, meaningful empty state and confirmed-subset messaging.
- `job_discovery/ui.py`: saved ranking denominator and discrepancy explanation.

Test changes:

- `tests/test_post_publication_accounting.py`,
  `tests/post_publication_accounting_harness.py`,
  `tests/fixtures/post_publication_accounting_snapshot56.json`: disposable
  regression fixture, native scorer/summary consistency, ranking, UI counters,
  C#/JavaScript, empty categories, serialization and historical-record controls.
  The fixture is a read-only JD/native-field projection; other resume evidence
  was removed. Only the explicitly audited source quotation is retained.
- `tests/test_per_jd_taxonomy_status.py`: scope its existing v1.5 historical
  receipts to the fixed v1.5 fixture. The v1.6 currentness failures were stale
  fixture setup, not relaxed production currentness checks.
- `tests/governed_review_fixtures.py`: scope and restore the A/B module's
  imported taxonomy-path alias too. Otherwise a first import during a temporary
  taxonomy scope could retain a deleted fixture path in subsequent tests.

The focused run passed **123/123 tests**, no failures/errors/skips, in 56.374
seconds. Exact module names and output are in
`reports/post_publication_accounting_tests.json` and `.log`. No project gate,
full discovery, live research, models, embeddings or network was run.
After the final defensive metadata guard, the affected accounting/observation/
ranking tests were rerun; their result is recorded with the final checkpoint.
That final affected rerun passed **25/25 tests** in 4.654 seconds.

The real snapshot-56 UI passed a read-only AppTest: 7 capability rows, two
identity rows, confirmed 7-of-43 caption, no empty table or JSON, explicit zero
review-route message, and passive rerender. All parent/provenance/evidence/
eligibility fields remain identical after deriving the summary. Disposable
database round-trip tests preserve both corrected and old stored structures.

The before/after hash manifests protect the live v1.6 taxonomy, registry,
scorer, adapter, resolver, scope policy, publication code, snapshot manager and
both live databases. Per-snapshot serialized hashes for 40 and 56 are in
`reports/post_publication_accounting_audit.json`. No live database, snapshot,
publication record, knowledge artifact or scoring policy was modified.
All **11 protected before/after hashes match**, and AST/whitespace checks plus
`git diff --check` passed.

Artifacts: the JSON audit, test results/log, and protected before/after manifests
under `reports/post_publication_accounting_*`. This handover is the only new
documentation. No commit, push or merge.

## Manual acceptance

1. Open EDB discovered job **146**, saved snapshot **56**, without refreshing it.
2. Under This JD's taxonomy status, confirm 100% is explicitly **7 of 43**
   analysis items, with 36 additional items outside the confirmed subset.
3. Open **Advanced / this JD's knowledge accounting**. Confirm seven readable
   capability rows and C# / `csharp`, JavaScript / `javascript` identity rows.
   Reviewed unresolved routes should explain the zero compatible rows; there
   should be no `{}` or `empty` placeholder table.
4. In selected-job resolution/ranking diagnostics, confirm saved ranking values
   remain historical and the disagreement notice explains the omitted final
   native decision. Do not expect snapshot 56's saved 6/37 summary to be rewritten.
   The corrected 7/36 derivation and 16%/17% projection are in the audit report.
5. Confirm the native API row still has its original selected evidence, DIRECT
   label and 3.536296 contribution. Evidence-policy correction is a separate
   review, not part of this patch.
6. Historical snapshot 40 remains available with its original versions and rows.

Stop for review; do not refresh, republish or migrate saved matches as part of
these acceptance steps.
