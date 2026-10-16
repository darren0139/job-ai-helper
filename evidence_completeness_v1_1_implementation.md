# Evidence Completeness V1.1 implementation and validation

Implemented for review; full validation is blocked by absent historical research inputs. The affected 151-test regression run passes. The complete quick/full gates have NOT passed; this is not a release approval.

## Scope and environment

- Worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
- Branch: `feat/llm-unresolved-requirement-adjudication-v1`.
- Baseline commit: `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc`. The two V1 review artifacts were the only initial untracked files and are preserved.
- Installed Python 3.13.12 and repository requirements (119 packages) in an isolated environment under ignored `venv/evidence-completeness-runtime/`. No other worktree or environment was used. The existing incomplete `.venv` was not replaced.
- Followed README dependency installation via `requirements.txt`; no dependency manifest changes. Dependency downloads were the only authorized external network operations.
- Reproduced the temporary-directory error on Python 3.13. Its owner-only Windows ACL is incompatible with the restricted execution token. A create/write/read/cleanup probe passes under the normal owner context. Test runs use that context, a worktree-owned TEMP/TMP, and a startup audit guard that blocks external socket/DNS operations and every non-disposable SQLite connection.
- Logs, interpreter, packages, bytecode and test state stay under ignored `venv/`. No live refresh, publication, actual resume update, commit, push, merge or branch change.

## Production changes

`tailoring/capability_taxonomy.py::_api_evidence_label` adds the approved bounded activity/object completeness predicate to the existing capability evaluator. It accepts action inflections and endpoint plurals, distinguishes service implementation from clients/documentation/data access, scopes negatives and protocol claims to the asserted activity, and checks design responsibility separately. Each decision uses one source row. Multiple activities in that same row can support the obligation; different source rows do not silently complete it.

`_evaluate_capability_record` keeps the named-protocol guard and applies that predicate only to `backend.api_development`. Protocol negation no longer treats an unrelated denial of backend architecture ownership as a denial of REST endpoint implementation. The published taxonomy v1.6 bytes, technology registry, recognition fallback and resolver remain unchanged. No taxonomy publication is required or performed.

`analysis_stability/stable_evidence_scoring.py` increments scoring from `stable-evidence-v1.16-phase6d20` to `stable-evidence-v1.17-phase6d21`. Existing currentness and stable-input identity therefore distinguish the new policy without rewriting records or automatically refreshing matches. The only recovery exception permits existing WEAK credit at zero literal overlap when the evaluator explicitly proves API implementation without the independently required design obligation and pins `api-evidence-completeness-v1.1`. Other weak-recovery gates, source ordering, preliminary ceilings, scoring values/formulas and candidate-fingerprint code are unchanged.

## Actual 23-scenario comparison

These are disposable development fixtures and policy expectations, not independently verified candidate facts. Before results were re-executed using the baseline evaluator through the same current native scoring path with its old scoring identity; the results agree with the frozen V1 outcomes. After results use the implemented evaluator. Matrix cases have deterministic repeat and canonical-identity checks; additional regressions verify input and provenance preservation.

| Scenario | API evaluator before -> after | Final native label before -> after | Synthetic score before -> after |
|---|---|---|---|
| postgrest | direct -> none | direct -> none | 100 -> 0 |
| intern_development | none -> direct | none -> direct | 0 -> 100 |
| intern_combined | none -> weak | none -> weak | 0 -> 22 |
| designed_implemented | direct -> direct | direct -> direct | 100 -> 100 |
| fastapi | direct -> direct | direct -> direct | 100 -> 100 |
| fastapi_implicit_rest | none -> none | none -> none | 0 -> 0 |
| integration | direct -> none | direct -> none | 100 -> 0 |
| integration_obligation | direct -> direct | weak -> weak | 22 -> 22 |
| skills_only | none -> none | none -> none | 0 -> 0 |
| documentation | direct -> none | direct -> none | 100 -> 0 |
| non_authoring | direct -> none | direct -> none | 100 -> 0 |
| negated_implementation | none -> none | none -> none | 0 -> 0 |
| grpc_not_rest | none -> none | none -> none | 0 -> 0 |
| grpc | direct -> direct | weak -> weak | 22 -> 22 |
| both_protocols | direct -> direct | weak -> weak | 22 -> 22 |
| separate_protocols | none/none -> none/none | weak -> weak | 22 -> 22 |
| mixed_obligation | direct -> none | none -> none | 0 -> 0 |
| mixed_evidence | direct -> direct | direct -> direct | 100 -> 100 |
| selection | direct/none -> none/direct | direct -> weak | 100 -> 22 |
| legacy_valid | direct -> direct | direct -> direct | 100 -> 100 |
| backend_control | none -> none | none -> none | 0 -> 0 |
| cpp_control | none -> none | direct -> direct | 100 -> 100 |
| frontend_control | none -> none | direct -> direct | 100 -> 100 |

Exact PostgREST statement: DIRECT/1.0 becomes NONE/0.0 for the EDB design/development requirement. Requirement recognition stays CAPABILITY_RESOLVED. Exact internship wording: NONE/0.0 becomes DIRECT/1.0 for development, and WEAK/.20 for combined design/development. Explicit API interface design plus handler implementation remains DIRECT/1.0.

