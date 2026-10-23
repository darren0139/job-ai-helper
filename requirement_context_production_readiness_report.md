# Requirement context correction — controlled production release preparation

## Release assessment

Repository: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `feat/unresolved-review-workflow-v1`.
This extends the preserved correction; it does not replace v1.24–v1.26 or publish taxonomy changes.

| Item | Assessment |
|---|---|
| Code ready for developer review | YES |
| Version/cache compatibility ready | YES; distinct scorer and parser-policy identities, no schema migration |
| User-facing presentation ready | YES; nullable metrics, assessment categories and retained context |
| Production activation ready | CONDITIONAL GO for a separately approved activation; **not activated or published** |
| Rollback ready | YES; switch remains OFF, prior identities/cache rows remain intact |

The historical source-ledger failure remains visible. An all-green full-CI release has not been established or claimed. No further classification research, taxonomy discovery or experimental scoring redesign was undertaken.

## A. Version, cache and persistence compatibility

Prepared publishable scorer: **`stable-evidence-v1.27-phase6d31`**.
Parser/importance policy: **`requirement-importance-context-v2`**.
Unchanged base/published default: `stable-evidence-v1.17-phase6d21`.
The earlier `stable-evidence-v1.17-phase6d21+importance-context-v2` preview remains a separate, unpublishable identity.

`analysis_stability/requirement_context_policy.py` has one source-controlled switch, **`PRODUCTION_ENABLED = False`**. Nothing in the application, environment or UI turns it on. Explicit request-local release scopes permit disposable integration verification. Tests simulate switching only with a temporary mock and restore it; the running application was not activated.

The effective-version helper now supplies Job Match currentness, document/A–B identity, Application Session currentness and Phase 8 verification fingerprints. Eight downstream generation/selection consumers also used a captured v1.17 constant; only their current-version lookups were changed. Without these changes they could reject a valid new analysis or retain a stale cache identity.

The native stable fingerprint is rehashed with the parser policy and release scorer. The pre-analysis résumé/JD cache fingerprint receives the release identity **before** a cache lookup. Its OFF fingerprint is unchanged. Job Finder's existing snapshot key already includes the scorer; no table/column migration is needed. Explicitly requesting the old cache identity while the release is selected is rejected. Archived old rows remain addressable under their own identities.

Existing preview namespaces and v1.24–v1.26 remain excluded from publication. The prepared release is admitted only with its expected policy, base identity, semantic-policy receipt and fingerprint. Empty geometry additionally requires actual retained non-scoring source receipts, null score components and the explicit unavailable status. A missing/ambiguous requirement packet is not accepted merely because its list is empty.

The existing explicit analysis persistence function previously rejected every empty requirement list. Its sole exception is now the verified context-only release contract. It still rejects duplicate/missing IDs and incompatible analysis identities. Disposable tests save/retrieve null JSON scores, preserve the immutable first Initial Analysis reference, and retain both old and new history rows.

### Explicit recomputation and evidence authority

- **Job Finder:** its existing Analyze Match path uses the same job JD and complete supplied Profile & Evidence snapshot. New-version cache misses re-use only a compatible extracted JD profile; they do not borrow another workflow's candidate evidence. A subsequent identical request is a cache hit. Tests use the actual inspection, analysis and snapshot persistence functions against disposable SQLite.
- **Initial/document analysis:** passive currentness shows the historical receipt as stale without rescoring. Explicit `refresh_application_session_analysis_report(..., recompute_requirement_context=True)` can re-evaluate a verified document receipt in memory through the existing native document analyzer. Exact original résumé/JD bytes and each document's own represented profile are retained. Existing local preferred overrides are preserved through their existing contract. Stored application data and initial references are not rewritten.
- **Phase 8:** stale-policy baselines require explicit recomputation. Passive automatic verification is suppressed for that policy transition. The existing Re-run action authorizes the bounded re-evaluation. A frozen initial document and a selected document are validated and evaluated separately; their evidence is never merged. Corrupt receipts or incompatible JD/source chains fail closed. The result labels its recomputed baseline separately from the unchanged archived Initial Analysis score.
- **Already frozen multi-stage execution bindings:** their own source/identity validators remain authoritative. This work does not migrate or rebind a historical execution chain. Such a chain must obtain an admissible fresh baseline through its existing explicit workflow; it cannot be made current by changing a version string.

