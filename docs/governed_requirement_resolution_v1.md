# Governed requirement resolution V1 — preview acceptance handover

V1.1 supersedes the capability-wide tightening preview described below. It adds a
fallback after exhausted native resolution, preserves Jobs 360/425 and existing
variants, supports the actual governor's isolated approval/publication/rollback,
and exposes historical snapshot 40 review. See `governed_requirement_resolution_v1_1.md`.
The original V1 report and its 1-new/2-removed results remain historical evidence.

**Functional native-resolver review is implemented. Production activation is blocked.**
No approval, publication, new capability, global stemming or production knowledge change was performed.

## Interface and native behavior

Open a saved Job Finder Job Match analysis, or the shared application Initial Analysis receipt.
Below the requirement table, expand **Unresolved Requirement Review**. Select a saved unresolved requirement.
The interface shows exact wording, importance, original JD source, parent scope and provenance.
**Inspect diagnostics** obtains the current native classification/rejection and existing capability contracts.
Lexical candidates and proposed full boundaries are not independent human-gold decisions.

**Preview proposed correction** explicitly builds an inactive bounded API-development policy and executes
the existing `resolve_requirement_with_production_knowledge` under the existing context-local
`temporary_taxonomy_scope`. No preview executes on rerender. Selection/input/current knowledge changes
discard prior preview state. **Reject proposed correction** discards the session-local preview; it never
creates a production rejection/approval receipt. **Download privacy-sanitized debug bundle** exports an
allowlisted, redacted JD-only ZIP, without candidate résumé evidence. **Approve and activate correction**
is disabled with concrete blockers; no decorative approval badge or replacement approval store exists.

The finite opt-in policy `bounded-rest-api-development-v1` reuses `backend.api_development`.
It accepts whole REST/RESTful API building/developing/implementing statements, including the three requested
positive controls. It rejects arbitrary tails, mixed object obligations, alternatives, negation,
familiarity-only wording, product names and shortened/conflicting parent context. Its matcher conjunctions,
product-context exclusions and applicant evidence tiers remain native. A matching JD predicate grants no
implementation evidence credit. The policy is absent from production JSON and inactive for all normal analyses.

## Demonstration and collateral review

`python -B -m scripts.preview_governed_requirement_resolution` uses the exact V1 database fingerprint,
read-only/query-only SQLite, latest active same-content-hash snapshots, original benchmark quarantine,
and conservative source privacy filtering. It refuses to overwrite its versioned output.
The final implementation independently reproduced the saved preview exactly after source/privacy hardening.

| Result | Count |
|---|---:|
| Active canonical inputs before quarantine | 656 |
| Non-benchmark/privacy-safe development inputs | 597 |
| Development jobs | 26 |
| Baseline unresolved | 449 |
| Proposed unresolved | 450 |
| Unchanged knowledge classifications | 594 |
| Newly resolved | 1 |
| Newly unresolved requiring review | 2 |
| Distinct affected jobs | 3 |

Exact changes:

- Job 146 / `req_9270e95898c8`: “Design and develop RESTful APIs” changes from UNRESOLVED to
  CAPABILITY_RESOLVED / `backend.api_development` through the real taxonomy resolver in temporary scope.
- Job 360 / `req_c8072bbc5839`: “Knowledge of Application Programming Interfaces (APIs) for web services using
  REST and RESTful web services” loses its existing API classification under the proposed implementation-only
  scope. Whether this knowledge requirement should retain recognition needs human policy review.
- Job 425 / `req_3dca18350c50`: “Preferably experienced in web service access and development and USB audio
  processing to enhance software capabilities” loses its existing API classification under the complete-scope
  rule. The USB obligation is not covered by API development; changing its saved classification still needs review.

These are knowledge-only comparisons, not evidence matches, scores or ranking changes. All 13 V2 development
cases are retained: only Job 146 changes; Job 163 remains unresolved and explicitly requires separate policy
confirmation. The nine partial and two non-applicable V2 cases receive no promotions. Applications are not
added to Job Finder totals. No frozen forty-case benchmark was used to design the policy.

