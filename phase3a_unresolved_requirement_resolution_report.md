# Phase 3A — unresolved requirement resolution

2026-10-22. **Bounded implementation completed; production promotion is NOT approved.**
This report applies the original Phase 3A prompt from
`C:/Users/Admin/Downloads/phase3a_original_prompt.md` and both mandatory amendments.
The full offline corpus is primary. Application #152 is a regression example.

## Repository and preservation

Worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch: `feat/job-match-unresolved-relevance-v1`; HEAD:
`788db03b90c55241cd43a54604f94205bccc6452`.
The Phase 2E checkpoint is present. Phase 2F is **uncommitted** and was preserved.
The initial tracked modification was `analysis_stability/coordinated_runtime.py`;
the existing five untracked files were the dashboard review, Phase 2F report,
observer, relevance preview and its tests. No branch, index or Git history was changed.

No original/master worktree or original production database was opened. No network,
model, embedding, Tavily, refresh, migration or application write was performed.
The existing copied development database was opened only through the verified
retrospective loader (`mode=ro`, `PRAGMA query_only=ON`, read transaction), with an
additional audit hook permitting only that exact URI and denying writes/network.
Its complete bytes were unchanged after the #152 check. Private evidence remains
in memory; this report contains no raw résumé, raw JD packet or private claim text.

## Actual dependency and authority map

These are inspected call paths, rather than a list of product surfaces.

```text
Job Finder
  matching.analyze_job_match -> extractor / reusable frozen JD profile
  matching.build_profile_evidence_context(authorized Evidence Library snapshot)
  matching._default_stable_builder
    -> canonicalise_requirements -> build_deterministic_keyword_match
    -> build_stable_analysis

Initial / résumé document analysis
  app.analyze entry -> document_grounded_analysis.analyze_actual_resume_against_jd
    -> represented_profile (literal document bounding)
    -> canonicalise_requirements -> build_deterministic_keyword_match
    -> build_stable_analysis (actual document, not Library fallback)

Phase 8
  phase8_verification.build_phase8_verification / resolve_phase8_baseline_analysis
    -> build_current_baseline_analysis / final verified profile reconciliation
    -> build_stable_analysis (separate before/after authoritative inputs)

Shared native stable analysis
  JD section inference -> source grounding -> atomic decomposition/canonical IDs
  -> original evidence index -> keyword linking -> structured scope matching
  -> validate linked rows -> single-record reselection
  -> phase6d_stable_scoring_adapter.apply_taxonomy_caps_to_requirements
     -> production_requirement_resolver.resolve_requirement_with_production_knowledge
        -> capability_taxonomy.classify_requirement_diagnostics
        -> technology_registry.resolve_requirement_text (approved mappings only)
        -> requirement_scope.technology_identity_scope (identity is not capability)
        -> approved bounded recognition fallback, only after earlier stages fail
     -> existing capability evidence evaluator, applying credit ceilings
  -> capability NONE recovery -> deterministic aggregation

Discovery / maintenance (review authority, not runtime scoring authority)
  observations / taxonomy_gaps -> taxonomy_evolution / corpus_gap_resolution
  -> maintenance_service.run_corpus_audit / list_gap_rows
  -> existing parsing, identity, relationship, capability, evidence-policy routes
  -> governed_research -> resolver_improvement / temporary native knowledge scopes
  -> independent review and regression receipts
  -> governed_publication.prepare_publication / publish_approved_change
     -> explicitly versioned native taxonomy/registry publication

Developer Diagnostics (explicit actions; no production persistence)
  developer_comparison_ui -> developer_real_comparison.load_retrospective
  -> sealed frozen JD + original Library ownership -> coordinated_preview
  -> published v1.17 and separately gated v1.21
  -> evidence_decision_trace (retained receipts, not attempted-candidate invention)
  -> native_evidence_observation (actual current-thread native execution)
  -> evidence_relevance_preview.evaluate (v1.24)
  -> evidence_relevance_preview.evaluate_eligible_recovery (new explicit v1.25)
```

The “Job Capability” matching function is the shared canonical resolver and
taxonomy adapters above; there is no separate authoritative `job_capability`
runtime engine in this checkout. Capability definitions, finite requirement
terms, aliases, guards and evidence tiers are accessible to both the resolver
and evaluator. Technology aliases and approved relationships are accessible via
the registry; an unmapped identity does not authorize capability credit.
Maintenance SQLite/research suggestions and RAG suggestions are not runtime
taxonomy authority. No missing automatic discovery-to-scoring connection should
be added: the approval/publication boundary is intentional.

Already working connections include shared native scoring, source-aware resolution,
structured scopes, taxonomy caps, original-record recovery, governed maintenance
and frozen-input comparisons. Missing historical candidate inputs are a fixture
limitation, not permission to borrow current Library or application-report data.
The seven unresolved examples do not establish that runtime cannot read taxonomy.

## Full Corpus Unresolved-Requirement Coverage and Resolution

### Verified baseline and denominators

