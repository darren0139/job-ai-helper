# Phase 2D — comparison dashboard and debug export

Implemented native Streamlit layout/navigation polish and an explicit, consolidated
debug export. This phase changes presentation and diagnostics only. The published
v1.17 and experimental v1.21 evaluators, inputs, evidence admission, taxonomy,
registry, ranking and persistence behavior are unchanged.

Verified branch: `feat/job-match-real-evidence-comparison-v1`, repository
`C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
All prior Phase 2–2C uncommitted work and unrelated untracked files were preserved.
No staging, commit, push, merge, reset or cleanup was performed.

## Layout and interaction

Before: real, synthetic and batch controls ran down one long page. The real review
used a separate multiselect, wide provenance dictionaries and fragmented exports.

After: three native tabs — **Real Application Comparison**, **Synthetic Comparison**,
**Synthetic Batch Audit**. Each keeps its existing explicit execution controls and
state. Tabs render controls/retained data eagerly, but only explicit Run/Compare or
batch actions invoke evaluation. Changing tabs cannot start scoring. Synthetic and
batch capabilities, keys, queues, independent expectations and scorer calls remain.

The real workflow now follows:

1. Explicit Browse, application/admission selectors in one row.
2. Side-by-side explicit Load and Compare actions; Compare is disabled without a
   loaded packet and all existing source/currentness checks still run.
3. Compact **Comparison scope**, source identities and excluded-current-report
   warning. Historical versions and saved results have a separate collapsed panel.
4. Two bordered native score cards with actual versions, nullable alignment,
   label counts and existing coverage/evidence components. Summary counts show
   identical rows, changed labels/sources, geometry mismatches, withholding and review.
5. A native checkbox-only editable requirement table with readable configured
   columns and horizontal/vertical scrolling. All runtime rows remain available.
6. Collapsed selected-requirement inspection, nested original source/evaluation
   receipts, metadata classifications, export and source-integrity panels.

The mockup guided grouping, hierarchy, spacing and navigation. No hardcoded 12%,
16-row count, company, selected rows, Deploy/settings controls or approval actions
were copied. The actual requirement count comes from exact canonical identities;
the user's matching 17-row input will display 17, not the illustrative 16.
The existing theme supplies all surfaces and colors. No custom CSS, HTML grid or
external assets/components were introduced.

When all labels, credits, allocations, parent/importance geometry and selected
source-reference identities agree without review/conflict flags, the UI states:

> No requirement-level scoring differences detected for this input.

It also explains that agreement does not establish scoring correctness. No claimed
improvement or downgrade is manufactured. Null/withheld values remain unavailable,
never zero. Retrospective incompatible geometry withholds comparative metrics and
table credits; standalone implementation receipts remain available in details.

## Checkbox review contract

The main `st.data_editor` has a visible pinned Select checkbox for every row.
Requirement ID, text, importance, labels, credits, difference and source/conflict
columns are disabled for editing. Parent allocation and full provenance move into
details. Full wording remains available in selected local inspection.

Search matches requirement wording or exact ID. Filters include published label,
experimental label, discrepancy and review state, plus the prior diagnostic filter.
Select all visible adds the current filtered IDs; Clear empties the complete
selection; Select changed or flagged selects that set from the full evaluated input.
Hidden selections survive filtering. Selection is stored by canonical ID, never
dataframe position. Editor identity includes input/filter/action revision, so action
buttons cannot accidentally restore an old checkbox state.

These checkboxes mean local inspection only. They never approve evidence, create
human review decisions, relabel requirements or update an application. Source,
application or admission-mode changes reset selection/exports through the existing
loaded/result invalidation path. Consent/configuration OFF clears retained debug
and private-excerpt data. Filters, checkboxes, details and downloads never evaluate.

## Source authority

The scope panel states that this input is a frozen Job Finder library snapshot and
discovered JD. It displays selected application/source/snapshot IDs, archived
version, current-report difference and exclusions. Retrospective mode explicitly says:

> Comparing original frozen Job Finder evidence with fresh scoring implementations. Current Application Session and Phase 8 results are not included.

Actual résumé-document analyses, different JD versions, local preferences, later
application reports and Phase 8 before/after sources are not interchangeable. An
expected cross-workflow difference is not labeled an application bug. Document
admission remains unsupported; the existing loader still blocks it. Strict and
retrospective admission functions were not modified in this phase.

## Consolidated export

**Export Comparison Debug** explicitly builds one retained in-memory report and
bundle. Separate download controls offer share-safe JSON and ZIP. A collapsed
copyable summary uses Streamlit's native code-block copy button; there is no fake
clipboard control or custom clipboard JavaScript. The bundle is not built on passive
rerenders or selection changes. Generation is bounded to 16 MiB of uncompressed ZIP
content and retained for one input identity. No files are written to disk by export.

ZIP members:

| File | Allowlisted contents |
|---|---|
| `manifest.json` | Schema, selected application ID, input identity, evaluated row count, each other file's byte count and SHA-256. No circular self-hash. |
| `comparison_summary.json` | Actual fresh versions, nullable scores/components, five label counts, counts of differences/review/withholding. |
| `requirements.csv` | Canonical IDs, labels, allocations, comparative credits, source/conflict/geometry/review and identical flags. Null CSV credits are blank, not zero. |
| `requirement_diagnostics.json` | Parent IDs, importance, native/effective labels, allowlisted dispositions, action counts, source-reference/receipt fingerprints, withholding and difference codes; published arithmetic explanation; metadata changes, warnings and safe exception codes. |
| `source_identity.json` | Deliberately selected application and source/snapshot IDs, mode, authority, historical versions, exact original and fresh fingerprints, geometry fingerprints, implementation source revision, current-report warning and workflow exclusions. |
| `metadata_v122.csv`, `metadata_v123.csv` | Line indices, allowlisted classifications, admission flags and hashed source/text/reason identities. No raw line wording. |
| `diagnostic_notes.md` | Concise share-safe summary, comparison caveats and privacy/metadata limitations. |

JSON and CSV derive from the same exact-ID records. ZIP ordering, timestamps and
serialization are deterministic. File hashes cover their exact encoded bytes.
The published arithmetic explanation uses the existing pure formatting helper on
already evaluated data; it does not call an analyzer, scorer, cache or writer. It
shows component weights/denominators/numerators and per-ID coverage/evidence points,
with parity explicitly reported, so a low alignment can be inspected in one bundle.
Experimental scores/credits remain their original retained nullable outputs.

Safe failure export is available after a comparison exception. It contains only
`COMPARISON_FAILED`, the selected input identity and explicit no-evaluation status;
there is no invented score or raw traceback. Empty result rows mean no successful
evaluation, not an empty source JD. A successful report has an empty exception list.
Admission failures remain readable existing blocked explanations; they do not
produce fabricated evaluated tables.

### Privacy boundary

Default bundles omit requirement wording, résumé text, evidence text, contact
information, private document contents, raw database rows, arbitrary source strings,
URLs/paths, secrets/environment, raw exceptions and opaque full production objects.
Source/evaluation identities use structured references and hashes. Unknown enum
values are not copied as free text. This is a field allowlist, not a promise of
universal text redaction or anonymity: selected application/requirement/source IDs
and fingerprints can still be linkable, so review a bundle before sharing it.

Optional **Private selected excerpts** is separate from the share-safe bundle.
It requires selected IDs, an explicit privacy checkbox and an explicit Preview
action. The preview is visible before its separate JSON download. Only selected
requirement wording and selected evidence excerpts are included, capped at 2,000
characters per excerpt. They are marked PRIVATE/UNREDACTED with no guaranteed
redaction. Changing selection/source or removing consent clears that preview.
There is no full-résumé, arbitrary database or raw-report export option.

## Files changed in Phase 2D

| File | Change |
|---|---|
| `app.py` | Clear the new real debug/selection session state when the existing configuration gate is OFF. Existing early read-only entry retained. |
| `job_discovery/developer_comparison_ui.py` | Three native tabs; compact real selectors/action row; delegate scope/results to the new native renderer; clear stale exports and expose safe comparison failure diagnostics. Synthetic/batch evaluation paths preserved. |
| `job_discovery/developer_review_ui.py` | Compact scope/cards, native checkbox/filter/action table, lazy details, explicit cached exports and optional private preview. |
| `job_discovery/developer_debug_export.py` | Pure receipt projections, exact-ID difference summaries, privacy allowlists, published arithmetic presentation, deterministic JSON/CSV/ZIP and safe failure/excerpt exports. |
| `tests/test_comparison_debug_dashboard.py` | Dashboard/export/privacy/determinism/identity/read-only/no-rescoring controls using disposable synthetic applications. |
| `tests/test_developer_real_comparison.py` | Existing selection interaction now uses the visible checkbox-table action and asserts the exact filtered ID set. Other assertions unchanged. |
| `tests/test_retrospective_comparison.py` | Same selection-locator update for retrospective UI; existing no-rescoring/withholding/read-only assertions retained. |
| This report | Structure, schemas, privacy, tests and manual acceptance. |

Existing `developer_real_comparison`, shared comparator/projection, production
scorers, parser/taxonomy/registry, database managers, Job Finder/Session/Phase 8
algorithms, version constants and historical fixtures/oracles remain untouched.
Unrelated `coordinated_batch_dashboard_review.md` still hashes to
`5a17ea791dbb78c7b21ea52bce6a8978f4553b4adb2c43fb5c3a0a150778d0bf`.

## Verification

The targeted run passed all 10 initial new dashboard/export controls plus four
existing real/retrospective UI controls (14 tests, 114.897 s). An earlier run during
active file edits invalidated retained source identities and stopped comparison;
the subsequent stationary run passed without weakening the stale-input guard.
Two additional final controls directly prohibit scorer/writer calls during export
and reject mismatched input/mode identities.

Final regression run: **95/95 PASS** (348.965 s), covering the 12 new dashboard
controls then present and all 83 existing real, retrospective, frozen-handoff,
synthetic and batch controls. Related application, cache, persistence, provenance
and historical-fixture regression run: **107/107 PASS** (171.035 s). Together
these preserve all 190 existing focused tests.

A final export edge-case control additionally requires an unavailable native label
to remain JSON null, rather than converting it to the evidence label `NONE`.
Only export presentation changed; the scorer receipt remains untouched. The
13-control dashboard follow-up: **13/13 PASS** (56.997 s). This is **203 distinct
focused tests passing**: the 190 existing tests plus 13 new controls. The follow-up
repeated the other 12 dashboard controls after the null-label export correction.
Git working and staged whitespace checks passed; new files also passed a direct
trailing-whitespace scan. No full project CI was run, as requested.

Protected production directories and historical fixtures have no diff from HEAD.
The existing real-admission controller retains SHA-256
`b9c8239c1192faa5ed7b0eb34cd0f7a6f5340ff62e5ec6afee947cf68641d190`.
Only the UI/export changes listed above were made during this phase; earlier
Phase 2–2C changes remain uncommitted and preserved.

Commands use the supported Python 3.13 interpreter and unchanged strict offline
launcher, synthetic/disposable SQLite only:

```powershell
$testPython = 'venv/evidence-completeness-runtime/environment/Scripts/python.exe'
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2d_dashboard tests.test_comparison_debug_dashboard tests.test_developer_real_comparison.RealUITests tests.test_retrospective_comparison.RetrospectiveTests.test_ui_explicit_retrospective_compare_retains_result_and_strict_mode
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2d_final_ui tests.test_comparison_debug_dashboard tests.test_retrospective_comparison tests.test_frozen_handoff_compatibility tests.test_developer_real_comparison tests.test_developer_comparison tests.test_developer_batch_audit
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2d_final_contracts tests.test_application_session_first_analysis_binding tests.test_application_session_analysis_currentness tests.test_initial_analysis_explainer tests.test_shared_application_session_identity tests.test_job_finder_v17_batch_ui tests.test_job_match_batch_matching tests.test_analysis_cache_manager tests.test_phase8_score_explainability tests.test_coordinated_job_match_preview tests.test_coordinated_library_sources tests.test_historical_source_fixtures tests.test_predicate_historical_fixtures
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2d_export_followup tests.test_comparison_debug_dashboard
git diff --check
git diff --cached --check
```

No live/copied application database was opened during this phase. No new #152
score, private export or 38-case research export was generated by the agent.
All existing scoring calculations still delegate to the unchanged evaluators.

## Manual acceptance

1. Restart the existing local app from this worktree with
   `JOB_AI_DEVELOPER_COMPARISON=1`. Use the established runtime and `app.py`; open
   `http://127.0.0.1:8503/?developer_comparison=1` directly (or the chosen local port).
   Use only the consistent development database copy. Pause other writers and
   record local database hashes/counts/analysis IDs before the smoke check.
