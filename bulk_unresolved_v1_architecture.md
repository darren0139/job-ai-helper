# Bulk Unresolved Requirement Resolution V1 — investigation and preview

2026-10-17. Investigation complete; ready for human review. No production recognition,
evidence, scoring or taxonomy policy has been changed or approved.

## Baseline and scope

- Worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
- Verified initial branch: `feat/llm-unresolved-requirement-adjudication-v1`.
- Clean checkpoint HEAD: `d37dbb5231d7211efc7b0c0297a20e34d6f597bf`.
- Its tracking branch was `origin/feat/llm-unresolved-requirement-adjudication-v1`;
  the locally recorded ahead/behind counts were 0/0. No fetch or other network call.
- No staged changes or unmerged entries. The requested branch did not exist locally
  or in the worktree listing. Created `feat/bulk-unresolved-resolution-v1` at that HEAD.
- Current scorer remains `stable-evidence-v1.17-phase6d21`, capability taxonomy
  `phase6d-capability-taxonomy-v1.6`, registry `technology-registry-v1.3`.
- Git needed owner-context access to shared repository metadata to create the
  authorized branch. No other checkout was inspected or modified.
- Only tracked offline fixtures were used. No live database, saved Job Match,
  resume, external source, provider, embedding, Chroma or search call was used.

The companion `bulk_unresolved_v1_inventory.json` contains every primary row,
its current resolution diagnostics, original fixture identity, recorded versions,
available parent/provenance fields, descriptive observations and raw-only comparison.
`bulk_unresolved_v1_preview.json` contains context-local proposal receipts, controls,
timings and the full 799-file before/after SHA-256 ledger. Neither is production data.

## A. Existing architecture and integration points