Primary tracked source: `tests/fixtures/per_jd_scoring_audit.json`, SHA-256
`a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.
It contains 30 JDs, 727 saved canonical requirement occurrences and raw JD text.
All 30 omit the original extracted profile and full frozen candidate context.
It therefore supports recognition inspection and raw-only parsing, **not full
historical evidence replay**. Existing selected historical evidence is not the
complete candidate search space.

The alternate `tests/fixtures/confirmed_taxonomy_coverage.json`, SHA-256
`6b5edb4287cceaae6b6c49a13fb4b149666a2514aaada34deb89e29ec2b7c299`,
contains 727 different row projections of the same 30 jobs. It is not another
30 jobs and must not be merged into the primary source.

The historical maintenance manifest pins scorer `stable-evidence-v1.16-phase6d20`,
taxonomy `phase6d-capability-taxonomy-v1.5`, registry `technology-registry-v1.3`,
and corpus fingerprint
`f59230038ed1c9ca97e5606ac564e3411f05d8b5bdbc39ad9cb1dee50e751eb2`.
Its 474 meaningful technical rows include **276 unresolved technical occurrences**.
This is the verified source of the approximate “200+” backlog. It is a narrower,
historical denominator than the complete current-resolution inventory.
Its addressability plan records 2 capability-gap controls, 6 non-addressable
annotations and 268 undetermined rows. Those annotations are not 276 independently
reviewed matching labels.

The existing `preview_bulk_unresolved_v1.load_jobs/build_inventory`, native
canonicalizer/resolver and backlog normalizer/near-group helpers were rerun with
network, subprocesses, database access and file writes denied by an audit hook.

| Current v1.17/v1.6 interpretation | Saved projection | Fresh raw-JD-only interpretation |
|---|---:|---:|
| JD count | 30 | 30 |
| Requirement occurrences | 727 | 716 |
| Capability resolved | 191 | 191 |
| Technology identity resolved | 0 | 6 |
| Unresolved occurrences | 536 | 519 |
| Distinct unresolved requirement IDs | 532 | 515 |
| Distinct normalized unresolved wordings | 534 | 517 |
| Exact repeated-wording groups | 2 | 2 |
| Privacy-safe near-wording groups | 4 | 4 |
| Occurrences in those near-wording groups | 9 | 9 |
| Texts excluded from near-wording inspection by existing privacy filter | 4 | 4 |
| Rows lacking saved source provenance | 727 | 0 |

Requirement ID alone is not a complete source/scope identity: the ID and wording
counts differ. Preserve job, full text, source parents, allocation and fingerprint.
The repeated wordings are the existing coordinated verb fragment (jobs 359/479)
and work-arrangement wording (jobs 240/319). Near-wording groups are descriptive,
not equivalence classes or approved shared fixes. No fuzzy deduplication was applied.
The 11-row geometry difference is not a claimed bug fix or score improvement.

Eight common IDs have different recognition between the two views: two existing
cross-functional scopes (jobs 15/479) and six pure technology identities (jobs
16/146/632). This already works when native source provenance is present. It is
not eight newly implemented fixes and does not permit grafting raw-only receipts
onto historical saved rows. All historical artifacts remain intact.

Of the 536 current unresolved saved rows, 70 carry historical positive lexical
credit. Of 191 currently recognized rows, 100 carry historical NONE. Neither
recognition status nor the absence of a capability ID is a candidate-credit oracle.

### Review cohorts and root-cause evidence

`unresolved_adjudication_benchmark_v2.json` contains 40 cases: two inherited
confirmed NAC review controls and **38 pending independent decisions**. Its
SHA-256 is `502f48b2501d786047adae31a32ba3240478fe4b15084b5433e029609c699d7d`.
The separate V5 review packet contains exactly those 38 pending cases; it does
not represent the full backlog. Its local bytes hash is
`ee08555df22ef5f29d0e103cb1dba78efec92beb719a252f5e71ecab4069bf7c`.
The four-case semantic report is exploratory, not four approved credit policies.
Application #152's seven example IDs occur in the primary fixture under Job 493.
No new human judgments or gold labels were manufactured.
The two confirmed controls are historical routing decisions on their frozen
inputs, not independently reviewed current candidate-credit labels for the entire
727-row corpus. A complete count of reviewed current evidence decisions is unavailable.

Existing inventory review categories partition the current unresolved rows:

| Native diagnostic route | Saved | Raw-only |
|---|---:|---:|
| Source/decomposition review | 335 | 240 |
| Possible compound review | 140 | 139 |
| Remaining identity/coverage review | 61 | 140 |
| Total | 536 | 519 |

These are review routes, **not independently proved causal defects**. In particular,
missing/unverifiable source scope must not be called a missing taxonomy definition.
Raw-only identity guards independently report: 245 unbounded scopes, 161 named
activities, 69 missing/activity-bearing/insufficient parent scopes, 33 mixed
behavior/technical scopes, 8 normalization blocks, 2 capability scopes and 1
architecture-pattern scope. Their sum is 519. A generic activity or AND token is
not proof of incorrect decomposition or a true taxonomy gap.

The older local `reports/unresolved_backlog_clustering_v1.json` is another clearly
separate scope: 38 latest snapshot jobs; active same-hash 656 rows/501 current
unresolved occurrences/494 normalized texts; inactive jobs 296/202/202; application
versions 928 rows/425 unresolved views, deduplicating to 221 occurrences/166 texts.
Its taxonomy is v1.5. Counts overlap historical sources and must not be added to
the 30-JD fixture. Its bytes hash is
`b98e0f0224b512c37f696d5d75bb0addac65d69ed1271713c325b7319bd6e056`;
inventory fingerprint `1d0cea426f8fc8b2c8c8483f629666d5aca2f8880eabb560a9736c574d7c4f4e`.
No originating live database was opened to recreate it.

### Before/after outcomes

| Measurement | Before | After this change |
|---|---:|---:|
| Published saved-view unresolved occurrences / distinct IDs | 536 / 532 | 536 / 532 |
| Published raw-only unresolved occurrences / distinct IDs | 519 / 515 | 519 / 515 |
| New taxonomy identities or aliases | 0 | 0 |
| New independently confirmed historical candidate false negatives | Not established | Not established |
| Independently specified eligibility counterexample | NONE | WEAK, explicit v1.25 only |
| 30-JD synthetic native probe: NONE / WEAK, 716 rows | 667 / 49 | 666 / 50 |
| Synthetic probe recognition changes | 0 | 0 |
| #152 six unsupported examples | NONE for all 6 | NONE for all 6 |
| #152 seven scope/credit questions | Pending, native NONE | Pending, native NONE |
| #152 quality correction inherited from v1.24 | WEAK in v1.24 | WEAK in v1.25 |

The one corpus probe change is Job 173 `req_bde373b20ce0`, a software-development,
scripting or automation scope. The synthetic profile contains an attributable
software application implementation claim and a short distractor. Existing
partial lexical evidence policy admits only WEAK for the qualifying original
record. This is an observed synthetic result under existing thresholds, not a
new gold label, historical candidate score or general claim that every newly
retrieved candidate deserves credit. No DIRECT result is introduced.
Counts of genuinely unsupported evidence across all 727 historical requirements
are **unavailable** without the complete frozen evidence packet and independent
review. They must not be filled with the unresolved count or the stored NONE count.

## Confirmed defect and implemented correction

`_fallback_weak_evidence` first chose the highest-scoring compatible record, then
checked eligibility. Containment similarity can favor a short record with one
shared word. Rejecting that record discarded a lower-ranked, independently
eligible original record. This also affects unresolved identities: generic native
WEAK fallback is allowed without inventing a capability ID.

Independent synthetic counterexample (nine requirement tokens):

| Candidate | Native score | Focus coverage | Overlap | Existing WEAK eligibility |
|---|---:|---:|---:|---|
| Short two-token distractor | .391 | 1/9 | 1 | Rejected |
| Attributable milestone-coordination claim | .300 | 3/9 | 3 | Accepted |

The original fallback returns no evidence. The corrected fallback selects the
second record under the existing minima (.28 score, .25 coverage, 2 overlap).
The same result is reproduced through the actual developer comparison pipeline.

An initial integration test used a one-token distractor and correctly failed:
the legacy keyword builder already assigns TRANSFERABLE from its containment
similarity rule in that different situation. The test input was refined to the
two-token distractor above, whose independently calculated metrics exercise the
actual NONE/WEAK eligibility defect. Assertions were not weakened and the legacy
positive was not silently rewritten. Short-record containment remains a separate
false-positive risk requiring credit-policy review; v1.25 does not claim to fix it.

Implemented in reusable native fallback, behind a default-false request-local
context. It scans original records separately using the existing native selector,
source compatibility and unchanged eligibility predicate. Stable first-wins ties
are preserved. Known-capability requirements and coordinated-action target parents
retain their original fallback and NONE recovery policy, avoiding interference
with existing semantic recovery caps and native NONE ceilings. The explicit wrapper
also rejects changes to any coordinated-action receipt.
No lexical threshold, taxonomy definition, decomposition, requirement weight or
evidence-credit rule was changed. Two insufficient bullets remain insufficient.

The explicit `evaluate_eligible_recovery` entry point reuses the verified frozen
comparison request, native coordinated pipeline, verified ownership ledger and
v1.24 quality correction. It checks unchanged geometry and rejects any unexpected
label/selected-evidence change beyond NONE-to-WEAK on an unrecognized capability.
Each positive change requires one verified original Library owner. It does not
join source records or infer missing actions/modifiers.

Native and coordinated analyses executed in this context are stamped
`stable-evidence-v1.25-phase6d29`, policy `eligible-single-record-weak-fallback-v1`,
a developer namespace and a separate deterministic fingerprint. Even direct native
builder calls cannot escape with a v1.17 identity. A bare v1.25 identity is rejected
by the existing central persistence/publication guard. Published constants, v1.21
and v1.24 entry points remain unchanged. No UI automatically activates v1.25.

## Seven-case resolution matrix and approval decisions

Exact frozen originals and original-record source receipts were inspected in Phase
2F; the verified retrospective loader and all 17 final labels were rechecked here.
Numbers below are original Library owner IDs, not newly borrowed current evidence.
Native disposition remains NONE for these seven. “Pending review” below describes
the unresolved decision; it does not fabricate a scorer REVIEW_REQUIRED receipt.

| Requirement / importance | Relevant original support and boundary | Responsible subsystem / smallest justified next decision |
|---|---|---|
| `req_d8a925b5b34e`, supporting: project objectives/role | Owners 1/2/4/5 describe participation/delivery; role-trained project objectives are not independently bounded by those claims | Professional scope/credit review. Existing end-to-end application capability does not mean participation in any project. Approve a bounded participation contract before credit; do not alias to end-to-end delivery. |
| `req_26d895b9a27f`, core: collaboration plus specify/design/build/maintain | Owners 2/4/5 support collaboration/integration; no single original establishes the complete lifecycle | Decomposition and mandatory-action completeness. Existing three-action P3 grammar is not authority for a four-action lifecycle plus collaboration. Proposed reviewed children must inherit the exact software object and conserve parent allocation; partial support must never become whole-parent DIRECT. |
| `req_30482086845a`, supporting: continuous improvement of development best practices | Owners 4/6 support particular workflow/pipeline/CI improvements; ongoing broad best-practice scope is not established | Evidence/scope policy, not a CI alias bug. Proposed bounded partial rule: an owned, implemented practice improvement can support only WEAK when that activity is the explicitly admitted component; generic tool use cannot. Approval needed. |
| `req_c3b362e0255b`, preferred: SQL/NoSQL knowledge | Owners 2/6 show relational data work; another original assertion mentions a nonrelational store. Different bullets are not one fabricated breadth proof | Knowledge/list-scope review. Existing database-design capability is not general database knowledge. Preserve slash ambiguity; approve ANY only with explicit alternative wording, or reviewed independent children for an explicit conjunction. No automatic database-design mapping. |
| `req_67c5d07c55c1`, preferred: AngularJS/NodeJS/ReactJS/framework list | Original React activity is relevant; Angular/Node ownership is absent | Requirement scope and structured technology matching. ReactJS alias already exists. Under explicit AND, React alone cannot prove the entire list; examples/ANY need explicit source support. No registry alias expansion is justified. |
| `req_73ffb410c613`, preferred: engineering concepts AND Agile | Software implementation exists; CI/GitHub Actions is not Agile experience | Compound scope/credit review. Preserve the Agile obligation. Proposal: independent children only for a verified conjunction; software work cannot satisfy the Agile child. No CI-to-Agile relationship. |
| `req_ba468f2924d8`, supporting: effective collaborative teamwork | Owners 1/2/4/5 contain team activity; effectiveness is broader than co-occurrence | A bounded generic teamwork recognition candidate belongs in existing Taxonomy Maintenance for review; effectiveness/credit still needs its own evidence boundary. Do not map same-function teamwork to cross-functional/stakeholder coordination. |

Reusable approval questions: (1) how explicit AND/OR/examples/slash scopes are
admitted without discarding obligations; (2) which owned practice/participation
claims justify partial professional-scope credit; (3) a separate bounded teamwork
definition and evidence tiers, if reviewers confirm a real coverage need.
Recommended defaults are conservative: unresolved list scope remains pending,
no incomplete parent becomes DIRECT, and no new definition is published automatically.

Positive/negative controls for those decisions: explicit relational OR nonrelational
knowledge versus an AND claim with one side; React activity versus Angular+Node+React
completeness; owned workflow improvement versus merely listing CI; explicit team
co-delivery versus a bare “team player” adjective; named separate functions versus
same-function collaboration; software implementation versus explicit Agile practice.
These are proposed contracts requiring approval, not silently enacted policies.

The six independently unsupported #152 cases remain protected: named PM/lead/
architect coordination, debugging, engineering documentation, industry monitoring,
rapid learning and the combined critical/analytical/creative claim. App-generated
reports are not engineering-document authorship; technical breadth is not learning
speed; generic coding is not debugging. No source packet change was used to force
credit on these cases.

## Maintenance routing and remaining integration boundaries

Use existing `maintenance_service` fix layers and their source-bound candidates:

- Existing alias/predicate misses: resolver review and temporary native impact,
  followed by current regression/approval/publication receipts. The 21 raw-only
  plural/predicate observations are candidates, not 21 approved fixes. They include
  false-positive traps such as Amazon Web Services and database-knowledge/design.
- Genuine bounded coverage gaps: existing capability-maintenance workflow. The two
  independently reviewed NAC controls remain proposals, not automatic publication.
- Decomposition/source loss: parsing review, retaining original parent allocation.
- Known identity but incomplete evidence or ambiguous requirements: evidence/scope
  review, not a taxonomy-definition request. Correctly unsupported claims stay NONE.

No maintenance database was populated or updated just to manufacture a review
receipt. Existing routing/review validators were exercised on disposable fixtures.
The implemented missing connection is between **per-record native eligibility and
fallback selection**, with current canonical resolution preserving the known-
capability policy boundary. Existing discovery-to-maintenance and approved-publication
connections were reused and verified; no duplicate approval engine was built.

Actual Job Finder `_default_stable_builder`, document initial-analysis builder and
Phase 8 `build_current_baseline_analysis` were exercised with separate synthetic
authorities and the experimental context. All selected the independently eligible
claim without substituting Library material into a document. A document lacking
the claim remained NONE even when supplied an unrepresented structured profile.
This proves the shared builder connection; it does **not** claim production UI,
saved historical migration or full end-to-end Phase 8 activation is complete.

## Validation and changed files

Focused results are recorded below. Full CI is intentionally not part of this
bounded phase, following the original prompt's focused-test scope rather than
the general AGENTS.md full-run default.
Known prior historical CI limitation: the old
`FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged`
compares v1.16 source pins with today's sources. It was already failing before
this phase. Its historical assertion/oracle was not weakened or rewritten.

Changed for Phase 3A:

- `analysis_stability/stable_evidence_scoring.py`: opt-in eligible-record fallback
  and mandatory experimental output stamping; default algorithm unchanged.
- `analysis_stability/coordinated_runtime.py`: context, v1.25 identity/fingerprint
  stamping and persistence rejection, retaining Phase 2F's v1.24 protection.
- `analysis_stability/coordinated_integration.py`: preserve experimental identity
  after the coordinated adapter's own identity construction.
- `job_discovery/evidence_relevance_preview.py`: explicit v1.25 verified comparison
  entry point, retaining the original v1.24 implementation.
- `tests/test_phase3a_eligible_evidence.py`: independent positive/negative controls,
  corpus probe, authority isolation, withholding, determinism and persistence checks.
- This report. Small diagnostic JSON remains ignored under the offline scratch root.

Unchanged/preserved: existing Phase 2F observer/tests/report and dashboard review,
published taxonomy/registry, parsers, historical fixtures/oracles, application UI,
Job Finder ranking, database contents and all saved analyses.

### Exact focused commands and outcomes

All commands used Python 3.13 from
`venv/evidence-completeness-runtime/environment/Scripts/python.exe -B`, followed by
`scripts/run_offline_release_checks.py --scratch-root reports/<lane>` and the
following explicit test arguments. The launcher contained network, secrets and
non-disposable database access. Mock research transports in maintenance tests
were synthetic; no actual provider was called.

| Lane / test arguments | Result |
|---|---|
| `phase3a_audit`: `tests.test_bulk_unresolved_v1 tests.test_source_aware_inventory tests.test_unresolved_independent_review_v5 tests.test_evidence_relevance_preview tests.test_coordinated_action_implementation.CoordinatedImplementationTests.test_gate_off_matches_hash_pinned_historical_native_on_30_jobs` | 50/50 PASS, 167.468s, before implementation |
| `phase3a_workflows`: `tests.test_job_discovery_job_match tests.test_document_grounded_analysis tests.test_initial_analysis_explainer tests.test_phase8_verification tests.test_api_evidence_completeness` | 65/65 PASS, 49.216s, before implementation |
| `phase3a_maintenance`: `tests.test_taxonomy_maintenance_service tests.test_tqd3_corpus_gap_resolution tests.test_unresolved_semantic_evidence.SemanticEvidenceTests` | 68/68 PASS, 40.479s |
| `phase3a_final`: `tests.test_phase3a_eligible_evidence tests.test_evidence_relevance_preview tests.test_api_evidence_completeness tests.test_coordinated_action_implementation tests.test_capability_none_recovery tests.test_capability_taxonomy_v1_4_single_row_reselection` | 63/63 PASS, 353.272s, before the additional coordinated-parent exclusion |
| `phase3a_guarded`: `tests.test_phase3a_eligible_evidence tests.test_evidence_relevance_preview tests.test_job_discovery_job_match tests.test_document_grounded_analysis.DocumentInputTests tests.test_phase8_verification tests.test_api_evidence_completeness tests.test_coordinated_action_implementation.CoordinatedImplementationTests.test_gate_off_matches_hash_pinned_historical_native_on_30_jobs` | 62/63 passed, 218.623s; one newly authored counterexample fixture was calibrated incorrectly; see below |
| `phase3a_verified`: `tests.test_phase3a_eligible_evidence` | **9/9 PASS, 87.403s**, corrected final fixtures and final implementation |

The guarded run had loaded the new ceiling-control fixture before its correction:
the positive record had four shared tokens, scored .400 and was already selected
by the legacy fallback. Removing the extra synthetic shared noun gave the intended
independently eligible three-token record ranked below the .391 distractor. The
expected NONE ceiling was retained. Its targeted rerun passed, then the entire
nine-test new module passed. All 54 other guarded-run tests passed on the final
production-source bytes; no implementation changed after that run began. The
earlier first-counterexample fixture issue is disclosed above. Neither failure
was hidden by rewriting a historical oracle or weakening an assertion.

Final tests cover the full 30-JD/716-row synthetic probe, no fabricated canonical
identity, per-record ownership and source filters, six unsupported scopes, P3 and
native NONE exclusions, API V1.1, determinism, context reset on failure, unavailable
aggregate/contribution handling, inherited v1.24 behavior and bare-version
persistence rejection. Existing coordinated controls and independently pinned
30-JD gate-OFF equivalence passed. The final synthetic probe again returned exactly
one NONE-to-WEAK change and zero recognition changes.

`git diff --check` and `git diff --cached --check` passed. AST parsing and trailing
whitespace checks passed for all five Python files changed for this phase. No
staged changes. Git's informational LF/CRLF conversion warnings are not whitespace
errors. `git diff --exit-code HEAD -- taxonomy tests/fixtures` passed: all published
knowledge and tracked historical/oracle bytes remain unchanged.

Protected SHA-256 checks:

| Artifact | SHA-256 |
|---|---|
| Published taxonomy v1.6 | `1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513` |
| Published registry v1.3 | `56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675` |
| Existing dashboard review | `5a17ea791dbb78c7b21ea52bce6a8978f4553b4adb2c43fb5c3a0a150778d0bf` |
| Original real-comparison loader | `b9c8239c1192faa5ed7b0eb34cd0f7a6f5340ff62e5ec6afee947cf68641d190` |
| Historical predicate report | `3f98ef19bc1d6ec32cf71985ec515354cd09c669aae2a7b098282088ed25ca5e` |
| Historical predicate manifest | `3b0c6891a98ca85ea09068568ee8652eddd5682e66dd460c4328202e56fdaf06` |

The shared native Python source intentionally changed behind the OFF context;
this is not a claim that its source hash remains historical. The existing published
scorer/version constants and gate-OFF outputs remain unchanged. Implementation
edits invalidate retained developer requests through existing source-revision
fingerprints; no saved cache was refreshed or activated.

Final #152 read-only assertion check: 17 rows/five original records, all six
unsupported and seven ambiguous rows NONE, one inherited quality WEAK, zero new
v1.25 changes, published and v1.25 alignment both 12; database bytes unchanged.

Optional ignored diagnostics:
`reports/phase3a_corpus_resolution_checkpoint.json` contains 1,443 occurrence
locators/fingerprints, native routing categories and source manifests, with no raw
requirement/evidence text. Its baseline inventory cache hash was checked against
the separately rerun baseline. It is 812,757 bytes and remains ignored. The final
synthetic summary is regenerated by the tests under `reports/phase3a_verified/`.
Neither artifact is a launch/test dependency or proposed Git fixture.

## Recommendation

**GO for explicit developer review of the bounded v1.25 correction; NO-GO for
production promotion.** It fixes one demonstrated reusable selection defect and
preserves existing ceilings. It does not solve all 536 unresolved occurrences.
The seven #152 questions still require the explicit contracts above; unreviewed
corpus candidates must not be called confirmed matching failures.

Promotion requires independent review of representative eligibility changes,
approved scope contracts where needed, version/cache acceptance review and the
existing release checks. Keep production gate defaults OFF, persistence rejection
active and old scorers intact. Rollback is simply leaving the new explicit entry
point unused; no database migration or score restoration is needed.

## Corpus-Wide Recognition and Scope Resolution — Final Review

2026-10-22 follow-up. The same branch/HEAD and uncommitted v1.24/v1.25 changes
were preserved. **One generalized approved-alias/source defect is corrected in
an explicit v1.26 experiment. Two real JDs demonstrate its allocation/scope impact.
The wider unresolved-capability backlog remains review-dependent.** No published
taxonomy, registry, scorer constant, saved analysis or production gate was changed.

### Final outcome matrix

| Required category | Verified outcome | Status / existing destination |
|---|---|---|
| Existing-policy recognition defect corrected | Native punctuation repair/trimming damages exact approved dotted aliases. `.NET` and case variants of `Node.js`/`React.js` must retain their registered spelling. The registry already owns these identities/aliases; no vocabulary was added. | Implemented in native surface normalization and trim seams, explicitly OFF by default. |
| Proven decomposition defect corrected | Damaged `.NET` becomes a false sentence boundary. Job 556 loses source objects and acquires two allocations for one requirement line; Job 595 splits one example scope into an easier Angular fragment and an orphan fragment. | Corrected using existing sentence/list/coherent-parent functions, without inventing a new AND/OR parser. |
| Repaired-scope scoring safety | Correctly restored text can expose an unapproved compound/activity scope to generic numeric matching. | v1.26 rejects numeric evaluation when a changed source group fails the existing complete-technology identity guard; parsing and recognition remain available for review. No fabricated NONE, zero or whole-JD percentage is returned. |
| Genuine missing taxonomy coverage | The two inherited independently confirmed NAC routing controls represent one network-admission capability gap, distinct from database authorization, packet capture and DNS/DHCP. | Existing capability-maintenance/governed publication workflow. No capability, alias or evidence credit was published. Other suggested gaps remain unconfirmed. |
| New recognition/scope/credit policies requiring approval | Regular-plural observations, broad database knowledge, named framework lists, lifecycle action completeness and professional/teamwork scopes. | Review contracts below; current finite published matchers are not silently broadened. |
| Correctly rejected or unresolved dimensions | AWS product-name text cannot prove API development; bare NET is not an approved `.NET` alias; a mixed example parent cannot be reduced to Angular; missing candidate profiles cannot prove absence of evidence. | Preserve guards and source limitations. Unresolved does not mean unsupported. |
| Identical-input corpus recognition results | Saved view unchanged; experimental raw interpretation has one fewer capability recognition and one more unresolved row, with the same total row count. | A misleading partial recognition is removed. No count-reduction claim. |
| Independently justified evidence effects | Synthetic original-record UI implementation remains correctly evaluable after case-preserving alias parsing; a document lacking that claim stays NONE. Published v1.17 and existing v1.24/v1.25 regressions pass. | Actual shared builders exercised. No historical candidate-score delta asserted. |

This is a bounded source-correctness fix, rather than a speculative matching
expansion. It matters even though it does not lower the unresolved count: the old
parser could give one source requirement two parent allocations and recognize an
incomplete fragment as if it were a complete independent requirement.

### What was actually reused and corrected

`_normalise_requirement_surface` unconditionally inserted a space after punctuation
before an uppercase letter. Thus `.NET` became `. NET`; independent trim seams then
removed its leading dot. The existing narrow-structure tests already documented
why a partial token-only patch was insufficient. The completed correction:

1. Builds a request-local, escaped whole-alias pattern from the **existing approved
   technology registry**, including its existing case-insensitive matching contract.
2. Preserves punctuation owned by a complete registered alias during ordinary
   sentence-spacing repair. Unregistered namespaces/suffixes do not become aliases.
3. Preserves alias-owned leading punctuation consistently through native sentence,
   comma-list, clause-record and other trim seams.
4. Runs the same native decomposition, source grounding, resolver and evidence
   evaluator. No new capability resolver, lexical synonym list or credit rule exists.
5. Before numeric evaluation, `_require_admissible_alias_preview` compares native
   canonical geometry for the same source with only alias preservation disabled.
   Changed groups must satisfy the existing `technology_identity_scope` admission,
   including its original-parent/activity guards. Otherwise evaluation raises an
   explicit recognition-only review error. Unchanged groups are not suppressed.

This last guard was present at the interruption and has now been verified on the
final code. It applies before evidence matching in both native and coordinated
entry points. Jobs 556/595 remain inspectable as corrected recognition inputs,
but their repaired mixed source scopes cannot produce a numeric v1.26 analysis.
React-only evidence also cannot turn an Angular/Node.JS/React development parent
into a full proof. This is fail-closed experimental input admission, not a new
credit policy or a claim that every rejected scope is unsupported. Approved simple
React.JS recognition still reaches existing matching through all three actual
workflow builders; unrelated document evidence stays NONE. Pure approved aliases
are not globally disabled. Generalizing numeric admission to activity-bearing
parents needs a separately reviewed complete-scope contract.

`coordinated_runtime.approved_alias_surface_preview()` is explicit and request-local.
It resets on exceptions and does not change an environment/global production gate.
Analyses in that context are stamped `stable-evidence-v1.26-phase6d30`, policy
`approved-registry-alias-punctuation-v1`, a developer namespace and a separate input
fingerprint incorporating the approved registry contents. Bare v1.26 identities
are rejected by the central persistence guard. The original v1.24 and v1.25 entry
points remain intact; the new surface context is not automatically selected by
either or by a production UI. The base scorer and eligible-fallback flag are
recorded, rather than claiming every experimental policy has been combined.

The earlier test-only structural simulation was adapted to the shared trim helper;
all its independent expected results remain unchanged. No historical oracle was
rewritten to endorse this implementation.

### Identical inputs, separate views and measured effects

The inputs remain the same tracked primary fixture (SHA-256 `a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`)
and separately catalogued alternate fixture (`6b5edb4287cceaae6b6c49a13fb4b149666a2514aaada34deb89e29ec2b7c299`).
Published taxonomy v1.6 and registry v1.3 bytes remain unchanged. The saved corpus
still represents historical v1.16/v1.5 analyses; current recognition does not
relabel those archived analyses or supply their missing complete candidate profiles.

| Metric | Saved before | Same saved inputs, experiment | Raw before | Same raw inputs, experiment |
|---|---:|---:|---:|---:|
| JDs | 30 | 30 | 30 | 30 |
| Requirement rows | 727 | 727 | 716 | 716 |
| Capability resolved | 191 | 191 | 191 | 190 |
| Technology identity resolved | 0 | 0 | 6 | 6 |
| Unresolved occurrences | 536 | 536 | 519 | 520 |
| Distinct unresolved IDs | 532 | 532 | 515 | 516 |
| Distinct normalized unresolved wordings | 534 | 534 | 517 | 518 |

Saved input geometry is unchanged. Damaged saved text such as bare `NET` was not
“repaired” by borrowing a different raw view. Experimental raw geometry changes
only in jobs **556 and 595**, using the exact same raw JD fingerprints. The unchanged
716-row aggregate hides offsetting changes: Job 556 is 23→24 rows; Job 595 is 16→15.
These are different derived canonical geometries, not compatible historical score
replays. They must not reuse old canonical-allocation/cache receipts.

- **Job 556:** the registered `.NET` spelling survives. The backend technology
  source line now has C#, `.NET (MVC & Core)` and SQL Server children under one
  source parent, with total fraction approximately 1 (`.999999` from existing
  six-decimal rounding), previously 2. Its additional backend obligation remains
  in original parent provenance; the children do not become unsupported pure
  identity proofs. An earlier truncated role object also retains its `.NET`/SQL
  Server tail. No implementation responsibility is inferred from tool names.
- **Job 595:** the complete Angular/.NET/C# **example** parent stays together.
  The incomplete Angular-only capability recognition is removed, rather than
  awarding credit to one example. Source allocation changes from 2 to 1.

No newly assigned corpus capability identity is counted as an evidence match.
There are **zero measured historical candidate-credit changes** because complete
frozen candidate contexts are absent. Existing v1.25's separate synthetic 30-JD
probe still reports its prior one NONE→WEAK result; it is not a historical score.

### Recurring recognition review groups

The complete unresolved inventory was inspected through the existing native
resolver, registry/identity guards, predicate observations and source-aware inventory.
The 21 raw-view predicate/plural observations form the following overlapping groups:

| Existing concept | Observations | Distinct JDs | Decision boundary |
|---|---:|---:|---|
| Stakeholder collaboration | 9 | 7 | Largest recurring group. Engagement/coordination must be separated from merely mentioning stakeholders or explaining concepts. A new whole-word plural matcher requires review through existing maintenance; do not globally grant collaboration credit. |
| API development | 4 | 3 | Three RESTful-API plural candidates across jobs 31/479; one AWS product-name observation is correctly excluded by the already-published product guard. Retain that rejection. |
| Database design | 3 | 3 | Data-model/schema activity, broad database knowledge and mixed obligations are not interchangeable. In particular, database product knowledge must not become schema-design credit. |
| Data processing | 2 | 1 | Data-pipeline plural candidates include multiple actions/qualifiers. Preserve full source scope; recognition alone does not prove all obligations. |
| UI development | 1 | 1 | User-interface plural wording plus responsiveness/building scope. A React name alone does not demonstrate all modifiers. |
| Live environment | 1 | 1 | Production-environment plural and actual responsibility scope require review. |
| Configuration | 1 | 1 | App configuration is not automatically the entire existing operational-configuration scope. |
| Motivation | 1 | 1 | “Interests” in an application invitation is not proof of an applicant's explicit same-domain motivation. |

There are 22 concept associations across 21 rows because a mixed row has two
observations. These are neither 21 confirmed defects nor approved aliases.
Current `any_terms` and governed contextual variants are finite, explicit contracts.
The approved `web services` product-context variant **already executes correctly**:
it does not authorize inferring API authorship from Amazon Web Services. The
existing multiword-plural `resolver_improvement` draft mechanism is reusable for
reviewed multiword candidates; it does not authorize a blanket plural expansion.
Single-word or meaning-changing definition proposals belong in the existing
maintenance review/update path, not an ad hoc runtime synonym dictionary.

Recommended next recognition decision: review the existing stakeholder and
RESTful-API groups as source-bound batches, with their exact full obligations,
negative controls, existing matcher guards and native impact receipts. Require
separate evidence-scope approval wherever added recognition would expose unsafe
whole-parent recovery. Frequency is a prioritization signal, not approval.
No other high-impact, already-approved recognition rule was independently proved
to be skipped at runtime. That finding does not establish that the remaining
requirements are unsupported or that all existing definitions are sufficient.

### The 140 possible-compound occurrences

All 140 saved-view occurrences were enumerated with original wording, input
fingerprint, native structural observations and source-availability diagnostics.
Their mutually exclusive **review cue strata**, not invented semantic gold, are:

| Cue stratum | Count |
|---|---:|
| Explicit AND cue | 114 |
| Explicit OR cue | 8 |
| Coherent/example-parent cue | 7 |
| Mixed AND/OR cues | 5 |
| Slash or mixed-scope review | 5 |
| Explicit alternative/one-or-more cue | 1 |
| Total | 140 |

An AND token does not prove a decomposition defect or that all named words are
independent obligations. Native component observations are retained separately.
All 727 saved projection rows lack native source-provenance receipts; locating
their wording in a raw JD is not permission to graft a fresh receipt onto them.
The raw-only cohort independently supplies native provenance. No clear obligation
is inferred merely because its cue stratum has an explicit connector.

Existing OR/example preservation, safe independent clauses, bounded named lists
and coordinated-action policies remain in use. No new AND/OR/slash semantics were
implemented. The punctuation-driven false decomposition is proved against source;
the other proposed compound/scope interpretations require the decisions below.
In particular, the earlier presentation-cleanup prototype still exposes API/REST/
gRPC scope risk and was **not** promoted.

### Seven regression examples: precise approval decisions

These remain policy decisions, not application-specific matching patches. Each
contract must be reusable and source-bound before any numeric change. Actual
original #152 evidence was inspected in the preceding phase; this follow-up does
not claim another historical rescore or replace it with current application data.

| Case | Recommended explicit decision / admissible positive | Required negative / ceiling |
|---|---|---|
| `req_d8a925b5b34e` project objectives/role | Decide whether a single original record describing an owned contribution to an explicitly shared project deliverable can support partial participation. Recommend at most WEAK under a separately approved professional-scope rule. | Team membership/title alone, generic project completion or an inferred trained role cannot establish the full claim. Never alias participation to end-to-end delivery. |
| `req_26d895b9a27f` collaboration/lifecycle | Preserve the complete software object and mandatory collaboration/specify/design/build/maintain obligations. Extend existing mandatory-action admission only after review; require one original record for complete ownership and retain native/P3 ceilings. | Separate bullets must not fabricate complete lifecycle ownership. One build/integration claim is not DIRECT for all actions. The existing three-action P3 rule is not automatic authority for this larger scope. |
| `req_30482086845a` continuous improvement | Decide whether an explicit owned introduction/improvement of a reusable development practice, with a concrete quality/workflow goal, can support WEAK for this broader obligation. | Merely using CI, a generic “best practices” adjective, or unrelated tool installation is insufficient. No automatic DIRECT or CI-to-practice equivalence. |
| `req_c3b362e0255b` SQL/NoSQL | Keep slash scope pending unless a reviewer explicitly approves ANY, ALL or examples. Under an approved knowledge-only ANY contract, attributable concrete data-access/query activity could support a bounded partial decision; product-to-family meaning must itself be approved. | SQL alone cannot prove a mandatory SQL AND NoSQL obligation; do not infer schema design or unapproved database-family relationships. Separate claims cannot be reworded into one complete ownership proof. |
| `req_67c5d07c55c1` frameworks | Recommend retaining ALL named frameworks unless the source explicitly or independently reviewed context establishes examples/ANY. Preserve the full-stack parent obligation and allocation. | React-only activity cannot satisfy AngularJS+NodeJS+ReactJS. Existing ReactJS recognition is not missing. No change to native ALL semantics or broader credit until approval. |
| `req_73ffb410c613` engineering concepts/Agile | Treat the conjunction as containing distinct obligations. Require explicit engineering-concept and Agile-practice evidence; any partial professional/knowledge credit needs its own approved boundary. | GitHub Actions/CI and generic coding do not prove Agile. Missing Agile proof is not replaced by an unrelated taxonomy identity. |
| `req_ba468f2924d8` effective teamwork | Review a bounded generic-teamwork definition through existing maintenance. A proposed WEAK tier would require concrete owned collaboration toward a shared deliverable in one original record. | Bare “team player”, incidental co-membership and same-function teamwork do not establish effectiveness or cross-functional/stakeholder coordination. Existing named-function safeguards remain. |

For approval, accept or reject these shared contracts with exact positive/negative
source examples, rather than approving a score for application #152. Its seven
questions remain pending and six unsupported examples remain protected by the
existing review and synthetic regression controls. No framework/Agile/database
knowledge policy was quietly introduced here.

### Independently reviewable benchmark and artifacts

`phase3a_pending_review_companion.md` contains all **38** original pending wordings,
current child-only recognition, individually grounded additional source scope,
unapproved candidate identities, specific human questions and a deduplicated
catalog of current native requirement contracts/exclusions. No wording was withheld
by the privacy filter; no candidate résumé/evidence text is included.

Its JSON companion also retains the archived original recognition receipt and
original input/source fingerprints. Current v1.6 contract snapshots are explicitly
**not historical taxonomy reinterpretations**. Additional verified parents are
explicitly outside the original child-only V5 packet. They are not silently
admitted as frozen V5 evidence.

The original V5 packet and blank receipt mechanism are untouched. Its exact bytes
(`ee08555df22ef5f29d0e103cb1dba78efec92beb719a252f5e71ecab4069bf7c`)
and the recovered V3 source bytes were authenticated through the tracked original
predicate manifest and its independently anchored fixture validator. All 38 new
companion judgments remain blank/PENDING. The companion is openly exposed-context
review, **not independently blind gold and not eligible for automatic gold import**.
Independent blind adjudication still uses the original existing V5 packet and its
validators; a context-aware human decision must be separately recorded through
existing governance. Two inherited NAC controls were not manufactured into new
pending decisions or new current candidate-credit labels.

Ignored diagnostic exports (not test/launch dependencies):

- `reports/phase3a_followup_final_review/corpus.json`: 215,408 bytes; seal
  `62e13e93ad49638b19413b8b66a39bb940d3961a2b6479f331259229250d6f43`.
- `reports/phase3a_followup_final_review/review_companion.json`: 343,695 bytes; seal
  `b96e5228f2c6f56ce29fb84093eea52692be93483c8cd922a910bce97d33482d`.

The corpus export includes all 140 scope-review locators, the 21 predicate
observations, two affected raw-JD before/after ledgers, exact source and current
implementation hashes, and explicit no-historical-evidence-replay flags. Export
generation refuses stale implementation fingerprints. An earlier metadata-only
formatter revision invalidated its prior export; the final corpus test was rerun
instead of accepting or editing the old fingerprint.

Reproduce using the existing script's new explicit `--final-review-dir` option
with a **new** directory under `reports/`. It refuses to overwrite prior artifacts.
The 38-source export requires the authentic locally available, independently
pinned V5/V3 originals and fails closed if they are missing/changed. Automated
companion tests use authored disposable fixtures; automated corpus tests regenerate
from tracked corpus fixtures. Neither requires ignored acceptance JSON or Git history.

### Final verification and workflow compatibility

All runs used the existing strict offline launcher and disposable scratch stores,
Python 3.13, no model/embedding/provider/network calls and no real database access.
Only mock research transports execute in maintenance tests. No production or copied
candidate database was opened during this follow-up. Full project CI was not run.

Commands use `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B
scripts/run_offline_release_checks.py --scratch-root reports/<lane>` plus:

| Lane | Explicit test arguments | Result |
|---|---|---|
| `phase3a_followup_scoring` | `tests.test_evidence_relevance_preview tests.test_phase3a_eligible_evidence tests.test_capability_none_recovery tests.test_api_evidence_completeness tests.test_capability_taxonomy_loader tests.test_capability_taxonomy_v1_4_boundaries tests.test_capability_taxonomy_v1_4_cpp_boundaries tests.test_capability_taxonomy_v1_4_single_row_reselection tests.test_jd_atomic_requirement_decomposition tests.test_coordinated_action_implementation` | **115 PASS**, 228.371s |
| `phase3a_followup_integration` | `tests.test_taxonomy_maintenance_service tests.test_tqd3_corpus_gap_resolution tests.test_taxonomy_discovery_registry_integration tests.test_taxonomy_discovery_triage tests.test_source_aware_inventory tests.test_bulk_unresolved_v1 tests.test_unresolved_independent_review_v5 tests.test_predicate_historical_fixtures tests.test_job_discovery_job_match tests.test_document_grounded_analysis tests.test_initial_analysis_explainer tests.test_phase8_verification` | **165 PASS**, 103.320s |
| `phase3a_followup_final_verified` | `tests.test_phase3a_final_review tests.test_phase3a_alias_surface` | **12 PASS**, 38.642s, final review/export code |
| Structural controls, also run with the new alias tests | `tests.test_narrow_structure_candidates tests.test_structural_remediation` | All **20** unchanged structural expectations passed |
| Separate historical lane | `tests.test_unresolved_semantic_evidence.FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged` | **1 pre-existing FAIL**, 0.147s; old protected-source map versus today's source tree |

The initial new punctuation test incorrectly expected an unseparated `.NET.Then`
string to be interpreted as ordinary sentence text. That is ambiguous with an
unregistered dotted namespace. The test was corrected to explicit terminal-space
punctuation; no unknown namespace alias was invented. The original seven-test alias module
and all existing structure expectations then passed. No historical expectation or
gold label was weakened. The historical source-hash failure remains separately
identified, reproduced and untouched; it is not included in a blanket CI-pass claim.

The earlier 115/165/12 results above predate the interrupted final admission guard;
they are retained as earlier-run evidence only, not final verification. The resumed
verification below reruns the relevant lanes on the guarded final code.

Resumed final-code verification (same Python/strict offline command prefix):

| Lane | Explicit test arguments | Final result |
|---|---|---|
| `phase3a_resume_small` | `tests.test_phase3a_alias_surface tests.test_narrow_structure_candidates tests.test_structural_remediation` | **28 PASS**, 2.077s; interrupted guard confirmed complete. |
| `phase3a_resume_final` | `tests.test_phase3a_alias_surface tests.test_phase3a_final_review tests.test_narrow_structure_candidates tests.test_structural_remediation` | **33 PASS**, 126.282s; final enhanced native/coordinated negative and fingerprint controls, full identical-input corpus. |
| `phase3a_resume_scoring` | `tests.test_evidence_relevance_preview tests.test_phase3a_eligible_evidence tests.test_capability_none_recovery tests.test_api_evidence_completeness tests.test_capability_taxonomy_loader tests.test_capability_taxonomy_v1_4_boundaries tests.test_capability_taxonomy_v1_4_cpp_boundaries tests.test_capability_taxonomy_v1_4_single_row_reselection tests.test_jd_atomic_requirement_decomposition tests.test_coordinated_action_implementation` | **115 PASS**, 626.487s; v1.24/v1.25, QueryAI/PostgREST negatives, API V1.1, 30-JD gate-OFF equivalence and coordinated acceptance invariants. |
| `phase3a_resume_integration` | `tests.test_taxonomy_maintenance_service tests.test_tqd3_corpus_gap_resolution tests.test_taxonomy_discovery_registry_integration tests.test_taxonomy_discovery_triage tests.test_source_aware_inventory tests.test_bulk_unresolved_v1 tests.test_unresolved_independent_review_v5 tests.test_predicate_historical_fixtures tests.test_job_discovery_job_match tests.test_document_grounded_analysis tests.test_initial_analysis_explainer tests.test_phase8_verification` | **165 PASS**, 275.552s, final guarded implementation. |
| `phase3a_resume_v121` | `tests.test_developer_comparison tests.test_coordinated_library_sources` | **22 PASS**, 212.571s; published/v1.21 isolation, null scores, currentness, explicit evaluation/rerender behavior and original occurrence ownership. |
| `phase3a_resume_historical` | `tests.test_unresolved_semantic_evidence.FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged` | **1 pre-existing FAIL**, 1.800s, same protected-source-map assertion at line 127. No assertion or historical bytes changed. |

The four final lanes total **335 passing tests** (33 + 115 + 165 + 22), excluding
the repeated initial 28-test confirmation and the separate known failure. No full
CI run or blanket green-CI claim is made. The unchanged v1.25 synthetic corpus
control again observes one NONE→WEAK row with zero recognition changes; that is
synthetic evidence evaluation, not a recovered historical candidate result.

The final alias module has eight tests. The explicit mixed-scope test covers both
native and coordinated entry points, Jobs 556/595 and React-only evidence for an
Angular/Node.JS/React activity parent. Repeated admissible previews have identical
fingerprints, distinct from the published evaluation. All four exported
implementation hashes and all source-file hashes were checked against current
bytes after regeneration. Both export seals validate. AST parsing passes for all
11 touched/preserved Python files. Git working/index whitespace checks pass and
the index is empty. Taxonomy, historical fixture tree, original V5 packet,
`developer_real_comparison.py` and the preserved dashboard report retain their
verified bytes. No database was opened outside disposable test stores.

Existing 30-JD independently pinned gate-OFF equivalence, API V1.1, native NONE/P3
ceilings, original-record recovery, source attribution and nullable withheld scores
passed. Parent allocation, false Angular recognition, exact alias preservation,
bare NET/unapproved-name negatives, explicit AND/OR/examples/slash/negation controls,
determinism, exception cleanup and bare-version persistence rejection are covered.

Actual Job Finder `_default_stable_builder`, document
`analyze_actual_resume_against_jd` and Phase 8 `build_current_baseline_analysis` were
executed under the explicit alias context. They use their own Library/document/
before-after source contracts. An owned synthetic React.JS UI implementation can
be recognized without false sentence fragments; unrelated document text cannot
borrow the supplied structured claim. These checks establish shared-builder
compatibility, **not** production UI activation or saved-analysis migration.

Published JSONs, registry, historical fixtures/oracles and original pending-review
artifacts remain unchanged. `git diff --exit-code HEAD -- taxonomy tests/fixtures`
passes. Whitespace and AST checks are included in the final workspace verification.
The published scorer remains v1.17, gate defaults OFF; v1.24/v1.25 policy semantics
remain preserved. New canonical IDs/allocation in v1.26 cannot be presented as a
reproduction of historical Job Match scores or activated in saved caches.

Any later promotion must separately approve the changed parser geometry and
complete-scope admission, retain distinct scorer/cache fingerprints and invalidate
incompatible canonical/allocation receipts. This audit provides no migration or
publication authorization. The v1.26 request-local context remains developer-only.

Files changed for this follow-up:

- `analysis_stability/stable_evidence_scoring.py`: approved-alias punctuation/trim
  primitive and fail-closed changed-scope admission behind the explicit OFF context;
  existing parser/evaluator and complete-technology guard reused.
- `analysis_stability/coordinated_runtime.py`: scoped approved-registry pattern,
  v1.26 identity/knowledge fingerprint and publication rejection.
- `scripts/preview_bulk_unresolved_v1.py`: bounded identical-view comparison,
  compound review ledger and authenticated exposed-context companion export.
- `tests/structure_candidate_simulation_support.py`: shared-trim adapter for the
  existing test-only hypothesis; independent expected outputs unchanged.
- `tests/test_phase3a_alias_surface.py` and `tests/test_phase3a_final_review.py`:
  alias, scope, authority, corpus, review/tamper and portability controls.
- `phase3a_pending_review_companion.md` and this appended report section.

All pre-existing Phase 2F/3A changes and `coordinated_batch_dashboard_review.md`
were retained. No stage, commit, push, merge, reset, cleanup or publication.

### Bounded final decision

**Ready for review of the verified alias/source correction and the 38-case packet;
NO-GO for production activation or claiming corpus-wide capability resolution.**
The full-corpus audit identified a real scope/allocation correctness defect and
corrected it without forcing taxonomy matches. The largest remaining recognition
groups require actual reviewed definition/inflection or scope decisions through
existing maintenance, rather than more speculative runtime patches. The immediate
human decisions are the source-bound recognition batches and seven reusable policy
contracts above. No new research architecture or indefinite diagnostics stage is
needed to make those decisions.
