# Evidence Completeness V1.2 — API knowledge review

Investigation and dry-run complete. No production policy, scoring identity, existing V1.1 file, taxonomy, registry, saved snapshot or actual resume evidence was changed. Stop for user review before implementation.

## Findings and recommendation

**Retain NONE for Job 81’s exact saved statement for now.** It documents PostgREST-backed data access and Row-Level Security applied to database operations. It does not state which API-development concepts the candidate understands. NONE denotes insufficient documented support for this scored obligation, not a finding that the candidate lacks knowledge. DIRECT is not justified by this wording.

**V1.1 is nevertheless too broad for knowledge obligations generally.** It requires endpoint/API implementation even for knowledge-level requirements. The hypothetical fixture that explicitly handles HTTP requests, JSON responses, authentication contracts and error statuses demonstrates a meaningful counterexample: it supports partial relevant concepts without claiming endpoint authorship. WEAK is a defensible review proposal for that stronger evidence. Do not infer those details from the saved PostgREST row, bare CRUD integration, SDK use, or database policy work.

An existing WEAK value can represent that partial support, but there is no pre-existing API-knowledge rule that automatically maps integration to development knowledge. Do not borrow the C++ identity-knowledge rule or treat all “Knowledge of” phrases alike. A narrowly reviewed knowledge-specific branch in the existing API evaluator is recommended; no implementation is included.

## Safety, baseline and provenance

- Worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
- Branch: `feat/llm-unresolved-requirement-adjudication-v1`.
- HEAD: `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc`; all pre-existing V1.1 changes and review artifacts are preserved.
- Current scoring identity remains `stable-evidence-v1.17-phase6d21`; published taxonomy remains v1.6.
- A before/after SHA-256 manifest covers all 57 existing V1.1/protected files selected at entry. Every hash matches after focused tests and previews.
- No live/user-level SQLite database, actual Job Match refresh, saved record rewrite, publication, actual resume edit, other worktree access, commit, push or merge.

Job 81 is inspected through `tests/fixtures/per_jd_scoring_audit.json`, not a live database. The original saved receipt is:

- Requirement: `req_8902c2c2d5c0`, `Knowledge of API development`.
- Parent: `Knowledge of data engineering concepts, API development, microservices architecture, and enterprise integration patterns`.
- Importance: core; conserved parent fraction .25.
- Original evidence ID: `ev_3e06933c2432`.
- Original source: `resume_profile.projects[1].bullets[1]`; section: projects.
- Exact text: “Implemented backend data access through PostgREST and applied Row-Level Security policies to secure database operations.”
- Historical fixture label/value: DIRECT/1.0; reason `explicit_backend_api_implementation`.

**The original project title is unavailable in this frozen projection.** Its baseline analysis has canonical requirements and its frozen inputs contain raw JD text, not the resume project-title mapping. The evidence ID is derived from section plus normalized text in `build_resume_evidence_index` (line 3007), so an identical ID does not authenticate a project title. QueryAI and this saved source must remain unlinked until a trusted mapping is supplied.

The user’s QueryAI clarification establishes API CRUD/integration, authentication, Realtime and REST-backed data access as separate context. The candidate did not implement the Python/Flask `/message` endpoint. No React source file is included in the supplied request or this Job81 projection; no code audit or handler/function/interface-design authorship is claimed. The richer request/response concept statements below are hypothetical fixtures, not new candidate facts or saved resume wording.

## Exact source trace

1. `tailoring/capability_taxonomy.py::_api_evidence_label` (672) finds `development` in the requirement and sets `development_required`. There is no knowledge-obligation branch. `integration_only` is false for `Knowledge of API development`.
2. The evidence action `Implemented` is followed by `backend data access through PostgREST`. The bounded API-object grammar does not find an authored API/endpoint/handler object. Applied database policies do not provide an API implementation activity. `implementation_complete` is false, so the result is NONE / `api_authorship_not_established`.
3. `_evaluate_capability_record` (795) applies this API completeness predicate for the recognized capability. Job81 has no named REST/gRPC protocol in its selected atomic requirement, so its immediate rejection is the authorship prerequisite, not a protocol mismatch. Named-protocol guards still apply to other matrix requirements.
4. `tailoring/phase6d_stable_scoring_adapter.py::cap_requirement_with_taxonomy` preserves canonical capability recognition and caps unsupported evidence. `analysis_stability/stable_evidence_scoring.py::_apply_capability_none_recovery` (3478) ignores rank-zero decisions, leaving no selected API evidence.
5. If the same evaluator receipt is counterfactually changed to WEAK, recovery still refuses zero-overlap evidence at line 3581. Its existing exception at 3576 is specifically version-pinned implementation-without-design evidence; a knowledge receipt does not qualify. The experiment never fakes overlap or misuses that production reason.
6. Native preliminary ceilings remain active. For example, a DIRECT knowledge-evaluator hypothesis can remain WEAK natively when there is already a positive preliminary match. Unresolved requirement phrasings do not necessarily invoke the API cap at all. Final native labels are reported separately from forced-capability evaluator probes.

