# Stage 2G — bounded R1 implementation

R1 is implemented only inside the existing explicit coordinated-action development gate. Production Job Match scoring remains OFF. This report records the implementation and acceptance evidence; it does not authorize activation, persistence or a commit.

Repository: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `feat/coordinated-review-disposition-v1`.
Entry HEAD: `eda9e7bbb9a312febff18bedf2e7c433c3e8ca33`.

## Contract defined and checked before scoring changes

The new independent fixture and nine standalone contract tests were written and passed **before connecting R1 to the scorer**. Seven affirmative expressions and 23 adversarial expressions were reviewed independently of detector outputs. The original Stage 2E reference and all earlier independent ownership/P3/API fixtures are preserved.

The recognizer parses complete affirmative activity statements into named semantic roles, with full text coverage and spans. Its three finite grammars recognize:

- Client consumption/calling of REST APIs using HTTP requests and JSON responses. Bounded variations include first-person wording, existing APIs, singular/plural, and `using`/`via`.
- Integration with Supabase PostgREST **generated** REST APIs for CRUD and authentication, including reversed purpose order. Generated integration does not establish custom endpoint authorship.
- ESP32/STM32 GPIO interrupt/pin configuration, which does not assert the requested software artifact ownership. A native positive topic match still vetoes R1.

These are activity grammars, not scenario-name matching, evidence-ID matching or the Stage 2F diagnostic exact-string catalogue. No research module or fixture is imported by the production contract. Extra clauses, unknown modifiers, subject uncertainty, negation, future/learning language, mixed implementation claims and unknown expressions fail closed.

R1 is deliberately limited to a single attributable original project with one substantive bullet. It requires explicit `projects`, `experience`, `education`, and `skills` sections; the latter three must be empty, as must any supplied certifications and raw text. Unknown top-level/project fields, additional projects/bullets, duplicate originals, omitted sections and nonempty other sections fail closed. This checks the original supplied packet before native index deduplication can hide a second source. It is not a general real-résumé exclusion engine.

The original index is rebuilt from that entire supplied input and compared exactly with the available index. All IDs, source paths, sections and text must agree, and every ownership proof is independently recomputed against that index. The original requirement is re-extracted and uniquely grounded in raw JD text. Unsupported parents, OR, negation and optional qualifiers cannot enter R1. A recognized neutral project-title grammar is metadata only: it never supplies negative evidence, and title-only/empty packets cannot pass.

Every substantive record must be affirmatively classified as an excluded activity, with no supported requested action, denied duty, ambiguous ownership or unexamined record. Native final label must already be NONE. The receipt expressly limits the conclusion to the entire supplied packet; it never claims the person has never performed the work. Unknown titles or richer profiles stay under review rather than being treated as absent experience.

## Integration and invariants

`build_coordinated_analysis` first runs the full native corrected-parent analysis, including native recovery and reselection. Existing COMPLETE/P3 admission and filtered scoring remain unchanged. Only when no original is admitted does the new terminal branch evaluate R1. Successful proof sets `R1_EXCLUDED_NATIVE_NONE`, retains numeric NONE/0, clears positive selected evidence and records every original source in `r1_exclusion`. No selection, recovery or reselection runs after that terminal decision.

The row keeps its original canonical identity, source provenance and 1.0 parent allocation. There is no redistribution, evidence synthesis, cross-bullet action union, new partial-credit formula or API authorship inference. P3 remains capped at WEAK/0.20, native NONE ceilings still bind, and all remaining review credit and aggregates remain null. Existing five admitted full-stack native-NONE outcomes retain their earlier governed source receipts.

The API V1.1 guard, design/implementation distinction, REST/gRPC handling, parser, taxonomy and registry are unchanged. Both Job 566 parents receive independent original-source checks. The embedded ESP32 topic-recovery DIRECT result remains REVIEW_REQUIRED, as do incomplete native-NONE ownership/modifier cases.

## Versioning, cache and persistence

