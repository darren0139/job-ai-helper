# JD metadata contamination: investigation and experimental admission fix

## Decision and scope

The contamination is reproducible without extraction, a model, a candidate database or the Job Match adapter. Administrative fields are admitted directly from raw JD text when a previous scoring section remains active. A bounded, explicitly invoked experimental route now excludes those fields before span grouping and decomposition. Published/default-OFF v1.17 and existing gated v1.20/v1.21 routes are unchanged by default.

Repository: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`; branch `fix/jd-metadata-requirement-filter`; entry HEAD `a58cc7b7e29d90b841cfa2ae1602c41dbfdcd81e`. The pre-existing untracked `coordinated_batch_dashboard_review.md` is preserved. No other worktree, live candidate data, live database, network or model was used.

**Experimental review only.** This does not change what the existing Streamlit comparison displays: that page still calls its v1.21 controller. No UI, normal Job Match route, saved result or Application Session was changed. Production activation and automatic cache migration remain blocked pending review.

## First incorrect transformation and complete pipeline

1. `job_discovery.matching.analyze_job_match` keeps the job's original description as `raw_jd_text`, obtains/reuses a structured profile, and invokes its stable builder. `_default_extract_jd_profile` delegates to `analyzer.extract_jd_profile`, which calls the extraction and review prompts. The profile has separate location and requirement fields. No extraction call was made in this investigation, so no claim is made about a particular live model response.
2. `stable_evidence_scoring._raw_section_for_heading` recognizes a controlled heading set. `_raw_jd_content_spans` also uses semantic list-heading inference. Unknown text does not reliably terminate the preceding scoring section. Classification depends on layout and child-list shape: `Job Information:` can be unrecognized in the supplied key/value layout, while some bullet layouts produce an inferred heading.
3. In the synthetic trailing metadata block, `_raw_jd_content_spans` retains `Job Requirements:` as the section heading for `Period: Permanent`, `Location: Jurong East` and the hours line. In frozen Job 359, `Period:` at line 16 follows responsibilities without a separating administrative boundary; `Permanent` is line 17, `Location:` line 18, the location value line 19 and hours line 21.
4. **The first incorrect requirement admission is `_raw_jd_requirement_rows`: its `if active_section and _tokenise(value)` branch treats those spans as requirements and appends split clauses with `raw_jd.requirements` or `raw_jd.responsibilities` provenance.** This happens before capability matching. The upstream structural leak creates the opportunity; this unconditional section-based admission turns it into a requirement candidate.
5. `_requirement_sources` admits raw rows first, then grounded structured-profile rows. A correct profile cannot cancel a bad authoritative raw row. Existing legacy profile-only fallback is another route that must not reopen a metadata-only experimental packet. The experiment therefore uses raw authority exclusively and retains the original profile as a receipt, without allowing its fragments to manufacture additional obligations.
6. `canonicalise_requirements` filters known headings/non-requirements, but its existing semantic filter does not establish that these administrative values are non-requirements. It assigns stable IDs, merges duplicates, creates atomic parent identities/provenance and assigns `group_weight_fraction`. Each observed metadata row receives a full parent allocation of 1.0.
7. `build_stable_analysis` follows native keyword/structured matching, validation, reselection, taxonomy caps and NONE recovery. Metadata generally has no supported capability evidence, so it becomes NONE. The native label is a downstream symptom, not the root cause.
8. `_weighted_coverage` includes eligible core rows in its denominator; `compute_deterministic_alignment` turns the contaminated coverage into an overall percentage. `matching.summarize_stable_match` faithfully summarizes that already-contaminated published analysis.
9. `coordinated_preview.prepare_comparison/run_comparison` preserve raw JD authority and run native OFF versus source-aware v1.21 separately. Both use the same raw JD admission, explaining contamination on both sides. The source projection fix for résumé ownership does not classify JD metadata.
10. Job Match saved/cache identity uses the published match/scorer/taxonomy contracts, content and candidate fingerprints. The developer comparison has its own source/policy/input identity. Neither existing route is switched to this new experiment. v1.22 is separately fingerprinted and rejected by publication, summary, ranking and refresh guards.

## Classification boundary

| Content | Experimental handling |
|---|---|
| Native responsibilities, qualifications and preferred headings | Retain native controlled and inferred heading decisions, importance, sentence processing, matching and decomposition. |
| Exact administrative section headings | Recognize a small explicit set (`Job Information`, employment/job/posting details/information/particulars). End inherited scoring-section admission; preserve the heading/text receipt. |
| Administrative fields | Recognize anchored field syntax such as `Period: Permanent`, `Location: Jurong East`, `Working Hours: ...`; retain bare field labels and their adjacent values as separate original occurrences. An inferred child list cannot promote an administrative field into a requirement heading. |
| Literal weekday/clock schedule | Recognize the bounded Monday–Friday plus clock/AM-PM form, not arbitrary mentions of working hours. |
| Explicit candidate eligibility | Preserve obligations such as the candidate **must** be willing to work on-site or **must be available** for rotating shifts, including under administrative/stop boundaries. Their original text is the obligation; no candidate availability is inferred from technical experience. |
| Technical uses of similar words | Keep experience developing location-based applications, permanent data storage and periodic system maintenance. No global word blacklist is used. |
| Unknown colon headings, mixed administrative values and obligations, or ambiguous content | Preserve original occurrences for review. Do not admit the uncertain text as a technical requirement and manufacture NONE/DIRECT. Withhold the experimental whole-JD score and band when classification remains unresolved. |
| Metadata-only packet | No invented requirement and no numeric zero overall. All whole-JD scores are unavailable. |

Each line receipt contains exact original text, line number, character interval, original section context, reason, admission decision and parser identity. The raw JD is never rewritten or deleted. The original structured profile is retained. Explicitly unindexed/ambiguous content stays available in the diagnostic receipt.

This policy is deliberately conservative on unfamiliar structures. It is not a general heading-language redesign. It can quarantine legitimate requirements when an unfamiliar boundary prevents reliable classification; those cases require review rather than automatic credit or absence findings.

## Implementation and version/cache boundary

`analysis_stability.jd_metadata_policy.build_metadata_preview(developer_enabled=True, ...)` is the sole new analysis entry. Omitting the flag raises. It installs a separate request-local `ContextVar`, calls the existing coordinated pipeline, and resets the context even on failure. The native parser's small hook is a no-op outside this context. No environment variable or application startup enables the policy.

| Identity | Value |
|---|---|
| Published scorer | `stable-evidence-v1.17-phase6d21`, unchanged |
| Original gated scorer | `stable-evidence-v1.20-phase6d24`, unchanged |
| Original library-projected scorer | `stable-evidence-v1.21-phase6d25`, unchanged |
| New explicit experimental scorer | `stable-evidence-v1.22-phase6d26` |
| New JD admission/parser policy | `jd-administrative-admission-v1` |
| New preview namespace | `jd-metadata-comparison-v1` |
| Coordinated decomposition | Existing `jd-atomic-requirement-decomposition-v1.2`; action splitting/ownership rules are unchanged |

The new fingerprint binds the underlying full pipeline fingerprint, new scorer/parser identities, original raw JD and classification receipts, original structured JD profile and existing evidence/projection identities. Coordinated row receipts carry the new scorer/parser policy identities. Old cache entries cannot represent the experiment. Nothing overwrites historical snapshots or approved fixtures. Bare v1.22 payloads are rejected even if the preview marker is stripped.

Administrative parents lose their invalid allocation; retained parents are not inflated to compensate. Total admitted allocation may fall, and governed coverage denominators consequently change. That change is explicit, versioned and reported, not hidden redistribution. All retained Job 359 canonical rows, IDs, allocation and provenance are asserted exactly equal to the old gated rows. Duplicate sources remain traceable and do not create a second parent allocation.

## Independent reproduction and before/after rows

The new fixture is independently specified in `tests/fixtures/jd_metadata_admission_v1.json`; it does not regenerate a historical oracle. It covers metadata before/after requirements, vertical labels/values, metadata without responsibilities, unfamiliar headings, unheaded prose, duplicate sections, preferred qualifications, metadata-only input, technical word boundaries and explicit eligibility. A further test covers mixed inline metadata/eligibility and preservation under stop headings.

For the supplied JD, metadata first is already excluded by the published parser: 3 canonical requirements. Metadata last reproduces the leak: 7 requirements. `Experience developing REST APIs` merges with `Develop REST APIs` under the existing native canonicalization; that merge is not changed by this fix.

With the same explicitly synthetic project claiming “I developed REST APIs using Python” and the same library projection:

| Trailing block / actual requirement | Previous classification / label | Experimental classification | Parent allocation before → after | Parent credit before → after |
|---|---|---|---|---|
| Design and maintain backend services | Core / NONE | Responsibility / NONE | 1 → 1 | 0 → 0 |
| Develop REST APIs (including merged qualification) | Core / DIRECT | Responsibility/qualification / DIRECT | 1 → 1 | 1 → 1 |
| Proficiency in Python | Core / DIRECT | Qualification / DIRECT | 1 → 1 | 1 → 1 |
| Job Information | Core / NONE | Administrative heading, not score-bearing | 1 → excluded | 0 → not applicable |
| Period: Permanent | Core / NONE | Administrative field, not score-bearing | 1 → excluded | 0 → not applicable |
| Location: Jurong East | Core / NONE | Administrative field, not score-bearing | 1 → excluded | 0 → not applicable |
| Working Hours: Mon–Fri 8am–5:30pm | Core / NONE | Administrative schedule, not score-bearing | 1 → excluded | 0 → not applicable |

The original 21 coverage-denominator weight units become 9 (core weight 3 per parent). The credited coverage numerator remains 6. Overall synthetic alignment changes **36% → 70%**, in both the published-v17/v21-before comparison versus v22. Metadata-first remains 70%. These are disposable synthetic calculations, not historical candidate or saved Job Match scores.

The vertical fixture isolates the five observed rows. `Period`, `Permanent`, `Location`, `Jurong East (Shuttle service provided)` and `Mon–Fri 8am–5:30pm` each previously have NONE, allocation 1, credit 0 and coverage-denominator weight 3. They now remain original non-scoring metadata receipts; the label/credit is not applicable rather than a fabricated scored zero. Python retains DIRECT and its allocation 1. Total parent allocation is 6 → 1; synthetic alignment 25% → 100%.

Explicit on-site and rotating-shift conditions remain candidate requirements with their own original source records. The synthetic API project provides no such availability evidence; retaining those obligations does not imply DIRECT. Technical location/storage/maintenance qualifications and preferred Docker remain recognized. Metadata-only and unresolved classification results expose null aggregate scores, bands and boundary status.

## Historical experimental deltas

The existing published OFF route passed independent comparison against the immutable hash-pinned historical implementation for all 30 JDs. Experimental comparisons use **empty synthetic candidate evidence**, never stored candidate profiles. The baseline for the following geometry comparison is gated v1.20, so coordinated decomposition is held constant. Any changed counts/withholding are new-policy observations, not historical candidate scores.

| Job | Rows before → after | Parent allocation before → after | Exact newly excluded canonical texts |
|---|---|---|---|
| 35 | 22 → 16 | 18 → 12 | `Skillset`; `Strong analytical, reasoning and problem-solving skills`; `Meticulous with an eye for detail`; `Good oral and written communication skills`; `Team player who is proactive and collaborative`; `This is a 2-Year Contract` |
| 45 | 24 → 23 | 21.999999 → 20.999999 | `Period: December 2026/January 2027, extendable and open for discussion` |
| 48 | 17 → 13 | 14 → 10 | `Other responsibilities include`; `Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time`; `Provide training and consultancy to lecturers on how to use the dashboards`; `Conduct knowledge transfer on data analytics and modelling to staff` |
| 359 | 29 → 24 | 29 → 24 | `Period`; `Permanent`; `Location`; `Jurong East (Shuttle service provided at selected MRT station)`; `Mon–Fri 8am–5:30pm` |

The other 26 jobs have unchanged requirement IDs/counts and allocation/importance. Across all 30, no requirement was added and no surviving requirement's allocation or importance changed. Fractional totals retain existing six-decimal native rounding.

Jobs 45 and 359 are the intended administrative exclusions. Jobs 35 and 48 also quarantine genuine-looking qualifications/duties because unfamiliar boundary handling cannot establish their section with this deliberately conservative policy. Their original content remains in classification receipts; these exclusions are **not** a claim that those duties are metadata. They are a release limitation requiring independent review, not a reason to expand scoring or silently classify them NONE.

Nineteen packets have classification ambiguity. Empty-evidence whole-JD availability changes from numeric 0 to null for jobs **35, 45, 48, 50, 72, 81, 146, 163, 240, 319, 361, 370, 493, 551, 556, 644**. Jobs **16, 359, 479, 566** already have withheld coordinated outcomes and remain withheld. Jobs **15, 31, 44, 141, 144, 158, 173, 187, 595, 632** remain numeric 0 with empty evidence. Thus 4 → 20 packets are withheld in this disposable experiment. This broad conservative withholding is a reason **not to activate v1.22 generally** without reviewing the ambiguity treatment; it is not a published scoring delta.

The exact per-job JSON, raw-section receipts, original/new rows, IDs, weights, labels, contributions and fingerprints are retained locally at `reports/jd_metadata_runtime/offline-release-118c885dc56c45db80c055b15cb455b0/coordinated-checks-76d4288728e74bb98e6377fa61679436/jd_metadata_diagnostics.json`. It is a diagnostic observation, not an expected-result oracle, and remains ignored. Prior overbroad draft diagnostics are not the final policy results.

## Verification and changed files

All runs use Python 3.13 and the existing `scripts/run_offline_release_checks.py` containment launcher, with task scratch under ignored `reports/jd_metadata_runtime/`. Secret, live database, external candidate artifact and network restrictions remain active. The containment scripts are unchanged. The known full-suite résumé-preview output-write problem is a separate task and is not bypassed here.

The new independent admission/Job 359 suite and deterministic diagnostic exporter pass **11 checks** (10 independent tests plus one diagnostic export check). Existing regression coverage passes **147 distinct checks across the combined run and targeted rerun**. Specifically, the 147-test combined run had 138 successes and nine errors in the retained batch UI class: implementation edits during that run invalidated the source-revision key and removed the retained batch before its later interactions. With sources held stable, the complete 13-test batch module reran green, covering every affected test. No UI assertion, oracle, timeout or production behavior was changed to obtain that result. The original combined log remains available; it is not represented as a clean single-run success.

Coverage includes all 60 original coordinated cases, all 38 realistic-profile expectations, the hash-pinned 30-JD default-OFF equivalence, API V1.1/P3/R1/native NONE safeguards, section-heading and atomic decomposition suites, default-OFF/currentness tests, E23 scope, E04/E05/B05 quarantine, E24 duplicate origins, C03 independent cloud/backend outcomes, provenance, null presentation and gated persistence rejection. The existing comparison AppTest suite also passes all five tests with no recomputation or persistence route.

Final protection verification: **967 of 969 entry files byte-identical**; the only two existing modifications are the explicit parser hook and v1.22 publication guard listed below. Published constants, taxonomy, registry, historical fixtures, prior reports, original oracles and containment scripts are preserved. Five new files are listed below. Syntax, tracked/new-file whitespace and staged whitespace checks pass. Branch and full HEAD are unchanged, and the index is empty.

Full project CI was **not rerun** in this bounded parsing task. The already established résumé-preview artifact-write containment failure remains unresolved in the separate fix, as requested. The focused results are not a claim of full-CI clearance. No filesystem restriction was relaxed.

Commands executed (the supported Python 3.13 interpreter here is `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B`):

```powershell
python -B scripts/run_offline_release_checks.py --scratch-root reports/jd_metadata_runtime tests.test_jd_metadata_admission scripts.preview_jd_metadata_admission

