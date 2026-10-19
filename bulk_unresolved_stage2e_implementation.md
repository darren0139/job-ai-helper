# Stage 2E — gated coordinated-action implementation

## Decision

- **IMPLEMENTED AND TESTED:** bounded Option A parsing, reviewed ownership detector,
  P3 ceilings, native-source selection, final evidence invariants, score withholding
  and development-result persistence rejection.
- **DEMONSTRABLE IN DEVELOPMENT PREVIEW:** isolated real Streamlit page using
  `build_stable_analysis`, the five actual frozen JD sources and synthetic evidence.
- **SAFE FOR PRODUCTION ENABLEMENT: NO.** The feature is default OFF. The normal
  application/Job Match flow has no new activation control.
- **BLOCKED / NEEDS APPROVAL:** live enablement/publication, unresolved partial and
  unsupported outcomes, and release/version allocation require separate review.

Entry worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch: `feat/bulk-unresolved-resolution-v1`; entry HEAD
`3e6ff34501b4d68cbe3e66b55ec8af5b0e288026`. Both index and working tree were clean.
Stage 2D was already checkpointed at this HEAD. No commit, push, branch change,
stash, reset, merge, live database access or saved Job Match mutation was performed.

## Gate and bounded implementation

The sole analysis activation parameter is
`build_stable_analysis(..., coordinated_actions_enabled=True)`; its default is False.
There is no environment activation and no persistent toggle. Disabled calls retain
the existing scorer, decomposition, recovery/reselection constants and fingerprint
contract. The request-local `ContextVar` resets through `finally`, including failures.

The parser admits the reviewed finite Design + Develop/Build + Maintain/Deploy AND
grammar and the five reviewed artifact families. It preserves one full parent before
the native splitter can create incomplete children. The native canonicalizer still
constructs IDs, source occurrences, importance and group allocation. All five affected
parents retain exact full wording, canonical semantics, original source grounding and
one total parent allocation. Action/document spans are Unicode character offsets in
the original source. Ambiguous duplicate document occurrences are not accepted.

Nearby three-action constructions with unsupported objects or Boolean grammar are
quarantined with review receipts. They are not automatically treated as complete.
Ordinary specific API requirements outside the admitted three-action correction
continue through the established API contract.

The promoted detector is independent production code; it does not import research
scripts, expected answers, private inputs or preview JSON. The original research
detectors and expectation fixtures remain unchanged. Only P3 is exposed by the
promoted eligibility function. Its bounded active, first-person passive and relative
clauses retain their original agent/negation/modality limitations. Family ownership
and full required technical-object support remain separate. No broad paraphrase,
pronoun-resolution, model inference or action-count formula is added.

## Evidence selection, ceilings and review handling

For each affected requirement, the native unchecked corrected-row result is retained
only as a diagnostic baseline. Verified candidate records are checked individually
against the original current source index and original native compatibility rules.
An eligible complete pool is considered before a partial pool; native ranking inside
that pool is unchanged. Separate partial bullets are never joined.

The same native keyword, linking, structured validation, reselection, taxonomy-cap
and NONE-recovery functions are used. A request-local source predicate constrains
them; no unrestricted replacement ranker or monkeypatch of production globals is used.
Every label-writing boundary and the final post-recovery invariant rechecks original
source, text, section and evidence ID, and records native versus effective labels.

- COMPLETE retains native capability ceilings and may still be NONE.
- P3 requires one source proving design and creation on the complete required object,
  with only lifecycle omitted and no denial, contradiction or unresolved ambiguity.
  Positive native credit is capped at existing WEAK **0.20**. Native final NONE stays
  NONE; detection cannot itself create recovery permission.
- The backend/API evaluator is independently binding. Integration/consumption cannot
  establish endpoint authorship. Its lower design/authorship label also acts as a
  ceiling, even when lexical recognition has not resolved the parent as API capability.
- Other partial, unsupported, ambiguous or unverified outcomes receive the diagnostic
  `REVIEW_REQUIRED` receipt and **null effective label/value**, never an unchecked
  DIRECT or invented NONE. This is stricter than the research preview's occasional
  retained NONE with a review disposition and implements Stage 2E's withholding rule.