| Identity | Current value / effect |
|---|---|
| Published OFF scorer | `stable-evidence-v1.17-phase6d21`, unchanged |
| Gated development scorer | `stable-evidence-v1.19-phase6d23`, replaces v1.18 only for explicit gated requests |
| New disposition identity | `coordinated_review_disposition_policy_version = coordinated-finite-packet-exclusion-v1` |
| Decomposition | `jd-atomic-requirement-decomposition-v1.2`, unchanged |
| Ownership completeness | `coordinated-action-evidence-completeness-v1`, unchanged |
| P3 partial policy | `coordinated-partial-action-credit-v1`, unchanged |
| Ownership language | `coordinated-ownership-language-v2d1`, unchanged |
| Recovery / reselection | `capability-single-row-none-recovery-v1.2` / `capability-single-row-reselection-v1.1`, unchanged |
| Taxonomy / registry | `phase6d-capability-taxonomy-v1.6` / `technology-registry-v1.3`, unchanged |

The full gated identity map participates in the input fingerprint. Tests confirm changing the disposition identity invalidates the fingerprint. Production `current_match_versions()` still reports OFF v1.17; v1.18/v1.19 gated cache identities cannot be mistaken for published current analyses. Historical snapshot formats and fixtures are unchanged.

The persistence guard retains explicit rejection of v1.18 and adds v1.19, including a test with the preview flag removed. Both REVIEW_REQUIRED and entirely numeric gated payloads remain development previews. Save tests reject R1-NONE payloads before schema/database initialization. No live database, real candidate, network, LLM, embedding or Tavily call was used.

Dashboard revision hashing includes the new production source automatically and explicitly includes the new independent R1 fixture. Existing revision-based session/cache invalidation and bounded 80-entry acceptance cache remain in place. Filtering and selection read stored batch receipts; they do not rebuild analyses. The historical Stage 2E reference remains visible and unchanged; current Stage 2G comparisons use a separate independently authored expectation delta. Expected historical differences are displayed separately from actual new-expectation failures. Selected details show R1 reasons and a collapsed exact-original-source receipt panel.

## Changed-file inventory

| File | Change |
|---|---|
| `analysis_stability/coordinated_r1.py` | New finite-activity recognizer and full-original-packet exclusion proof. |
| `analysis_stability/coordinated_integration.py` | Terminal gated R1 disposition, receipts and new gated identities. |
| `analysis_stability/coordinated_runtime.py` | Reject the new gated scorer identity before persistence. |
| `scripts/coordinated_batch_dashboard.py` | Separate current expectations, R1 reason column and fixture revision invalidation. |
| `coordinated_actions_preview.py` | R1 receipt details and distinct historical/current acceptance status. |
| `tests/fixtures/coordinated_r1_contract_v1.json` | New independent positive/negative language controls, exact 14-case delta and counts. |
| `tests/test_coordinated_r1_disposition.py` | Contract, real 60-case acceptance, complete-packet, source, ceiling, version/cache and persistence checks. |
| `tests/test_coordinated_batch_dashboard.py` | Current independent counts, historical differences, R1 details and unchanged no-recompute assertions; identify main grid separately from the historical delta grid. |
| `tests/test_coordinated_action_implementation.py` | Authorized review-to-NONE expectations for excluded packets, retaining native-positive recovery quarantine and zero-credit assertions. |
| `bulk_unresolved_stage2g_implementation.md` | This implementation, acceptance and review report. |

The pre-existing Stage 2F report, audit script, audit tests and dashboard report are preserved. Earlier ignored diagnostics remain local and untouched. New runtime exports stay under already ignored `/reports/*`; no ignore change is needed.

## Validation and remaining limits

The first combined focused run checked 54 tests. Scoring/contract/historical checks passed; three AppTest assertions selected the 14-row historical-delta dataframe instead of the main 60-row grid. This was an outdated test locator exposed by the newly populated historical table. The locator was corrected to distinguish the grids. No expected scoring result or assertion was weakened. The affected dashboard/R1 modules were rerun.

Only focused offline checks were used through `scripts/run_coordinated_preview_checks.py`, using Python 3.13.12 and Streamlit 1.66.0. The launcher disables dotenv/model-cost retrieval, blocks network and non-disposable SQLite access, and fixes imports to this checkout. No full or quick project-wide runner was executed.

Commands: the guarded runner with `--scratch-root reports/stage2g_runtime`, first for `tests.test_coordinated_r1_disposition.R1ContractTests` before scoring integration; then for the R1 module, dashboard module, API completeness module, preserved Stage 2F audit tests, and eight selected implementation methods (historical OFF equivalence, P3 late-stage ceilings, modifier safeguards, deployment denial/separate records, source/cap invariants, API/Boolean guards, raw grounding and topic/consumption ceilings). The affected rerun uses `tests.test_coordinated_batch_dashboard tests.test_coordinated_r1_disposition --batch-dashboard-preview reports/stage2g_runtime/acceptance_batch.json`.