No actual application database was opened or migrated. No cache activation or persistence operation was performed against real data.
Missing legacy résumé-profile evidence blocks policy recomputation rather than producing numeric NONE from an incomplete packet. Document-mode recomputation instead requires the verified original document bytes and receipt.

## B. Result and summary presentation

The real Job Finder summary now retains explicit null scores. Unavailable results are ineligible for trusted numeric ranking; both ranking helpers handle them without inventing zero alignment or failing a numeric sort.

Existing Job Finder metrics, application detail/Markdown summaries, Initial Analysis receipts, Phase 8 comparisons and score explanations use null-safe rendering. Context-only output is **Unavailable**, not `0%`, `None/100`, a fabricated zero-point reconstruction or a zero delta. An unavailable Phase 8 delta cannot satisfy the approval/“score not lower” gate.

The existing result views expose these categories:

| Category | Presentation |
|---|---|
| Explicit required/deal-breaker qualification | Mandatory applicant qualification |
| Core technical responsibility | Core role relevance / future responsibility |
| Other core qualification | Core applicant qualification |
| Preferred qualification | Preferred qualification |
| Supporting trait | Supporting attribute |
| Excluded benefit, values or bounded people-development duty | Non-scored context, retained with its source/reason |

The UI uses the actual native assessment-basis metadata and importance. Future duties can contribute to alignment, but the explanations do not assert that their missing prior evidence is a mandatory qualification failure. No new dashboard was added. Large original diagnostics remain in existing expandable views.

## C. Identical-input results

The approved classification rules, numeric weights, parent allocation and evidence evaluator were retained. This task changes compatibility/presentation and makes the same correction publishable under a distinct identity.

| Actual raw JD | Changed requirement | Scored rows | Required/core denominator |
|---|---|---:|---:|
| Job 15 | `req_7b667a24f1e0` — Public Service Spirit values statement | 28 → 27 | 79 → 76 |
| Job 158 | `req_0c34f8e720fe` — Plan and guide your team's professional growth | 28 → 27 | 79 → 76 |
| Other 28 JDs | No changed IDs or importance classifications | Unchanged | Unchanged |

Thirty-JD raw view: **716 → 714** rows. Surviving parent weights and source provenance are identical. The saved historical view remains separate: **727 stored rows**, with the previous classification-only projection of **725**; no saved analysis was rewritten or numerically replayed.