| Stage | Actual implementation | Boundary relevant to unresolved requirements |
|---|---|---|
| JD extraction | `analyzer.extract_jd_profile`; `job_discovery.matching._default_extract_jd_profile` | The normal extraction path makes initial/review `ask_json` calls. It was inspected, never executed. Original extracted profiles are absent from these fixtures. |
| Raw sections and semantics | `analysis_stability.jd_section_inference.infer_semantic_list_heading`; scorer `_raw_jd_content_spans`, `_raw_jd_requirement_rows`, `classify_jd_statement_semantics` | Headings, introduction/context and qualification cues determine which text becomes a requirement. Filtering and extraction are distinct from capability recognition. |
| Decomposition | Scorer `_split_single_requirement_clause`, `_split_non_preference_clause`, `_split_shared_head_and_list`, `_split_safe_independent_and_pair` | Produces children, parent scope and alternative/coherent-parent decisions. A syntactically split fragment need not be a complete obligation. |
| Canonical identity | Scorer `canonicalise_requirements`, `_canonical_key`, `_stable_id`, `_ground_profile_requirement_to_raw_span` | Merges canonical requirements and retains source-parent occurrences, raw grounding, importance and allocation. Requirement ID is not a complete scope/provenance cache key. |
| Native taxonomy | `tailoring.capability_taxonomy.classify_requirement_diagnostics` | Applies v1.6 any/all/group terms, custom policies, complete named-function scope and guarded contextual phrase variants. Diagnostics expose rejected product-context candidates. |
| Registry | `taxonomy_discovery.technology_registry.resolve_requirement_text`, `_candidate_terms`, `_approved_mapping` | Exact alias after bounded wrapper handling. Only one approved `maps_to_capability` relationship supplies a capability; an identity with no mapping is not expertise. The registry deliberately does not split arbitrary lists here. |
| Identity scope | `tailoring.requirement_scope.technology_identity_scope`, `_identity_provenance`; `phase6d6_structured_matching.technology_requirement_structure` | Requires a complete pure technology scope, authoritative source provenance and correct ALL/ANY semantics. Activity, architecture and mixed obligations cannot be reduced to a token. |
| Bounded native fallback | `classify_requirement_fallback_diagnostics`; `bounded_api_development_scope` | Runs only after earlier native stages leave the row unresolved. v1.6 opts into the finite REST API-development rule, with complete-source boundaries. No general semantic resolver is active. |
| Combined resolver | `tailoring.production_requirement_resolver.resolve_requirement_with_production_knowledge` | Returns `CAPABILITY_RESOLVED`, `TECHNOLOGY_IDENTITY_RESOLVED` or `UNRESOLVED`, plus each stage's diagnostics. It does not persist or calculate a Job Match score. This investigation calls this helper. |
| Evidence and scoring | `phase6d_stable_scoring_adapter.cap_requirement_with_taxonomy`; scorer `link_requirement_matches`, `_apply_capability_single_row_reselection`, `_apply_capability_none_recovery`, `compute_deterministic_alignment`, `build_stable_analysis` | Recognition and candidate credit are separate. Existing evidence caps, source compatibility, protocol completeness, preliminary ceilings and weak-recovery gates still apply. Recognition does not establish candidate evidence. |
| Retrieval | Adapter `build_capability_retrieval_trace` | Candidate suggestions do not establish an approved identity. Investigation retrieval mode is off; no embedding/vector access. |
| Unresolved semantic proposals | `unresolved_adjudication.build_input`, `prompt_for`, `validate_response`, `run_cases`; providers module | Native resolution runs first. Bounded candidates and exact source spans constrain report-only proposals. Invalid responses become UNKNOWN. `run_cases` needs explicit execution/transport and is not a native resolver fallback. No calls were made. |
| Discovery and triage | `observations.build_taxonomy_resolution_diagnostics`, `build_unresolved_observations`, `aggregate_unresolved_observations`; `triage.enrich_discovery_report`; `unresolved_multidimensional_triage.predicate_observations`; `taxonomy_gaps.aggregate_corpus_gaps` | Existing exact observation aggregation and overlapping diagnostic dimensions are reusable. Plural-term observations are explicitly not native classifications or independent gold. A taxonomy-oriented unresolved count can also differ from full technology-identity status. |
| Governance | `governed_requirement_resolution.diagnostic_view`; `governed_research.research_plan`, `create_draft`, `temporary_impact`; `resolver_improvement.resolver_overlay`; `governed_publication.prepare_publication`, `publish_approved_change` | Existing source-bound proposals, impact receipts, independent approval and versioned publication remain the path to activation. No competing taxonomy, approval store or publisher is needed. None of these writers was called. |
| Identity and history | `job_discovery.matching.current_match_versions`, `_identity`; scorer `build_stable_analysis`; `database.job_match_manager.get_job_match_snapshot`; `regression_corpus.replay_current_corpus` | Lookup/input identity includes knowledge/scoring versions and evidence context. Full replay fails closed without saved raw JD, extracted profile and evidence context. Historical diagnostics honor pinned receipts rather than silently reinterpreting old snapshots. |

The first unresolved identity appears after native taxonomy/registry/identity/fallback
attempts are exhausted. Evidence selection cannot repair missing requirement identity;
it answers a different question. Retrieval and adjudication can propose research routes,
but do not automatically activate an identity. A source/decomposition error can occur
earlier still: subsequent exact recognition correctly declines an incomplete clause.

The new script composes these existing pure helpers and context-local taxonomy scopes.
It is an offline investigation entry point, not an application-integrated resolver.

## B. Cross-job inventory and limitations

Primary source: tracked `tests/fixtures/per_jd_scoring_audit.json`, 30 jobs and 727 rows.
Its saved analyses declare scorer v1.16/taxonomy v1.5. The table below reports today's
v1.17/v1.6 resolver applied to their saved requirement inputs; it does not relabel the
historical analyses as current or mutate them.

Tracked `tests/fixtures/confirmed_taxonomy_coverage.json` contains another 727 row
views of the same 30 jobs. These are **different projections**, with differing scope
fields and no frozen raw JD/analysis versions. They are catalogued separately in
`source_manifests.alternate_views`; they are not merged or counted as another 30 jobs.

| Current analysis cohort | Rows | Unresolved | Capability resolved | Technology identity resolved |
|---|---:|---:|---:|---:|
| Saved requirement projection | 727 | 536 | 191 | 0 |
| Separately canonicalized raw-JD-only cohort | 716 | 519 | 191 | 6 |