The contract intentionally refuses richer packets and unsupported paraphrases. It does not establish completeness of a person's lifetime experience, and is not authorization for an on-by-default production feature. Expanding the grammar or packet schema needs new independently reviewed near-miss controls and a policy/fingerprint identity change. The other 26 reviews are not addressed by R1. No historical or live candidate score change is claimed.


## Final acceptance results

**PASS for the bounded default-OFF implementation; production activation remains unauthorized.** All 54 distinct focused checks are green across the focused runs: the affected 27-test dashboard/R1 rerun passed after correcting the table locator, and the other 27 unchanged API, historical, source, P3 and Stage 2F checks passed in the initial run. The nine contract tests had also passed before any scoring integration.

| Measure | Preserved Stage 2E / Stage 2F baseline | Actual Stage 2G |
|---|---:|---:|
| Scenarios | 60 | 60 |
| DIRECT | 12 | 12 |
| WEAK | 3 | 3 |
| NONE | 5 | 19 |
| REVIEW_REQUIRED selected parents | 40 | 26 |
| Canonical review rows across full JDs | 64 | 44 |
| Whole-JD scores withheld | 45 | 31 |
| Scenario exceptions | 0 | 0 |
| Historical Stage 2E differences | 0 | 14, all independently expected |
| Current Stage 2G expectation mismatches | Not applicable | 0 |

Exactly the 14 Stage 2F proposed case keys match the actual R1 case keys. The independently retained Stage 2F frozen batch input hash was verified before comparison. All **60 OFF payloads** are identical to that frozen export. For all **46 other selected cases**, labels, numeric credit, selected evidence, requirement IDs, provenance, allocation and whole-JD score/coverage/evidence-strength metrics are unchanged. This includes all existing positive credit and the six incomplete native-NONE cases that must remain under review. All 1716 unrelated canonical-row occurrences across these 60 analyses are also identical to the frozen batch, and every canonical ID, parent allocation and provenance is preserved. These are synthetic comparisons only.

There are 20 R1 canonical rows: 14 selected-parent rows and six companion rows. In the six Job 566 consumption/integration/topic scenarios, both parents independently become NONE and the whole JD becomes available. The five positive cloud-parent scenarios still have an unresolved backend parent and remain withheld. No scalar zero substitutes for an unresolved score.

Existing independent action/scope/P3 receipts: **32/32 agree across 18 scenarios**. That coverage is reported separately from the 60 current expectation comparisons and the new R1 language/packet tests; uncovered old fixtures are not labeled independently PASS. Near-miss tests cover extra authored clauses, missing modifiers, denials, mixed duties, unknown language, uncertain actors, future/learning claims, unindexed fields, duplicate/second sources, missing index entries and forged source identities. Genuine authored Java REST endpoints and design/protocol distinctions retain the approved API results.

### The 60 original scenarios

The baseline column below is the preserved Stage 2E **gated complete-parent** output, not the dashboard's separate legacy OFF two-child Before table. All corrected parents keep allocation 1.0. Credit `unavailable` and whole-JD `unavailable` mean null; they are never numeric zero. Source IDs are original bullet records in order; they are not synthesized ownership unions. Full per-source text, scope, actions, API guards, recovery/reselection and R1 spans are in the ignored full batch and available in the selected-case dashboard details.

| Job / family | Scenario | Native | Stage 2E label | Stage 2G label | Disposition | Parent credit | Whole-JD alignment | Original bullet IDs |
|---|---|---|---|---|---|---:|---|---|

