# Taxonomy Maintenance v1

## Stale candidate binding / grouped Human Review checkpoint

The real network-access-control refresh failure was reproduced read-only on
2026-10-09. Current candidate `tqd3taxgap_939ade7db57775706ff8f67d` has fingerprint
`939ade7db57775706ff8f67d981a3686f025a9a47cc17b564eb4246f5a112ba4`.
All three historical attempts embed candidate
`tqd3taxgap_b20d0f278bf7de04d30c1e3d` and fingerprint
`b20d0f278bf7de04d30c1e3d608b340c8d93488ee2ad50e41819c52b4e435f55`.
The most recent applicable historical result is
`tqd3h1_19884c4d1f80959711396c54` (2026-10-07T09:57:21.682523+00:00).
The precise failing comparison is `candidate.current_versions`: historical
`scoring_version=stable-evidence-v1.11-phase6d17`,
`match_contract_version=job-match-snapshot-v2.2.0` and its composite
`match_version` differ from current v1.14 / v2.3. Taxonomy v1.5, registry v1.2,
knowledge fingerprint and source-authority fingerprint are unchanged. A fresh
audit therefore could not repair the old record passed directly to refresh.

The native `re_evaluate_saved_evidence` now accepts an explicit current candidate.
Its original no-current-candidate path retains strict currentness. Rebinding
validates historical record/candidate/raw-evidence integrity, verifies compatible
canonical scope and overlapping source provenance, validates the current
candidate, builds a current native target/plan, and runs the unchanged native
interpreter. The refreshed result must pass full current result validation.
Raw provider evidence/request ID remain unchanged; old result/candidate IDs are
recorded in interpretation lineage. Persistence uses the existing immutable
cache/store and appends a normal unapproved result; no schema, draft, approval,
publication, scoring or knowledge change is introduced.

`maintenance_service.build_review_targets` anchors compatible attempts to current
audit candidates. Canonical concept/normalized scope, route, concrete entity
identity, explicit identity/mapping fields and source lineage distinguish groups;
display text alone never merges records. A valid current interpretation is primary
when available, otherwise the newest intact applicable attempt is primary.
Ambiguous/missing bindings stay diagnostics-only with a precise lineage blocker.
Human Review renders one primary option per group and read-only history expanders.
Refresh consumes the current audit candidate, not the historical candidate.
No provider plan displays actionable Human Review text instead of an empty table.
Successful local refresh invalidates the old displayed plan; subsequent preview
uses freshly computed native readiness rather than snapshot-era research status.

Real saved-evidence reinterpretation against a fresh job-163 audit now returns
`research_more` / "Authoritative definition/boundaries not sufficiently established"
under current versions, with zero provider calls. That real-data check used
`persist=False`; the production review-store hash was unchanged. Native persistence
and the full UI click/rerender path were verified in temporary fake-provider stores,
including three historical attempts -> one primary -> three preserved historical
attempts plus one refreshed result. A live browser click remains for UI retest.

138 distinct focused tests passed across these targeted runs (local Python 3.14.4;
temporary fixtures required approved elevated execution):

```text
.venv/Scripts/python.exe -B -m unittest tests.test_taxonomy_maintenance_service tests.test_taxonomy_maintenance_ui tests.test_tqd3_governed_research -q
.venv/Scripts/python.exe -B -m unittest tests.test_taxonomy_maintenance_service tests.test_taxonomy_maintenance_ui tests.test_tqd3_bulk_candidate_operations tests.test_tqd3_h1_1 tests.test_tqd3_h1_2 -q
.venv/Scripts/python.exe -B -m unittest tests.test_taxonomy_maintenance_service.MaintenanceServiceTests.test_refresh_rejects_incompatible_lineage_and_stale_current_context tests.test_taxonomy_maintenance_service.MaintenanceServiceTests.test_ambiguous_current_lineage_remains_diagnostics_only tests.test_tqd3_explicit_publication -q
.venv/Scripts/python.exe -B -m unittest tests.test_taxonomy_maintenance_service tests.test_taxonomy_maintenance_ui -q
.venv/Scripts/python.exe -B -m unittest tests.test_taxonomy_maintenance_service.MaintenanceServiceTests.test_current_candidate_rebinds_old_versions_and_preserves_all_attempts -q
.venv/Scripts/python.exe -B -m unittest tests.test_taxonomy_maintenance_service.MaintenanceServiceTests.test_review_grouping_uses_canonical_namespace_not_display_text tests.test_taxonomy_maintenance_ui.MaintenanceUITests.test_distinct_canonical_namespaces_have_distinguishable_read_only_options -v
.venv/Scripts/python.exe -B -m scripts.check_phase9e_blueprint_selection
```