All 13 provisional controls pass, with baseline and proposed native outputs in
`reports/governed_requirement_resolution_v1_preview.json`. Reading singular REST API documentation is already
recognized by the legacy literal selector; the proposed complete-scope policy rejects it. This is a proposed
policy restriction, not an assertion that the old selector violated its contract. Plural mentions without
implementation, negations, product names, REST/gRPC compounds, unrelated mandatory activities, alternatives
and unvalidated platform tails remain unresolved in preview. “Develop RESTful API endpoints” already resolves
under the legacy singular term and continues to resolve in preview.

## Precise activation blocker and next authorization

Existing governance was inspected and reused where compatible; it was not bypassed:

| Existing component | Reuse / limitation |
|---|---|
| `capability_taxonomy.classify_requirement_diagnostics` | Native selector; finite scope policy is optional and capability-specific. |
| `requirement_scope` | Whole-source boundary helper; no parser children or weights changed. |
| `production_requirement_resolver` | Unmodified, actual before/after resolver. |
| `temporary_taxonomy_scope` / `CapabilityTaxonomy` | Existing context-local preview and schema validation. |
| `candidate_refinement.product_context_names` | Existing product vocabulary and exclusion guard. |
| `governed_research.knowledge_fingerprint`, `matching.current_match_versions` | Existing freshness and content/version identities. No new production version system. |
| `resolver_improvement.resolver_draft/resolver_overlay` | Existing draft contract represents guarded plural phrases, not this capability-wide scope policy; its overlay replaces variants. |
| `governed_publication._approved/_prepare` | Requires linked persisted local research, exact approved draft/regression and current full scoring receipts; refuses pre-existing contextual variants. API already has a guarded web-services variant. |
| V1 backlog selection/quarantine and V2 manifest | Exact development sources only, read-only inventory; no gold decisions consumed. |

The existing local-deterministic research path does not require Tavily, but no valid scoped draft/publication
contract currently links it to this new policy. We did not fabricate research, approve a preview, clear the
pre-existing API variant, or create a competing writer. `activate()` fails closed even with explicit confirmation.
There is **no actual approved production activation demonstration** in this milestone.

Next human decision: accept/reject the preview and adjudicate the two collateral restrictions. A separately
authorized extension must preserve/merge existing variants, bind this scope policy into the existing local
draft/review/publication contracts, obtain full native scoring regression receipts and then explicitly publish
a bumped native taxonomy version. That work is not silently included here.

## Versions and preservation

Production taxonomy remains `phase6d-capability-taxonomy-v1.5`; registry remains `technology-registry-v1.3`;
scorer remains `stable-evidence-v1.16-phase6d20`. No scorer formula, thresholds, weights, registry, taxonomy JSON,
parser, project-selection or tailoring code changed. The unmodified resolver consumes an optional policy through
the taxonomy selector; without that policy, normal behavior is unchanged. Temporary knowledge uses the existing
taxonomy-version/currentness contract with a `review-only-<proposal fingerprint>` version. Future publication
must advance the native taxonomy version; no current bump is warranted for an inactive policy.

All production database bytes, saved snapshots and previous research artifacts were preserved. Checked 147
prior protected files excluding the three explicitly edited integration files. No Ollama, model, embedding,
Tavily, live benchmark or external calls. No approval, publication, commit, push, merge, reset or branch change.

## Files changed

Modified:

- `tailoring/capability_taxonomy.py` — validate and evaluate the optional finite API scope policy only.
- `tailoring/requirement_scope.py` — bounded whole-obligation/source guard; no evidence evaluation.
- `tailoring/initial_analysis_explainer_ui.py` — shared receipt integration point.

Added:

- `taxonomy_discovery/governed_requirement_resolution.py` — inactive proposal, native temporary preview,
  provisional controls, currentness checks, fail-closed activation and sanitized ZIP.