| 16 / pipeline | Maintenance only | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_9b94dab99069 |
| 16 / pipeline | Design and development | DIRECT | WEAK | WEAK | ELIGIBLE_PARTIAL | 0.2 | 11% | ev_1c907fe3b6dc |
| 16 / pipeline | All mandatory actions | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 16% | ev_2e1fc06c7ad4 |
| 16 / pipeline | Passive first-person ownership | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 15% | ev_9af304c66e98 |
| 16 / pipeline | Relative-clause ownership | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 13% | ev_6c07e8119fc1 |
| 16 / pipeline | Shortened object | NONE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_c9771c718864 |
| 16 / pipeline | API consumption | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_c79dee18eaa2 |
| 16 / pipeline | PostgREST integration | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_5b3eb55dd534 |
| 16 / pipeline | Complete alternative second bullet | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 15% | ev_f8f54824fa5a, ev_9af304c66e98 |
| 16 / pipeline | Zero-overlap topic recovery | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_1ad64fbd77d3 |
| 16 / pipeline | Separate partial records | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_57771dd968e7, ev_95b9d94c88e8, ev_9b94dab99069 |
| 16 / pipeline | Denied lifecycle | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_6224ed7b47d2 |
| 359 / embedded | Maintenance only | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_bb4d622bf990 |
| 359 / embedded | Design and development | DIRECT | WEAK | WEAK | ELIGIBLE_PARTIAL | 0.2 | 21% | ev_404485602c67 |
| 359 / embedded | All mandatory actions | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 23% | ev_2e8966182caf |
| 359 / embedded | Passive first-person ownership | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 23% | ev_e33504e2ccdd |
| 359 / embedded | Relative-clause ownership | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 23% | ev_797fff3dad48 |
| 359 / embedded | Shortened object | TRANSFERABLE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_255b7ad49b26 |
| 359 / embedded | API consumption | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_c79dee18eaa2 |
| 359 / embedded | PostgREST integration | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_5b3eb55dd534 |
| 359 / embedded | Complete alternative second bullet | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 23% | ev_1a035784426d, ev_e33504e2ccdd |
| 359 / embedded | Zero-overlap topic recovery | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_1ad64fbd77d3 |
| 359 / embedded | Separate partial records | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_a2549674b9f3, ev_c7dbb684b2bd, ev_bb4d622bf990 |
| 359 / embedded | Denied lifecycle | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_73382f14ff40 |
| 479 / fullstack | Maintenance only | NONE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_7b011e9bb3ee |
| 479 / fullstack | Design and development | NONE | NONE | NONE | ELIGIBLE_PARTIAL | 0.0 | 10% | ev_507e7c8a99cb |
| 479 / fullstack | All mandatory actions | NONE | NONE | NONE | COMPLETE | 0.0 | 10% | ev_bedf363ebef3 |
| 479 / fullstack | Passive first-person ownership | NONE | NONE | NONE | COMPLETE | 0.0 | 10% | ev_a43a155c6c9c |
| 479 / fullstack | Relative-clause ownership | NONE | NONE | NONE | COMPLETE | 0.0 | 10% | ev_e826f64912a5 |
| 479 / fullstack | Shortened object | NONE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_ac265235de2e |
| 479 / fullstack | API consumption | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 7% | ev_c79dee18eaa2 |
| 479 / fullstack | PostgREST integration | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 7% | ev_5b3eb55dd534 |
| 479 / fullstack | Complete alternative second bullet | NONE | NONE | NONE | COMPLETE | 0.0 | 10% | ev_ac5df2053a85, ev_a43a155c6c9c |
| 479 / fullstack | Zero-overlap topic recovery | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_1ad64fbd77d3 |
| 479 / fullstack | Separate partial records | NONE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_db2e79a94498, ev_6b8705ba2f39, ev_7b011e9bb3ee |
| 479 / fullstack | Denied lifecycle | NONE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_1036861c27e3 |
| 566 / backend | Maintenance only | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_8f9ba3952324 |
| 566 / backend | Design and development | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_ad1ef197f62e |
| 566 / backend | All mandatory actions | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_17621154d7ef |
| 566 / backend | Passive first-person ownership | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_bc5b2afd8555 |
| 566 / backend | Relative-clause ownership | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_87030b0849bc |
| 566 / backend | Shortened object | TRANSFERABLE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_39c0e6685bbd |
| 566 / backend | API consumption | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_c79dee18eaa2 |
| 566 / backend | PostgREST integration | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_5b3eb55dd534 |
| 566 / backend | Complete alternative second bullet | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_73326e293525, ev_bc5b2afd8555 |
| 566 / backend | Zero-overlap topic recovery | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_1ad64fbd77d3 |
| 566 / backend | Separate partial records | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_133076d5e400, ev_a09445c804f7, ev_8f9ba3952324 |
| 566 / backend | Denied lifecycle | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_ab8bc178cf62 |
| 566 / cloud | Maintenance only | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_5e17c3a5b484 |
| 566 / cloud | Design and development | DIRECT | WEAK | WEAK | ELIGIBLE_PARTIAL | 0.2 | unavailable | ev_9466eb10e548 |
| 566 / cloud | All mandatory actions | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | unavailable | ev_11802e4864b8 |
| 566 / cloud | Passive first-person ownership | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | unavailable | ev_2a5d14c0e019 |
| 566 / cloud | Relative-clause ownership | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | unavailable | ev_187f2d6fbd09 |
| 566 / cloud | Shortened object | NONE | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_ad91213960c6 |
| 566 / cloud | API consumption | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_c79dee18eaa2 |
| 566 / cloud | PostgREST integration | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_5b3eb55dd534 |
| 566 / cloud | Complete alternative second bullet | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | unavailable | ev_448a4d19bdce, ev_2a5d14c0e019 |
| 566 / cloud | Zero-overlap topic recovery | NONE | REVIEW_REQUIRED | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% | ev_1ad64fbd77d3 |
| 566 / cloud | Separate partial records | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_e8e911f1241c, ev_1e461f3a75e1, ev_841d0d17cdab |
| 566 / cloud | Denied lifecycle | DIRECT | REVIEW_REQUIRED | REVIEW_REQUIRED | REVIEW_REQUIRED | unavailable | unavailable | ev_36023d6f2498 |