Initial new fixture failures were diagnosed without relaxing guards: historical
fixtures must simulate both native version consumers, and distinct canonical
identities must have distinct source contexts to satisfy existing duplicate-call
prevention. One before/after preview assertion was placed before refresh and was
corrected to assert stale before, current after. The affected individual tests
passed after those corrections; already-green unrelated groups were not repeated.

Read-only real job-566 replay still reports NONE / 23 under
`stable-evidence-v1.14-phase6d20`; its database hash is unchanged. Phase 9E smoke
reports 61. Taxonomy/registry hashes match the preceding checkpoint. Changed-file
AST parsing and `git diff --check` passed. No full CI, real provider/model call,
production knowledge mutation, automatic approval/publication, commit or push.

The secondary **Taxonomy Maintenance** navigation page operates the existing
taxonomy system. Ordinary Job Match, scoring formulas, importance policy,
taxonomy files, registry files, and production versions are unchanged.

## Architecture reuse

| Existing component | Responsibility | Maintenance adapter |
| --- | --- | --- |
| `regression_corpus.export_saved_corpus` | Latest stored snapshots with hash-matched JD text and frozen evidence | Stored corpus scope; optional selected job IDs |
| `regression_corpus.replay_current_corpus` | Offline production matcher/scorer replay | Current-code audit baseline; candidate ranking/cap receipts |
| `corpus_gap_resolution.audit_corpus_resolution` | Consolidation, operational routes, meaningful denominator, coverage, native triage priorities | Summary and consolidated queue, without new clustering |
| `corpus_gap_resolution._route_requirement_keys`, `_weight`, `_integrated_ranking` | Native parent/child provenance, importance allocation, ranking | Provenance, diagnostic impact, and before/after ranks |
| `bulk_candidate_operations.build_candidate_queue` | Production identity/resolution, readiness, saved research/review/publication state | Current queue diagnostics |
| `bulk_candidate_operations.prepare_bulk_plan`, `execute_bulk_plan` | Bounded cache-first governed research with explicit execution | Exact plan preview and separate confirmed research action |
| `bulk_candidate_operations.create_bulk_drafts` | Native proposal contracts, no approval | Structured human capability fields; explicit draft creation |
| `bulk_candidate_operations.preview_bulk_regression` | Per-item and supported combined temporary overlays | Candidate validation; no second scoring engine |
| `taxonomy_discovery_review_manager` | Persisted raw research, drafts, regression, human decisions | Read-only reload; explicit preview/decision persistence |
| `governed_publication.prepare_publication`, `publish_approved_change` | Exact approved draft, source authority, regression and publication guards | Additional audit-currentness guard; explicit singleton publication |
| `current_match_versions`, native `fingerprint` | Production version and content identity | Audit/validation manifest and staleness |

`maintenance_service.py` translates existing operational routes into presentation
fix layers. `maintenance_ui.py` owns widgets and session receipts, not domain
semantics. Evidence-policy rows come from native maintenance triage. Filtered
source prose remains a separate native parsing/noise diagnostic. Ambiguous
technical concepts retain MANUAL_REVIEW; they are not promoted to capability gaps.

## Workflow

1. Explicitly run a stored or uploaded frozen corpus audit. Audit results remain
   in the current session; page load, filters, and rerenders do not rerun scoring.
2. Inspect coverage, fix-layer counts, native parsing exclusions, and independent
   Job Match Health. Inspect exact contributing requirement IDs and provenance.
3. Build a deterministic, bounded tranche (default 5; maximum 20) from actual
   capability gaps. No candidates/research records are persisted. Existing
   backlog items remain references. Published, rejected, deferred, compound,
   identity, relationship, evidence-policy, parser and noise rows are excluded.
