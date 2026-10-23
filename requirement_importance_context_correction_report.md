# Requirement importance and context correction

## Decision and scope

Bounded correction implemented in the existing shared native pipeline. **Ready for controlled review; production activation remains NO-GO pending explicit promotion and cache/currentness integration.** No replacement scoring engine, taxonomy change or new review framework was introduced.

Worktree: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `feat/unresolved-review-workflow-v1`; checkpoint HEAD: `e917c11f684af122b5e256a792315e8349166872`.
The two pre-existing untracked Markdown reports were preserved. No application database, candidate packet or downloaded debug bundle was opened. No files were staged, committed, pushed or published.

Published v1.17 remains unchanged when the correction is not explicitly requested. Existing v1.24/v1.25/v1.26 gates retain their own behavior. The correction is an explicit request-local validation path, not an environment switch or an enabled application feature.

## 1. Existing implementation and actual call path

Commit `93d2a9e44dae84607d1f40c8f304bf0af27e54c6` merged supporting-importance classification, explicit preference handling, required-heading precedence, preference splitting and importance-sensitive fuzzy-deduplication safeguards. It already addressed much of the reported strictness. It must not be replaced wholesale.

Actual shared path:

1. `stable_evidence_scoring._raw_jd_content_spans`: existing section inference, stop sections, bullet/continuation boundaries and raw span identity.
2. `_raw_jd_requirement_rows` / `_unheaded_role_rows`: sentence-local importance, obligation wrappers and original grounding. Explicit Required Qualifications differs from a generic Requirements heading.
3. `_requirement_sources`: raw-authoritative sections; grounded structured profile rows; explicit legacy profile-only compatibility. Structured summaries cannot invent a second allocation for an existing raw section.
4. `canonicalise_requirements`: semantic context exclusion, canonical identity, safe deduplication, original parent occurrence, source provenance and conserved child fractions.
5. `build_deterministic_keyword_match` / `build_stable_analysis`: original evidence indexing, native matching, structured evaluation, reselection, taxonomy caps and NONE recovery.
6. `compute_deterministic_alignment`: excludes non-scoring rows and calculates coverage by parent allocation. Explicit required/core and preferred coverage remain separate.
7. Job Finder uses `matching._default_stable_builder` and `summarize_stable_match`; Initial Analysis uses `document_grounded_analysis.analyze_actual_resume_against_jd`; Phase 8 uses `phase8_verification.build_current_baseline_analysis` and the shared builder for verification. JD intake also calls the shared canonicalizer.

Presentation already distinguishes supporting counts and omits supporting rows from important-gap classification. App summaries still use a combined Required/Core coverage label. The native score is role alignment, not a hard applicant rejection decision.

An important arithmetic detail: nominal weights are required=4, core=3, supporting=2, preferred=1, but supporting rows do **not** enter required/core or preferred coverage. Positive supporting evidence can enter the existing evidence-strength component; absent supporting evidence does not lower required/core coverage. This behavior and the published 80/10/10 or 90/0/10 aggregation were retained.

## 2. Reproduced defects and corrected behavior

Independent synthetic expectations are in `tests/test_requirement_context_correction.py`.

| Source statement | Published classification | Corrected classification |
|---|---|---|
| Hands-on experience managing database systems required | Required | Required |
| You will gain hands-on experience managing database systems | Core, scored | Training outcome, excluded |
| You will develop a traffic-control platform | Core role responsibility | Retained for role relevance; explicitly not a prior-experience prerequisite |
| Experience developing traffic-control systems is required | Required | Required |
| Ability to learn quickly | Core | Supporting |
| Public Service Spirit | Core | Values context, excluded |
| Plan and guide the professional growth of your team | Core | Non-prerequisite people-development duty, excluded |

The old training exclusion recognized “Throughout the project, you will gain hands-on experience …” but missed the generic future-learning form. The old learning-trait rule required a named software/technology/tool object. Values and the specified people-development duty otherwise entered core coverage.

