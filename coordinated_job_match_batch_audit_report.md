# Developer Diagnostics Phase 1.1 — complete synthetic batch audit

## Outcome

**All 38 registered synthetic examples were actually evaluated**, twice during
this task. The final contained run completed 38, errored 0, and left 0 pending.
These are execution counts, not declarations that scoring/classification is
correct. All 13 existing independently specified library-projection label
controls agree. No independent oracle or production algorithm was changed.

Worktree and branch verified before changes:
`C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`,
`feat/coordinated-job-match-ui-integration`, HEAD
`2a0bf28916e338daf8a64e18df278e6e5c9dcc0a`.
Phase 1 was already uncommitted in this checkout. It was preserved and extended;
the unrelated `coordinated_batch_dashboard_review.md` remains untouched.

## Architecture and UX

The existing main-app Developer Diagnostics route and
`JOB_AI_DEVELOPER_COMPARISON=1` gate are reused. Both single and batch evaluation
also require session consent and an explicit Run action. Normal startup,
selection, filtering, sorting, export and reruns do not invoke scoring.

`developer_comparison.evaluate` remains the shared authentic adapter: published
v1.17 with its coordinated gate OFF, library/source-aware v1.21 built on v1.20,
and separate v1.22/v1.23 metadata **classifications only**. No scored metadata
comparison or live application/library loading was added.

The original single inspector remains available. A native checkbox table now
supplements it with multi-requirement review, select all displayed, clear, and
select changed/flagged controls. Filters include evidence labels, source
differences, conflict quarantine, withholding, geometry and missing counterparts.
Only the Select column is editable. Stored selection consists of exact
requirement IDs, never table positions. Hidden selections survive filtering;
new input identities reset the editor. Selection is inspection, not approval.
Selected requirements have nested expandable details and a matching selected-ID
export. Original evidence, native/effective labels, actions, technical scope,
source provenance and conflict/scoring receipts remain inspectable.

Batch presets:

| Preset | IDs |
|---|---|
| Quick | E01, E02, E04 |
| Extended | E01, E02, E03, E04, E07, E12, E24, F01, B01, C01 |
| Complete | All 38, in original registry order |
| Custom | Any 1–38 distinct registered IDs, normalized to registry order |

**Run selected** and **Run all 38** queue cases and execute one bounded chunk.
Choose 1, 2 or 3 cases per explicit step; the default is 1. **Continue next
chunk** explicitly resumes pending cases. No automatic loop/rerun executes the
next chunk. **Stop pending cases** stops between chunks and preserves completed
receipts; Continue explicitly resumes. The in-process synchronous scorer cannot
be forcibly interrupted by the Stop button. Progress identifies the running
case, completion/error status and attempted count.

The consolidated table shows actual nullable alignments, comparison
availability, D/W/T/N/R counts, geometry, exact-ID label changes, conflicts,
withholding, metadata warning count, execution status and inspection priority.
Filters cover score changes, label changes, suspicious metadata, withholding,
errors and unchanged cases. Select multiple completed cases to open their
requirement tables and original receipts. Detail panels render large receipt
JSON only after their expanders are opened. All tables are native Streamlit;
no CSS, dark HTML tables or new dependencies were added.

Changing a preset configures the next Run; it does not relabel retained results.
The actual retained case list is shown explicitly. Partial results distinguish
COMPLETED, ERROR and PENDING; errors have no numeric result and never appear as
zero or PASS. Changing input/implementation bytes invalidates the batch and its
prepared downloads. Completed cases are reused only for an identical batch
revision. Results and download bytes stay session-local under new developer
keys and never enter production analysis/cache/ranking keys.

## Offline execution and resource bounds

