# Phase 2 — real application comparison

Developer-only real-data comparison: **PARTIAL**. Exact frozen Job Finder library
handoffs can be compared. Configured Application Sessions, actual résumé document
receipts, legacy/unbound applications and application-local overrides fail closed.
Their authority is not interchangeable with the existing library projection.
Production scorer promotion: **NO**.

Verified worktree: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `feat/job-match-real-evidence-comparison-v1`; starting HEAD
`012cd6ed6ea17e83d8855060295eba3349133538`.
Parent GitHub Actions result remains **UNKNOWN**; no network lookup or full CI run
was performed. No real database, candidate document or application payload was
accessed during development or verification.

## Files

| File | Change |
|---|---|
| `job_discovery/developer_real_comparison.py` | Separate read-only frozen-handoff admission controller, identity/currentness checks, existing in-memory evaluator, selected summary export. |
| `job_discovery/developer_comparison_ui.py` | Separate real workflow: explicit Browse, select one application, Load, Compare; saved receipt, diagnostic results, filters, multiselect, lazy details and selected summary download. |
| `app.py` | Early developer route before production imports, secret loading, schema initialization, tracking repair and document/sidebar loading. Normal page startup retains its existing path. |
| `tests/test_developer_real_comparison.py` | Disposable persisted handoffs, actual evaluator and independent E04 conflict expectation, read-only/fail-closed contracts and AppTests. |
| `tests/test_developer_comparison.py` | One locator now targets the original synthetic Run button by its stable key instead of its position; assertions unchanged. |
| This report | Architecture, source restrictions, validation and manual procedure. |

`coordinated_batch_dashboard_review.md` is unrelated and remains untouched. Its
SHA-256 is `5a17ea791dbb78c7b21ea52bce6a8978f4553b4adb2c43fb5c3a0a150778d0bf`.
Nothing was staged, committed, pushed, merged, reset or cleaned.

## Existing authority and compatibility boundaries

* Job Finder: `job_discovery.matching.analyze_job_match` obtains the explicit
  library context, frozen JD extraction and raw discovered-job JD; the published
  deterministic builder saves `job_match_snapshots`. `inspect_job_match` checks
  current library/version identity. The new controller calls neither operation
  nor `current_evidence_context`.
* Handoff: `create_job_finder_application_session` stores the sealed
  `applications.entry_binding_json`, including exact raw JD and full selected
  snapshot, then creates an application-owned `application_analysis_versions`
  Initial Analysis. This is the supported persisted shape.
* Initial résumé analysis: `app.run_resume_analysis` extracts the actual document,
  then `document_grounded_analysis.analyze_actual_resume_against_jd` records exact
  raw document text, represented profile and document authority. Explicit cache
  persistence freezes initial references. `load_application_initial` is a genuine
  read-only authoritative loader; `load_frozen_document_report` validates document
  authority. A document receipt is not evidence-library originals.
* Application Sessions: `initial_analysis_explainer_ui` displays frozen initial
  receipts; `jd_user_input_overrides` can apply local preferences and refresh a
  current-facing report. Neither refresh nor override application is invoked here.
  Confirmed Phase 9F sessions also bind a JD-library source version and selected
  document source. These are explicitly incompatible with this bounded admission.
* Phase 8: `job_match_ab_analysis` builds document A/B snapshots by exact
  requirement identities; `phase8_score_explainability` builds its numeric saved
  contribution receipts. The real UI reuses `build_analysis_receipt` only for the
  already published saved result. Experimental nulls use `coordinated_preview_model`
  and never enter Phase 8 numeric formatting or reconciliation.
* Cache/persistence: `analysis_cache_manager` maintains exact-input history and
  frozen initial pointers. Existing preview rejection remains intact. No preview
  is passed to any persistence, cache activation, ranking or generation API.