All 727 saved rows omit `source_provenance`. The raw-only cohort retains native
provenance for all 716 rows. It calls `canonicalise_requirements({}, raw_jd_text=...)`
without model extraction. This is **not historical replay**: no original extracted
profile or full candidate context is available. Eleven saved IDs are absent from the
raw-only cohort; there are no raw-only new IDs. These differences must not be presented
as eleven bugs fixed, eleven filtered non-requirements, or a production scoring delta.
Eight common IDs change knowledge status: six pure identities and two capabilities.
The JSON also records diagnostic-only changes separately from status changes.

Of the 191 recognized saved rows, 100 have stored NONE (92 have no selected evidence,
8 retain a selected row), 69 have stored partial credit and 22 have stored DIRECT.
These describe saved selected receipts, not the availability of the full resume
library. Conversely, 70 currently unresolved saved rows have stored positive lexical
credit. Equating NONE with unresolved, or positive lexical credit with recognition,
would therefore misclassify this backlog in both directions.

The 536 unresolved occurrences occupy 534 exact-normalized wording clusters. Only two
wordings recur, each in two jobs: `Design, develop` and `manage your own time to deliver
your best, wherever you are, and whatever works best for you`. The first is a likely
verb fragment needing source review; the second is work-arrangement language. Neither
is evidence of a repeated missing technical capability.

There are 38 overlapping descriptive clusters in each cohort. They group investigation
dimensions, not semantic equivalence classes, and their counts must not be added.
Four potentially contact-sensitive saved wordings are withheld in exported text;
requirement IDs and fingerprints remain intact. Descriptive counts below cover the
remaining 532 unresolved saved rows. Broad privacy heuristics can withhold a benign
numeric string; the original tracked fixture is not edited.

| Saved unresolved diagnostic dimension | Occurrences | Jobs | Meaning |
|---|---:|---:|---|
| Parent provenance not verified | 532 | 30 | Projection limitation, not 532 proven production parser defects. |
| Activity cues | 200 | 29 | Many distinct activities; related theme, not one capability. |
| Generic technical cues | 183 | 30 | Too broad for automatic normalization or capability creation. |
| Familiarity/exposure cues | 98 | 25 | Knowledge level and implementation responsibility must remain distinct. |
| Optional/alternative cues | 74 | 25 | Preserve optional examples and ALL/ANY semantics. |
| Professional behavior | 64 | 21 | Generally related but non-equivalent behaviors; not automatic technical gaps. |
| Technology alias observations | 39 | 18 | Identity mentions, not approved capability relationships. |
| Credential/duration cues | 22 | 17 | Eligibility/credential routing, not technical alias expansion. |
| Existing predicate/plural observations | 21 | 13 | Candidates for scope review, not 21 valid alias fixes. |

The raw-only cohort still contains 519 unresolved identities, including 245 with
`Complete scope not bounded by native identity structure`, 161 with an explicit
activity, 69 with missing/activity-bearing/unverifiable parent proof, 33 mixed
behavior/technical scopes, 8 normalization blocks, 2 capability scopes and 1
architecture-pattern scope. These are diagnostic reasons, not a verified gold partition
of defects versus legitimate new capabilities. No genuinely new capability is confirmed.

The fixture breadth is sufficient for this investigation without live data. Population
frequency, current production prevalence, generalization and full match-impact claims
are not supported. Any later live export needs separate bounded read-only authorization.

## C. Root causes and prioritized proposals

### P0 — complete source-aware inventory and replay readiness first

**Mechanism A/B/G:** `technology_identity_scope` rejects rows before pure-identity
recognition when `_identity_provenance` cannot verify full source scope. For Job 632,
`Experience with Node.js`, saved `req_ead8b32809ed` is unresolved: registry identity is
recognized but unmapped, and parent proof is absent. The current raw-only row with the
same ID has native provenance and resolves `TECHNOLOGY_IDENTITY_RESOLVED`, with no
capability asserted. MongoDB and Keycloak in the same job behave similarly. Job 16's
Python/SQL requirement and Job 146's JavaScript identities supply further controls.

