# Stage 2I — Scoped contradiction quarantine and source occurrence safety

Development implementation only. Repository `Job-AI-Helper-Codex-Resolver`, branch `feat/coordinated-realistic-evidence-v1`; entry HEAD `fa794cdf341efe2bd7a5b81c7b51fdcefec60be2`. Nothing is staged, committed, pushed or activated. Published/default-OFF scorer remains `stable-evidence-v1.17-phase6d21`.

## Implemented boundary

The explicitly gated scorer is now `stable-evidence-v1.20-phase6d24`. New identities are `coordinated-scoped-conflict-quarantine-v1` and `coordinated-original-occurrences-v1`. Existing decomposition, ownership language, P3, recovery, reselection and R1 identities remain unchanged. The input fingerprint includes the original-occurrence ledger and new identities. The dashboard revision includes source/fixture bytes and policy identities; neither dashboard requires ignored exports.

Before native evidence-index deduplication, a read-only ledger enumerates original project/experience headings and bullets, including duplicates with distinct source paths, container IDs and occurrence IDs. It also records unindexed fields, raw-only text, unavailable text/container coverage and native-index coverage. Per-parent diagnostics retain independent original-record ownership proofs, API implementation clauses and denial spans. This ledger is not an alternative scoring index.

For an already-selected, verified positive original, the detector checks narrowly attributable denials of a supported mandatory action against the same required technical object in the same original project/experience container. API implementation denials additionally distinguish endpoint/interface/handler artifact, REST/gRPC protocol and explicit endpoint routes. Different containers, unrelated objects, explicit third-party denials, protocol mismatches and client/consumption activities do not create a global veto. Potentially applicable but unresolved actor, temporal, object, route or original-source scope is review-required, not a clean-source assertion.

The terminal check runs after native selection, validation, caps, recovery and reselection. Applicable conflicts quarantine only the affected coordinated parent. Its effective label, value and governed contribution become null; original positive/negative receipts and stage trace remain available. All existing aggregate fields are recomputed through the existing withheld-score path. No later stage can recover quarantined credit. No positive bullets are joined and no fallback selection is added.

## Actual before/after results

These are synthetic preview outcomes, not historical/live candidate score changes. Stage 2H original inputs, behavior hypotheses, observations and semantic expectations are unchanged. Stage 2I deltas are specified separately in `tests/fixtures/coordinated_conflict_policy_v1.json`.

| Suite | Version | DIRECT | WEAK | NONE | REVIEW_REQUIRED | Whole-JD withheld | Exceptions |
|---|---|---:|---:|---:|---:|---:|---:|
| Realistic 38 | Gated v1.19 observed baseline | 16 | 2 | 2 | 18 | 22 | 0 |
| Realistic 38 | Gated v1.20 | 12 | 2 | 2 | 22 | 26 | 0 |
| Original 60 | Gated v1.19 baseline | 12 | 3 | 19 | 26 | 31 | 0 |
| Original 60 | Gated v1.20 | 12 | 3 | 19 | 26 | 31 | 0 |

For the realistic packets, exact dispositions change from COMPLETE 17 / ELIGIBLE_PARTIAL 2 / REVIEW_REQUIRED 18 / R1_EXCLUDED_NATIVE_NONE 1 to COMPLETE 13 / ELIGIBLE_PARTIAL 2 / REVIEW_REQUIRED 22 / R1_EXCLUDED_NATIVE_NONE 1. All five affected canonical parents change contribution from 1.0 to null. E04/E05/E24 whole-JD previews change from 29% to unavailable, C03 from 24% to unavailable, and B05 remains unavailable. No score becomes numeric zero.

| Case | Previous selected-parent label → current | Whole-JD effect | Scope evidence |
|---|---|---|---|
| E04 | DIRECT → REVIEW_REQUIRED | Previously available; now withheld | Same project, positive embedded lifecycle ownership plus explicit maintenance denial in another original bullet. |
| E05 | DIRECT → REVIEW_REQUIRED | Previously available; now withheld | E04 statements in reversed order; same result. |
| B05 | DIRECT → REVIEW_REQUIRED | Already withheld because another parent was unresolved | Same project, authored REST endpoints versus explicit REST endpoint implementation denial. |
| E24 | DIRECT → REVIEW_REQUIRED | Previously available; now withheld | Selected project 0 is conflicted; project 1's duplicate remains in the ledger but is absent as an independently selectable native-index origin. No fabricated fallback. |
| C03 | Cloud DIRECT preserved; backend DIRECT → REVIEW_REQUIRED | Previously available; now withheld | Independent complete cloud original remains valid; backend REST implementation denial conflicts with its selected backend original. |

Preserved selected-parent outcomes include E01 DIRECT, E02 WEAK, E09 DIRECT, B01 DIRECT, C01 DIRECT and E23 DIRECT. E23's different-project denial does not invalidate its independent ownership. E03/B02 remain review-required without action union. E06's same-original denial remains review-required. E19 duplicate positives remain DIRECT with both original occurrences recorded. Native NONE, P3 WEAK and API V1.1 authorship ceilings remain in place. R1 is not generalized.

