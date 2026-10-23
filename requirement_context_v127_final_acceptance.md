# v1.27 final controlled release acceptance

Date: 2026-10-23. Branch: `feat/unresolved-review-workflow-v1`.
Checkpoint HEAD: `e917c11f684af122b5e256a792315e8349166872`.

## Decision

**CONDITIONAL GO for controlled activation after user approval**, including explicit
acceptance of the single historical CI exception below. No new release-blocking
production defect was found. **End engineering work on this bounded correction**;
do not start another scoring investigation. Code, version/cache compatibility,
presentation and rollback are ready for review; activation remains approval-gated.

Production remains **OFF**:
`analysis_stability/requirement_context_policy.py: PRODUCTION_ENABLED = False`.
Prepared identity: `stable-evidence-v1.27-phase6d31`; context policy:
`requirement-importance-context-v2`. Default native identity remains
`stable-evidence-v1.17-phase6d21`.

## Historical CI exception

The unchanged failing test is
`tests.test_unresolved_semantic_evidence.FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged`.
Its first assertion compares an old research ledger against a dynamically globbed
current source tree. It is not a current-version scoring oracle.

**The exact assertion already fails at checkpoint HEAD.** Verification executed
the original HEAD test body and original HEAD `protected_hashes()` function against
an isolated materialization of HEAD's protected files. Existing ignored historical
JSON inputs were held byte-for-byte fixed. No branch/worktree switch or original
file modification was involved. This is a reproduction of the exact assertion,
not a claim that a full clean-HEAD suite was run or that ignored reports are tracked.

The report records historical commit
`befaace942de996bf5d80f2a5651556a026ee0ab`, scorer v1.16 and taxonomy v1.5.
Its 103-path ledger already differs from HEAD's 112-path projection at **24 paths**:

| Reason | Exact paths |
|---|---|
| Eight substantive changes predating v1.27 | `analysis_stability/stable_evidence_scoring.py`; `tailoring/capability_taxonomy.py`; `tailoring/initial_analysis_explainer_ui.py`; `tailoring/jd_user_input_overrides.py`; `tailoring/phase6d_stable_scoring_adapter.py`; `tailoring/production_requirement_resolver.py`; `tailoring/requirement_scope.py`; `taxonomy/capability_taxonomy_v1.json` |
| Seven checkout-line-ending differences, without content differences from the historical pin | `analysis_stability/__init__.py`; `analysis_stability/evidence_support.py`; `tailoring/deterministic_project_rules.py`; `tailoring/job_match_ab_analysis.py`; `tailoring/phase6d_ranking_adapter.py`; `tailoring/phase9b_role_family.py`; `tailoring/phase9e_tailoring_base_visual_preview.py` |
| Nine source paths added before checkpoint HEAD, absent from the historical ledger | `analysis_stability/coordinated_conflicts.py`; `analysis_stability/coordinated_integration.py`; `analysis_stability/coordinated_ownership.py`; `analysis_stability/coordinated_policy.py`; `analysis_stability/coordinated_r1.py`; `analysis_stability/coordinated_runtime.py`; `analysis_stability/jd_metadata_policy.py`; `analysis_stability/jd_metadata_v123.py`; `tailoring/unresolved_requirement_review_ui.py` |

All eight substantive historical pins match the recorded historical commit's bytes
under LF or CRLF; neither newline form of their HEAD bytes matches the pin. Thus
the failure cannot be explained away as only Windows newline conversion. Git history
attributes these changes to the already committed API completeness, governed
resolution, developer preview and experimental matching work.

For example, the native scorer's historical SHA-256 is
`16cbd0096e228356aade8d495d66e5135332c6e7ebff7e077ac8394e877afb98`;
HEAD LF is `ec17df43bf83c04e3575606cd852b1b2b79efbdc86b49b4b49ceb8b8bff3d8c5`;
HEAD CRLF is `e5cfcac41417dd1893ca37afcd94be1242f4da9415f6659b2a32ad4034b870ec`.

The release additionally changes 18 files covered by that glob and adds two covered
source files. Current comparison: 114 paths, 39 differences from the old ledger,
including pre-existing differences. These counts do not represent 39 release defects.
The exact per-path historical, HEAD and current SHA-256 values, newline checks and
historical-commit checks are retained in
[the local hash-only ledger](reports/v127_final_integrity.json).

The historical report's original seal validates. Historical JSON, taxonomy,
registry and test fixtures were not rewritten. Taxonomy v1.6 was already at HEAD;
the ledger's older v1.5 pin is not evidence of a v1.27 taxonomy edit.
`git diff HEAD -- taxonomy tests/fixtures` is empty. The original assertion remains
active and its fresh execution still fails; no hashes or expectations were replaced.

