# A1 governance closure — 2026-10-23

## Decision

**Formal Taxonomy Maintenance approval: NO-GO. Production publication: NO-GO.
Further A1 engineering should stop under this task.** The existing evidence and
contract packet is ready for human policy discussion, but not a publication-ready
governed artifact.

No small compatibility correction preserves the complete A1 contract. Its source
admission, unresolved-only precedence and null-credit semantics are executable
only in the developer review function. Publishing its lexical overlay would not
publish those safeguards. Fixing the publication collision alone would therefore
be unsafe. The task's stop condition applies: no runtime/governance redesign or
policy widening was implemented.

Only `tests/test_a1_governance_closure.py` and this report were added. All previous
Phase 2F/3A changes remain. No scorer, taxonomy, registry, gate, cache, persistence
or publication implementation was changed in this closure task.

## Exact incompatibilities

| Boundary | Verified finding | Type |
|---|---|---|
| A1 input availability | The three raw Job 31/479 parents are available and admissible to the existing review function. Saved projections do not have the required source receipts. Missing historical receipts cannot be filled from a fresh raw interpretation. | Source-authority limitation; not missing raw wording. |
| Candidate/research | `governed_research._validate_candidate_identity` requires an eligible native route. A bare plural candidate is not eligible. `interpret` accepts an explicit `requested_recognition_rule` only when it equals the old `API_RECOGNITION_FALLBACK` and passes its complete-scope grammar. A1 is a different contract. | Unsupported governed request, not a missing approval flag. |
| Draft creation | `create_local_governed_draft` first calls `propose`, whose old complete REST-development grammar rejects all three qualified/compound A1 cases before any database access. `resolver_draft` v2 describes inflected phrases or the old bounded fallback; it does not encode A1 source admission, precedence or review disposition. | Unsupported contract fields/semantics. |
| Temporary overlay | `resolver_overlay` creates a temporary taxonomy. Its corrected additive merge preserves variants/exclusions/fallbacks, but those variants run in ordinary taxonomy matching, before the registry/identity fallback. A1 instead runs after all existing recognition. | Runtime precedence mismatch. |
| Credit and scope | The ordinary native scorer does not interpret an A1 review receipt or impose its null-credit disposition. The review function's source/action checks do not travel with a generic phrase variant. Complete compound obligations and modifiers cannot be guaranteed by that variant. | Runtime policy mismatch. |
| Validation inputs | All 30 primary fixtures have only `raw_jd_text` in `frozen_inputs`; no original extracted profile, evidence snapshot or context. The governed `temporary_impact` requires a compatible replayable corpus, checks evidence/context identity and performs native scoring replay. | Missing authentic historical scoring inputs. Synthetic controls cannot substitute for them. |
| Review integrity | `_approved` requires saved research, exact deterministic draft, current fingerprints, saved validation and an explicit reviewer approval bound to those bytes. A1's diagnostic packet is not such a result or draft. | Legitimate artifacts not created; validators correctly reject substitution. |
| Publication | `_prepare` rejects plural publication into an entry already containing contextual variants. The current API entry has the published guarded `web services` variant. The generic publication branch also freezes product names over its applied list; simply removing the collision guard would not preserve A1's complete contract or necessarily retain existing static exclusions exactly. | Publication incompatibility; not permission to weaken preflight. |

These checks are in `governed_research.py` (candidate validation, interpretation,
draft creation and temporary impact), `resolver_improvement.py`,
`governed_requirement_resolution.py`, `governed_publication.py` and
`database/taxonomy_discovery_review_manager.py`. The taxonomy schema supports the
existing API scope/fallback contract, not an arbitrary A1 contract field.

## Decisive executable counterexample

Using an authored disposable source requirement, **“Develop efficient, secure
RESTful APIs”**, and synthetic evidence **“Implemented custom Java REST API
endpoints.”**:

| Execution | Observed result |
|---|---|
| Existing A1 review function | Pending recognition candidate; contribution and whole-JD score **null**. |
| Same phrase added via the generic additive temporary taxonomy, then ordinary native scoring | **DIRECT, 100** for this one-requirement synthetic input. |

This is not a real candidate score or an asserted new gold label. It demonstrates
that the generic artifact does not carry A1's review semantics. Endpoint authorship
does not independently establish efficiency/security. Allowing that artifact
through preflight would not close the governance connection safely.

A complete implementation would need an explicitly supported typed requirement
rule in candidate interpretation/draft regeneration, runtime unresolved-only
dispatch, source/action admission and parent review/credit handling, plus matching
validation and publication support. That is a policy/runtime extension across
existing layers, not a metadata or merge repair. It exceeds this task's allowed
small compatibility correction. Adding ignored JSON fields, forcing a candidate
route, relabeling the packet as a draft, accepting v1 bytes as v2 or removing the
publication guard would all conceal this mismatch.

## Legitimate lifecycle verification

Tests exercised the lifecycle only as far as legitimate inputs permit:

1. **A1 source → existing draft creator:** all three exact positive wordings
   produce review candidates, but the supported old draft contract rejects them.
   No review store is opened/created. A source packet exists; an approved artifact
   does not.