4. Select targets and preview the exact native research plan/budget, then
   explicitly confirm research. Native readiness, provider controls, caching,
   call ceilings and persistence remain authoritative.
5. Inspect persisted evidence. Define bounded capability and evidence predicates
   through structured fields, then explicitly prepare a native draft. Definitions,
   aliases and relationships are not silently derived or approved by this page.
6. Preview the saved draft for human review. This is necessary because existing
   approval requires a saved regression. Save a separate named human decision.
7. Validate approved, unpublished drafts against the same frozen corpus and
   current production baseline. Native temporary overlays report requirement,
   score, rank, cap/rejection and duplicate-credit receipts. Newly DIRECT rows
   carry overlap/compound/negation/child-provenance review warnings; broad cloud
   mappings require contextual review. Production canaries also run inside the
   overlay. Failed canaries block publication.
8. Publish only after fresh native preflight, current exact validation and an
   explicit fingerprint-bound confirmation. Nothing is published during audits,
   research, draft preparation, approval or validation.
9. Export a ZIP containing summary, consolidated JSON/CSV, tranche, validation,
   manifest and Markdown debug summary. Provider request payloads embedded in
   drafts are excluded from the validation export. Before/after evidence receipts
   remain available. Exports exist in memory until downloaded by the user.

## Snapshot/currentness contract

The audit-only schema version does not replace production versioning. The
manifest records timestamp, Git HEAD, production match/scoring/taxonomy/registry
versions, native content fingerprints, knowledge-file SHA256s, source-authority
fingerprint, relevant implementation hashes, source corpus identity and job IDs,
and replayed corpus identity. Validation additionally pins exact draft and native
regression fingerprints. Artifacts are sealed with the existing fingerprint
function; altered artifacts fail closed.

Stored audits check the current stored corpus/evidence identity. Frozen uploads
remain pinned to their uploaded inputs. Relevant implementation, knowledge,
authority, HEAD or corpus changes mark the snapshot stale. Missing frozen inputs,
an empty corpus and incomplete production replay block tranche/research/validation
and publication. Inspection and export of stale historical receipts remain possible.

## Boundaries and limitations

Targeted correction checkpoint (2026-10-09, local Python 3.14.4):
194 distinct focused tests passed. The following module commands were executed
with `.venv/Scripts/python.exe -B`, `LITELLM_LOCAL_MODEL_COST_MAP=True`,
and `CAPABILITY_RAG_MODE=off`; only fake providers and
isolated test databases were used:

```text
-m unittest tests.test_taxonomy_maintenance_service tests.test_taxonomy_maintenance_ui -q
-m unittest tests.test_taxonomy_offline_execution -q
-m unittest tests.test_tqd3_regression_corpus tests.test_tqd3_governed_research tests.test_tqd3_taxonomy_evolution tests.test_tqd3_corpus_coverage tests.test_tqd3_corpus_expansion tests.test_tqd3_bulk_candidate_operations tests.test_tqd3_research_readiness tests.test_taxonomy_discovery_triage -q
-m unittest tests.test_taxonomy_maintenance_service tests.test_taxonomy_maintenance_ui tests.test_taxonomy_offline_execution tests.test_tqd3_h1_2 tests.test_tqd3_explicit_publication tests.test_capability_none_recovery -q
-m unittest tests.test_taxonomy_maintenance_service.MaintenanceServiceTests.test_tranche_exclusions_and_bulk_routing_are_read_only tests.test_taxonomy_maintenance_service.MaintenanceServiceTests.test_tranche_is_deterministic_bounded_and_actual_gaps_only tests.test_taxonomy_maintenance_ui.MaintenanceUITests.test_excluded_candidates_are_inspectable_and_bulk_routing_stays_local -q
-m scripts.check_tqd3_discovery_workflow_consolidation
-m scripts.check_phase9e_blueprint_selection
```

The first combined maintenance run had one outdated primary-layer assertion;
it was replaced with assertions preserving the native primary layer and checking
the new secondary decomposition hold. A new stale-research test initially used
current insufficient evidence; it now changes its temporary authority fixture
to exercise genuine staleness. Final targeted runs pass. Default sandbox temp
permissions prevented fixture setup; focused fixture runs used approved elevated
execution. No full CI/project gate was run.

