# Governed requirement resolution V1.1

**Implementation and isolated end-to-end publication: PASS. Live approval/publication: BLOCKED pending real receipts and explicit authorization.**

## Native integration

`bounded-rest-api-fallback-v1` is a finite, explicit recognition descriptor in the existing taxonomy's
`backend.api_development.requirement.recognition_fallback_rules`. The production taxonomy JSON is unchanged.
No rule is globally active. The ordinary production resolver first exhausts taxonomy, contextual variants,
registry mappings and identity resolution. Only UNRESOLVED inputs reach the optional bounded fallback.
Existing approved outcomes are never overridden. Rule provenance is returned and recorded in newer analyses.

The whole-obligation grammar recognizes designing/developing/building/implementing/creating REST/RESTful APIs,
optionally endpoints/services, or explicit experience doing those activities. It rejects negations, marketing,
familiarity alone, unrelated tails, AND/OR object mixtures and incomplete/conflicting source boundaries. Native
evidence tiers, REST/gRPC completeness, parent weights and eligibility remain separate and unchanged.
No job ID or requirement ID is embedded in the runtime rule. No global plural stemming or arbitrary rule language.

Approved singular API documentation/familiarity wording may already resolve under legacy rules. V1.1 preserves
that result; it does not introduce new fallback recognition or evidence credit for those negatives. This is
explicitly separate from legacy-scope tightening. Provisional control reports distinguish preserved baseline
outcomes from newly recognized API-development meaning; they are not independent human-gold adjudications.

## Original development comparison

| Gate | Actual result |
|---|---|
| Original development inputs | 597 across 26 jobs — PASS |
| Unchanged | 596 |
| Newly resolved | 1: EDB 146 / snapshot 40 / `req_9270e95898c8` |
| Newly unresolved | 0 |
| Different capability on previously resolved input | 0 |
| Unexpected changes | 0 |
| Jobs 360 / 425 | Baseline classifications preserved |
| Unseen controls | 7/7 passed |

The global V1 inventory fingerprint differs: a new CSIT snapshot 55 exists and active-job count changed from
325 to 323. The replay excludes later snapshots using the original frozen snapshot inventory boundary (54),
then verifies the full original active-snapshot inventory against V1 before proceeding. No cohort was silently
substituted. Original V2 canonical/JD hashes also match. Source inventory/cohort fingerprints and every changed
requirement are recorded in `reports/governed_requirement_resolution_v1_1_validation.json`.

Historical snapshot 40 remains untouched. This is current-version evaluation of its saved requirement,
not executable historical replay. Job Finder ranks are not discovered job IDs. Job 214 / snapshot 55 is the
separate CSIT role; do not use displayed rank #146 to select the EDB target. No application backlog was added.

## Actual governance bridge

The existing local-deterministic `governed_research.research_plan/execute_plan` creates a source-bound result
without a provider call. `resolver_draft` emits a sealed bounded-rule draft; `resolver_overlay` composes the new
rule without replacing any terms, evidence policies or contextual variants. Existing research/draft/impact/review
tables are reused. No parallel rule store, publisher or resolver was created.

`validate_governed_draft` executes the real native full-scoring `temporary_impact` and persists the exact receipt.
Approval and `_prepare` require that receipt's controls, draft fingerprint, current knowledge, corpus availability,
product vocabulary, duplicate-credit invariants and zero unexpected changes. A preview is not an approval receipt.
The existing governed publisher stages, validates, checks the parent artifact, journals intent and atomically
replaces the native JSON. Bounded-rule publication never triggers automatic snapshot refresh, even through an
older caller. Failed staging leaves the native artifact unchanged. Existing legacy publication behavior remains.

Isolated demonstration used actual persistence, native regression, the real review API, `_prepare`, public atomic
publisher, file deserialization/cache reload and ordinary resolver. Test reviewer is explicitly ISOLATED TEST
REVIEWER; no real approval or independent gold was fabricated. Native taxonomy advanced 1.5 → 1.6; source-bound
RESTful APIs resolved using the same capability ID and rule provenance. Existing web-services variants were
preserved. The finite rollback in the same governor uses its native atomic replacement/version mechanism,
checks the exact active artifact hash, removes only the added rule and advances 1.6 → 1.7. Behavior returns to
baseline without reusing an old version or rewriting analyses. Subsequent artifact changes block that rollback.

Live taxonomy remains `phase6d-capability-taxonomy-v1.5`, registry `technology-registry-v1.3`, scorer
`stable-evidence-v1.16-phase6d20`. No scorer formula/weights/thresholds changed. Existing taxonomy version and
fingerprint/currentness mechanisms detect publication; no second versioning system. Future analyses use the
approved native artifact; existing analyses remain historical until separately requested recomputation.

## Historical safeguards

- `(c) Front-end frameworks such as React, Node.js, or Angular 2`: current resolution is not modern C++.
  Legitimate C++ development still resolves. Historical C++ classification carried match value 0; no historical
  score increase is claimed.
- Agile-team requirement with only “Frontend development”: current full scorer returns NONE.
- Code-review requirement with only “code integration”: current full scorer returns NONE, not DIRECT.
- Explicit Agile/code-review source statements retain the existing WEAK distinction when supplied as skills
  sources; these are not verified employment claims or manufactured direct qualifications.