Application tracking's apparent read `list_application_tracking_rows` initializes
and repairs tracking. Sidebar `get_recent_applications` and
`list_job_finder_application_bindings` use a read/write connector. They are not safe
panel loaders. The controller reads their established application identities via
parameterized SELECTs on `mode=ro`, with connection-level `query_only=ON` and a
read transaction. It uses the existing snapshot decoder, fingerprint contracts,
pure canonical scope fingerprint helper, saved receipt formatter and comparison pipeline. No schema
or production manager was changed.

## Admission and identity contract

The gate remains exactly `JOB_AI_DEVELOPER_COMPARISON=1`, plus session opt-in.
Browsing is independently explicit so using synthetic tools never opens application
storage. Listing contains only identifying application columns. Detailed reads
occur for the single explicitly loaded ID; queries never select a newest fallback.

Admission verifies:

1. Positive integer existing application ID; sealed Job Finder binding and origin.
2. Exact source job ID, content-generation hash, raw JD text and handoff JD hash.
   The existing handoff hash uses `validate_jd_text`'s stripped text; request identity
   additionally fingerprints the exact retained raw string. No fictitious
   JD-library version is assigned: `jd_version_id=null` and the authoritative
   job/hash/snapshot identity is displayed instead.
3. Exact selected snapshot row equals the entire frozen bound snapshot, including
   saved extraction, evidence payload and versions.
4. Exactly one application-owned initial row with the bound analysis ID, input
   fingerprint and complete original initial-reference metadata. Conflicting
   initial/document references are rejected.
5. Published match/scorer/taxonomy/registry identities are compatible. Current
   canonical scope and allocations match the saved parent geometry. Modified local
   report/override or configured document-session authority is blocked.
6. Nonempty frozen library evidence, matching native evidence fingerprint,
   unique positive original item IDs, and replay-verifiable field/occurrence
   ownership. Saved résumé profile/raw projection, JD profile/raw text and stable
   result must equal the frozen handoff. There is no global-library lookup.

One loaded input/result pair is retained per session. An identity includes complete
selected application, saved receipt, frozen snapshot, source job and the adapter's
source/policy fingerprint. Passive result display rechecks this identity without
scoring. Compare rechecks before and after evaluation; source/implementation changes
discard the result. Switching application or disabling consent clears the retained
pair; disabling the configuration gate also clears identifying listing state.

Currentness means **compatible frozen historical inputs**, explicitly not a claim
that today's library still contains the same records. Cosmetic saved-record changes
can also require explicit reload; this is conservative and does not refresh data.
These local selectors are not a multi-user authorization service: all stored
applications are in the existing single-user application's visible scope. Forged
IDs, cross-application receipts and altered loaded payloads cannot substitute a
different source. No new remote application API is introduced.

Unsupported sources stop at an explicit BLOCKED/INCOMPATIBLE/STALE explanation.
Document bytes may be recoverable through their existing interfaces, but admitting
them as library originals would fabricate source identity. No document adapter was
invented. Supporting configured/document sessions requires a separately reviewed
document-occurrence admission design; some legacy receipts cannot recover originals.

## Results, privacy and read-only behavior

The saved Initial Analysis is displayed separately from the fresh published v1.17
diagnostic. The experimental result uses the unchanged verified source-aware
v1.21 adapter, built on v1.20. Both fresh calculations use deterministic keyword
matching, retrieval disabled and no extractor/model. A fresh diagnostic is not
claimed to reproduce the saved historical result or its original retrieval mode.

Requirement joins use exact IDs only. Tables show labels, parent allocation,
nullable credit, evidence source, importance, parent ID, JD provenance and reason
for disagreement. Native multiselect retains exact IDs across filters; selected
details expose local evidence, native/effective labels, actions, technical scope,
conflict and source receipts without rescoring. REVIEW_REQUIRED contribution stays
null. Whole-JD scores are unavailable when withheld; there are no numeric deltas
across incompatible geometry or unavailable aggregates.