Expected behavior is complete identity recognition only when source scope is proven;
the current raw path already supports this. **Do not relax the provenance guard or
patch these IDs.** Reuse existing corpus/export records and retain parent occurrences,
raw grounding, alternative mode and source allocations in future offline exports.
Separate export completeness from native recognition defects. Expose missing selected
evidence and insufficient stored credit as evidence review states, never taxonomy gaps.

Acceptance: current native outputs unchanged; every exported occurrence has its own
source/version receipt or an explicit blocker; alternate projections cannot overwrite
one another; no inference from a technology token to architectural expertise. This
metadata-only investigation/export improvement needs an export-schema identity, not
a scorer or taxonomy change. No live export was performed here.

### P1 — inspect coordinated-action decomposition before adding aliases

**Mechanism B:** `_split_safe_independent_and_pair` checks the second clause's prefix
and token count, but does not prove that the first clause has its own object. Through
`_split_non_preference_clause`, `Design, develop and maintain ...` can leave `Design,
develop` beside the meaningful object-bearing clause. The repeated fragment appears
in Jobs 359 and 479. Job 566 also has a bullet-prefixed variant. Preserve the complete action/object obligation rather than map
`Design, develop` to backend development. The source-backed raw-only rows remain
available for focused diagnosis; no decomposition was replaced in this preview.

Related parser/normalization observations include zero-width characters, `Proficiency
in in Java ...`, `.NET` fragments and qualification/example tails. They are separate
mechanisms, not one license to remove punctuation or globally stem text.

Smallest proposed correction: a bounded coordinated-verb/object check at the earliest
incorrect split. Preserve coherent obligations and optional examples. Tests must cover
shared objects, truly independent clauses, design versus implementation, ALL/ANY lists,
parent occurrence allocation, stable IDs under benign line wrapping and unchanged
source grounding. A production parser change requires a scoring/currentness version
decision and generally a scorer increment. Taxonomy publication alone does not fix it.

### P2 — review existing-capability plural/qualified wording, through governance

**Mechanisms A/C/E:** `_contains` uses exact normalized phrase boundaries; `REST API`
does not match `REST APIs`. The published fallback admits only its finite, complete
REST API-development grammar, excluding arbitrary qualifiers and mixed obligations.

Actual unresolved observations include:

- Job 31 / `req_d0a20edbb7ae`: `Proven experience building efficient, secure RESTful
  APIs with frameworks such as Express.js, Fastify, FastAPI, Spring Boot, or equivalent
  enterprise-grade tools`. This is a qualified development obligation, broader than
  the bare endpoint control but not proof that every listed framework is mandatory.
- Job 479 / `req_5eabf1000188`: `Develop and integrate RESTful APIs with front-end
  applications`. Development and integration are separate responsibilities.
- Job 479 / `req_fc4e6757e8e4`: `Experience developing and consuming RESTful APIs`.
  Development and consumption must both remain represented.

All three remain unresolved in both cohorts. The existing plural observation helper
finds API terms, but cannot prove that a broadened alias represents the entire
qualification. No automatic mapping or evidence credit is recommended for these rows.

The deterministic proposal experiment covers the smaller exact pairs `Knowledge of
REST APIs`/`Knowledge of REST API`, `Knowledge of RESTful APIs`/singular, and
`Develop`/`Implement REST endpoints` versus explicit `REST API endpoints`. These are
analyst equivalence candidates, not independently reviewed gold. They preserve modality
and the named protocol. A knowledge requirement's protocol object is related to API
development, but does not imply endpoint authorship. The separate V1.2 knowledge-policy
question remains unapproved.

Use `governed_requirement_resolution` diagnostics, `governed_research` and the existing
temporary taxonomy/governed publisher for any approved change. The current fallback
descriptor is finite; extending complete-scope grammar needs explicit validation and
governance support. Do not add phrases to global `any_terms` merely because a local
experiment works. Preserve existing contextual variants and product exclusions.
Published alias changes require a taxonomy version; code recognition/evidence changes
also require an explicit scoring-identity decision. No version is chosen here.