## Final protection and whitespace verification

Entry protection ledger: **942 existing paths**, consisting of 938 tracked paths plus the four pre-existing untracked Stage 2F/dashboard artifacts. Exactly the six tracked files listed in the inventory changed; the other **936 entry paths are byte-identical**. Thus all four pre-existing untracked artifacts are preserved and 932 tracked paths are unchanged. There are four new Stage 2G files, including this report. No unexpected file change was found.

The Stage 2F ignored frozen batch still matches the input SHA-256 recorded in its preserved diagnostic. All new writes were directed to the Stage 2G source/test/report files and new `reports/stage2g_runtime/` scratch/exports. No earlier ignored diagnostic was overwritten or deleted. No SQLite/database file was created even in the Stage 2G scratch tree.

| Unchanged protected path | SHA-256 |
|---|---|

| `analysis_stability/stable_evidence_scoring.py` | be404e28437720a861686b0c9b34b6b2a7db719ed82ab1a67178dafe2be6f4ba |
| `analysis_stability/coordinated_policy.py` | 41e1f991b170e646a34d4d7d079ad67cf444064bb08139faf77f2d503ec4c786 |
| `tailoring/capability_taxonomy.py` | 373c3cb8d7aedd8122d258c2fc395d49dbb5ca73f93ff02a87b3a254ba7db96f |
| `tailoring/phase6d6_structured_matching.py` | 90658676df9bb04e6215345f468c6837b7157c5ddf7decb4abda4aabf100e744 |
| `taxonomy/capability_taxonomy_v1.json` | 1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513 |
| `taxonomy/technology_registry_v1.json` | 56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675 |
| `tests/fixtures/coordinated_stage2e_batch_reference_v1.json` | 475806fdaa1f05533edd1fe46539afc58899a22da9fcbd03ecc9b37e57017bac |
| `tests/fixtures/coordinated_action_ownership_oracle_v1.json` | 00d23501233547b71c0203039740aa70178251ec1f5f7ce3faa4f54d0ea0fdd1 |
| `tests/fixtures/coordinated_partial_action_policy_v1.json` | 4f94b900ed177dfbb4288a4e245f9f87f551116a46c3af6bb84cda37634b6112 |
| `tests/fixtures/per_jd_scoring_audit.json` | a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f |

`git diff --check` and `git diff --cached --check` pass; the new files also have no no-index whitespace errors. The index is empty. Branch and HEAD are unchanged. No staging, commits, pushes, merges, production activation or live persistence occurred.

Local-only outputs (already ignored by `/reports/*`): `reports/stage2g_runtime/acceptance_batch.json` holds the full 60-case analysis; `acceptance_summary.json` holds compact outcomes, source receipts and frozen-baseline comparisons; `entry_hashes.json` and `protected_verification.json` hold protection ledgers. Guarded scratch folders hold only test runtime artifacts. These exports are not launch or test dependencies and must remain excluded from Git history.

**Stop for review.** R1 is ready for review as a bounded gated change. The remaining 26 reviews, richer-profile support, grammar expansion and any production activation require separately scoped decisions.