Existing knowledge contracts are local: `_v14_label` (85) allows a narrow C++ knowledge claim from an explicit language token, while memory/cache and data-oriented policies distinguish concepts from requested implementation in their own ways. `analysis_stability/evidence_support.py::classify_verified_evidence_support` supplies lexical support thresholds, not universal semantic knowledge proof. `_looks_supporting_requirement` (148) treats certain familiarity/basic-knowledge phrases as supporting importance; the unqualified Job81 knowledge child remains core. Importance classification and evidence completeness are separate contracts.

Values remain DIRECT 1.0, TRANSFERABLE .55, WEAK .20, NONE 0.0. No API-specific transfer rule or new tier is invented.

## Job 81 counterfactuals through the actual native selector

The disposable projection uses all six previously selected evidence statements and the original JD. It is not a complete candidate library or a live-score prediction. Native projected sources are remapped into one disposable project; the original saved source receipt above is retained separately.

| Evaluator choice | Recovery policy | Final label/value | Rounded projected score | Selected evidence |
|---|---|---|---:|---|
| NONE (recommended for exact saved wording) | Current V1.1 | NONE / 0.0 | 8 | None |
| WEAK sensitivity | Current V1.1 | NONE / 0.0 | 8 | None: zero-overlap recovery blocked |
| WEAK sensitivity | Experimental knowledge-only exception, in memory | WEAK / .20 | 8 | Same PostgREST statement, `projects[0].bullets[4]` in projection |
| DIRECT sensitivity; unsupported restoration | Current V1.1 | DIRECT / 1.0 | 10 | Same PostgREST statement, `projects[0].bullets[4]` in projection |

WEAK plus the hypothetical exception changes the required/core numerator from 2.40/58 to 2.55/58 (coverage 4.137931% -> 4.396552%). Core parent weight is unchanged at 3*.25=.75; the partial contribution is .75*.20=.15. Evidence strength stays 40 and rounded overall score stays 8. DIRECT raises the numerator to 3.15/58 and evidence strength to 52, giving 10. These are classification sensitivities, not a reason to choose a label for score improvement.

## 27 representative cases

`K` below is a fixture-specific knowledge-label hypothesis, not an implemented matcher or independently verified gold. For each case the JSON contains exact evidence text, hypothesis basis, baseline evaluator reasons, full native labels/values, selected text/IDs/sources, scoring components, and both recovery variants. `B` is current V1.1; `P` uses the hypothesis with current recovery; `P+` additionally permits only an experimental knowledge WEAK receipt at zero overlap.