Technical duties are not blanket excluded. Central technical work remains useful role-alignment information, with `assessment_basis=role_relevance_not_prior_experience_prerequisite`. No claim that the applicant already performed that work is inferred. Core still includes role relevance for compatibility; it is not an eligibility verdict.

### Implemented boundaries

- Explicit hard words and Required Qualifications retain precedence, including genuinely essential soft skills. Preferred learning traits remain preferred.
- Future-learning exclusion recognizes the existing “gain hands-on experience” concept, including the wrapper-stripped unheaded form.
- The Public Service Spirit exclusion accepts the bare value and a bounded values explanation. A technical qualification after that label is retained; arbitrary colon content is not automatically discarded.
- The people-development exclusion accepts the demonstrated imperative duty forms, not general mentoring qualifications or all leadership work.
- Parent scope is checked before excluding a decomposed child. AND/OR and coordinated technical action controls remain intact. No remaining child borrows a lost parent's allocation or a candidate evidence claim.
- Excluded headed statements retain the entire source-row grounding receipt in `filtered_non_requirement_rows`. Unheaded exclusions remain in `decomposition_debug.unheaded_raw_exclusions`. Existing non-scoring sections retain their separate diagnostics.
- A context-only diagnostic has an unavailable/null alignment, not an invented zero-percent result.
- Recognition and evidence credit are unchanged. No alias, new capability, manufactured soft-skill evidence, API authorship, cross-record ownership or numeric promotion was added.

## 3. Exact code changes

| File | Change |
|---|---|
| `analysis_stability/requirement_context_policy.py` | Small request-local classification policy, bounded exclusions, supporting-trait extension, explicit result/cache identity and context-only null result |
| `analysis_stability/stable_evidence_scoring.py` | Hooks into existing importance/semantic classification, complete-parent safeguard, preserved exclusion receipts, policy metadata and result stamping |
| `analysis_stability/coordinated_runtime.py` | Rejects even a bare correction identity at existing publication/persistence boundaries |
| `tests/test_requirement_context_correction.py` | Ten independent focused tests, including requested examples, false-positive controls, actual shared workflow builders, corpus geometry, source authority and persistence rejection |
| `requirement_importance_context_correction_report.md` | This report |

No application UI, taxonomy/registry, parser decomposition rule, matching threshold, evidence evaluator, weight, saved fixture, reviewer decision or production version constant was edited. The native scoring module was modified only to connect the explicitly isolated classification correction.

## 4. Corpus results: separate source views