python -B scripts/run_offline_release_checks.py --scratch-root reports/jd_metadata_runtime tests.test_coordinated_batch_dashboard tests.test_coordinated_action_implementation tests.test_coordinated_r1_disposition tests.test_coordinated_conflicts tests.test_coordinated_conflict_acceptance tests.test_coordinated_realistic_evidence_audit tests.test_api_evidence_completeness tests.test_coordinated_library_sources tests.test_coordinated_job_match_preview tests.test_coordinated_job_match_preview_ui tests.test_jd_atomic_requirement_decomposition tests.test_jd_structure_inference tests.test_jd_structure_inference_bullet_boundary tests.test_jd_structure_inference_regression_guard tests.test_jd_structure_fingerprint_compat

python -B scripts/run_offline_release_checks.py --scratch-root reports/jd_metadata_runtime tests.test_coordinated_batch_dashboard

git diff --check
git diff --cached --check
```

| Changed/new file | Purpose |
|---|---|
| `analysis_stability/stable_evidence_scoring.py` | Request-local early raw-line admission hook and explicit eligibility source receipt; experimental raw-authority profile guard. Default behavior/constants preserved. |
| `analysis_stability/coordinated_runtime.py` | Reject bare experimental v1.22 identity from publication. |
| `analysis_stability/jd_metadata_policy.py` | New pure deterministic classification/provenance and explicit experimental builder. |
| `tests/fixtures/jd_metadata_admission_v1.json` | New independently specified synthetic admission fixture. |
| `tests/test_jd_metadata_admission.py` | New independent admission, actual Job 359, ownership/source, null, isolation and rejection tests. |
| `scripts/preview_jd_metadata_admission.py` | Contained deterministic synthetic/30-JD diagnostic export; observations are not expected-result oracles. |
| `jd_metadata_contamination_investigation.md` | This report. |

## Remaining blockers and next action

Do not enable the policy in production or silently change the existing comparison route. Review the explicit classification receipts and corpus deltas, especially unfamiliar headings and missing raw authority, before selecting any opt-in UI or migration scope. A published parser/scorer transition would require separately approved cache/currentness and saved-analysis compatibility treatment. Existing saved results stay untouched.

Finite administrative-field vocabulary, conservative ambiguity handling, wrapping/unknown structures and the separate full-CI artifact-write issue remain disclosed limitations. No ownership, P3, R1, API V1.1, source selection, taxonomy or registry policy was expanded.

**Verdict: PASS for the isolated administrative-admission fix and reproducible review diagnostics; NO-GO for general activation of v1.22.** The metadata exclusion is demonstrated and protected, but the conservative ambiguity behavior causes broader withholding and quarantines genuine-looking duties in Jobs 35/48. The next decision should review those concrete receipts and select a bounded ambiguity policy before any new UI/default/migration work. Do not label the conservative withholding as an improvement in candidate scores.

Final evidence: ignored `reports/jd_metadata_runtime/policy_and_diagnostics_final.log` (11/11), `regressions.log` (138 successes, nine superseded UI invalidations), `dashboard_verified.log` (13/13), `entry_hashes.json`, `protection.json`, and the final deterministic JSON path above. Earlier draft logs remain local for transparency. No staging, commit, push, merge, production activation, saved-analysis rewrite or Application Session change was performed. Stop for review.