v1.22/v1.23 metadata outputs are classification-only **NO-GO** diagnostics. No
classification changes eligibility or rescoring inputs. Existing parser footer or
benefits contamination remains a disclosed limitation; this UI grants no new
eligibility and makes no claim that current parsing has been corrected.

The developer route is dispatched before ordinary application initialization,
including `.env`/secrets and production imports. Direct entry and page rerenders
therefore bypass schema creation, tracking synchronization/repair, browser bridge,
sidebar document loads and production model configuration. Navigating back to a
normal page resumes its existing workflow and lies outside this read-only route.
For strict cold entry, set the flag in the process environment and use the URL
below. Starting on a normal page still runs normal initialization.

Only the selected real data is rendered locally. No raw payload is logged or
automatically exported by this controller. Downloads exist only after explicit
requirement selection, use an allowlist of IDs, labels, allocations, credits and
version/fingerprint identities, and omit wording, contact fields, application
names, evidence text/source strings, URLs, paths, full receipts and environment.
No raw-export switch is provided. Browser download handling remains the normal
local user action. A raw private export would require a separate privacy decision.

## Validation

Only the supported interpreter and strict offline launcher were used. The guard
prohibits network/model routes, non-disposable SQLite and secret/document access;
fixtures and all test writes are confined to disposable scratch under `reports/`.
The new tests seed genuine production persistence shapes with synthetic evidence,
then check file bytes unchanged by listing/loading/evaluation/UI rerenders, enforce
SQLite read-only writes, and assert forbidden production/library writers are never
called. The main-app cold-entry AppTest patches production startup to fail if called.

An initial fixture setup used an empty extraction, correctly rejected by the native
handoff writer; the fixture was corrected. A subsequent regression run found that
shared synthetic session consent attempted application listing. The strict guard
blocked it before database access; explicit Browse now separates those workflows.
No assertion or existing oracle was weakened to address either finding.

An older failure-path AppTest addressed the first button by position, which became
Browse. Its locator now uses the existing synthetic Run key, retaining all original
error/privacy assertions; the targeted retry passed (1 test, 3.041 seconds).
Dependency inspection also found that the JD-intake module imports LLM configuration.
Admission now uses the existing pure scope fingerprint helper and native canonicalizer
directly; a regression control makes the intake and LLM modules unavailable during
loading. No duplicate parser or matching algorithm was introduced.

Final focused results: **167 tests passed**, zero failures/errors/skips in the
final runs. The new/Phase 1/Phase 1.1 invocation passed **60/60** in **221.432 s**
(27 new controls, 17 Phase 1, 16 Phase 1.1). The separate related regression and
historical-validator invocation passed **107/107** in **96.883 s**. These are
focused test counts, not a new 60-scenario acceptance export or a full CI result.

Commands (from the repository root; no full/quick project runner):

```powershell
$testPython = 'venv/evidence-completeness-runtime/environment/Scripts/python.exe'
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2_real_comparison tests.test_developer_real_comparison tests.test_developer_comparison tests.test_developer_batch_audit
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2_real_regressions tests.test_application_session_first_analysis_binding tests.test_application_session_analysis_currentness tests.test_initial_analysis_explainer tests.test_shared_application_session_identity tests.test_job_finder_v17_batch_ui tests.test_job_match_batch_matching tests.test_analysis_cache_manager tests.test_phase8_score_explainability tests.test_coordinated_job_match_preview tests.test_coordinated_library_sources tests.test_historical_source_fixtures tests.test_predicate_historical_fixtures
git diff --check
git diff --cached --check
```

Additional development runs used the same launcher for the new module, the exact
binding + two UI controls, and the single corrected existing failure-path test.
No full 38-case export was regenerated; original independent fixtures/oracles were
left byte-for-byte unchanged. All disposable test artifacts remain ignored locally.
Protected scorer/parser/policy, database managers, taxonomy/registry, scripts,
historical fixtures, synthetic controller, batch controller/UI and shared comparison
adapter show no Git diff against the starting HEAD. Whitespace checks pass; Git's
LF-to-CRLF advisory is not a whitespace failure. New untracked source/report files
were also checked for trailing whitespace.

