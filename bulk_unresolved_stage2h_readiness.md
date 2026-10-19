# Stage 2H — realistic multi-record evidence readiness

**Audit complete: PASS. General realistic-profile production readiness: BLOCKED.** The current gated scorer accepts independently complete originals in rich profiles, but does not reconcile conflicting originals. It can award DIRECT and return a whole-JD numeric preview despite a same-project explicit denial. Production behavior was not modified or activated.

Repository: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`. Branch: `feat/coordinated-realistic-evidence-v1`. Entry and final HEAD: `fa794cdf341efe2bd7a5b81c7b51fdcefec60be2`. Existing untracked `coordinated_batch_dashboard_review.md` preserved.

## Scope and independent inventory

The review covered Stage 2E–2G integration, ownership detection, P3 eligibility, R1 packet validation, runtime/persistence protection, evidence-index construction, acceptance generation and baseline expectations. Relevant source functions are `build_coordinated_analysis`, `_evaluate_row`, `detect_ownership`, `coordinated_policy.detect/eligibility`, `exclusion_packet`, `build_resume_evidence_index` and `assert_analysis_publishable`. Stage 2E/G acceptance tests and reports define the unchanged 60-case baseline (12 DIRECT, 3 WEAK, 19 NONE, 26 REVIEW_REQUIRED, 31 withheld, zero exceptions). That baseline was reviewed, not regenerated as a new oracle.

The new fixture contains **38 explicitly synthetic profiles**, using the five frozen parent requirements: Job 16 pipelines; Job 359 embedded modules; Job 479 full-stack applications; and Job 566 backend/API and cloud applications. Projects, companies, job history, skills and dates are fictional. Original JD objects were copied independently into the fixture and checked for exact source grounding; they were not generated from detector results. Full profile text is in `tests/fixtures/coordinated_realistic_profiles_v1.json`.

For each case, independent statements specify both (a) a pre-run v1.19 behavior hypothesis and (b) the semantic/safety judgment about the supplied evidence. These are distinct from approved scoring policy. Initial 35 cases were executed, then three separately specified source/conflict boundary controls (E23, E24, C03) were added before their first execution. All original 35 profiles and expected labels were preserved. The final 38-case execution used the actual explicitly gated `build_stable_analysis` on full frozen JD text, with offline retrieval, original profile and raw-text arguments. Expected outcomes were never scorer inputs.

## Actual outcomes and discrepancies

| Measure | Actual |
|---|---:|
| Synthetic profiles | 38 |
| Selected-parent DIRECT | 16 |
| Selected-parent WEAK | 2 |
| Selected-parent NONE | 2 |
| Selected-parent REVIEW_REQUIRED | 18 |
| Whole-JD scores withheld | 22 |
| Whole-JD scores available in gated preview | 16 |
| Exceptions | 0 |
| Pre-run current-label hypotheses matching | 37/38 |

All 38 payloads remain development previews and fail the publishability guard. Passing diagnostic integrity tests does not certify that every numeric result is semantically safe. Numeric whole-JD values below are artificial full-JD fixture previews, not historical/live candidate scores or saved Job Match changes. The sample deliberately overrepresents difficult cases; these counts are not a population estimate.

**One behavior-hypothesis discrepancy: F02.** Its fixture expected the native full-stack NONE ceiling seen in F01, but adding explicit frontend/backend implementation in the same original yields native DIRECT and effective DIRECT. All three exact-scope actions and concrete implementation details are in that one original. This agrees with the independent positive-evidence judgment and does not override a native NONE ceiling: the native label itself is DIRECT. It is a mistaken conservative pre-run hypothesis, not evidence of a new scoring defect. The original NONE expectation remains unchanged and the discrepancy stays visible.

**Six selected-parent semantic discrepancies:** E04/E05/B05 are DIRECT despite unresolved same-project denial; P01/P02 are REVIEW_REQUIRED despite independently explicit complete ownership expressed outside the finite grammar; F01 has complete literal ownership but remains numeric NONE under the native capability ceiling. F01 is a required current-policy ceiling, not permission to upgrade it.

**One whole-JD safety discrepancy:** C03 has an independently valid DIRECT cloud parent, plus a backend DIRECT/endpoint-denial conflict. The raw fixture semantic annotation `REVIEW_REQUIRED` describes whole-JD readiness, not a demand to remove valid cloud credit. Its current cloud DIRECT is valid in isolation; the backend parent and the available whole-JD score are the issue. The machine's seven raw semantic-discrepancy IDs therefore comprise six parent-label comparisons and this separate whole-JD readiness judgment. No cloud/backend ownership is combined.

## Profile inventory and actual results

`Unavailable` means null, never zero. Every corrected parent retains allocation 1.0. `Expected` is the independently declared current-behavior hypothesis, not a revised oracle. Full original profiles, source IDs, proofs, native labels, stage receipts, companion parents and per-record review cards are in the ignored actual diagnostic export. The explanations following the table distinguish valid current-policy withholding from potential safety failures.

| ID | Family | Independent evidence class / profile theme | Expected | Actual | Native | Disposition | Parent credit | Whole-JD alignment |
|---|---|---|---|---|---|---|---:|---|

| E01 | embedded | MATCHING — Complete original amid multiple projects, bullets, experience and skills | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E02 | embedded | RELEVANT_INCOMPLETE — P3 original amid unrelated records | WEAK | WEAK | DIRECT | ELIGIBLE_PARTIAL | 0.2 | 26% |
| E03 | embedded | RELEVANT_INCOMPLETE — Same-project actions in three separate bullets | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| E04 | embedded | CONTRADICTORY — Same project: complete claim then explicit denial | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E05 | embedded | CONTRADICTORY — Same project: denial then complete claim | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E06 | embedded | CONTRADICTORY — Same original contains positive and denial | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| E07 | embedded | MISSING_MODIFIERS — Required technical scope only in project title | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| E08 | embedded | MISSING_MODIFIERS — Required technical scope only in skills | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| E09 | embedded | MATCHING — Complete original in experience | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E10 | embedded | INCOMPLETE_PACKET — Complete statement in unindexed summary field | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| E11 | embedded | MATCHING — Same complete text in structured and raw input | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E12 | embedded | UNSUPPORTED_AMBIGUOUS — Complete evidence available only in raw text | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| E13 | embedded | INCOMPLETE_PACKET — Empty supplied profile | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| E14 | embedded | MATCHING — Missing sections but one complete original | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 27% |
| E15 | embedded | INCOMPLETE_PACKET — Missing sections and consumption only | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| E16 | embedded | NONQUALIFYING — Two independently excluded bullets in a neutral project | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| E17 | embedded | UNSUPPORTED_AMBIGUOUS — Ambiguous team ownership with realistic metadata | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| E18 | embedded | MATCHING — Complete individual original plus unrelated ambiguous team record | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E19 | embedded | MATCHING — Identical complete claims under two projects | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E20 | embedded | RELEVANT_INCOMPLETE — Related technology and partial implementation without full duties | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| E21 | embedded | NONQUALIFYING — Original narrow R1 control | NONE | NONE | NONE | R1_EXCLUDED_NATIVE_NONE | 0.0 | 0% |
| E22 | embedded | UNSUPPORTED_AMBIGUOUS — Unknown expression alongside otherwise excluded activity | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| P01 | pipeline | MATCHING — Natural explicit role preface on a complete original | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| P02 | pipeline | MATCHING — Complete original with harmless purpose suffix | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| P03 | pipeline | NONQUALIFYING — Multiple neutral projects with exclusively known nonqualifying originals | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| P04 | pipeline | NONQUALIFYING — Generic data skill names without responsibility | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| F01 | fullstack | MATCHING — Complete family claim under native full-stack NONE ceiling | NONE | NONE | NONE | COMPLETE | 0.0 | 12% |
| F02 | fullstack | MATCHING — Complete claim plus concrete frontend/backend implementation in same original | NONE | DIRECT | DIRECT | COMPLETE | 1.0 | 15% |
| B01 | backend | MATCHING — API consumption plus genuine complete authorship original | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | Unavailable |
| B02 | backend | RELEVANT_INCOMPLETE — Family ownership and endpoint authorship in separate originals | REVIEW_REQUIRED | REVIEW_REQUIRED | DIRECT | REVIEW_REQUIRED | Unavailable | Unavailable |
| B03 | backend | RELEVANT_INCOMPLETE — Authored Java endpoints without complete backend lifecycle | REVIEW_REQUIRED | REVIEW_REQUIRED | NONE | REVIEW_REQUIRED | Unavailable | Unavailable |
| B04 | backend | RELEVANT_INCOMPLETE — P3 family pair and endpoint proof in same original | WEAK | WEAK | DIRECT | ELIGIBLE_PARTIAL | 0.2 | Unavailable |
| B05 | backend | CONTRADICTORY — Complete API authorship then explicit endpoint denial | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | Unavailable |
| C01 | cloud | MATCHING — Both Job 566 parents independently complete in separate originals | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 24% |
| C02 | cloud | MATCHING — Cloud parent complete while backend parent remains unresolved | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | Unavailable |
| E23 | embedded | MATCHING — Complete project plus denial scoped to a different project | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| E24 | embedded | MATCHING — Duplicate complete claims with denial only in first project | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 29% |
| C03 | cloud | CONTRADICTORY — Both parents complete plus same-project API endpoint denial | DIRECT | DIRECT | DIRECT | COMPLETE | 1.0 | 24% |

### Independent evidence categories

| Category | Profiles |
|---|---:|
| CONTRADICTORY | 5 |
| INCOMPLETE_PACKET | 3 |
| MATCHING | 15 |
| MISSING_MODIFIERS | 2 |
| NONQUALIFYING | 4 |
| RELEVANT_INCOMPLETE | 6 |
| UNSUPPORTED_AMBIGUOUS | 3 |

These are independent descriptions of the supplied text, not detector classifications. Relevant incomplete and missing-modifier evidence cannot be converted to NONE merely because the full obligation is unproven. Unsupported language is not proven absence. An incomplete packet may still contain valid positive evidence, but cannot support an exhaustive negative conclusion.

## Findings from the actual path

### 1. Rich structure does not inherently lose an admitted positive original

E01 has multiple projects, multiple bullets, experience and skills, yet selects the complete original at `resume_profile.projects[0].bullets[1]` and returns DIRECT. E09 selects a complete experience bullet despite company/date metadata. E02 and B04 preserve P3 WEAK/0.20: the design+creation pair and full technical scope share one original, with API authorship proof in that same original for B04. E18 and E23 demonstrate that an unrelated ambiguous record or denial in a separately scoped project need not erase valid ownership elsewhere.

B01 has client API consumption followed by a genuine authored Java REST-endpoint original. DIRECT selects the authorship record, not the consumption record. B02 separates family ownership and endpoint authorship into different bullets; it correctly remains REVIEW_REQUIRED under the no-union rule. B03's actual endpoint authorship does not establish the full scalable backend design/build/maintain obligation. Neither record structure nor API vocabulary licenses fabricated ownership.

E03 splits design, development and maintenance across three bullets in one project; no complete original or P3 pair exists. It stays REVIEW_REQUIRED. E07/E08 place technical scope only in a title/skills while the responsibility bullet is shortened. Those metadata records are not silently attached to the action claims; review is correct under the current contract.

### 2. Cross-record contradiction is not governed

E04 and E05 reverse two bullets within the same project: one says “I designed, developed, maintained embedded software modules supporting waveform processing systems.”; the other says “Never maintained embedded software modules supporting waveform processing systems.” Both orders return DIRECT/1.0 with a 29% whole-JD preview. The ownership proof explicitly records `maintain` as denied in the negative original, but this disqualifies only that original. A separate COMPLETE pool still selects the positive original. `_evaluate_row` preserves it through linked, structured, validated, reselected, capped, recovered and final-invariant stages. No later packet-level contradiction check runs.

B05 has complete backend/API family ownership plus explicit REST interface/Java endpoint authorship in one bullet, then “Never implemented REST API endpoints.” in another bullet under the same project. The positive original passes API V1.1 on its own and receives DIRECT. The endpoint denial does not prove the family object, so the coordinated proof's denied-action set is empty; a future conflict receipt must inspect the API component/protocol, not only the family action list. Whole-JD withholding in B05 currently comes from the unrelated unresolved cloud parent, not from this contradiction.

C03 adds the complete cloud original as well. Both Job 566 parents are scored DIRECT and whole-JD alignment is **24%**, despite the same-project backend endpoint denial. This demonstrates that “all parents numeric” does not itself establish realistic packet consistency. The existing development/persistence gate still prevents publication, but the preview needs an explicit safety warning; these results must not be presented as human/policy-cleared evidence.

E06, by contrast, puts positive duties and lifecycle denial in the same original and is withheld. The gap is cross-record reconciliation, not removal of the within-record negation safeguard. Do not infer that every negative claim anywhere invalidates every positive claim: E23 is an explicit different-project counterexample.

### 3. Deduplication preserves text, but can lose source occurrences

E11's raw duplicate is absent from the index while its structured project original remains correctly selected. E19's identical complete claim under a second project is also absent as a separate index source. Positive text is not lost, and current credit remains DIRECT; later source occurrence attribution is lost.

E24 makes this important: project 0 contains a complete claim and a denial; project 1 independently repeats the complete claim without denial. Current selection still uses project 0, while the project-1 positive occurrence is deduplicated away. A DIRECT label may be supported by the independently supplied second project, but the current indexed proof does not establish that unconflicted fallback. A future global veto could also incorrectly suppress that valid source. Preserve original occurrence accounting before attempting contextual conflict handling or universal negative proofs; do not change identity rules globally without a versioned design.

### 4. Evidence can be present but unavailable to the approved source/grammar path

E10 places a complete positive claim in `summary`, an unindexed top-level field. The profile is not empty: supplied positive text is outside the supported projection. Current R1 rejects the unknown field and stays REVIEW_REQUIRED, which avoids an incorrect negative conclusion. E12 contains complete ownership only in raw text; current ownership admission deliberately requires an attributable project/experience original. Raw text is observed but is not admitted as such an original. Do not describe this as the user providing no evidence or forged evidence.

P01's “As lead engineer, I designed, developed and maintained …” is independently explicit individual ownership, but `_subject` marks the preface `AMBIGUOUS_SUBJECT`. P02 retains the full literal required pipeline object and adds “for an internal prototype”; the detector sees all three actions but exact technical-object equality fails. These are bounded language/representation false-negative candidates. Broad synonym matching or modifier inference is not authorized as a remedy. E07/E08 actually omit responsibility-bound scope, and must remain separate from P02's extra harmless context.

E14 omits core profile sections but includes a complete attributable original; DIRECT can be justified by that positive original. In contrast, E13's empty packet and E15's missing sections with consumption only remain review-required. Positive evidence sufficiency and exhaustive negative packet completeness are different obligations.

### 5. Native recovery and reselection

No tested unresolved split, shortened-scope, raw-only, team-ambiguous or related-technology profile regains positive credit through late recovery. E20 has native DIRECT from relevant embedded activity but is quarantined because no admitted full-scope ownership exists. All tested native-NONE ceilings and P3 late-stage WEAK ceilings hold.

The contradiction positives are already DIRECT at linking and stay DIRECT at every subsequent captured stage. They are not caused by a NONE-to-DIRECT recovery jump. The failure mode is that a locally valid positive original survives without contextual reconciliation. F01 is capped to NONE at the capability stage and stays NONE through recovery; F02 is DIRECT before and after that stage because the same original now supplies concrete frontend/backend implementation.

### 6. Whole-JD availability

Eighteen selected parents require review. Four additional profiles have numeric selected parents but another unresolved Job 566 parent: B01, B04, B05 and C02. Thus 22 whole-JD results are withheld. Each unresolved parent independently withholds all governed aggregate fields; no score is rescaled over just the resolved rows.

C01 has independently complete cloud and backend/API originals, so both parents can be governed without unioning records inside either parent. C02 has a complete cloud original but consumption cannot prove backend/API development, so whole-JD alignment remains unavailable. C03 shows why resolving all parents is insufficient when an unresolved cross-record contradiction has not itself generated a review disposition.

## R1 generalization feasibility — proposal only

Current R1 deliberately accepts a complete single-project/single-bullet schema. E21 remains the valid narrow negative control: only client consumption is supplied and native NONE is retained. F01's other NONE is a native capability ceiling over a positive complete family claim, not an absence-of-evidence finding and not R1.

**Two bounded shape-only opportunities:** E16 has two known excluded activities in one neutral project; P03 has those same activities under two neutral projects. All original activity records are affirmatively understood as client consumption or generated integration, all other declared sections are empty, and native final labels are NONE. R1 blocks them at the bullet/project cardinality checks. It is overly restrictive for these deliberately closed packets, but that does not establish a safe general real-résumé classifier.

A feasible future extension would use universal exclusion over a complete **original occurrence** ledger: every substantive record has an independently approved exclusion receipt for this requirement; all metadata roles are explicitly accounted for; positive, relevant-incomplete, shortened-scope, denied, ambiguous, unknown, unsupported or unexamined records veto exclusion; native NONE remains mandatory; and at least one affirmative activity exclusion is required. Universal negative proof is not unioning positive ownership actions. Skills, education, experience headers, omitted fields, raw text and unknown schema must have their own coverage contracts rather than being discarded as “noise”.

Only as a manually reviewed hypothetical, resolving E16/P03 would change this sample to 16 DIRECT / 2 WEAK / 4 NONE / 16 REVIEW_REQUIRED and 20 withheld whole-JD scores. No proposed labels feed back into v1.19. This leaves the contradiction hazards entirely unchanged. E22 must still fail closed despite containing one known excluded statement; its unknown second statement is not exclusion proof. P04's generic technology use also does not match the approved finite exclusion grammar. Missing actions alone never establish NONE.

**Recommendation: defer R1 generalization until source occurrence coverage and scoped conflict treatment are independently specified.** No policy expansion is implemented by this audit.

## Safe user-facing REVIEW_REQUIRED treatment

The diagnostic-only `review_card` view model demonstrates a read-only explanation without changing any scoring output. It displays the complete parent, current disposition, exact source IDs/text, per-record supported/unproven/denied actions, technical-scope status and the current R1 blocker. It never pools actions across rows or turns an unavailable contribution into zero. “Unproven in this original” is preferable to “candidate lacks this skill”. Raw-only and unindexed-field evidence need source-coverage explanations, not claims of absence.

For E03, a safe presentation is:

> **Review required — contribution unavailable.** Three original statements were found. No single original establishes the complete obligation or the approved design+creation pair. Review each statement's actions and scope below. This does not mean the candidate has no experience. The whole-JD alignment is unavailable while this parent remains unresolved.

Keep each parent's 1.0 allocation visible and show counts of unresolved parents, not invented partial percentages. Known parent results may be shown individually, but do not calculate a “score ignoring unresolved requirements”, an optimistic/pessimistic replacement score, or a normalized score over known rows. A legitimate governed zero such as E21 must remain distinguishable from an unavailable review value.

Current receipt reasons are insufficient on their own: `native_final_ceiling_is_not_NONE` explains why R1 cannot run, not whether the actual problem is missing scope, ambiguity, source projection or denial. Per-record facts and source-coverage receipts are needed. A future conflict warning should be separate from the actual current label: C03 currently returns DIRECT/numeric, so the UI must not silently relabel it or imply a policy change. Explain that the gated numeric preview has conflicting source statements and is not publication-ready. The diagnostic view model is not itself a general conflict detector or a production UI modification.

## Smallest justified Stage 2I scope

1. Build a read-only, development-only source occurrence/coverage and conflict explanation layer. Preserve original project/experience occurrence IDs before deduplication; distinguish unknown/unindexed fields, duplicate origins and unsupported ownership sources. Display per-record proofs and unreconciled exact same-project/same-object or same-protocol contradictions, including conflicts in an independently scored companion parent. Keep actual v1.19 outputs visible and unchanged in this first bounded usability step.
2. Separately seek approval for a gated conflict-quarantine policy before broader numeric use. The narrow candidate is an explicit same-project/exact-object lifecycle denial, or same-project matching-protocol API implementation denial, conflicting with the selected positive source. Such a conflict should require review, not numeric NONE or ordinary P3 omission. Unrelated-project denials and protocol mismatches must not veto valid ownership elsewhere. E24 demands occurrence-aware fallback or explicit source-coverage review; a global “any denial anywhere” rule is unsafe.
3. Defer general R1 relaxation and broader natural-language matching. They address different problems and should not be bundled to increase numeric coverage.

A presentation-only diagnostic schema needs its own schema/revision identity, not a scorer bump. Any later change to numeric disposition/aggregate withholding or admitted source selection requires a new gated scorer and relevant policy/source identity included in fingerprints and cache currentness; do not reuse v1.19 for changed behavior. Published OFF v1.17, default-OFF activation and persistence rejection must remain intact. No new identities were allocated here.

## Required independent regression tests before any later scoring change

- Same-original versus same-project cross-original denials; positive/negative order reversal; global/unqualified versus temporally scoped claims; explicit same-object binding; incomplete conflict context requires review.
- Matching REST endpoint denial versus unrelated gRPC denial, API client use, UI design, and true authored Java endpoints. Preserve API V1.1 and design/implementation separation.
- E23 valid ownership under a different project; E24 duplicate positive source with only one conflicting occurrence; source-order permutations and original-source receipt preservation. Never union bullets or fabricate an unindexed fallback.
- Complete single-record ownership amid multiple projects/experience/skills; P3 pair amid unrelated records; three separate atomic duties remaining review-required; native NONE and late-stage P3 ceilings.
- Closed all-excluded multi-record packets versus an added positive, denied, ambiguous, unknown, missing-modifier or unindexed record; missing sections and empty packets; cardinality-independent full occurrence coverage, including deduplicated/raw aliases.
- Role-preface and harmless-suffix language positives, with third-party, team, modal, negated and true scope-omission near misses. Any recognition expansion requires separate approval.
- Every unresolved parent and every unresolved conflict withholding all aggregate fields; numeric selected cloud plus pending backend; both parents complete but conflicted companion; no zero/reweighting substitute for review.
- Read-only reason-card display, correct original text/IDs, no analysis recomputation on selection/filtering, no model/network/DB/persistence calls, default-OFF equivalence on the 30 raw JD fixtures, cache invalidation for any new policy identity and persistence rejection for all gated numeric payloads.

## Validation, files and protections

**24 distinct focused tests passed:** six new diagnostic-integrity controls over all 38 profiles, nine existing R1 contract controls, eight existing API completeness tests (including the original 23-scenario fixture), and the existing complete default-OFF equivalence check against the independently hash-verified historical scorer across all 30 frozen JDs. New tests deliberately do not assert that every research hypothesis or safety judgment agrees with current production behavior. The F02 discrepancy and conflict risks remain visible; there is no self-generated oracle PASS.

Commands used Python `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B` with `scripts/run_coordinated_preview_checks.py --scratch-root reports/stage2h_runtime`:

- `tests.test_coordinated_realistic_evidence_audit` (initial 35 profiles, then the final 38).
- `tests.test_coordinated_r1_disposition.R1ContractTests tests.test_api_evidence_completeness tests.test_coordinated_action_implementation.CoordinatedImplementationTests.test_gate_off_matches_hash_pinned_historical_native_on_30_jobs`.
- The affected `RealisticEvidenceAuditTests.test_independent_expectations_and_discrepancies_are_preserved` method after making diagnostic export optional for ordinary test runs. No test input depends on an ignored export or private launcher. No full or quick project-wide suite ran.

The guarded launcher disables dotenv/model-cost retrieval, blocks network and non-disposable SQLite, and fixes project imports to this checkout. Pure publishability checks rejected all 38 gated analyses before any DB call. No real candidate, saved Job Match, live DB, LLM, Tavily or embedding access was used. Existing 60-case expectations and all earlier oracles are byte-identical.

Only these new reviewable files were created:

| File | Purpose |
|---|---|
| `bulk_unresolved_stage2h_readiness.md` | This readiness report and all actual results. |
| `tests/fixtures/coordinated_realistic_profiles_v1.json` | Independently declared full synthetic profiles, behavior hypotheses and semantic judgments. |
| `scripts/audit_coordinated_realistic_evidence.py` | Read-only execution/diagnostics, original-origin accounting and a diagnostic review-card model. |
| `tests/test_coordinated_realistic_evidence_audit.py` | Integrity, source/weight/ceiling, unavailable aggregate, persistence-rejection and discrepancy-preservation controls. |

All **946 entry paths** (945 tracked paths and the existing untracked dashboard report) are SHA-256 unchanged. This covers production scoring/parser/policy, source selection, taxonomy v1.6, registry v1.3, v1.19/cache identities, historical fixtures, Stage 2E/G acceptance and prior research. Branch/HEAD remain unchanged and the index is empty. `git diff --check`, `git diff --cached --check` and no-index checks on the four new files have no whitespace errors.

Actual full diagnostics are local under `reports/stage2h_runtime/coordinated-checks-ace5527bc6d24f608b788972e319cc94/actual_profiles.json`. `reports/stage2h_runtime/readiness_summary.json` contains compact actual results, all discrepancy IDs, explicit semantic dimensions and a separately labeled hypothetical R1 count estimate. Entry/protection ledgers and later repeated audit exports are also under this already ignored tree (`/reports/*`). Earlier diagnostic exports were preserved; no large export is a test dependency or proposed Git artifact.

**Final recommendation:** PASS for completion of this audit; BLOCKED for realistic-profile numeric readiness/production activation. Prioritize source-coverage and scoped-conflict explanations, then independently govern conflict quarantine. R1 expansion may be feasible for proven closed packets but is not the immediate safety fix. No production rules, identities, gate defaults or existing oracles changed. Nothing was staged, committed, pushed or merged. Stop for review.