**Recommendation: accept this single, named legacy assertion as an explicit release
exception**, subject to the user's release approval. Do not exempt its whole module,
other integrity failures, source ownership checks or future regressions. Current
release integrity is assessed independently through source/fixture byte stability,
the unchanged protected artifacts and the focused acceptance/regression results below.
That is sufficient for this bounded release decision; it does not establish all-green
full CI or authenticate unrelated historical research outcomes.

## Application acceptance

Checks use actual application functions and passive Streamlit components with
synthetic/disposable inputs, not live application data or a browser session backed
by the user's database.

| Acceptance case | Verified behavior |
|---|---|
| Job 15 Public Service Spirit | Only `req_7b667a24f1e0` is excluded; 28 → 27 raw-JD requirements; required/core denominator 79 → 76 |
| Job 158 people-development context | Only `req_0c34f8e720fe` is excluded; 28 → 27 raw-JD requirements; denominator 79 → 76 |
| Thirty-JD raw corpus | 716 → 714 rows; other 28 JDs unchanged in requirement identity/importance; surviving parent allocations and provenance preserved |
| Mandatory, preferred and Supporting | Explicit required/essential qualifications retain precedence; existing Supporting weighting retained; unsupported Supporting learning does not reduce Required/Core coverage |
| Future technical responsibilities | Retained as Core role relevance; explanation explicitly distinguishes them from mandatory prior qualifications; mixed technical obligations are not swallowed by context exclusions |
| Context-only results | Null scores remain null through summary, ranking, persistence, A/B comparison and Phase 8 reconciliation; UI says Unavailable; null deltas cannot authorize approval |
| Archived v1.17 | Still readable under the original identity; passive load does not relabel or recompute it |
| Explicit recomputation | Job Finder uses its original Profile & Evidence context; document analysis uses verified original document/JD receipts; Phase 8 uses its own baseline/final authority; missing/corrupted originals block |
| Cache and rollback | New identity invalidates old currentness; repeated identical current input hits its own cache; leaving the isolated scope restores old identity/cache selection |
| A1/S1 and v1.24–v1.26 | No new alias, recognition predicate or publication; experimental scopes remain separate and unpublishable; approval boundaries remain enforced |

The saved 727-row corpus remains historical and separate from the fresh raw-JD
view. Complete authentic candidate packets for Jobs 15/158 are unavailable in the
JD-only fixture: no historical candidate score increase is claimed. The independent
synthetic arithmetic control verifies 55 → 100 after excluding culture, and 100
with an unsupported Supporting learning trait.

## Final regression record

Production and repository test code remained frozen throughout these runs. The
added disposable check's loader correction is distinguished below. Commands use
Python 3.13 and the existing strict offline launcher:

```text
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/v127_final_acceptance <test selections>
```

| Fresh completed lane | Result | Local log |
|---|---:|---|
| Release acceptance + correction, four importance modules, atomic decomposition, native scorer, API completeness and NONE recovery | 123 passed | `reports/v127_final_native.log` |
| Eight complete Phase 8 modules + registry currentness/cache module | 70 passed | `reports/v127_final_phase8.log` |
| Ten complete Job Match, cache, overrides, document analysis and Initial Analysis modules | 103 passed | `reports/v127_final_workflow.log` |
| Experimental isolation, approval boundaries and downstream identities, plus the added workflow check | 83 passed; one added test had six failing subtests from its fixture loader; not an all-green batch | `reports/v127_final_isolation.log` |
| Added Job 15/158 check, corrected UTF-8 loader, all six workflow subtests | 1 passed on focused rerun | `reports/v127_final_application_utf8.log` |
| Original historical hash assertion | 1 known failure | `reports/v127_final_historical.log` |

Earlier verification is documented in
`requirement_context_production_readiness_report.md`: its workflow lane had one
timeout followed by a passing isolated rerun; its isolation lane had two errors
followed by passing isolated reruns; its broad downstream lane was interrupted.
Those are not described as complete passing suites. The fresh runs above supersede
only their corresponding selections. No full project CI was run.

The new disposable acceptance script initially used `Path.read_text()` without an
encoding. Windows cp1252 decoding corrupted the UTF-8 fixture before evaluation:
Job 158 parsed as 17 rather than 28 rows, and neither expected original requirement
ID was removed. A separate unchanged-loader rerun reproduced all six failures
(`reports/v127_final_application_recheck.log`). The loader now explicitly uses
UTF-8 and validates the original fixture's complete SHA-256. The same hardcoded
exclusion IDs, unchanged surviving evidence labels, source ownership and allocation
assertions pass across all three builders. No production code or expectation was
changed to obtain that result. The 84-test batch is still recorded as failed;
only the corrected one-test rerun is recorded as passing.