The pure `developer_batch_audit.run_chunk` is shared by the UI and CLI. It calls
the existing adapter without duplicating scoring logic. The CLI launches one
controlled Python child with the existing offline guard installed before
project imports. No daemon, worker pool, model or network service is involved.

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_developer_batch_audit.py --developer-enabled --preset complete --scratch-root reports/coordinated_batch_cli
```

Other options: `--preset quick`, `--preset extended`, or
`--cases E01 E02 E04`. Source text requires the deliberate
`--include-synthetic-text` option. Output goes into a new unique directory
under the requested checkout `reports/` root. The CLI returns 0 only when all
requested evaluations complete; partial/error runs return 2. Ctrl+C retains
completed cases and exports a partial report where possible; an interrupted
active case is not marked successful. Cross-process resume/import of arbitrary
serialized receipts is not implemented. UI Continue is the supported resumable
path; CLI reruns evaluate afresh.

Bounds: exactly the reviewed 38-case registry, at most 38 cases per CLI call,
1–3 per UI action, the existing 250 KB serialized input limit per example,
96 MiB aggregate serialized full-receipt retention and 64 MiB combined export
budget. These are content bounds, not an OS-enforced heap limit or execution
timeout. A callback can stop the pure runner before the next case. No claim of
preemptive cancellation or hard wall-clock enforcement is made.

Measured costs, using the supported Python 3.13 environment:

| Measurement | Result |
|---|---:|
| Initial E01 adapter cost audit | 8.030 s; 547,842 full-receipt bytes |
| Initial 38-case run, including exports | 233.434 s |
| Final 38-case run, including exports | 280.010 s |
| Final retained serialized full receipts | 19,307,462 bytes |
| Final process peak working set | 67,407,872 bytes |
| Final summary CSV | 5,484 bytes |
| Final structured JSON | 3,585,510 bytes |
| Final ZIP | 160,103 bytes |

The final run overlapped focused tests; timings are observations, not a
controlled benchmark. Working set includes interpreter/import/export overhead
and is separate from serialized receipt size. Several seconds per case justify
the explicit chunks; a synchronous 38-case button would unnecessarily block
navigation. Only byte/source fingerprint checks and lightweight projections run
on ordinary reruns. Download archives are generated on **Prepare batch
downloads**, then reused until the batch revision/content or text option changes.

## Actual findings and interpretation

Severity taxonomy:

- **ERROR / INVARIANT_VIOLATION:** an observable breach such as numeric credit
  despite an explicit quarantine/withholding receipt. This is distinct from a
  heuristic judgment about evidence quality.
- **ERROR / EXECUTION_ERROR:** failed evaluation/validation/resource bound, with
  no successful numeric result.
- **REVIEW / HEURISTIC_REVIEW:** a reason to inspect; no claim of a proven defect.
- **INFO / OBSERVATION:** structural or version differences, not assertions of
  scoring correctness or a regression.

Every finding carries case ID, source/requirement identity, actual observed
fields, reason and deterministic audit provenance. Exported findings are ordered
by severity, registry case order, code and identity.

| Finding code | Count | Meaning |
|---|---:|---|
| METADATA_FOOTER_REVIEW | 456 | Recruiting/administrative cues in admitted qualification lines, across case/version/line occurrences |
| DIRECT_DOWNGRADED_OR_REMOVED | 67 | Exact-ID DIRECT removed/downgraded, including geometry changes; not necessarily wrong |
| METADATA_VERSION_DIFFERENCE | 76 | Existing v1.22/v1.23 classifications/admissions differ |
| INCOMPATIBLE_GEOMETRY | 38 | Decomposition/allocation differs; no invented requirement-credit delta |
| SAME_SCORE_DIFFERENT_GEOMETRY | 8 | Same percentage with different requirement geometry |

Total: **645 findings = 523 REVIEW + 122 INFO**. There were **zero detected
invariant violations or execution failures**. This does not prove absence of
all source/ownership or detector limitations.

All 38 cases have geometry differences. Twenty-seven experimental whole-JD
scores remain null/unavailable. Three cases have differing available percentages;
these are observed values under distinct geometries/contracts, not automatically
score regressions. Eight have equal available percentages with different
geometry. No numeric requirement delta or historical/live candidate score claim
is made.

E01 independently reproduced v1.17/v1.21 **27% / 27%**, with **30 / 29** rows.
Both classifiers still admit `raw_jd.lines[34]` through `[42]` as candidate
qualifications despite recruiting contacts, submission instructions, company
details and privacy language. All nine v1.23 lines are covered by a focused
independent audit-detection assertion. These are diagnostic heuristics only;
no JD parser/exclusion rule was changed. The metadata classifiers are not used
to compute either displayed score, so these findings do not claim that their
admissions caused the published score.

Many profiles share the same original JD. The 456 footer flags are therefore
**not 456 independent parser defects**. Consumers should group by JD/source line
when planning a later investigation. The current UI/export preserves case-level
provenance rather than deduplicating away which cases carry each observation.

The 13 existing independent label controls checked against final receipts were
E01, E02, E03, E04, E05, E23, E24, B01, B02, B05, C01, C03 and F01. All agree,
including P3 WEAK, conflict REVIEW_REQUIRED, complete ownership DIRECT and the
native full-stack NONE ceiling. Published summaries, experimental summaries,
requirement/source records and metadata classifications are unchanged across
the two 38-case executions; that equivalence is a behavior-preservation check,
not an independent correctness oracle.

## Export schema and sanitization

Batch schema: `developer-synthetic-batch-audit-v1`. JSON includes a preview-only
manifest, requested/completed/error/pending counts, batch implementation
fingerprint, per-case fingerprints and input identities, actual scoring and
metadata identities, summary, prioritized findings and sanitized individual
reports. Individual reports extend the Phase 1 allowlist with object family,
native/effective label, action/scope support, quarantine reasons and source IDs.
They contain enough structural evidence for a reviewer to trace every finding
without visiting 38 screens. They cannot establish the semantic correctness of
omitted original text; deliberate synthetic-text opt-in supplies that context.

CSV is a concise summary. Null scores become empty CSV cells, never numeric
zero. JSON preserves null. ZIP contains **41 members**: `manifest.json`,
`summary.csv`, `findings.json` and 38 `cases/<ID>.json` reports. Member order and
timestamps are deterministic; same-state JSON/CSV/ZIP byte equality is tested.
Runtime timing measurements are kept separately from deterministic reports.

Default output omits requirement/JD wording, résumé excerpts, full raw analyses,
environment, credentials, unrelated applications and local filesystem paths.
Original source *identifiers* such as `raw_resume_text[0]` and section name
`raw_text` remain valid provenance; they contain no résumé content. Opt-in adds
selected synthetic originals/contrary originals and original JD/requirement
wording, never a live candidate input. Default/full text behavior and selection
agreement are tested. Selected-requirement exports contain only the requested
exact IDs and their review/evidence receipts, without unrelated metadata lines.

Final local artifacts (ignored, not Git source):

`reports/coordinated_batch_final/batch-audit-a5358f36f2c74a62ba154c57147346f0/`

- `synthetic_batch_audit.json`
- `synthetic_batch_audit.csv`
- `synthetic_batch_audit.zip`
- `measurements.json`
- `verification.json`

Final JSON SHA-256:
`da1105539c951237be7a88a6b7f9594d3c3fea434e1a7e87b583cb34f8b317d5`.
The report and ZIP were checked for exact case coverage, selected independent
labels, absent source-content fields, no root path/contact leakage, and matching
ZIP/JSON per-case contents. No export was uploaded or written to a database.

## Future AI reviewer contract — OFF, not configured

This phase performs **no AI review**. The UI says OFF/not configured and does
not call a provider or Ollama. Existing general inference interfaces do not
provide this bounded, citation-validated advisory contract; integrating them
would expand this task.

A subsequent separately reviewed adapter may accept only the sanitized batch
schema with `source_text_included=false`, explicit completed/error/pending
coverage and input fingerprint. Require a separate default-OFF reviewer gate
and explicit action; bind its response to that exact report hash. The advisory
response should contain whole-batch patterns, suspected false positives/false
negatives, review priority, cited case IDs/requirement IDs/source-line references,
observed fields, uncertainty, and an explicit inability to determine correctness
where evidence is insufficient. Validate every citation against the input
manifest; reject unsupported IDs and stale responses. Store/render advisory
notes separately from deterministic findings and original receipts.

The reviewer must have no tools or authority to change scores, evidence,
identities, metadata labels, approvals, production settings or persistence.
External transmission of diagnostic source text requires separate explicit
approval. No mock/model conclusions are presented as actual analysis here.
Deterministic operation and all tests are independent of AI availability.

## Exact file changes and integrity

Changed during Phase 1.1:

- `job_discovery/developer_comparison_ui.py`: add isolated batch section and
  multi-requirement review, retaining existing Phase 1 controls.

New during Phase 1.1:

- `job_discovery/developer_batch_audit.py`: bounded pure runner, summaries,
  diagnostic triage, exact-ID selection helpers and sanitized exports.
- `job_discovery/developer_batch_ui.py`: native checkbox review, chunk controls,
  status/filter tables, multi-case detail panels, download preparation, AI OFF state.
- `scripts/run_developer_batch_audit.py`: explicit offline CLI, guard setup,
  partial-result export and runtime/resource measurements.
- `tests/test_developer_batch_audit.py`: independent assertions and actual
  adapter/Streamlit coverage; no existing oracle edits.
- `coordinated_job_match_batch_audit_report.md`: this report.

Pre-existing Phase 1 files carried forward unchanged in this phase:
`app.py`, `job_discovery/developer_comparison.py`,
`tests/developer_comparison_harness.py`, `tests/test_developer_comparison.py`,
`coordinated_job_match_ui_integration_report.md`. The unrelated untracked
`coordinated_batch_dashboard_review.md` is excluded from this work.

`reports/coordinated_batch_*`, the local cost probe and output-verification
script are disposable ignored diagnostics; no large exports were added to Git.

Published scorer remains `stable-evidence-v1.17-phase6d21` and experimental
v1.20–v1.23 remain default OFF. No edits to scoring, taxonomy, classification,
allocation, cache/persistence policy, Job Finder ranking or CI workflows.
Historical v1.16 accounting fixture SHA-256 remains
`a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.
Historical registration/byte checks still report 169 current assertions and
143 archived assertions registered; no historical experiment was executed.
No live candidate data or production database was accessed. New outputs were
contained under disposable reports directories.