### P3 — identity, relationships and architecture need different routes

**Mechanisms D/E/I:** `resolve_requirement_text` deliberately requires exact aliases
after bounded wrapper handling and refuses arbitrary list splitting. A recognized
Node.js/MongoDB identity can remain unmapped to a capability. `technology_identity_scope`
then requires a pure complete obligation; `Experience with Microservices` is an
architecture-pattern scope and cannot be treated like a pure library identity.
`Python for building robust internal tools` adds an activity, not merely an alias.

For pure identities, retain scope and reuse approved registry aliases. For a genuine
new identity, use the existing identity proposal/review path. For technology-to-capability
relationships, require source-backed governed relationship review. No universal mapping
from AWS, SQL, Node.js or a database name to architectural/development expertise.
Registry publications require registry identity advancement; code-level scope changes
need a scoring/currentness decision. Corpus data does not confirm a new capability.

### P4 — ambiguous, mixed and nontechnical requirements need bounded triage

**Mechanisms B/F/G:** nine stakeholder predicate observations across seven jobs do not
all mean the same thing: influencing senior stakeholders, describing analytics results
and maintaining working relations differ. Credentials, team behavior and work-life
language likewise do not become technical capabilities by sharing words. Retain
UNRESOLVED or non-taxonomy-addressable review states where appropriate.

Reuse `unresolved_multidimensional_triage`, the report-only adjudication schema and
human source review. `build_input` currently supplies no authoritative nearby context
from its frozen occurrence source; that is a known limitation, not permission to invent
context. LLM proposals cannot fix missing source boundaries or activate policy.
Source-grounded semantic equivalence can prioritize review when deterministic structure
is insufficient, but requires separate execution authorization and strict validation.

### P5 — evidence completeness and selection are independent

**Mechanisms G/H:** Job 81's `Knowledge of API development` is already recognized.
Its PostgREST evidence classification is a separate V1.2 policy question and is not a
bulk identity defect. Recognition cannot waive source eligibility, combine unrelated
evidence rows, satisfy REST with gRPC, or remove V1.1 authorship/design checks. Existing
weak recovery still needs positive overlap except its specifically versioned approved
implementation-without-design case. No further recovery exception is proposed here.

| Strategy | Appropriate use | Rejected shortcut |
|---|---|---|
| Deterministic normalization | Bounded, source-preserving representation defects with metamorphic tests. | Global singularization/stemming or deleting meaningful punctuation. |
| Existing aliases | A proven equivalent complete scope within an existing capability. | Promoting every plural observation or product-name substring. |
| Bounded semantic equivalence | Grounded candidate review retaining modality, protocol, negatives and obligations. | Similarity score as approval or evidence credit. |
| Registry relationships | Reviewed identity or explicit approved relationship. | Technology use as architectural expertise. |
| Governed adjudication | Proposal routing after native diagnostics with exact spans and candidate IDs. | Model result as an automatic runtime resolver. |
| Discovery/new capability | Confirmed coherent reusable gap after earlier causes are excluded. | Treating every unresolved row as a gap. |

## D. Deterministic preview and protected behavior

The script runs the existing resolver before and after an explicitly local taxonomy
scope for four exact analyst examples. It verifies the existing comparator's capability
identity first, retains the entire requirement input and restores the scope afterward.
The overlay version is marked DRY_RUN_ONLY. Its application guard is a test harness,
**not a deployable recognition rule**. It does not create drafts or approval receipts.

| Original control | Baseline | Proposed local recognition | Capability |
|---|---|---|---|
| Knowledge of REST APIs | UNRESOLVED | CAPABILITY_RESOLVED | backend.api_development |
| Knowledge of RESTful APIs | UNRESOLVED | CAPABILITY_RESOLVED | backend.api_development |
| Develop REST endpoints | UNRESOLVED | CAPABILITY_RESOLVED | backend.api_development |
| Implement REST endpoints | UNRESOLVED | CAPABILITY_RESOLVED | backend.api_development |

