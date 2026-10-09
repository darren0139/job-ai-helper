# Taxonomy Gap Reduction Assistant v1

The assistant ranks the native unresolved-corpus maintenance queue by safe addressable impact. It does not presume an unresolved requirement is a missing capability. It remains useful with zero eligible or publishable capability candidates: technology/registry, parser, decomposition, evidence policy, noise and manual work are legitimate outcomes.

## Architecture

UI and CLI call `taxonomy_discovery.gap_reduction_assistant.build_plan`. It consumes the existing exact-current `maintenance_service.run_corpus_audit` snapshot, reconciles saved research with native `list_gap_rows`, and uses governed `select_saved_interpretation`. No new scorer, resolver, decomposition, source-authority, sufficiency, registry or taxonomy engine is introduced. Compatible historical request IDs/rounds preserve native budgets; local reinterpretations do not count as new calls.

## Ranking

Lexicographic ordering: unresolved meaningful required/core weight; unresolved meaningful total weight; affected required/core weight; total native importance/fraction weight; distinct jobs; distinct job/requirement keys; lower provider cost; lower risk; stable action ID. Research readiness does not add priority. Weights come from the production audit and retain decomposition fractions. Already-resolved evidence-policy rows have zero unresolved contribution and remain visible for review without claiming taxonomy gap closure. Every meaningful unresolved job/requirement key links to its native action families, preserving parent/child provenance. Families can share requirements: never add affected counts across families to predict coverage. Lower-ranked categories remain visible in all-actions/grouped reports. Input toggles determine top-action selection, not native routing or visibility of excluded categories.

Estimated impact is addressable existing requirement weight, not a probability or claimed gap reduction. Validated impact exists only after explicit native temporary overlay/regression. The service calls `maintenance_service.run_candidate_validation(approved=False)` on eligible existing governed saved drafts. This retains native currentness, evidence receipts, duplicate-credit checks, canaries, caps/rejections and ranking comparison. It creates no drafts and approves nothing. No `283 -> 280` or score uplift is claimed from planning alone.

## Finite research states

- RESEARCH_READY: first native bounded plan passes governed readiness and impact policy.
- TARGETED_RESEARCH_AVAILABLE: current insufficient interpretation supports one materially new bounded query with budget left.
- ELIGIBLE_FOR_HUMAN_REVIEW: current governed support is eligible; human review remains necessary.
- NEEDS_SCOPE_REFINEMENT: repeated unchanged missing support or partial support with unresolved definition/boundaries; show observed JD wording and missing fields, not invented narrower capabilities.
- NEEDS_DECOMPOSITION: native compound/child provenance excludes paid capability research.
- RESEARCH_EXHAUSTED: native three-round ceiling or no new query; no call just because a nominal budget remains.
- BLOCKED_EVIDENCE_INSUFFICIENT: governed readiness/interpretation ambiguity blocks execution.
- FIX_LAYER_REQUIRED: non-capability work, or explicit offline refresh of stale saved interpretation.
- DEFERRED: preferred-only single-job low-impact gaps or existing governance decisions.

Sufficiency v2.1 `research_more` is evidence, not failure. Repeated partial evidence may correctly cause scope refinement or deferral. Research should resume only after meaningful new corpus evidence, manually reviewed scope changes, or governed authority changes; these do not silently reset historical ceilings. Every action records support gained/missing, selected interpretation, rounds, costs and next-action reason.

## Boundaries and confirmation

First button/CLI dry-run: zero providers/models/production writes. Exact current audits are reused without repeating scoring. The assistant plan fingerprint binds audit/candidate knowledge, full saved results/reviews/drafts, publications, interpreter version, assistant implementation, options, ordering, cost and native query plans. Execution regenerates and compares the exact plan before any mutation. Changed data, currentness, scope, versions, authority or evidence require re-preview. Explicit external authorization is an additional gate; there is no generic `--yes`.

Confirmed execution may refresh saved evidence locally and invoke the native bounded research executor. It never patches parser/evidence/scorer code or production knowledge, creates drafts automatically, awards evidence credit, mutates Job Match snapshots, approves or publishes. Local/parser/registry recommendations are human/Codex work recommendations, not silently applied changes. Research is only proposed for eligible capability routes in v1; existing technology research remains in its native workflow. Global per-run native limits: at most 25 working actions, 8 external candidates and 20 calls; selected assistant budget defaults to3. Native per-candidate ceiling remains3 query intents.

## CLI

```powershell
python -m scripts.run_taxonomy_gap_reduction --scope stored --max-actions 10 --research-budget 3 --dry-run --output <directory>
python -m scripts.run_taxonomy_gap_reduction --scope frozen --corpus <frozen-corpus.json> --dry-run --output <directory>
```

Outputs: audit.json, plan.json, summary.md. `--audit` reuses a current saved audit. To preview at most one ranked capability target, use `--preview-research-id <candidate_id>` with the same audit. Empty/terminal eligible sets produce no query and no calls.

After separate human research authorization, execution requires `--execute-plan <plan.json> --audit <audit.json> --confirm-fingerprint <exact fingerprint> --allow-external-research`; local-only plans do not require the external flag. `--validate-plan <plan.json> --result-id <saved eligible draft ID>` uses the same exact confirmation and produces receipt.json. Execution is not enabled implicitly by dry-run. Scope must match the saved audit.

## Performance

One native audit/replay, followed by one queue reconciliation and a bounded research planner. Requirement/job lookup uses consolidated native row provenance, never requirements × whole-corpus rescoring. Audit currentness still hashes/fetches corpus and evidence; stored audits must be checked, not blindly cached. Re-preview does not rerun scoring. JSON retains native audit artifacts locally and does not include provider credentials.