Internal NONE is used only to quarantine inadmissible records while native functions
run. It is replaced by a null review result before aggregate interpretation. Review
receipts preserve all candidate source proofs and the original native selection.

`compute_deterministic_alignment` returns null aggregate metrics and the explicit
"Score withheld pending policy review" state if any requirement is pending.
The weighted-coverage primitive also refuses pending rows, preventing callers from
silently dropping them from a denominator. No unchecked aggregate percentage survives
in the gated response. When every numeric disposition is governed, the ordinary
native aggregation formula is used unchanged; no new parent/action weighting exists.
Row contributions are allocation times native label value, not action fractions.

All gated outputs, including completely governed synthetic ones, are marked
`development_preview_only`. Job Match snapshot saving, analysis-cache saving and
explicit application-analysis persistence reject them **before database initialization**.
Thus a successful development percentage is not permission to persist a new snapshot.

The whole JD is evaluated. Job 566 contains two affected parents: proving one while
leaving the other unresolved correctly withholds that JD's aggregate. Per-parent
defined contribution does not imply that its whole-job percentage can be published.

## Visible Streamlit acceptance

Page: `coordinated_actions_preview.py`.
Local development URL: <http://127.0.0.1:8503>.

The page offers all five source parents and twelve scenarios per parent: maintenance,
design/development, all actions, passive ownership, relative ownership, shortened
scope, REST consumption, PostgREST integration, complete second source, zero-overlap
topic recovery, separate partial records and explicit lifecycle denial. Full-stack
action ownership with native NONE is visible by selecting that parent.

The toggle starts OFF and evaluates only the existing analysis in that state. Turning
it on displays the corrected requirement, native label, capped label or review status,
original source IDs, supported/missing actions, technical scope, allocation/contribution
and detailed stage receipts. Pending cases show an explicit withheld state. There is
no upload, saved-candidate selector, database operation or save button.

The page uses actual complete JD fixtures and the actual native analysis functions,
not Stage 2D's cloned namespace or precomputed diagnostic exports. Streamlit AppTest
executes the real page and exercises OFF -> maintenance review -> design/development
WEAK -> complete passive ownership. It asserts rendered alerts, labels and metrics.
The local server runs only on loopback with telemetry disabled; model/provider
transports are not used.

Launch from this repository using Python 3.13 and the existing dependencies:

```powershell
python -B -m streamlit run coordinated_actions_preview.py --server.address 127.0.0.1 --server.port 8503 --server.headless true --browser.gatherUsageStats false
```

## Versions, history and currentness

Published OFF identities are unchanged: scorer `stable-evidence-v1.17-phase6d21`,
decomposition v1.1, recovery v1.1, reselection v1, taxonomy v1.6 and registry v1.3.
Gated results identify the prospective immutable bundle:

| Contract | Prospective identity |
|---|---|
| Scorer | `stable-evidence-v1.18-phase6d22` |
| Decomposition | `jd-atomic-requirement-decomposition-v1.2` |
| Completeness | `coordinated-action-evidence-completeness-v1` |
| Partial credit | `coordinated-partial-action-credit-v1`, variant P3 |
| Recovery boundary | `capability-single-row-none-recovery-v1.2` |
| Reselection boundary | `capability-single-row-reselection-v1.1` |
| Bounded language binding | `coordinated-ownership-language-v2d1` |

The gated fingerprint covers this complete bundle, native input fingerprint, original
evidence index and corrected canonical rows. It differs from OFF even when an input
happens to yield the same numeric outcome. Native recovery/reselection receipt versions
are retained separately from the effective gated boundary versions.

Local `git log --all -G` checks found no earlier production use of these prospective
identities in analysis, tailoring, database or Job Finder code. Research documents and
tests already mention proposed names. No remote release state was queried: external
allocation remains a release check, not a claim that these names are unused everywhere.

Tests read and compare the hash-pinned Stage 2D scorer against current OFF behavior on
all 30 JDs. A synthetic snapshot in a disposable database remains byte-identical and
readable; querying it under the prospective scorer returns no current match. Existing
frozen snapshots and knowledge fixtures are not rewritten or relabelled.

The historical research source pin is preserved against the exact Stage 2D Git object
after adding intentional OFF hooks to the current scorer. All other source pins remain
strict against current files. The original full semantic-digest expectations still
bind current OFF output and pass. No historical oracle or expected digest was changed.
These historical comparisons require Git and commit
`3e6ff34501b4d68cbe3e66b55ec8af5b0e288026` to be present locally; a shallow checkout
omitting that object must restore its history before running those comparisons.