Source: `tests/fixtures/per_jd_scoring_audit.json`, SHA-256:
`a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.
Thirty JDs in each view; alternate coverage fixture not pooled.

| View | Rows before → after | Core | Required | Preferred | Supporting |
|---|---:|---:|---:|---:|---:|
| Saved historical rows: classification-only projection | 727 → 725 | 628 → 626 | 33 → 33 | 43 → 43 | 23 → 23 |
| Fresh raw-JD native interpretation | 716 → 714 | 622 → 620 | 30 → 30 | 42 → 42 | 22 → 22 |
| Unmodified v1.26 raw interpretation | 716 → 716 | 622 → 622 | 30 → 30 | 42 → 42 | 22 → 22 |

The saved projection applies only the new bounded classification decisions to copies of saved rows. It is not a saved-analysis migration, historical score replay or reconciliation of the different saved/raw requirement geometries. The v1.26 baseline was measured separately; the new policy intentionally rejects composition with other previews. No combined v1.26/correction scoring result is claimed.

Exactly two IDs become non-scored in both the saved projection and actual fresh corrected path:

| Job | Requirement ID | Original text | Before → after | Required/core denominator |
|---:|---|---|---|---:|
| 15 | `req_7b667a24f1e0` | Public Service Spirit: You care deeply about the public good and understand the responsibility of working on critical national infrastructure that impacts millions of lives daily | Core → values context | 79 → 76 |
| 158 | `req_0c34f8e720fe` | Plan and guide your team’s professional growth, in both general and technical areas | Core → role context | 79 → 76 |

Each excluded parent carried one core allocation of weight 3. Other JD denominators and surviving importance classifications are unchanged. The actual raw Job 15 count is 28→27; raw Job 158 is 28→27. The saved Job 158 count is separately 29→28. Preferred denominators for the affected jobs remain zero. No newly created requirement IDs occur.

The exact generic learning examples are independently tested synthetic controls; they do not account for an additional claimed corpus reduction. The corpus's existing longer quick-learning statement was already supporting. Broad interest/passion wording and unfamiliar duties have not been reclassified through unreviewed blanket rules.

Machine-readable local accounting: `reports/requirement_context_corpus.json` (ignored). Historical frozen inputs do not supply the complete original candidate packets. Therefore no historical candidate score improvements, matching successes or application #152 score changes are claimed. Separate synthetic evidence controls verify no invented credit and preserve workflow source authority.

## 5. Verification

All tests use Python 3.13 and `scripts/run_offline_release_checks.py --scratch-root reports/requirement_context_correction`, with disposable storage, secrets isolation, network/model prevention and no original application database access.

| Lane / log | Result |
|---|---|
| `reports/requirement_context_core.log`: correction controls; four importance suites; atomic decomposition; stable evidence scoring; API V1.1; NONE recovery | 106 passed |
| `reports/requirement_context_workflows.log`: source-aware inventory; Job Match; document-grounded analysis; Initial Analysis explanations; Phase 8 | 71 passed |
| `reports/requirement_context_final_controls.log`: final ten correction tests, including the exact two-ID corpus assertion | 10 passed |
| `reports/requirement_context_isolation.log`: v1.24/v1.25/v1.26; coordinated implementation; metadata v1.22/v1.23 | 71 passed |
| `reports/requirement_context_historical_hash_verified.log`: existing historical protected-byte assertion | 1 failed, separately identified below |
| `git diff --check`; `git diff --cached --check` | Passed |

Initial narrow testing exposed a compound-learning-parent exclusion; retaining/checking the complete parent fixed it, with the original negative assertion retained. An initial broad combined run was interrupted without a completed result; the independent final lanes above replace it. One historical check was first invoked with an incorrect unittest class name, then rerun using `FrozenInvestigationArtifactTests`; the corrected invocation exposes the existing real hash failure. Neither incomplete invocation is counted as a pass.

The three final regression lanes contain **248 passing tests**. The final ten-control run is a repeat of tests included in the core lane, after strengthening its exact corpus-ID assertion; it is not counted as ten additional distinct tests. The one existing historical-ledger failure remains separate. No full project CI was run.

Exact final regression invocations (prefix each with `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/requirement_context_correction`):

```text
tests.test_requirement_context_correction tests.test_requirement_importance_supporting tests.test_requirement_importance_context_supporting tests.test_requirement_importance_less_strict tests.test_requirement_importance_preference_split tests.test_jd_atomic_requirement_decomposition tests.test_stable_evidence_scoring tests.test_api_evidence_completeness tests.test_capability_none_recovery

tests.test_source_aware_inventory tests.test_job_discovery_job_match tests.test_document_grounded_analysis tests.test_initial_analysis_explainer tests.test_phase8_verification