No unrelated current scoring defect was reproduced in these controls. Existing Phase8 lineage and API/gRPC
evidence safeguards remain green. Full scoring is tested separately from requirement-only previews.

## UI acceptance

1. From the existing branch, start `.venv\Scripts\python.exe -m streamlit run app.py`.
2. Open **Capability Discovery → Production Resolver Inspector → Saved Job Match**. Enter **Discovered job ID 146**.
   Click **Inspect saved Job Match**. Verify EDB, Software Engineer, SGN, snapshot **40**, timestamp
   `2026-10-02T22:51:17`, JD hash `8925a25e5c847c728ddabc189a2152f17dafe04aa335feb5ae60139d31ab9605`.
3. Expand **Unresolved Requirement Review** beneath Persisted requirements. Select
   **Design and develop RESTful APIs** / `req_9270e95898c8`. Do not refresh the historical match.
4. **Inspect diagnostics** distinguishes saved historical classification from current native resolution.
   **Preview proposed correction** displays the inactive rule and current-versus-proposed native result.
5. **Validate draft** explicitly persists an inactive local draft in the existing separate taxonomy-review store,
   reads frozen corpus inputs and computes/saves native regression. It does not write application snapshots.
   Missing inputs, stale versions, unexpected changes or failed controls block readiness. Results include draft
   ID/fingerprint, regression fingerprint and actual blocker lists.
6. Review diagnostics and the sanitized ZIP. Rejected previews have no effect; rejecting a persisted draft requires
   a named reviewer and records REJECT through the real review API. Selection/knowledge changes invalidate state
   and reset approval/publication confirmations. Rerenders do not execute validation, approval or publication.
7. **Approve validated draft** requires a reviewer, exact validation and confirmation. **Review approval readiness**
   runs the existing fresh `_prepare` preflight. **Publish approved correction** remains disabled unless ready
   and separately confirmed. This task has NOT authorized real approval/publication: stop before those actions.
8. Confirm no saved score changes during inspection/preview/validation. Publication tests here were isolated.
   Normal future analysis, rather than a UI shortcut, would compute any later score from real evidence.

The same shared review remains in Job Finder/current application receipt views. Historical Inspector delegates
to that interface; it does not duplicate a resolver or require refreshing snapshot 40.

## Files changed in V1.1

Modified: `tailoring/capability_taxonomy.py`, `tailoring/requirement_scope.py`,
`tailoring/production_requirement_resolver.py`, `tailoring/phase6d_stable_scoring_adapter.py`,
`taxonomy_discovery/governed_requirement_resolution.py`, `taxonomy_discovery/resolver_improvement.py`,
`taxonomy_discovery/governed_research.py`, `taxonomy_discovery/governed_publication.py`,
`database/taxonomy_discovery_review_manager.py`, `tailoring/unresolved_requirement_review_ui.py`,
`taxonomy_discovery/production_resolver_inspector_ui.py`, `scripts/preview_governed_requirement_resolution.py`,
`tests/test_governed_requirement_resolution.py`, `docs/governed_requirement_resolution_v1.md`.

Added: `tests/test_governed_requirement_activation_v1_1.py`, this document,
`reports/governed_requirement_resolution_v1_1_validation.json`.

Existing V1/V2 reports, other research artifacts and earlier uncommitted work were preserved. The shared receipt
integration/harness from V1 was reused. No production taxonomy/registry JSON, live database, gold receipt or frozen
benchmark was modified. Old inaccessible scratch directories were not deleted or permission-modified.

## Focused validation and status

**206 distinct focused tests passed; zero failures/errors.** Exact module lists and timings are in the JSON report:
22 feature/UI/isolated activation tests, 144 existing governance/resolver/registry/scoring/decomposition/importance/
Phase8/currentness/override tests, and 40 Phase9E selection/shared-receipt tests. Commands used
`.venv\Scripts\python.exe -B -` with `unittest.defaultTestLoader.loadTestsFromNames([...])` and the documented
process-local temporary-directory workaround below; ordinary tests and assertions were unchanged.

```python
def inherited_mkdtemp(suffix=None, prefix=None, dir=None):
    path = Path(dir or Path.cwd() / "reports") / ((prefix or "tmp") + uuid.uuid4().hex + (suffix or ""))
    path.mkdir()  # inherited permissions; avoids Windows mode-0700 sandbox denial
    return str(path)
tempfile.mkdtemp = inherited_mkdtemp  # test process only; TemporaryDirectory owns cleanup
```

Replay command: `.venv\Scripts\python.exe -B -m scripts.preview_governed_requirement_resolution --output reports/governed_requirement_resolution_v1_1_validation.json`.
The first attempt stopped at the global inventory check; investigation and exact active-inventory reconstruction
resolved that comparison boundary before the successful replay. The JSON was then enriched with actual isolated
publication receipts, native outcomes, held-out controls, test results and gate states. No full project gate,
full discovery, live model or external network was run.

Native resolution, additive compatibility, variant composition, persistence, real native regression, isolated
approval/publication/reload/rollback, unseen controls, historical safeguards and UI end-to-end gates: **PASS**.
Live approval and publication: **BLOCKED** by missing real receipts/authorization, not claimed completed.
AST, whitespace, diff, protected-content and database byte-integrity checks are recorded in the final JSON.

Stopped for user acceptance review. No commit, push, merge, automatic approval or live activation.