2. Verify the three tabs. Opt in, Browse and select the intended application. For
   #152 choose retrospective admission. Explicitly Load, verify scope/old versus
   fresh identities, then Compare. Its actual counts, scores and statuses must come
   from runtime; no fixture/mockup values should appear by construction.
3. For the previously observed matching input, expect 17 actual rows and the
   zero-difference message only if the new runtime receipts still agree. Verify
   actual DIRECT/TRANSFERABLE/WEAK/NONE/REVIEW counts. Agreement is not a correctness
   certification, and no improvement should be asserted.
4. Tick rows directly, search by text/ID, filter each label/discrepancy/review state,
   Select all visible, Clear and Select changed/flagged. Hidden selections must
   survive filters; details must correspond to IDs rather than row positions.
   Filters, tab changes and inspection must retain results without scoring again.
5. Expand only selected source/evaluation details and metadata when needed. Verify
   v1.22/v1.23 classifications are separately NO-GO and do not change scores. The
   current application/Phase 8 exclusions and archived reference must remain clear.
6. Click Export Comparison Debug once. Download the JSON or ZIP and inspect all
   eight members, component arithmetic, per-ID row diagnostics, nullable credits,
   metadata changes and source/revision identities. Use the native copy icon in
   Copy concise diagnostic summary. Do not upload private results automatically.