## Changed files

| File | Purpose |
|---|---|
| `analysis_stability/stable_evidence_scoring.py` | Default-OFF dispatch, bounded parser/source hooks, review-aware aggregation boundary. Published constants unchanged. |
| `analysis_stability/coordinated_runtime.py` | Request-local context, parser probe, source predicate, review/publication guards. |
| `analysis_stability/coordinated_ownership.py` | Promoted finite extraction/ownership grammar and original source/document spans. |
| `analysis_stability/coordinated_policy.py` | Promoted technical-scope proof and approved gated P3 eligibility/ceilings only. |
| `analysis_stability/coordinated_integration.py` | Real native pipeline orchestration, complete-source priority, per-stage caps, receipts and effective identities. |
| `database/job_match_manager.py` | Reject development Job Match payloads before opening a database. |
| `database/analysis_cache_manager.py` | Reject development payloads at both application-analysis save boundaries. |
| `scripts/coordinated_acceptance.py` | Deterministic synthetic scenarios and five-parent real-analysis comparisons. |
| `coordinated_actions_preview.py` | Small standalone Streamlit comparison page, default OFF and no persistence. |
| `tests/test_coordinated_action_implementation.py` | Focused parser, P3, source, late recovery, API ceiling, aggregation, historical/currentness, persistence and rendered UI tests. |
| `scripts/run_coordinated_preview_checks.py` | Adds implementation tests and optional acceptance export; narrow Windows stdlib socketpair allowance, preserving external HTTP/DNS blocks. |
| `scripts/preview_coordinated_evidence_v1.py` | Verifies the original historical scorer source pin while current OFF frozen semantic checks remain binding. |
| `bulk_unresolved_stage2e_implementation.md` | This implementation and acceptance report. |

The runner's Windows allowance accepts only `socket._fallback_socketpair` connecting
to its own loopback listener. Arbitrary loopback, DNS and external connections remain
blocked. AppTest scratch and synthetic historical databases use inherited runner-scratch
ACLs because private `mkdtemp` ACLs are inaccessible in this sandbox. Scratch remains
local for inspection. No test result assertions are weakened for these harness fixes.

## Release blockers and future improvements

Release blocking:

- Feature must remain OFF for live matches. No live enablement or publication approval
  was given; development results are deliberately rejected by persistence.
- Unsupported/other-partial/denied-lifecycle cases have no approved numeric disposition.
  Any affected aggregate stays withheld until each outcome is governed.
- Confirm external identity allocation and approve a complete immutable scoring bundle
  before releasing a new currentness contract or enabling live consumers.

Future improvements, outside this bounded implementation:

- Broader technically grounded paraphrases, omitted modifiers and richer attribution
  grammar require separately reviewed evidence rules.
- P2 missing-design credit and an explicit-denial exception remain unapproved.
- Generic backend/API text may prove family duties while lacking API-specific authorship
  or interface-design proof; the conservative independent guard can require review.
- A future normal-flow activation must retain explicit withheld UI handling and all
  publication guards; the isolated page intentionally supplies no live activation.

Focused execution, deterministic acceptance tables and protected-hash results follow.

## Focused results and reproducibility

**151 distinct focused tests passed across completed runs: 132 existing regressions and 19 implementation/UI tests.** This is not a single 151-test invocation. The final implementation-module run passed 17 tests in 144.782 seconds; the subsequently added cloud-lifecycle control passed, and the raw-grounding control plus directly affected P3 ceiling check passed. All 132 earlier Stage 1–2D/API/recovery/parser/currentness tests passed together in 119.751 seconds. No complete or quick project-wide suite was run.

Initial failures were test-harness issues: the Windows asyncio self-pipe was blocked by the offline socket audit, and private-ACL temporary folders prevented opening a disposable SQLite file. The final harness permits only the exact stdlib self-pipe and uses inherited scratch ACLs. Rendered UI assertions and real disposable-database assertions then passed; no policy expectations, historical fixtures or credit rules were relaxed.

Executed through `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B` with the portable runner:

```text
scripts/run_coordinated_preview_checks.py --scratch-root reports/stage2e_runtime tests.test_api_evidence_completeness
scripts/run_coordinated_preview_checks.py --scratch-root reports/stage2e_runtime tests.test_partial_action_credit_preview tests.test_coordinated_ownership_preview tests.test_coordinated_evidence_preview tests.test_coordinated_action_preview tests.test_source_inventory_export_safety tests.test_source_aware_inventory tests.test_bulk_unresolved_v1 tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_jd_atomic_requirement_decomposition tests.test_jd_structure_fingerprint_compat
scripts/run_coordinated_preview_checks.py --scratch-root reports/stage2e_runtime --stage2e-preview reports/bulk_unresolved_stage2e_acceptance.json tests.test_coordinated_action_implementation
scripts/run_coordinated_preview_checks.py --scratch-root reports/stage2e_runtime --stage2e-preview reports/bulk_unresolved_stage2e_acceptance_final.json tests.test_coordinated_action_implementation.CoordinatedImplementationTests.test_cloud_denial_and_separate_records_use_deployment_not_maintenance
scripts/run_coordinated_preview_checks.py --scratch-root reports/stage2e_runtime tests.test_coordinated_action_implementation.CoordinatedImplementationTests.test_profile_only_parent_cannot_bypass_exact_raw_grounding tests.test_coordinated_action_implementation.CoordinatedImplementationTests.test_p3_ceiling_and_every_late_stage
```

Additional small UI/publication/unsupported/API-ceiling controls were run through the same runner during iteration; their logs are under `reports/stage2e_runtime/`. The final deterministic acceptance artifact is **`reports/bulk_unresolved_stage2e_acceptance_final.json`**, 24875083 bytes, SHA-256 `5bfdd63c8e78940b361c6454007f131bfc5a5d77bb5fe3f5663cdd54a948de51`. It contains 60 complete before/after real-analysis payloads and original synthetic inputs, with sorted UTF-8 JSON and no timestamps. Repeated production-entry calls are asserted equal, including source receipts, scores and fingerprints. No claim of a second byte-identical full 60-case export is made; earlier exports are superseded diagnostics.

The final raw-grounding fallback additionally quarantines missing source metadata. Its target decisions were checked equal to the exported decisions across every canonical row in all 60 cases; it does not change this acceptance artifact.

Across the 60 target-parent results: 12 DIRECT, 3 WEAK, 5 native NONE and 40 null review labels. Whole-JD aggregates are withheld in 45 cases. A full-stack target can stay NONE while unrelated, normally scored JD requirements yield a nonzero synthetic aggregate; this does not upgrade that target's zero contribution.

## Five-parent acceptance results

Before contribution is the sum of original row allocation times native value. After contribution is the one corrected parent's value at allocation 1.0. These are synthetic observations, not candidate/live/historical Job Match changes. For a rejected case, action/scope columns show the first original bullet's diagnostic proof; no records are combined. For an admitted case they show the actual selected record.

### Job 16 — pipeline

Design, build, and maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds.

Source occurrence `srcgrp_e822a3bdbba5`; full canonical ID `req_acdd8f777d09`; parent allocation 1.0. Mandatory actions: design, develop, maintain. Required scope: `scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds`.

Original rows: `req_fd6f5ea4f9bf` Design, build (weight 0.5); `req_191dd0c2eef9` maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds (weight 0.5).