None of the four applies to any of the 727 saved or 716 raw-only corpus rows. This
experiment therefore demonstrates bounded mechanisms and guard behavior, **not a bulk
coverage gain**. All corpus proposal receipts retain baseline status and identity.
The actual qualified/mixed API rows above stay pending scope review.

The 19 controls also retain current results for singular REST knowledge, API-development
knowledge, the approved complete design/development fallback, REST/gRPC mixtures,
API integration, non-authoring Supabase usage, AWS product context, gRPC-only endpoints,
design-only obligations, negation, compound tails and generic data. Additional tests
reject missing/conflicting/empty provenance and preserve parent scope.

Each proposal receipt records original/proposed status and capability, comparator,
review basis, original requirement ID, complete input and fingerprint. Decomposition,
parent fractions, source provenance and evidence eligibility are not modified. No
candidate evidence is supplied to the proposal resolver, and no match score is computed.
Existing empty-evidence labels are diagnostic outputs, not forecasts of candidate credit.
Recognition might enable later evidence capping/recovery, including reducing existing
lexical credit; full frozen inputs and a governed native scoring impact review would
be required to quantify that effect. No live or synthetic Job Match totals are claimed.

The focused tests exercise genuine Java REST implementation as DIRECT eligible,
implementation without design as WEAK for combined obligations, PostgREST-only
authorship rejection, REST/gRPC completeness and generic data as **not DSA**. Existing
native API scenario, source-selection, decomposition, accounting, historical-staleness
and fingerprint tests also pass. Generic PostgREST data-access evidence earns NONE
against the actual DSA capability as an explicit negative test.

## Performance and incremental design

Measured three warm-import resolver passes across 727 saved inputs, with full-input
cache comparison. Latest medians: approximately **4.707 seconds uncached** versus
**4.696 seconds with exact memoization**. There are 726 unique complete inputs, so only
one call can be reused. This small timing difference is noise, not demonstrated benefit.
Imports, extraction/model latency and canonicalization are outside this measurement.
The three samples and exact implementation are in the preview artifact.

Existing taxonomy/registry file-signature caches already avoid repeated loading.
Do not add pairwise fuzzy clustering or optimize the entire scoring pipeline. Existing
`backlog.clusters` produces overlapping descriptive groups; stable exact cluster IDs
use a versioned normalization/text fingerprint and do not change when another job joins.
They are investigation IDs, never canonical capability identities.

For a future batch coordinator:

1. Process new/changed JD content hashes incrementally; pin extraction/parser/scoring,
   taxonomy/registry content/version and source completeness. Reuse unchanged receipts.
2. Cache pure native recognition by full scope-bearing input and knowledge identity;
   keep evidence labels out of this cache. Requirement text or ID alone is insufficient.
3. Store occurrences separately from wording groups; preserve original job/source,
   optionality, negation, parent and allocations. Similar words can need separate reviews.
4. Reuse the existing governor's `interpretation_cache_key`, saved-evidence re-evaluation
   and compatible-lineage checks before authorizing new research. Current
   `unresolved_adjudication.run_cases` itself has no general cross-job memoization.
5. A future adjudication cache must pin schema/prompt/model, allowed candidates,
   knowledge, authoritative context and scope. Revalidate grounded spans and occurrence
   identity on reuse. A reused semantic proposal never inherits approval/publication.
   Do not call a model repeatedly for identical validated inputs; do not assume fuzzy
   wording equivalence is reusable. No provider or persistent cache was added here.

## E. Implementation roadmap and readiness