## Focused verification

Supported interpreter and existing offline containment were used. Commands:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_batch_tests tests.test_developer_batch_audit

& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_batch_extra_tests tests.test_developer_batch_audit.BatchContracts.test_source_text_requires_deliberate_opt_in tests.test_developer_batch_audit.BatchContracts.test_priority_order_and_pending_exports

& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/coordinated_batch_regressions tests.test_developer_comparison tests.test_coordinated_job_match_preview tests.test_coordinated_job_match_preview_ui tests.test_coordinated_library_sources tests.test_jd_metadata_v123 tests.test_application_session_analysis_currentness tests.test_application_session_first_analysis_binding tests.test_initial_analysis_explainer tests.test_job_finder_v17_batch_ui tests.test_analysis_cache_manager tests.test_stable_evidence_scoring tests.test_ollama_test_lanes tests.test_job_match_batch_matching tests.test_phase8_verification tests.test_phase8_score_explainability

git diff --check
git diff --cached --check
```

| Check | Passed | Failed | Errors | Skipped |
|---|---:|---:|---:|---:|
| New batch/multi-select tests | 14 | 0 | 0 | 0 |
| Additional opt-in and pending/priority contracts | 2 | 0 | 0 | 0 |
| Existing Phase 1 and focused regressions (279.516 s) | 169 | 0 | 0 | 0 |
| Final full synthetic CLI evaluations | 38 | 0 | 0 | 0 |

The first command ran the initial 14 tests; the two added tests then ran
separately. These cover all 16 current new tests. The cost probe was a separate
one-test diagnostic and is not counted as new regression coverage. The
complete CLI's 38 cases are evaluations, not 38 additional unittest methods.
Full project CI: **NOT RERUN**.

Final verdict: **PASS for review / ready for an isolated checkpoint**. There
were **185 distinct focused unittest passes** (16 new + 169 existing), zero
failures, errors or skips, plus the final 38 successful synthetic evaluations.
Both Git whitespace checks and AST/trailing-whitespace checks on all five
new/changed Python files passed. Existing Phase 1 tests exercised the actual
main `app.py` navigation and evaluator after this integration; Job Finder,
Initial Analysis, Application Session, Phase 8, stable scoring, persistence
denial and historical registration regressions all passed.

Remaining limitations are intentional: UI execution is chunked, synchronous
cases cannot be forcibly interrupted, CLI receipts are not imported/resumed
across processes, heuristic triage cannot establish scoring correctness, metadata
experiments remain NO-GO, live application comparison is unavailable, and AI
review remains unconfigured. This is not approval to publish experimental scores.

No staging, commit, push, merge, reset, clean, branch switch, production
activation or model/network call was performed.