| Scenario | Before labels | Before contribution | Native full parent | P3 label | Disposition | Owned / missing | Technical | After contribution | Aggregate display | Original evidence receipt |
|---|---|---|---|---|---|---|---|---|---|---|
| Maintenance only | NONE / DIRECT | 0.5 | DIRECT | REVIEW | REVIEW_REQUIRED | maintain / design,develop | FULL | None | withheld | ev_9b94dab99069 @ resume_profile.projects[0].bullets[0] |
| Design and development | DIRECT / DIRECT | 1.0 | DIRECT | WEAK | ELIGIBLE_PARTIAL | design,develop / maintain | FULL | 0.2 | yes | ev_1c907fe3b6dc @ resume_profile.projects[0].bullets[0] |
| All mandatory actions | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_2e1fc06c7ad4 @ resume_profile.projects[0].bullets[0] |
| Passive first-person ownership | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_9af304c66e98 @ resume_profile.projects[0].bullets[0] |
| Relative-clause ownership | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_6c07e8119fc1 @ resume_profile.projects[0].bullets[0] |
| Shortened object | DIRECT / NONE | 0.5 | NONE | REVIEW | REVIEW_REQUIRED | design,develop,maintain /  | UNPROVEN | None | withheld | ev_c9771c718864 @ resume_profile.projects[0].bullets[0] |
| API consumption | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_c79dee18eaa2 @ resume_profile.projects[0].bullets[0] |
| PostgREST integration | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_5b3eb55dd534 @ resume_profile.projects[0].bullets[0] |
| Complete alternative second bullet | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_9af304c66e98 @ resume_profile.projects[0].bullets[1] |
| Zero-overlap topic recovery | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_1ad64fbd77d3 @ resume_profile.projects[0].bullets[0] |
| Separate partial records | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design / develop,maintain | FULL | None | withheld | ev_57771dd968e7 @ resume_profile.projects[0].bullets[0] |
| Denied lifecycle | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop / maintain | FULL | None | withheld | ev_6224ed7b47d2 @ resume_profile.projects[0].bullets[0] |

Complete-alternative rows are evaluated with the native selector restricted to complete eligible originals. The cloud first maintenance statement is not deployment and is excluded; its complete second statement explicitly proves deployment. Native capability and API guard ceilings still bind.

### Job 359 — embedded

Design, develop, and maintain embedded software modules supporting waveform processing systems.

Source occurrence `srcgrp_af665d2ba39b`; full canonical ID `req_1933523263de`; parent allocation 1.0. Mandatory actions: design, develop, maintain. Required scope: `embedded software modules supporting waveform processing systems`.

Original rows: `req_95479a28180a` Design, develop (weight 0.5); `req_bda00d6856dc` maintain embedded software modules supporting waveform processing systems (weight 0.5).

| Scenario | Before labels | Before contribution | Native full parent | P3 label | Disposition | Owned / missing | Technical | After contribution | Aggregate display | Original evidence receipt |
|---|---|---|---|---|---|---|---|---|---|---|
| Maintenance only | NONE / DIRECT | 0.5 | DIRECT | REVIEW | REVIEW_REQUIRED | maintain / design,develop | FULL | None | withheld | ev_bb4d622bf990 @ resume_profile.projects[0].bullets[0] |
| Design and development | DIRECT / DIRECT | 1.0 | DIRECT | WEAK | ELIGIBLE_PARTIAL | design,develop / maintain | FULL | 0.2 | yes | ev_404485602c67 @ resume_profile.projects[0].bullets[0] |
| All mandatory actions | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_2e8966182caf @ resume_profile.projects[0].bullets[0] |
| Passive first-person ownership | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_e33504e2ccdd @ resume_profile.projects[0].bullets[0] |
| Relative-clause ownership | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_797fff3dad48 @ resume_profile.projects[0].bullets[0] |
| Shortened object | DIRECT / DIRECT | 1.0 | TRANSFERABLE | REVIEW | REVIEW_REQUIRED | design,develop,maintain /  | UNPROVEN | None | withheld | ev_255b7ad49b26 @ resume_profile.projects[0].bullets[0] |
| API consumption | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_c79dee18eaa2 @ resume_profile.projects[0].bullets[0] |
| PostgREST integration | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_5b3eb55dd534 @ resume_profile.projects[0].bullets[0] |
| Complete alternative second bullet | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | design,develop,maintain /  | FULL | 1.0 | yes | ev_e33504e2ccdd @ resume_profile.projects[0].bullets[1] |
| Zero-overlap topic recovery | NONE / DIRECT | 0.5 | DIRECT | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_1ad64fbd77d3 @ resume_profile.projects[0].bullets[0] |
| Separate partial records | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design / develop,maintain | FULL | None | withheld | ev_a2549674b9f3 @ resume_profile.projects[0].bullets[0] |
| Denied lifecycle | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop / maintain | FULL | None | withheld | ev_73382f14ff40 @ resume_profile.projects[0].bullets[0] |

Complete-alternative rows are evaluated with the native selector restricted to complete eligible originals. The cloud first maintenance statement is not deployment and is excluded; its complete second statement explicitly proves deployment. Native capability and API guard ceilings still bind.