2. **Supported bounded contract control:** existing fixture helpers create a real
   local deterministic research result, saved draft and native validation in
   disposable storage. No reviewer approval is written by this new control.
   Publication preflight correctly remains not ready.
3. **v1/v2 boundary:** a resealed synthetic v1 draft is rejected by the current
   v2 overlay validator. Resealing cannot make an incompatible contract current.
4. **Existing lifecycle regressions:** unchanged tests exercise labelled fixture
   approval/preflight/publication/rollback and stale/missing/forged artifacts.
   Those disposable simulation receipts are not real reviewer approvals.

The existing store allows replacing a sealed legacy resolver draft only through
its explicit rejected-legacy replacement path; it does not silently reinterpret
an approved or pending v1 draft. v2 fixes additive merging, not A1 semantics.

## Preserved corpus and safeguards

| Separate view | Rows | Native unresolved baseline | Pending A1 review candidates | Published recognition/scoring changes |
|---|---:|---:|---:|---:|
| Saved historical projection | 727 | 536 | 0 | 0 |
| Native raw-only | 716 | 519 | 3 | 0 |
| Explicit v1.26 raw-only | 716 | 520 | 3 | 0 |

The three candidates remain Job 31 `req_d0a20edbb7ae` and Job 479
`req_5eabf1000188`, `req_fc4e6757e8e4`. Job 566
`req_b34860727bff` remains the AWS negative control. Framework/security modifiers,
develop+integrate, develop+consume and complete parent provenance/allocation stay
intact in the existing A1 tests. Previously resolved identities, API V1.1,
product exclusions, old REST fallback, v1.24/v1.25/v1.26 isolation and workflow
authority remain protected. No three-candidate result is described as solving
the 536 saved unresolved occurrences or as an evidence-matching success.

S1 remains a separate proposed action-to-stakeholder contract. No stakeholder
plural alias, grammar or runtime behavior was added.

## Actionable next work: human review, not more A1 plumbing

1. Use the existing **38-case original pending packet and blank receipts** with
   `unresolved_independent_review.py` and its validators. Obtain independent
   judgments before exposing proposed answers. The existing context-aware
   companion is explicitly nonblind and must not be imported as independent
   gold. Reviewers must record exact source spans, uncertainty and deferrals.
   Keep all 38 pending until legitimate judgments arrive.
2. Separate recognition judgments from scope/credit decisions. Route verified
   definition/alias gaps through existing maintenance; keep decomposition,
   evidence relevance, incomplete profiles and missing credit policies distinct.
   Do not turn an unresolved ID into an unsupported-evidence label.
3. Put the seven reusable questions before the policy reviewer as shared
   contracts: owned project participation; complete collaboration/lifecycle
   actions; owned development-practice improvement; SQL/NoSQL ANY versus ALL
   versus examples; named-framework completeness; engineering concepts AND
   Agile; and bounded effective teamwork. Retain the positive/negative boundaries
   in the prior decision matrix. None is approved by this closure.
4. After independently reviewed labels exist, use approved controls to validate
   generalized recognition/decomposition corrections across the same source view.
   Evaluate evidence only with complete, attributable candidate inputs. Stop A1
   engineering now; reopen only if a separate decision authorizes the required
   runtime/credit contract. No new architecture or scorer version is proposed.

## Tests and integrity

The first focused closure run passed **3 tests in 1.518s**. The final lane passed
**77 tests in 66.020s; zero failures or errors.** All runs use Python 3.13, `-B` and the strict
offline launcher with disposable storage. No real application/maintenance database,
network, model or embedding service is accessed. No full project CI is run.

Final command:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/a1_governance_closure_final tests.test_a1_governance_closure tests.test_reviewed_api_plural tests.test_api_evidence_completeness tests.test_governed_requirement_resolution tests.test_governed_requirement_activation_v1_1 tests.test_tqd3_governed_research.GovernanceImpactTests tests.test_taxonomy_maintenance_service tests.test_evidence_relevance_preview.RelevancePreviewTests.test_geometry_published_parity_and_determinism tests.test_phase3a_eligible_evidence.EligibleEvidenceTests.test_native_source_guards_none_ceiling_and_known_capabilities_unchanged tests.test_phase3a_alias_surface
```

The final lane includes the three new boundary tests, seven existing A1 tests,
eight API V1.1 tests, twelve governed-resolution tests, seven disposable lifecycle
tests, seven governance-impact tests, 23 maintenance tests, two v1.24/v1.25
isolation controls and all eight v1.26 tests. No historical assertions or oracles
were edited. The supported-contract lifecycle is a control, not evidence that
A1 itself reached the human-approval checkpoint.

Synthetic observation output is retained only in ignored disposable storage:
`reports/a1_governance_closure_final/offline-release-37e1f84e10d0470290566110aba15c45/a1_governance_boundary.json`.
No real requirement/resume evidence is exported by that observation.

The previously known historical protected-source-hash assertion remains separate
and untouched; it is not fixed or silently rewritten by this closure task.
Published files, original fixtures, earlier reports and prior implementation
hashes are checked without regenerating historical outcomes. All work remains
uncommitted; no staging, push, merge, publication or production-data writes.