When both PostgREST and internship rows are supplied, selected evidence changes to the real endpoint-development statement at `resume_profile.projects[0].bullets[1]`. Its evaluator decision is DIRECT; the existing preliminary lexical ceiling leaves this particular multi-row native fixture at WEAK/.20 (score 22). The standalone internship development fixture recovers DIRECT (score 100). This preserves the existing selection/scoring contract rather than globally promoting positive preliminary matches.

Generic integration/gRPC/dual-protocol synthetic phrasings retain their pre-existing native WEAK classifications even where the direct API evaluator differs, because those exact synthetic phrasings are not resolved through the canonical API path. Recognition was deliberately preserved. The resolved Job 566 compound/protocol control remains NONE, and consuming REST alongside authored gRPC does not establish REST authorship. These distinctions are recorded explicitly rather than calling every native result an API evaluator result.

All before/after values, complete native receipts, evidence IDs/sources and policy reasons are in `evidence_completeness_v1_1_results.json`. Direct/weak/none retain values 1.0/.20/0.0; no new tier or weighting is introduced.

## Cross-job impact and score limits

30 disposable job projections cover 716 canonical requirements using only previously selected evidence from the tracked audit fixture. One projection changes: Job 81, `req_8902c2c2d5c0` (Knowledge of API development), loses DIRECT/1.0 credit for the same PostgREST data-access statement, becoming NONE/0.0; projected score 10 -> 8. Every changed row is an API capability row. The comparison asserts unchanged requirement identities, recognition, importance, parent allocation, eligibility and source provenance; unrelated capabilities have no unexpected changes in these projections.

These projections are incomplete evidence libraries, not live candidate profiles, verified gold labels or production ranking predictions. The EDB snapshot projection also omits other resume evidence and cannot reproduce its saved score of 20, so no corrected live EDB total or precise removal of the previously attributed ~3.536296 contribution is claimed. Historical scores and snapshots 40/56 were not recalculated or rewritten.

## Validation

- Supported baseline: 63 tests passed before production changes. The initial run was 62 passes plus one missing ignored-report dependency. That test now uses all 43 requirements in the tracked EDB fixture and retains the exact assertion that only `req_9270e95898c8` changes recognition. It does not claim to reproduce the unavailable original 13-case cross-job manifest.
- New contract module: 8 tests passed, including all 23 matrix scenarios and additional scoped-action, passive/negative, protocol, source-tie, zero-overlap and identity controls.
- Affected suite: 151 tests passed, including recovery, taxonomy, compound completeness, ranking, accounting, historical staleness and exact fingerprint controls.
- Final source compilation: all 631 Python files passed. The corrected taxonomy-loader class passed 2/2 tests.
- Quick and full project gates were attempted using the supported isolated interpreter. Both reached unittest execution after their 43 configured zero-cost smoke checks passed. They were interrupted after independently confirming the missing-input blocker, following the request to stop when the required test environment cannot be completed. No complete gate pass is claimed. At interruption, logs contained 618 quick-test entries (one stale taxonomy-version assertion, subsequently corrected and independently verified) and 80 full-test entries. These are partial observations, not total suite results. No test processes remain.
- Direct missing-artifact checks: two test methods errored on the absent Ollama historical report, and the semantic investigation class errored during setup on its absent historical report (2 tests run, 3 errors including class setup). The dependent gold packet is also absent. These pre-existing research checks were not skipped, weakened or supplied fabricated outputs.
- Known absent pre-existing full-suite inputs: `reports/ollama_unresolved_adjudication_smoke_v1.json`, `reports/unresolved_semantic_layer1_evidence_relevance_v1.json`, and `reports/unresolved_gold_review_packet_v4.json`. No replacement research/model outputs are fabricated.
- Commands use the isolated interpreter with the same Python runner invoked by the Windows batch launchers: `python scripts/run_project_checks.py --mode quick` and `--mode full`. The existing batch launchers require the incomplete `.venv`, so their interpreter path is not used or patched.

## Protected artifacts and history

All 22 protected artifacts other than the two intentionally edited policy sources have identical before/after SHA-256 values. This includes published taxonomy/registry JSON, resolver/scope/adapter sources, governed publication-related sources, snapshot manager and both tracked historical audit fixtures. Full hashes are in the JSON.

| Intentionally edited source | Before SHA-256 | After SHA-256 |
|---|---|---|
| `analysis_stability/stable_evidence_scoring.py` | `16cbd0096e228356aade8d495d66e5135332c6e7ebff7e077ac8394e877afb98` | `3e4fad843517f20d446650c35b7173ad08eab30e16f3e09f97e4f4d4b2adfaa0` |
| `tailoring/capability_taxonomy.py` | `0e4d603533d7430fd80749ca1a951f4f2e3938b05b244ea3d41e78b6e0f1dfcf` | `373c3cb8d7aedd8122d258c2fc395d49dbb5ca73f93ff02a87b3a254ba7db96f` |