### Job 479 — fullstack

Design, develop and maintain scalable full-stack applications using React, TypeScript and Python technologies.

Source occurrence `srcgrp_b729779d18ec`; full canonical ID `req_7cf592b15461`; parent allocation 1.0. Mandatory actions: design, develop, maintain. Required scope: `scalable full-stack applications using React, TypeScript and Python technologies`.

Original rows: `req_95479a28180a` Design, develop (weight 0.5); `req_533286e95145` maintain scalable full-stack applications using React, TypeScript and Python technologies (weight 0.5).

| Scenario | Before labels | Before contribution | Native full parent | P3 label | Disposition | Owned / missing | Technical | After contribution | Aggregate display | Original evidence receipt |
|---|---|---|---|---|---|---|---|---|---|---|
| Maintenance only | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED | maintain / design,develop | FULL | None | withheld | ev_7b011e9bb3ee @ resume_profile.projects[0].bullets[0] |
| Design and development | DIRECT / NONE | 0.5 | NONE | NONE | ELIGIBLE_PARTIAL | design,develop / maintain | FULL | 0.0 | yes | ev_507e7c8a99cb @ resume_profile.projects[0].bullets[0] |
| All mandatory actions | DIRECT / NONE | 0.5 | NONE | NONE | COMPLETE | design,develop,maintain /  | FULL | 0.0 | yes | ev_bedf363ebef3 @ resume_profile.projects[0].bullets[0] |
| Passive first-person ownership | DIRECT / NONE | 0.5 | NONE | NONE | COMPLETE | design,develop,maintain /  | FULL | 0.0 | yes | ev_a43a155c6c9c @ resume_profile.projects[0].bullets[0] |
| Relative-clause ownership | DIRECT / NONE | 0.5 | NONE | NONE | COMPLETE | design,develop,maintain /  | FULL | 0.0 | yes | ev_e826f64912a5 @ resume_profile.projects[0].bullets[0] |
| Shortened object | DIRECT / NONE | 0.5 | NONE | REVIEW | REVIEW_REQUIRED | design,develop,maintain /  | UNPROVEN | None | withheld | ev_ac265235de2e @ resume_profile.projects[0].bullets[0] |
| API consumption | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_c79dee18eaa2 @ resume_profile.projects[0].bullets[0] |
| PostgREST integration | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_5b3eb55dd534 @ resume_profile.projects[0].bullets[0] |
| Complete alternative second bullet | DIRECT / NONE | 0.5 | NONE | NONE | COMPLETE | design,develop,maintain /  | FULL | 0.0 | yes | ev_a43a155c6c9c @ resume_profile.projects[0].bullets[1] |
| Zero-overlap topic recovery | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_1ad64fbd77d3 @ resume_profile.projects[0].bullets[0] |
| Separate partial records | DIRECT / NONE | 0.5 | NONE | REVIEW | REVIEW_REQUIRED | develop / design,maintain | FULL | None | withheld | ev_6b8705ba2f39 @ resume_profile.projects[0].bullets[1] |
| Denied lifecycle | DIRECT / NONE | 0.5 | NONE | REVIEW | REVIEW_REQUIRED | design,develop / maintain | FULL | None | withheld | ev_1036861c27e3 @ resume_profile.projects[0].bullets[0] |

Complete-alternative rows are evaluated with the native selector restricted to complete eligible originals. The cloud first maintenance statement is not deployment and is excluded; its complete second statement explicitly proves deployment. Native capability and API guard ceilings still bind.

### Job 566 — backend

· Design, build and maintain scalable backend services and API.

Source occurrence `srcgrp_ff65d3ef26a4`; full canonical ID `req_3a7798a7fae0`; parent allocation 1.0. Mandatory actions: design, develop, maintain. Required scope: `scalable backend services and API`.

Original rows: `req_fd6f5ea4f9bf` · Design, build (weight 0.5); `req_86462bb5cd2a` maintain scalable backend services and API (weight 0.5).