## Manual acceptance (user-run, no destructive scripts)

1. Stop other application writers for the comparison window. Record database file
   hashes locally (and existing WAL sidecars if present), application/analysis row
   counts, bound IDs and visible saved scores using established read-only tooling.
   Do not attach private data to an issue or report. A live concurrent writer makes
   a before/after file-hash comparison inconclusive.
2. From this worktree, in PowerShell, restart the existing local Streamlit server
   with the flag (or use a free port if 8503 is occupied) and the established entry point:

   ```powershell
   $env:JOB_AI_DEVELOPER_COMPARISON='1'
   & venv/evidence-completeness-runtime/environment/Scripts/python.exe -B -m streamlit run app.py --server.port 8503
   ```

   Open `http://127.0.0.1:8503/?developer_comparison=1` directly. The query selects
   navigation only and is consumed; it cannot enable the environment gate.
3. Opt in, click **Browse saved applications**, select one existing saved
   application, then **Load saved comparison inputs**. Verify application ID,
   authoritative job/hash/snapshot and initial receipt IDs, evidence fingerprint
   and version/currentness context. Nothing has been rescored yet.
4. For an eligible unchanged frozen library handoff, click **Compare loaded
   application**. Inspect saved versus fresh result labels. Filter changed/review
   rows, select a requirement, expand its details and original evidence receipts.
   If this application's results contain no disagreement, do not invent one; the
   independent synthetic E04 control demonstrates the conflict/null path.
5. Inspect an existing configured/document, stale or missing-source application.
   Expect INCOMPATIBLE/STALE/BLOCKED, with no fallback. Do not alter private data to
   manufacture this case; disposable tests cover deletion and source-change races.
   If every saved application uses an unsupported authority, report that limitation
   and stop; do not create or rebind an application merely to pass this smoke test.
6. Change filters and selected requirements. Results must remain retained, with no
   automatic Compare. REVIEW_REQUIRED and whole-JD withholding remain unavailable,
   never zero. Incompatible geometry has no inferred percentage/credit delta.
   Download only a selected privacy-safe summary if needed.
7. Recheck the locally recorded hashes/counts/IDs/scores before leaving Diagnostics.
   No saved analysis or pointer should change. Separately navigate to normal Job
   Finder/Application Sessions and confirm their established behavior; ordinary
   startup is active again there. Do not run Analyze, Refresh, Generate or Save as
   part of the read-only smoke check. Disable the flag to verify normal navigation
   hides Diagnostics. Production scoring and Phase 8 remain unchanged.

## Release decision

| Check | Verdict |
|---|---|
| Developer-only real-data comparison | PARTIAL — verified frozen library handoffs only |
| Exact JD binding | PASS for admitted source job/hash/snapshot; incompatible JD-library/document sources blocked |
| Exact evidence binding | PASS for admitted original library snapshots; document/legacy reconstruction unsupported |
| Published stable scorer unchanged | PASS |
| Experimental gates unchanged | PASS |
| No writes/models/network in comparison | PASS under offline contracts; user-data smoke not performed |
| Existing synthetic tools unaffected | PASS — existing Phase 1 and Phase 1.1 focused tests |
| Ready for manual UI smoke | YES for eligible existing handoffs; other sources explicitly blocked |
| Production scorer promotion | NO |

Remaining work before broader real-source support is a separately approved
document-authority admission contract and its independent occurrence/provenance
tests. Before any production promotion, require independently reviewed real
examples, confirmed parent CI result, existing release blockers resolved and
explicit activation/persistence approval. This diagnostic phase changes no
published scorer version, ranking, cache identity constants or persistence policy.