Exact executed test identities and launcher details are retained in
[the local test receipts](reports/v127_final_test_receipts.json). The intentionally
omitted expensive exploratory checks are the old full-corpus synthetic credit probe
and the three-view temporary recognition-impact experiment; the complete release
30-JD geometry and immutable baseline-parity checks were run instead. This is bounded
release regression coverage, not a complete project-suite claim.

## Patch audit and integrity

The actual scope is **29 tracked modified files plus four new Python files**,
not exactly 25. That is 28 production modules and five test files. The exact file
inventory and purposes remain in section D of the production-readiness report.
All tracked diffs and both new production modules were reviewed: bounded semantic
admission/importance, source receipts, effective identity/cache/persistence admission,
explicit recomputation, nullable display/comparison and eight downstream identity
consumers. The downstream changes replace captured version lookups; they do not
change ranking, generation or selection algorithms. Three existing tests change
only their version-injection seam or optional UI dependency warmup, retaining their
assertions. The two new test modules contain independent expected results.

No additional production correction was necessary during final acceptance. This
task adds this report and ignored local verification artifacts only. Existing
reports, code, decisions and unrelated changes remain preserved. No real database,
saved analysis, résumé evidence, taxonomy, registry or historical fixture was edited.

Final integrity: **849 source files and 15 protected artifacts byte-identical to
the audit's captured inputs**, all 33 changed/new Python files parse successfully,
and both `git diff --check` and `git diff --cached --check` pass. Protected taxonomy/
fixture Git diff is empty; no staged changes exist. The hash-pinned historical
native implementation also produces identical default-OFF analyses on all 30 JDs
in `test_gate_off_matches_hash_pinned_historical_native_on_30_jobs`.

Protected current SHA-256 values:

- Historical research report: `d8d5327ed93d05cc215b3ea263684ee66a6ab88db2f905d80d9cb2bd58d1493d`.
- Original V4 review packet: `1731bcb85197139fd85eb7019df760ec97fdc142fba1df39a14eceb3b9d40ad1`.
- Taxonomy v1.6: `1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513`.
- Registry: `56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675`.
- Thirty-JD fixture: `a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.

Local logs, hash receipts, the disposable acceptance script and isolated HEAD
materialization remain ignored under `reports/`; nothing was uploaded. Historical
JSON copied for the reproduction stays local and should remain excluded from Git.
No model/network calls or real database access were used. Nothing was staged,
committed, pushed, published or activated.

The semantic change is confined to the approved bounded requirement-context policy:
future learning benefits, pure culture/people-development context, generic learning
importance and the qualification-versus-role-relevance explanation. Supporting/
preferred weights, explicit mandatory precedence, parent allocations and evidence
credit rules are preserved. All other reviewed edits support its compatibility,
null handling or explicit original-input recomputation.

## Controlled activation — only after explicit approval

1. Obtain approval for this bounded v1.27 policy and the named historical CI exception.
   Review the complete file inventory, including the new policy/presentation modules
   and tests. Include all compatibility changes together in the release artifact.
2. In a separately authorized release change, set only
   `analysis_stability/requirement_context_policy.py: PRODUCTION_ENABLED = True`.
   Keep the existing v1.27/policy identities; do not overwrite native v1.17, publish
   A1/S1, enable another experimental scope, or migrate a database.
3. Deploy the reviewed artifact and restart application workers/Streamlit so no
   process retains the old switch or cached module state. Confirm effective scorer
   v1.27 and policy v2 on a disposable explicit Analyze action first.
4. Use existing explicit Analyze/Re-run actions on admissible original inputs.
   For programmatic application refresh, use
   `refresh_application_session_analysis_report(..., recompute_requirement_context=True)`;
   for the version transition in Phase 8, use its explicit Re-run action. Keep
   archived reports intact. Do not bulk-refresh, relabel old scores, substitute
   another workflow's evidence or automatically rebind frozen Phase 9 sources.
5. Check independently reviewed examples, context-only Unavailable display, source
   receipts and stale/current cache identities. A workflow without verifiable
   original inputs stays blocked. Ordinary separately requested saves retain their
   existing persistence controls; activation itself performs no data migration.

## Rollback

1. Set the same source-controlled switch back to `False` and redeploy/restart all
   workers. If restoring a deployment artifact, retain the compatible historical
   readers and all stored records.
2. Confirm effective identity returns to v1.17 and the original cache fingerprint.
   Job Finder selects its compatible v1.17 snapshot; retained v1.27 results remain
   historical, never relabeled. Do not delete caches, rewrite snapshots or clear
   application-local overrides.
3. Read existing archived results. If a new analysis is needed, explicitly recompute
   from that workflow's own admissible original inputs. Incompatible frozen bindings
   remain blocked rather than being migrated or silently rebound.

The rollback tests verify identity restoration and selection of the original saved
Job Finder snapshot. Rollback is a policy/identity selection, not an undo of saved data.