| Scenario | Before labels | Before contribution | Native full parent | P3 label | Disposition | Owned / missing | Technical | After contribution | Aggregate display | Original evidence receipt |
|---|---|---|---|---|---|---|---|---|---|---|
| Maintenance only | NONE / DIRECT | 0.5 | DIRECT | REVIEW | REVIEW_REQUIRED | maintain / design,develop | FULL | None | withheld | ev_8f9ba3952324 @ resume_profile.projects[0].bullets[0] |
| Design and development | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop / maintain | FULL | None | withheld | ev_ad1ef197f62e @ resume_profile.projects[0].bullets[0] |
| All mandatory actions | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop,maintain /  | FULL | None | withheld | ev_17621154d7ef @ resume_profile.projects[0].bullets[0] |
| Passive first-person ownership | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop,maintain /  | FULL | None | withheld | ev_bc5b2afd8555 @ resume_profile.projects[0].bullets[0] |
| Relative-clause ownership | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop,maintain /  | FULL | None | withheld | ev_87030b0849bc @ resume_profile.projects[0].bullets[0] |
| Shortened object | DIRECT / DIRECT | 1.0 | TRANSFERABLE | REVIEW | REVIEW_REQUIRED | design,develop,maintain /  | UNPROVEN | None | withheld | ev_39c0e6685bbd @ resume_profile.projects[0].bullets[0] |
| API consumption | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_c79dee18eaa2 @ resume_profile.projects[0].bullets[0] |
| PostgREST integration | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_5b3eb55dd534 @ resume_profile.projects[0].bullets[0] |
| Complete alternative second bullet | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | maintain / design,develop | FULL | None | withheld | ev_73326e293525 @ resume_profile.projects[0].bullets[0] |
| Zero-overlap topic recovery | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / design,develop,maintain | UNPROVEN | None | withheld | ev_1ad64fbd77d3 @ resume_profile.projects[0].bullets[0] |
| Separate partial records | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design / develop,maintain | FULL | None | withheld | ev_133076d5e400 @ resume_profile.projects[0].bullets[0] |
| Denied lifecycle | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop / maintain | FULL | None | withheld | ev_ab8bc178cf62 @ resume_profile.projects[0].bullets[0] |

Complete-alternative rows are evaluated with the native selector restricted to complete eligible originals. The cloud first maintenance statement is not deployment and is excluded; its complete second statement explicitly proves deployment. Native capability and API guard ceilings still bind.

### Job 566 — cloud

· Design, develop and deploy cloud-based applications with large-scale data processing capabilities.

Source occurrence `srcgrp_8ac40e9b5dc4`; full canonical ID `req_490d136c0a8a`; parent allocation 1.0. Mandatory actions: design, develop, deploy. Required scope: `cloud-based applications with large-scale data processing capabilities`.

Original rows: `req_95479a28180a` · Design, develop (weight 0.5); `req_9f75638e8bda` deploy cloud-based applications with large-scale data processing capabilities (weight 0.5).

| Scenario | Before labels | Before contribution | Native full parent | P3 label | Disposition | Owned / missing | Technical | After contribution | Aggregate display | Original evidence receipt |
|---|---|---|---|---|---|---|---|---|---|---|
| Maintenance only | NONE / DIRECT | 0.5 | DIRECT | REVIEW | REVIEW_REQUIRED |  / deploy,design,develop | UNPROVEN | None | withheld | ev_5e17c3a5b484 @ resume_profile.projects[0].bullets[0] |
| Design and development | DIRECT / DIRECT | 1.0 | DIRECT | WEAK | ELIGIBLE_PARTIAL | design,develop / deploy | FULL | 0.2 | withheld | ev_9466eb10e548 @ resume_profile.projects[0].bullets[0] |
| All mandatory actions | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | deploy,design,develop /  | FULL | 1.0 | withheld | ev_11802e4864b8 @ resume_profile.projects[0].bullets[0] |
| Passive first-person ownership | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | deploy,design,develop /  | FULL | 1.0 | withheld | ev_2a5d14c0e019 @ resume_profile.projects[0].bullets[0] |
| Relative-clause ownership | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | deploy,design,develop /  | FULL | 1.0 | withheld | ev_187f2d6fbd09 @ resume_profile.projects[0].bullets[0] |
| Shortened object | DIRECT / NONE | 0.5 | NONE | REVIEW | REVIEW_REQUIRED | deploy,design,develop /  | UNPROVEN | None | withheld | ev_ad91213960c6 @ resume_profile.projects[0].bullets[0] |
| API consumption | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / deploy,design,develop | UNPROVEN | None | withheld | ev_c79dee18eaa2 @ resume_profile.projects[0].bullets[0] |
| PostgREST integration | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / deploy,design,develop | UNPROVEN | None | withheld | ev_5b3eb55dd534 @ resume_profile.projects[0].bullets[0] |
| Complete alternative second bullet | DIRECT / DIRECT | 1.0 | DIRECT | DIRECT | COMPLETE | deploy,design,develop /  | FULL | 1.0 | withheld | ev_2a5d14c0e019 @ resume_profile.projects[0].bullets[1] |
| Zero-overlap topic recovery | NONE / NONE | 0.0 | NONE | REVIEW | REVIEW_REQUIRED |  / deploy,design,develop | UNPROVEN | None | withheld | ev_1ad64fbd77d3 @ resume_profile.projects[0].bullets[0] |
| Separate partial records | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | develop / deploy,design | FULL | None | withheld | ev_1e461f3a75e1 @ resume_profile.projects[0].bullets[1] |
| Denied lifecycle | DIRECT / DIRECT | 1.0 | DIRECT | REVIEW | REVIEW_REQUIRED | design,develop / deploy | FULL | None | withheld | ev_36023d6f2498 @ resume_profile.projects[0].bullets[0] |