The old F02 semantic/behavior hypothesis remains visibly discrepant: the actual v1.19 and v1.20 outputs are DIRECT, whereas the old fixture hypothesizes NONE. Other pre-existing incompleteness, metadata distribution, finite language recognition and R1 schema restrictions are not repaired or hidden by this change. The four selected-label deltas and C03 companion delta are intentional new policy behavior, not rewritten historical expectations.

Specifically, old semantic mismatches were E04/E05/P01/P02/F01/B05/C03. Current comparisons against that immutable semantic oracle differ on P01/P02/F01/E24/C03: P01/P02 still hit finite recognition limits; F01 remains native NONE; E24 intentionally withholds despite the oracle's proposed safe alternative because no fallback policy is authorized; C03's oracle concerns whole-JD review while its selected cloud label correctly remains DIRECT. Current comparisons against old behavior hypotheses differ on E04/E05/F02/B05/E24. The new Stage 2I expected delta agrees on all 38 selected outcomes and withholding states; it does not erase those historical/semantic discrepancies.

## Coverage and independent controls

The ledger distinguishes evidence identity (native content-derived ID) from original occurrence identity (source path plus original text) and container identity (original project/experience path). Identical text across projects can share an evidence ID while retaining separate occurrence IDs. Native deduplication and selection remain unchanged. E24 demonstrates why content identity alone cannot prove a safe alternative source. Unknown/unindexed evidence is never promoted to a new candidate or used to establish complete ownership.

Across the 38 separately supplied packets, the ledger retains 256 occurrences: 252 INDEXED_ORIGINAL, two UNINDEXED_ORIGINAL and two DUPLICATE_OTHER_ORIGIN. E10's summary and E12's raw-only evidence remain covered diagnostically; E19/E24 retain their duplicate project origins. Normalized-text duplicates also receive the duplicate-origin status. Unavailable original text in a selected container produces uncertain-coverage review. Stable IDs/weights of every canonical row match the frozen v1.19 execution; only the five documented canonical labels change.

Independent detector controls were authored and passed before integration. They cover same/different project and experience, same/different technical artifact, third-party versus uncertain actor, temporal prefix/suffix, pronoun ambiguity, raw/unindexed negative scope, unrelated activity, matching REST endpoint authorship, different REST/gRPC protocols, endpoint/client/interface distinctions, unknown protocol, consumption denial and explicit route matching/mismatch. Forged source/ID/text/section and deduplicated fallback receipts fail closed. Read-only/determinism tests protect caller inputs.

## Validation

Only focused offline suites run under `scripts/run_coordinated_preview_checks.py`, with dotenv disabled, network/model access blocked and database access restricted to disposable runner scratch. Python is 3.13.12. The historical snapshot compatibility test uses its existing disposable synthetic SQLite fixture; no live database is opened. Full and quick project-wide suites are not run.

The commands below use `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_coordinated_preview_checks.py --scratch-root reports/stage2i_runtime` as their common launcher:

1. Initial integration/acceptance run: `tests.test_coordinated_conflicts tests.test_coordinated_conflict_acceptance tests.test_coordinated_realistic_evidence_audit tests.test_coordinated_r1_disposition tests.test_coordinated_action_implementation tests.test_api_evidence_completeness tests.test_coordinated_batch_dashboard --batch-dashboard-preview reports/stage2i_runtime/actual_original60.json` — 71 tests, 69 passed and two test issues identified. The requested final export is skipped on an unsuccessful run. A new UI test initially asserted against a truncated DataFrame string representation; the actual cell was correct. The corrected test reads the explicit withheld rows/column, preserving the unavailable-value assertion. The existing default-OFF test also inherited Streamlit's populated cache from earlier AppTest modules and therefore observed no builder call. Its fixture now clears the Streamlit test cache before observing the initial page; all original assertions remain unchanged.
2. Earlier-layer regressions: `tests.test_coordinated_action_preview tests.test_coordinated_evidence_preview tests.test_coordinated_ownership_preview tests.test_partial_action_credit_preview tests.test_capability_none_recovery` — **65 tests PASS**.
3. Final independent conflict and realistic acceptance controls: `tests.test_coordinated_conflicts tests.test_coordinated_conflict_acceptance` — **12 tests PASS**, including all 38 profiles, temporal/unindexed-source withholding through the actual pipeline, distinct-project preservation, stripped-metadata version rejection and native Streamlit selection events without recomputation.
4. Warm-page regression followed by isolated dashboard checks: `tests.test_coordinated_action_implementation.CoordinatedStreamlitTests tests.test_coordinated_batch_dashboard` — **14 tests PASS**. This order deliberately exercises the shared-cache condition before the fixture clears it. The actual 60-case batch has zero current-expectation mismatches, zero unexpected historical changes and zero exceptions. All 32 independently covered checks agree; the 14 governed Stage 2G differences from the older Stage 2E reference remain visible. Default-OFF, no persistence, filters/selection without recomputation, unavailable scores, exception visibility and revision invalidation all pass.