- `tailoring/unresolved_requirement_review_ui.py` — functional selection/inspection/preview/rejection/export.
- `scripts/preview_governed_requirement_resolution.py` — read-only development-pool demonstration.
- `tests/test_governed_requirement_resolution.py` — 12 core/native/scoring/source/privacy/currentness tests.
- `tests/test_unresolved_requirement_review_ui.py` — three explicit execution/rerun/rejection/freshness AppTests.
- `tests/governed_requirement_review_harness.py` — static repository-local AppTest entry point.
- `reports/governed_requirement_resolution_v1_preview.json` — sealed controls and all three corpus changes.
- `docs/governed_requirement_resolution_v1.md` — this handover.

## Focused validation

Final coverage: **118 distinct focused tests passed**, with no remaining assertion failures.

- `.venv\Scripts\python.exe -B -m unittest tests.test_governed_requirement_resolution tests.test_unresolved_requirement_review_ui -v`:
  initial 12 core passes, three temporary-script environment errors; static harness fixed the test setup.
- `.venv\Scripts\python.exe -B -m unittest tests.test_unresolved_requirement_review_ui -v`: 3/3 passed.
- `.venv\Scripts\python.exe -B -m unittest tests.test_capability_taxonomy_loader tests.test_phase6d_taxonomy_mapping tests.test_phase6d_stable_scoring_adapter tests.test_phase6d_stable_scoring_integration tests.test_phase6d_compound_splitting_refinement tests.test_requirement_importance_supporting tests.test_capability_none_recovery tests.test_phase8_claim_lineage tests.test_phase9e_registry_currentness_cache tests.test_phase9e_blueprint_selection -q`:
  46 passed; 26 fixture setup errors from Windows temporary-directory permissions.
- Process-local retry via `.venv\Scripts\python.exe -B -` of the failed duplicate-capability loader test plus
  `tests.test_phase9e_blueprint_selection`: **26/26 passed in 288.354s**.
- Final process-local `.venv\Scripts\python.exe -B -` run loading `tests.test_governed_requirement_resolution`,
  `tests.test_unresolved_requirement_review_ui`, `tests.test_initial_analysis_explainer`,
  `tests.test_tqd3_production_resolver_inspector`, `tests.test_low_confidence_project_selection_override`:
  **46/46 passed in 12.737s**.

The retry changes only test-process directory creation: replace `tempfile.mkdtemp` with UUID-named directories
created using inherited permissions (`Path.mkdir(mode=0o777)`), then use the ordinary unittest loader/runner.
No test assertions, production permissions or installed dependencies were modified. The initial failed attempt
left 26 inaccessible scratch directories under `reports/tmp*` (created 19:01:44–19:01:47). Removing only those
own test directories was also denied; no ACL repair or outside-sandbox execution was attempted. They are not
deliverable files. Python 3.13 validation remains a CI follow-up; local interpreter is Python 3.14.

Native empty-evidence full scoring remains zero while preview can resolve the API requirement; IDs,
importance, allocations and evidence caps remain intact. Existing Phase8 lineage, API/gRPC completeness,
manual override and Phase9E selection/currentness tests pass. No full project gate or full discovery was run.

## Manual acceptance steps

1. Open Job Finder's saved Job 146 analysis. Expand **Unresolved Requirement Review** below the requirement table.
2. Select “Design and develop RESTful APIs”, then **Inspect diagnostics**. Confirm current UNRESOLVED and the
   existing API capability candidate; inspect the exact source/parent provenance.
3. Click **Preview proposed correction**. Confirm native before UNRESOLVED, proposed CAPABILITY_RESOLVED /
   `backend.api_development`, and 13 passing provisional controls. No saved score should change.
4. Rerun/refresh and select a different requirement. Confirm no automatic preview execution and no stale
   selected-requirement result. Changing current knowledge requires a fresh explicit preview.
5. Download the sanitized ZIP and inspect its JD-only payload. Click **Reject proposed correction**; confirm
   the proposal disappears and ordinary production resolution still returns UNRESOLVED.
6. Inspect Job 163's stakeholder requirement separately; confirm no automatic stakeholder policy is enabled.
7. Confirm **Approve and activate correction** remains disabled with the exact governor blockers. Review the
   Job 360/425 collateral restrictions before authorizing further governance integration.

Stopped for user acceptance testing. Production activation is not ready.