tests.test_evidence_relevance_preview tests.test_phase3a_eligible_evidence tests.test_phase3a_alias_surface tests.test_coordinated_action_implementation tests.test_jd_metadata_admission tests.test_jd_metadata_v123
```

The final repeat uses `tests.test_requirement_context_correction`; the separately failing historical invocation uses `tests.test_unresolved_semantic_evidence.FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged` with the same strict launcher.

API consumption versus endpoint authorship, PostgREST/Supabase-only evidence, genuine Java REST endpoint authorship, generic data versus DSA and zero-overlap NONE recovery are covered by the unchanged API/NONE suites. Gate-OFF verification includes the existing hash-pinned native comparison on all thirty historical JDs.

The shared-builder synthetic test executes Job Finder's real native builder, the actual document-grounded Initial Analysis function and the Phase 8 baseline builder. The document-authority negative control cannot borrow a project claim omitted from the supplied document. Profile inputs remain unchanged. A mock persistence connection receives zero SQL calls for the correction identity. Existing workflow tests additionally exercise disposable persistence contracts. This is not a claim of enabled end-to-end application deployment.

### Protected artifacts and historical failure

All taxonomy/registry and historical fixture paths have an empty Git diff. Current artifact hashes:

- Taxonomy: `1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513`.
- Technology registry: `56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675`.
- Alternate coverage fixture: `6b5edb4287cceaae6b6c49a13fb4b149666a2514aaada34deb89e29ec2b7c299`.

The existing `FrozenInvestigationArtifactTests.test_protected_bytes_and_report_seal_unchanged` compares an old source-tree ledger with today's evolving sources. It fails and was not weakened or regenerated. For the native scorer alone its historical pin is `16cbd0096e228356aade8d495d66e5135332c6e7ebff7e077ac8394e877afb98`; checkpoint HEAD already differs with both LF (`ec17df43bf83c04e3575606cd852b1b2b79efbdc86b49b4b49ceb8b8bff3d8c5`) and CRLF (`e5cfcac41417dd1893ca37afcd94be1242f4da9415f6659b2a32ad4034b870ec`) normalization. Thus the failure predates this task; today's intentional source edits also change source hashes. No all-green historical-protection claim is made.

## 6. Identity, compatibility and release blockers

Correction policy: `requirement-importance-context-v2`.
Explicit diagnostic scoring identity: `stable-evidence-v1.17-phase6d21+importance-context-v2`.
Published `SCORING_VERSION`, current match-version defaults and all existing experimental version constants remain unchanged.

The correction result records its base identity, policy, development-only namespace and a different deterministic input fingerprint. Even stripping the development flag does not make its scoring identity persistable. Incompatible preview compositions are rejected rather than silently relabelled. Existing snapshots are readable under their own identities and are not reclassified in place.

Concrete blockers to activation:

1. Approve the bounded classification/promotion contract and allocate the final published scorer/parser-policy identity. The explicit candidate identity must not masquerade as unchanged v1.17.
2. Wire that approved identity through currentness/cache admission and a deliberate recomputation path. Keep archived analyses intact; do not migrate saved scores by editing rows or clearing overrides.
3. Before enabling end-user results, verify all presentation/summary paths preserve the context-only unavailable result. In particular `matching.summarize_stable_match` currently coerces null scores to zero; it rejects this preview before reaching that coercion today. That existing coercion must not be used to publish the promoted empty-context result.
4. Surface the existing role-relevance-versus-qualification metadata in any promoted explanation so a Core role-alignment row is not presented as evidence of a missing mandatory prior qualification. A wholesale duties/traits classifier or UI redesign is not required.
5. Keep the unrelated historical ledger failure visible in release verification; a separate historical/current source-compatibility decision is needed for an all-green full runner.

Optional improvements: broader trait/interest wording, unfamiliar leadership language and additional source-specific explanations. They are not justification for withholding review of the verified correction until all 38 assisted cases become independent gold. Conversely this patch does not claim to solve those broader classifications or the 536-occurrence unresolved corpus.

## 7. Controlled promotion plan

Review the seven independent examples, hard-qualification/compound negatives and the two exact corpus exclusions. Approve a final version identity and bounded semantics. Make only the necessary null-safe summary/currentness changes; test those actual application paths before activation. Recompute explicitly selected inputs under the new identity using each workflow's own evidence authority; retain historical results as historical. Compare the default-OFF fixtures and API/source controls again at the final promotion commit.

Rollback is to select the prior published identity and its existing caches; never reinterpret the corrected cache as v1.17 or rewrite archived snapshots. Existing A1/S1 governance and the 38-case independent-review workflow remain separate.

**Final recommendation: conditional GO for the bounded correction review; NO-GO for production activation today.** No further broad scoring research is required to make the explicit promotion/null-summary decisions above.