Complete-alternative rows are evaluated with the native selector restricted to complete eligible originals. The cloud first maintenance statement is not deployment and is excluded; its complete second statement explicitly proves deployment. Native capability and API guard ceilings still bind.

## Protected-file and Git verification

All **927 entry-tracked paths** were compared by SHA-256. Exactly the five existing files listed in the change table differ; the other **922 are byte-identical**. All Stage 2D reports/detectors/fixtures and original Stage 2B oracle/semantic baselines are preserved, except the explicitly extended runner and historical-source verifier described above. The before/after ledger is local at `reports/stage2e_runtime/protected_hashes.json`.

| Unchanged protected file | SHA-256 |
|---|---|
| tailoring/capability_taxonomy.py | 373c3cb8d7aedd8122d258c2fc395d49dbb5ca73f93ff02a87b3a254ba7db96f |
| tailoring/phase6d6_structured_matching.py | 90658676df9bb04e6215345f468c6837b7157c5ddf7decb4abda4aabf100e744 |
| tailoring/production_requirement_resolver.py | d773bdfaebdaad0dfcf4da5cec376c6756cdd5809069dd5834191e08917061bb |
| tailoring/requirement_scope.py | 053c694ecbc3f9e5233d686ff946863a41cd569bbc9578820b73461cf38d3c7c |
| taxonomy/capability_taxonomy_v1.json | 1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513 |
| taxonomy/technology_registry_v1.json | 56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675 |
| tests/fixtures/coordinated_action_ownership_oracle_v1.json | 00d23501233547b71c0203039740aa70178251ec1f5f7ce3faa4f54d0ea0fdd1 |
| tests/fixtures/coordinated_partial_action_policy_v1.json | 4f94b900ed177dfbb4288a4e245f9f87f551116a46c3af6bb84cda37634b6112 |
| tests/fixtures/per_jd_scoring_audit.json | a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f |

The intentionally modified scorer retains every published version constant. Parser behavior remains unchanged with the gate OFF; default-OFF full payload equivalence, not just scalar score equality, is asserted against the historical hash-pinned source on all 30 JDs. Historical fixture files and actual saved snapshots are untouched.

`git diff --check`, `git diff --cached --check` and no-index whitespace checks for all new files passed. The index remains empty. The branch and entry HEAD are unchanged; all source/report changes remain unstaged. There are no unexpected tracked changes.

Local exclusions: `reports/bulk_unresolved_stage2e_acceptance_final.json`, superseded `reports/bulk_unresolved_stage2e_acceptance.json`, and `reports/stage2e_runtime/` (logs, disposable synthetic databases and hash ledger). Existing `/reports/*` ignores them. Do not stage these large diagnostic/runtime outputs; they are not test dependencies. No `.gitignore` change or artifact deletion was needed.

**Final recommendation:** PASS for the bounded default-OFF implementation and development acceptance. Production enablement/publication remains BLOCKED for the explicit release reasons above. Stop for review; no commit or push.