Read-only replay of real job 566 confirms `req_86d57d2e033d` remains NONE and
score 23. Phase 9E smoke confirms score 61; scorer remains
`stable-evidence-v1.14-phase6d20`. The production database hash was unchanged by
that replay; taxonomy and registry hashes match the prior checkpoint. Changed
Python files passed AST parsing; `git diff --check` passed.

Applying only the maintenance boundary to the supplied 12-row review export
yields 6 ready, 5 decomposition, 1 fix-layer review. Before top five: network
access control; critical-infrastructure security sentence; data analysis and
insights; CMS/web/cloud deployment sentence; FPGA/DSP/RF integration sentence.
After top five: network access control; data analysis and insights; microservices
architecture; cloud security; distributed systems. This compares the supplied
queue order, not a new full-corpus replay. Existing network-access-control
research remains stale/refresh with zero provider calls; readiness of a concept
does not imply executable or sufficient-authority research.

### Explicit research and maintenance routing correction

Audits, snapshot replay, regression overlays and publication refresh now share
`offline_execution`: a context-local network ban with overlap-safe restoration
of the original socket transport and retrieval mode. Overlapping process-wide
`mock.patch` scopes previously could leave an audit socket mock installed after
completion. Snapshot/tranche JSON carries provenance, not network policy.
Explicit maintenance research enters a fresh context and calls the existing
governed bulk executor/provider, preserving independent network restrictions.
An abandoned legacy audit mock is reported as blocked (restart Streamlit); it is
never removed to bypass a restriction. Preview also checks configured credentials
without a provider request. Production execution requires the exact confirmed
preview fingerprint and rechecks eligibility/configuration before any write/call.

Native fix layers are preserved. Actual capability gaps receive a secondary
maintenance-only boundary: `RESEARCH_READY`, `NEEDS_DECOMPOSITION`, or
`REVIEW_FIX_LAYER`. The adapter reuses native requirement decomposition, semantic
eligibility and research atomicity/readiness. Sentence-sized scopes (over seven
words) are conservatively held for normalization, even when native decomposition
cannot establish a safe split. Conjoined multiword scopes are also held for
decomposition review; generic descriptor/skill statements need fix-layer
review. These holds are review hints, not automatic child creation or knowledge.
Only ready concepts enter the default tranche. Excluded concepts and their
reasons remain visible. Bulk review routing is deterministic, sealed and confined
to the current session; it does not modify saved candidates or research state.

Operations show running/completion/failure status, with no fabricated percentage.
Audit clicks reuse the same current session snapshot for identical scope/inputs;
an in-flight action is deduplicated. Source, evidence, code, authority or knowledge
changes invalidate that reuse through existing currentness checks. Research plans
show executable, stale/refresh and blocked selections separately. Failed research
receipts display failure, not success. Human Review labels new, stale, blocked and
historical results, selecting newly completed results first. Stale authority can
be explicitly reinterpreted via the existing local saved-evidence refresh API;
unsupported stale knowledge fails closed. Refresh never repeats provider work,
creates drafts, approves or publishes.

- Research requires configured provider credentials and a separate user action.
  Development/tests use fake transports; no live research is necessary.
- Existing insufficient-authority backlog findings remain unpublishable.
- Native combined overlays support capability tranches. Other artifact families
  require singleton validation; unsupported combinations fail closed.
- Publication is singleton through the existing contract. Atomic multi-proposal
  publication is not invented. A publication changes knowledge identity, so the
  next publication needs refreshed currentness/review as required by native guards.
- First audit and controlled validation replay production scoring and can be slow
  on a large corpus. No repeated replay occurs during ordinary filtering/rerenders.
  Only exact session receipts are retained; no incomplete-key global cache exists.
- Diagnostics warn and expose evidence receipts; they do not invent evidence or
  treat a score increase as correctness. Human evidence-boundary review remains
  required.

## Focused validation

Run the new service and AppTest modules, plus directly related corpus-gap, bulk,
governed-research, taxonomy-evolution, regression-corpus, triage and currentness
modules. Discovery/triage CLI smokes must use their read-only snapshot loader
when run against production data; their ordinary legacy loader initializes schema.
Do not run providers, approve real drafts or publish real knowledge for validation.