Live databases, user-level databases and database-backed publication receipts were not accessed. Consequently this review does not claim byte hashes of live databases or serialized live snapshots. Protection is evidenced by blocked non-disposable SQLite access, unchanged source/fixture hashes, immutable saved-fixture assertions and disposable database round trips. The tests explicitly preserve the historical DIRECT receipt while rejecting a fresh unsupported authoring decision, and prove that the saved old scoring identity is stale under the new version without mutating it.

## Every changed or added repository file

| File | Purpose |
|---|---|
| `analysis_stability/stable_evidence_scoring.py` | Approved scoring identity increment and version-pinned API partial-evidence recovery. |
| `evidence_completeness_v1_1_implementation.md` | Review findings, limitations, validation and acceptance instructions. |
| `evidence_completeness_v1_1_results.json` | Executed before/after, cross-job and hash evidence. |
| `scripts/check_api_evidence_completeness.py` | Offline baseline/new evaluator and native selection comparison, 30 disposable projections, protected hashes. |
| `scripts/check_capability_taxonomy_v1_4.py` | Correct stale v1.5 smoke expectation to the already-published v1.6. |
| `scripts/check_jd_section_heading_filter.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `scripts/check_requirement_importance_context_supporting.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `scripts/check_requirement_importance_less_strict.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `scripts/check_requirement_importance_preference_split.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `scripts/check_requirement_importance_supporting.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `scripts/run_project_checks.py` | Include the new contract regression module in the quick gate. |
| `tailoring/capability_taxonomy.py` | Bounded API evidence completeness and scoped protocol negation. |
| `tests/fixtures/api_evidence_completeness_v1.json` | Self-contained original 23 scenarios with frozen baseline receipts and approved expectations. |
| `tests/test_api_evidence_completeness.py` | Evaluator/native scenario, selection, negation, design, protocol, provenance and identity regressions. |
| `tests/test_capability_none_recovery.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_capability_taxonomy_loader.py` | Correct stale default taxonomy version expectation to v1.6. |
| `tests/test_capability_taxonomy_v1_4.py` | Correct stale default taxonomy version expectation to v1.6. |
| `tests/test_capability_taxonomy_v1_4_boundaries.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_governed_requirement_resolution.py` | Replace ignored report dependency with the tracked 43-requirement EDB source fixture. |
| `tests/test_jd_structure_fingerprint_compat.py` | Use production scoring identity and pin the approved new exact input hash. |
| `tests/test_phase8_scoring_correctness.py` | Use production scoring identity and correct stale published taxonomy version expectation. |
| `tests/test_phase9c_shared_scoring_regression.py` | Use production scoring identity and update the exact hash while preserving all score/evidence assertions. |
| `tests/test_phase9e_registry_currentness_cache.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_phase9e_tailoring_base_master_docx_downloads.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_phase9e_tailoring_base_original_docx_preview.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_phase9e_tailoring_base_visual_preview.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_post_publication_accounting.py` | Scope historical presentation to its original scoring version; assert fresh rejection, saved receipt preservation and new-version staleness. |
| `tests/test_production_technology_knowledge.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_requirement_importance_context_supporting.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_requirement_importance_less_strict.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_requirement_importance_preference_split.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_requirement_importance_supporting.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |
| `tests/test_resume_evidence_structural_headings.py` | Replace duplicated stale scoring-version literals with the production currentness identity; retain semantic assertions. |

## Manual acceptance and remaining review

1. Review the two production source changes, the version increment and all 23 actual outcomes. Verify the internship statement factually before any later resume update; no wording has been saved to the candidate profile.
2. Review the selection ceiling and unresolved generic-phrase limitations above. No broader recognition/decomposition or partial-scoring changes are included.
3. Resolve missing historical full-suite artifacts through a trusted, user-provided source if required. Do not reconstruct model results, access master or alter protected saved records to obtain a green gate.
4. After the trusted missing inputs are available, rerun BOTH complete project gates using the isolated Python 3.13 environment and disposable/network guards. Current logs are partial, so broader failures remain unknown. Do not release based on the focused pass alone.
5. Review the protected hash ledger and disposable historical round trips. Any production Job Match refresh, resume update, commit, push, merge or publication requires a later explicit instruction.

No unresolved policy approval is needed for the implemented bounded contract. Broader validation and human review remain release gates. Stop for review; do not begin Bulk Unresolved Resolution V1.

## Exact test commands and logs

The full command list and final status are in the JSON `validation` section. `isolated-python` denotes `venv/evidence-completeness-runtime/environment/Scripts/python.exe`. The ignored local `venv/evidence-completeness-runtime/run_checks.ps1` launcher sets TEMP/TMP, bytecode redirection, disposable review/usage database overrides and the startup socket/SQLite audit guard before executing the runner. Logs are adjacent (`baseline.log`, `focused.log`, `loader_final.log`, `compile_final.log`, `quick.log`, `full.log`, `missing_artifact_checks.log`). Installed dependency pins are in `installed_requirements.txt`.

Final protected-hash verification matches the JSON ledger. The two pre-existing V1 reports remain unchanged. No supported-runtime or ACL blocker remains for the affected tests; the outstanding blocker is missing trusted historical test data for the complete suite.