| Stage | Small deliverable | Acceptance criteria |
|---|---|---|
| 0 — completed here | Fixture-only inventory, native diagnostic comparison and guarded preview. | Reproducible inputs, separate historical views, honest counts, negative controls, protected hashes. |
| 1 — recommended next | Review/batch export contract retaining complete existing provenance and explicit replay blockers. | No production recognition change; source IDs, versions, ALL/ANY, privacy and parent allocations preserved; duplicate/alternate view tests; missing extracted profile/evidence never synthesized. |
| 2 | Narrow coordinated-action decomposition proposal and focused native replay. | Reproduce actual source failure; preserve shared objects, independent obligations and conserved scoring parents; approve scoring-version implications before implementation. |
| 3 | One source-complete governed recognition family at a time. | Independent reviewed positive/negative cases, no protocol/modality collapse, product guard intact, complete frozen native impact receipts, versioned publication only after approval. |
| 4 | Scoped registry identity/relationship proposals and legitimate gap research. | Separate pure identities, architecture/activity scopes and true gaps; no generic data-to-DSA or vendor-to-expertise mapping. |
| 5 | Incremental review orchestration using existing lineage/cache/governance. | Exact reuse invalidation, bounded batches, explicit provider authorization and human approval, no automatic saved-match refresh. |

**Investigation readiness: PASS. Production activation: NOT AUTHORIZED.** The data
supports a reusable diagnostic/provenance stage first, not a broad alias rollout.
Complete production impact replay is blocked by absent full frozen inputs in the
selected fixtures; this does not prevent their use for the present identity investigation.
No full-suite/release claim is made and no unrelated historical pipeline was run.

## Validation and changed files

Python 3.13.12 in the existing isolated runtime. Smallest new module: 8 tests pass.
Focused selection: 78 tests pass. After the final additional DSA evidence assertion,
the same 8-test module was rerun and passed; counts overlap, they are not 86 unique tests.
An initial new-module test exposed the false assumption that the two fixtures were
identical; the investigation loader now records them as alternate historical views.
No production defect or existing assertion was weakened to resolve that failure.

Commands, using `venv/evidence-completeness-runtime/environment/Scripts/python.exe`:

```text
python -B -m unittest tests.test_bulk_unresolved_v1 -v
python -B -m unittest tests.test_bulk_unresolved_v1 tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_governed_requirement_resolution tests.test_jd_atomic_requirement_decomposition tests.test_post_publication_accounting tests.test_jd_structure_fingerprint_compat -v
python -B -m scripts.preview_bulk_unresolved_v1 --protected-baseline venv/evidence-completeness-runtime/bulk_v1_protected_before.json
git diff --check
git diff --cached --check
```

The ignored task launcher `venv/evidence-completeness-runtime/bulk_v1.ps1` sets
worktree-owned disposable TEMP/TMP/database overrides, no-bytecode output, local cost
metadata and retrieval off. The existing startup audit guard blocks external DNS/socket
calls and non-disposable SQLite connections. Owner context was used only where existing
temporary-directory ACLs require it. Logs: `bulk_v1_small.log`, `bulk_v1_focused.log`,
`bulk_v1_preview.log` in that runtime. No full discovery, quick gate or full runner.

All **799** pre-existing tracked Python/JSON/Markdown source/configuration/fixture files
in the baseline ledger retain byte-identical working-tree hashes, including V1.1,
published knowledge and historical fixtures. This is not a live-database hash claim.
Historical fixture/disposable round-trip tests preserve saved receipts and detect
version staleness. HEAD is unchanged. Git whitespace checks pass; the index is empty.

Five new review files, no modified tracked files:

| File | Purpose |
|---|---|
| `scripts/preview_bulk_unresolved_v1.py` | Offline inventory, current native diagnostics, existing descriptive clusters, exact review overlays and measured cache comparison. |
| `tests/test_bulk_unresolved_v1.py` | Source-view, provenance, privacy, scope restoration, API and DSA safeguards. |
| `bulk_unresolved_v1_inventory.json` | Source manifests, every primary/current/raw-only row, comparisons and clusters. |
| `bulk_unresolved_v1_preview.json` | Controls, all corpus proposal receipts, timing samples and protected SHA-256 ledger. |
| `bulk_unresolved_v1_architecture.md` | Architecture, root causes, prioritized proposals, limitations and roadmap. |

Only task-owned ignored launcher/baseline/log/disposable runtime state was also created.
No commit, push, merge, taxonomy publication, live write or saved-snapshot rewrite.
Stop for human review before any production implementation.