| Case | API evaluator B -> K | Native B | Native P | Native P+ | Baseline selected source(s) |
|---|---|---|---|---|---|
| saved_job81_statement | none -> none | none/0 | none/0 | none/0 | none |
| development_knowledge_crud_only | none -> none | none/0 | none/0 | none/0 | none |
| development_knowledge_contract_practices | none -> weak | none/0 | weak/0.2 | weak/0.2 | none |
| development_knowledge_custom_endpoints | direct -> direct | direct/1 | direct/1 | direct/1 | projects[0].bullets[0] |
| rest_knowledge_plural_supabase | none -> weak | weak/0.2 | weak/0.2 | weak/0.2 | projects[0].bullets[0] |
| rest_knowledge_singular_supabase | none -> weak | none/0 | weak/0.2 | weak/0.2 | none |
| rest_knowledge_contract_practices | none -> direct | none/0 | weak/0.2 | weak/0.2 | projects[0].bullets[0] |
| rest_knowledge_sdk_only | none -> none | none/0 | none/0 | none/0 | none |
| integration_knowledge_supabase | direct -> direct | none/0 | none/0 | none/0 | none |
| integration_obligation | direct -> direct | weak/0.2 | weak/0.2 | weak/0.2 | projects[0].bullets[0] |
| authoring_postgrest | none -> none | none/0 | none/0 | none/0 | none |
| endpoint_authoring | direct -> direct | weak/0.2 | weak/0.2 | weak/0.2 | projects[0].bullets[0] |
| endpoint_authoring_exact_noncanonical_phrase | direct -> direct | weak/0.2 | weak/0.2 | weak/0.2 | projects[0].bullets[0] |
| skills_only | none -> none | none/0 | none/0 | none/0 | skills.Listed technologies[0] |
| documentation_only | none -> none | none/0 | none/0 | none/0 | none |
| development_experience_denied | none -> none | none/0 | none/0 | none/0 | none |
| development_knowledge_denied | none -> none | none/0 | none/0 | none/0 | projects[0].bullets[0] |
| non_authoring_but_contract_practices | none -> weak | none/0 | weak/0.2 | weak/0.2 | none |
| supabase_generated_endpoints | none -> none | none/0 | none/0 | none/0 | projects[0].bullets[0] |
| separate_rows_do_not_complete_knowledge | none/none -> none/none | none/0 | none/0 | none/0 | none |
| wrong_protocol | none -> none | none/0 | none/0 | none/0 | none |
| compound_protocols | none -> none | none/0; none/0 | none/0; none/0 | none/0; none/0 | none |
| internship_development | direct -> direct | direct/1 | direct/1 | direct/1 | projects[0].bullets[0] |
| internship_combined | weak -> weak | weak/0.2 | weak/0.2 | weak/0.2 | projects[0].bullets[0] |
| cpp_knowledge_control | none -> none | direct/1 | direct/1 | direct/1 | skills.Listed technologies[0] |
| frontend_control | none -> none | direct/1 | direct/1 | direct/1 | projects[0].bullets[0] |
| database_policy_control | none -> none | weak/0.2 | weak/0.2 | weak/0.2 | projects[0].bullets[0] |

The main differences are obligation-specific. Bare vendor/CRUD usage remains NONE for development knowledge in this conservative proposal. Explicit contract-practice evidence supports a WEAK development-knowledge hypothesis even when endpoint authorship is denied. Practical REST CRUD can support limited REST knowledge; a richer concept row has a DIRECT evaluator upper-bound hypothesis, but its native preliminary ceiling remains WEAK. That DIRECT hypothesis is not a recommended automatic rule or restoration of Job81 DIRECT.

Exact `Knowledge of REST APIs` is UNRESOLVED in the native path, while singular `Knowledge of REST API` is capability-resolved. The former already receives lexical WEAK in the CRUD fixture despite a NONE API probe. Exact `Knowledge of API integration` has a DIRECT API evaluator probe but remains UNRESOLVED/NONE natively in this fixture. These pre-existing recognition/selection limits are not evidence that a knowledge-policy patch alone will fix all native cases.

Authorship controls remain unchanged: PostgREST-only design/development is NONE, real endpoint implementation is DIRECT eligible, generated Supabase endpoints do not imply handler authorship, and the exact internship wording retains DIRECT development / WEAK combined coverage. The existing V1.1 23-scenario regression also passes. C++ knowledge, frontend and database-access-control controls retain their baseline native behavior. The PostgREST statement still has legitimate database-policy support; API NONE does not discard it for every capability.

## Experimental method and regression limits

The review does not implement a new general knowledge matcher. `tests/api_knowledge_review_support.py` injects exact fixture-label hypotheses after the real evaluator, preserving its protocol guard. For the zero-overlap alternative it compiles the existing recovery function in memory and adds one condition scoped to the experimental knowledge reason, version and exact bounded requirement forms. Normal source compatibility, ranks, tie order, weights, single-row receipts and scoring execute unchanged. Context managers restore all patches and each matrix case is rerun to detect leaked behavior.

No altered overlap counts, falsely attributed implementation-without-design reasons, combined evidence receipts, or production files are used. The unchanged current input fingerprint can describe different counterfactual outputs in memory; these preview results must never be stored as valid v1.17 production matches. They demonstrate why an implemented knowledge-policy change needs a new scoring identity.

Tests assert unchanged requirement IDs, knowledge resolution, capability IDs, importance, parent fractions, source provenance and eligibility across previews. Wrong protocols, skills-only lists, documentation titles, explicit denials and split-row concept/consumption examples stay unsupported under the proposed hypotheses. No unexpected authoring/non-API regression is observed in these fixtures. A fixture receipt experiment does not prove the safety or generalization of a future natural-language predicate.

## Minimal correction for a later approved implementation