All 30 historical JD default-OFF comparisons pass against the independently hash-pinned native scorer. Existing coordinated implementation checks pass for allocation, source grounding, P3/native NONE/API ceilings, late recovery/reselection and persistence rejection before DB initialization. Eight API completeness tests pass. All current focused controls pass across the initial successful methods and the two corrective reruns; the original failed run remains recorded rather than presented as green.

Protection verification: **945 of 950 entry files are byte-identical**; only the four authorized integration/runtime/dashboard files and one test-isolation fixture are modified. This preserves published scoring/parser/policy, ownership/P3/R1 recognition, taxonomy v1.6, registry, historical snapshots/fixtures, independent E/G references and all five pre-existing untracked Stage 2H/dashboard files. `git diff --check`, `git diff --cached --check` and no-index whitespace checks on the six new Stage 2I files pass. Git's LF-to-CRLF advisory is not a whitespace defect. Changed/new Python files also pass AST parsing. The index is empty and branch/HEAD are unchanged.

Task-local, already ignored evidence is in `reports/stage2i_runtime/`: focused/regression/final-control logs, actual synthetic receipts, `summary.json` and `protected_verification.json`. These exports are output only; no launch/test reads them. The concise comparison script used the frozen Stage 2H diagnostic read-only to verify canonical identity/weight conservation and the five exact canonical-label changes.

## Changed-file inventory

| File | Change |
|---|---|
| `analysis_stability/coordinated_conflicts.py` | New original occurrence ledger, coverage/proof diagnostics and scoped selected-source conflict detector. |
| `analysis_stability/coordinated_integration.py` | New gated identities, ledger-before-index construction, terminal quarantine, diagnostic receipts and fingerprint inputs. |
| `analysis_stability/coordinated_runtime.py` | Reject new v1.20 preview identity from persistence/publication, including stripped metadata controls. |
| `scripts/coordinated_conflict_acceptance.py` | Bounded realistic-profile batch cache, actual baseline/current labels and independent expected delta comparison. |
| `scripts/coordinated_batch_dashboard.py` | Revision invalidation includes realistic-profile helper and independent fixture bytes. |
| `coordinated_actions_preview.py` | On-demand 38-profile table, retained row details, scoped conflict/original-source relationship and actual unavailable scores. |
| `tests/fixtures/coordinated_conflict_policy_v1.json` | New independent scope controls, known actual v1.19 baseline and Stage 2I delta. |
| `tests/test_coordinated_conflicts.py` | Independent source, duplicate, scope, actor, temporal, artifact, protocol and route controls. |
| `tests/test_coordinated_conflict_acceptance.py` | Actual 38-profile delta, terminal null-credit receipts, duplicate safety and retained UI tests. |
| `tests/test_coordinated_batch_dashboard.py` | Clear the shared Streamlit cache at fixture entry so default-OFF call observation remains independent of AppTest execution order; no expectation changes. |
| `bulk_unresolved_stage2i_implementation.md` | This implementation/result/limitations report. |

Five pre-existing untracked files are preserved byte-for-byte:

- `bulk_unresolved_stage2h_readiness.md`
- `coordinated_batch_dashboard_review.md`
- `scripts/audit_coordinated_realistic_evidence.py`
- `tests/fixtures/coordinated_realistic_profiles_v1.json`
- `tests/test_coordinated_realistic_evidence_audit.py`

The existing Stage 2H script and synthetic fixture are source dependencies of the new 38-profile view. A future checkpoint must include those safe files with Stage 2I; committing only the newly created Stage 2I files would omit dependencies. They are not generated acceptance exports. Local diagnostics remain under already ignored `reports/stage2i_runtime/`; no large JSON is a test/launch dependency or recommended Git artifact.

## Remaining release boundary

This is a finite, development-gated conflict recognizer, not a general contradiction, chronology or source-identity resolver. Unsupported paraphrases, implicit subjects, cross-project renames, inaccessible originals and broader role/temporal interpretation need separately governed work. Uncertain cases are not evidence of absence; review values must remain unavailable. R1 multi-record generalization, source selection/fallback and broader positive recognition are deferred. Production activation and realistic-profile numeric publication remain blocked pending review of this bounded policy and remaining semantic/coverage limitations.

**Final verdict: PASS for the bounded development-gated Stage 2I implementation and review. BLOCKED for production activation or general realistic-profile numeric publication.** The selected-source conflict bug is quarantined, the original 60 outcomes and published OFF behavior are preserved, and the remaining semantic/source-selection/language limits are explicit. Stop for review; no activation or Git checkpoint action is authorized.