Primary frozen JD fixture SHA-256:
`a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.

The fixture does not contain complete authentic original candidate packets for Jobs 15/158. Their actual historical alignment effects are therefore **not established**. JD-only denominator changes are not candidate score improvements.

An independently specified synthetic Python example verifies actual end-to-end arithmetic: before, one DIRECT core qualification and one unsupported culture row give 50% core coverage × 90% + 100% credited evidence strength × 10% = **55**. Excluding the culture row produces **100** using the same candidate input. Replacing culture with an unsupported Supporting learning trait also leaves core alignment at 100, preserving existing supporting behavior. These are synthetic controls, not historical candidate findings.

Context-only input previously produced a scored core row and zero alignment. The release instead has zero scored rows, retained context receipts, **null** alignment/coverage/evidence scores and `UNAVAILABLE_NO_SCORING_REQUIREMENTS`. Explicit Required Qualifications, preferred precedence, technical-role relevance and API authorship protections are preserved.

## D. Changed files

The previously untracked correction policy/tests and reports were preserved. This task changes or adds the following files:

| Files | Purpose |
|---|---|
| `analysis_stability/requirement_context_policy.py` | Prepared release identity/switch, preview isolation, null/source-receipt contract |
| `analysis_stability/stable_evidence_scoring.py` | Shared policy hooks, native-baseline isolation and null preservation during re-aggregation |
| `analysis_stability/coordinated_runtime.py` | Publication/persistence admission and rejection boundaries |
| `analysis_stability/requirement_presentation.py` | Shared passive score formatting, assessment labels, metrics and context expander |
| `database/analysis_cache_manager.py` | Pre-analysis identity salt and narrowly admitted context-only persistence |
| `database/job_match_manager.py` | Reject outer/inner scorer cache-identity mismatch |
| `job_discovery/matching.py` | Effective version, null-safe summary, stale identity rejection and assessment metadata |
| `job_discovery/match_ranking.py`, `job_discovery/ranking.py` | Unavailable score ranking safety |
| `job_discovery/ui.py`, `app.py` | Existing selected-job/application metrics and Markdown presentation |
| `tailoring/document_grounded_analysis.py` | Explicit in-memory recomputation from verified original documents |
| `tailoring/jd_user_input_overrides.py` | Effective currentness, explicit refresh, original sources and local overrides |
| `tailoring/initial_analysis_explainer.py`, `tailoring/initial_analysis_explainer_ui.py` | Valid context-only receipts, role-basis explanation and passive display |
| `tailoring/job_match_ab_analysis.py` | Nullable snapshot scores and deltas |
| `tailoring/phase8_verification.py`, `tailoring/phase8_verification_ui.py` | Versioned currentness, explicit transition, nullable comparison/readiness and baseline labeling |
| `tailoring/phase8_score_explainability.py`, `tailoring/phase8_score_explainability_ui.py` | No numeric reconstruction of unavailable scores |
| `tailoring/evidence_grounded_bullet_tailoring.py`, `tailoring/final_scoring_seed.py`, `tailoring/phase9c_blueprint_evaluation.py`, `tailoring/phase9d_global_blueprint.py`, `tailoring/phase9e_blueprint_selection.py`, `tailoring/phase9e_blueprint_selection_ui.py`, `tailoring/phase9f_starting_source_ranking.py`, `database/phase9f_application_execution_manager.py` | Current-version lookup only; existing algorithms, ownership and workflow rules retained |
| `tests/test_requirement_context_release.py` | Independent release, cache, source, arithmetic, persistence, rollback and Streamlit acceptance tests |
| `tests/test_phase8_multiline_jd.py`, `tests/test_phase9e_registry_currentness_cache.py` | Inject future identity through the effective-version helper; original invalidation assertions retained |
| `tests/test_document_grounded_analysis.py` | Preload optional UI dependencies outside AppTest's script deadline; original 30-second rendering/no-write assertions retained |
| `requirement_context_production_readiness_report.md` | This report |

No published taxonomy/registry, historical fixture, independent scoring oracle, résumé output, secret or real database was edited. The existing `tests/test_requirement_context_correction.py` remains intact and is rerun.

## E. Verification record

All lanes use Python 3.13 and the existing strict offline launcher:

```text
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/requirement_context_release <modules>
```

Network/model calls and non-disposable SQLite access are prohibited by that launcher. Runtime logs stay ignored under `reports/`.

| Final evidence | Result |
|---|---|
| `requirement_context_release_acceptance.log` — new release acceptance, including two AppTests | 17 passed |
| `requirement_context_release_native_regressions.log` — importance, atomic parser, stable scorer, API V1.1, QueryAI/data/DSA and NONE recovery | 106 passed |
| `requirement_context_release_phase8_final.log` — eight Phase 8 regression modules | 64 passed |
| `requirement_context_release_workflow_regressions.log` plus `requirement_context_release_passive_trace.log` — workflow/cache/ranking | 102 passed in the batch; its one AppTest timeout passed on focused rerun (all 103 covered) |
| `requirement_context_release_identity_focused.log` and `requirement_context_release_source_identity.log` — shared downstream identities | 9 + 5 passed |
| `requirement_context_release_isolation_regressions.log` plus `requirement_context_release_isolation_recheck.log` — v1.24–v1.26, coordinated, metadata and A1/S1 | 75 passed in the batch; its two errors passed on focused rerun (all 77 covered) |
| `requirement_context_release_final_verification.log` — final code: all 17 new tests, multiline identity and selection-cache identity | 28 passed (includes overlaps with rows above) |
| Existing historical protected-source ledger | 1 known failure; not regenerated or weakened |
| Git whitespace, final Python syntax and protected-file checks | Passed; 33 touched/retained Python files parsed; taxonomy/registry/fixture diff empty |

The new tests exercise actual Job Finder analysis/inspection and disposable persistence, document-native analysis and persistence, full Phase 8 reconciliation, null-safe comparison/readiness and existing passive Streamlit components. They also verify malformed release rejection, stale-cache refusal, exact cache reuse, default-OFF equivalence, temporary activation simulation and rollback to the old cache identity.

During development the controls caught the empty-geometry persistence rejection and v1.26 baseline-probe isolation issue; both were corrected without relaxing the original source/credit constraints. An older version-injection test targeted a removed module-local constant; its injection seam was updated, preserving the assertion that a version change invalidates the fingerprint. AppTest dependency-import timeouts and a truncated DataFrame string assertion were corrected at the harness/assertion-access level; no expectation of null display or zero writes was removed.

The isolation batch's observer error occurred while source edits invalidated a prepared preview's code-revision fingerprint; rejecting it was correct. The other isolation error was an AppTest deadline. Both exact methods passed on the frozen-code rerun. Original failed/incomplete logs remain available; no all-green combined-batch result is substituted for them. An initially over-broad downstream selection was stopped before completion and replaced by the fourteen relevant identity/currentness/source checks above; no completed-suite claim is made for that stopped lane. No full project CI was run.

Exact module selections for the completed main lanes:

```text
# Native (106)
tests.test_requirement_context_correction tests.test_requirement_importance_supporting tests.test_requirement_importance_context_supporting tests.test_requirement_importance_less_strict tests.test_requirement_importance_preference_split tests.test_jd_atomic_requirement_decomposition tests.test_stable_evidence_scoring tests.test_api_evidence_completeness tests.test_capability_none_recovery
# Workflow (103, including the separately completed passive UI rerun)
tests.test_job_discovery_job_match tests.test_job_match_ranking tests.test_job_match_session_ab tests.test_job_match_batch_inspection tests.test_job_match_state_queries_v16 tests.test_analysis_cache_manager tests.test_analysis_cache_mode tests.test_application_session_jd_user_inputs_v2_3a tests.test_document_grounded_analysis tests.test_initial_analysis_explainer
# Phase 8 (64)
tests.test_phase8_verification tests.test_phase8_scoring_correctness tests.test_phase8_score_explainability tests.test_phase8_requirement_reconciliation tests.test_phase8_claim_lineage tests.test_phase8_canonical_guard tests.test_phase8_multiline_jd tests.test_phase8_phase9c_aggregation_parity
# Isolation (77, including the two separately completed reruns)
tests.test_evidence_relevance_preview tests.test_phase3a_eligible_evidence tests.test_phase3a_alias_surface tests.test_coordinated_action_implementation tests.test_jd_metadata_admission tests.test_jd_metadata_v123 tests.test_a1_governance_closure tests.test_phase3a_recognition_review
# Final code verification (28)
tests.test_requirement_context_release tests.test_phase8_multiline_jd tests.test_phase9e_registry_currentness_cache
```

Protected byte hashes remain: taxonomy `1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513`; registry `56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675`; alternate coverage fixture `6b5edb4287cceaae6b6c49a13fb4b149666a2514aaada34deb89e29ec2b7c299`. The primary corpus hash is recorded above.

The historical failure is `tests.test_unresolved_semantic_evidence.FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged`. Its original source-tree ledger already differs from checkpoint HEAD (documented in the preceding report); intentional source edits also differ now. No old research output, manifest or hash oracle was rewritten to make it pass. This remains a release-verification exception, not a newly introduced candidate-credit defect.

## Activation and rollback decision

Production is still **OFF**. Before publication, review this bounded patch and the final results, explicitly approve the new identity and switch change, and handle the historical-ledger failure through a separate honest compatibility decision. There is no database migration to run and no automatic rewrite of archived analyses.

After approval, deploy the version and switch as one change. Use the existing explicit Analyze/Re-run paths on admissible original inputs; never mark old outputs current by relabeling them. Monitor null rendering and source receipts on independently reviewed examples. Rollback sets the switch OFF and selects the prior identities/caches; retain new-version history for audit. Do not delete/rewrite either version's snapshots.