1. In the existing `_api_evidence_label`, distinguish explicit bounded development-knowledge requirements from endpoint-authoring requirements before enforcing `implementation_complete`. Preserve all V1.1 authoring rules.
2. Preserve actual endpoint implementation as strong knowledge evidence. For non-authoring evidence, require concrete relevant development concepts/practices in one eligible row, with scoped denial checks, rather than a product name or consumption/integration alone. Existing WEAK is appropriate for demonstrably partial support; leave the exact Job81 row at NONE unless stronger attributable evidence is supplied.
3. Use the existing capability evaluator, normal caps, source compatibility and none-recovery selector. The richer concept fixture already recovers WEAK with the current positive-overlap gate. Do not add a Job81 zero-overlap waiver or a global knowledge-prefix rule by default. Any separately justified semantic waiver would itself need review.
4. Increment the scoring identity if any production classification changes. `current_match_versions` (196) and stable-input identity use versions, not evaluator source bytes. No new version is chosen or applied during this investigation.
5. No taxonomy edit is needed to review evidence for already-resolved `Knowledge of API development`. Improving unresolved knowledge plurals/integration recognition is a separate governed scope decision; do not silently edit published v1.6 or broaden its approved development-only fallback.

## Focused validation and protection

**117 focused tests passed, zero failures/errors**, on the existing isolated Python 3.13.12 environment. Coverage includes the nine investigation tests, V1.1 API completeness, capability recovery, knowledge policies, protocol/single-row completeness, source selection, exact scoring identity and historical snapshot preservation. The database and external-network startup guard remained active; historical database tests use disposable paths. No model or embedding calls.

Command:

```text
isolated-python -B -m unittest tests.test_api_knowledge_review tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_capability_taxonomy_v1_4 tests.test_capability_taxonomy_v1_4_boundaries tests.test_post_publication_accounting tests.test_jd_structure_fingerprint_compat tests.test_production_technology_knowledge.ProductionTechnologyKnowledgeTests.test_current_analysis_identity_invalidates_old_cached_knowledge -v
```

`isolated-python` is `venv/evidence-completeness-runtime/environment/Scripts/python.exe`. The task-specific ignored launcher `venv/evidence-completeness-runtime/v1_2_focused.ps1` sets disposable TEMP/TMP/database overrides, bytecode redirection and the existing startup audit guard. Log: `venv/evidence-completeness-runtime/v1_2_focused.log`. The initial nine-test review run also passed; it is included in the final 117-test run, not an additional unique-test total.

Preview command:

```text
isolated-python -B -m scripts.preview_api_knowledge_review --protected-baseline venv/evidence-completeness-runtime/v1_2_protected_before.json --output evidence_completeness_v1_2_results.json
```

Per the V1.2 instruction, neither complete/quick project gate nor unrelated historical research pipeline was run. Missing legacy reports were not recovered, regenerated or bypassed. All 57 initial V1.1/protected source, fixture and review-artifact hashes match; the complete ledger is in `evidence_completeness_v1_2_results.json`. The production policy source hashes are unchanged in this turn. Live databases and live snapshots were not read or hashed; no live byte-preservation claim is substituted for the passing immutable fixture/disposable round-trip checks.

## Files added in this investigation

| File | Purpose |
|---|---|
| `tests/api_knowledge_review_support.py` | 27 separately scoped fixtures, original Job81 receipt, in-memory hypothetical receipts and bounded recovery experiment. |
| `tests/test_api_knowledge_review.py` | Nine tests protecting scopes, denials, protocols, provenance, currentness and patch restoration. |
| `scripts/preview_api_knowledge_review.py` | Reproducible offline native previews and verification of all existing V1.1/protected hashes. |
| `evidence_completeness_v1_2_results.json` | Exact baseline/preview decisions, selected evidence, scores, original provenance, tests and hashes. |
| `evidence_completeness_v1_2_review.md` | Findings, limitations, minimal recommendation and review instructions. |

No existing repository file was modified by V1.2. The pre-existing dirty V1.1 tree remains as found.

## User review before any implementation

Review the exact saved Job81 wording and keep QueryAI unlinked without an attributable source mapping. Review whether concrete non-authoring development-concept evidence warrants the proposed narrow WEAK branch, and define any complete-knowledge criteria separately. If proceeding, authorize the bounded policy and scoring-version increment before production code changes. Do not update the candidate profile, attribute `/message` authorship, refresh live matches or begin Bulk Unresolved Resolution V1 automatically.