7. If wording is necessary, deliberately select only relevant rows, opt in to
   private excerpts and press Preview. Inspect the unredacted preview before any
   download/sharing. Verify that this text is absent from the share-safe ZIP.
8. Check a synthetic REVIEW_REQUIRED/geometry case and a blocked strict/document
   input. Unavailable scores stay null; unsupported authority is never silently
   substituted. Source/mode changes require reload and clear prior debug/private
   data. Disable consent/gate and verify real debug state is cleared.
9. Recheck the development database/IDs/scores before leaving Diagnostics. No Save,
   Refresh, cache activation, override clearing or generation action is part of
   this smoke test. Confirm synthetic single/batch actions still require their
   explicit buttons and preserve their established behavior.

## Known limits and verdict

Native styling follows the installed theme and browser viewport, not pixel-exact
mockup colors. AppTest verifies structure/interactions; the user's dark-theme
browser smoke remains the visual acceptance step. Clipboard permissions/rendering
are handled by Streamlit's native copy control. Very large debug bundles fail the
in-memory size bound instead of writing files. Private excerpts include selected
accepted references, not a full candidate database or guaranteed-redacted packet.
Hashes provide integrity/correlation, not anonymization. No document authority
adapter, new scoring rule or broader historical replay was introduced.

| Check | Verdict |
|---|---|
| UI inspection | **PASS** for automated native layout/interaction checks; browser visual acceptance remains manual. |
| Checkbox selection | **PASS** |
| Debug ZIP export | **PASS** |
| Source authority distinction | **PASS** |
| No rescoring on rerender | **PASS** |
| No database writes | **PASS** |
| Production scoring unchanged | **PASS** |
| Ready for manual UI acceptance | **YES** |

Manual acceptance is the next user review step. Production scorer promotion
remains **NO**. Nothing was staged, committed, pushed or merged.
