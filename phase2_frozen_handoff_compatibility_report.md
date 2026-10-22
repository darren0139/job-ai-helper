# Phase 2B — application #152 frozen handoff diagnosis

**BLOCKED for the requested v1.17/v1.21 historical comparison. No historical
mode was implemented.** The original frozen JD/library evidence and Initial
Analysis remain verifiable across their persisted records, but they belong to
scorer **v1.16 / taxonomy v1.5**, not the required **v1.17 / taxonomy v1.6**.
The task explicitly requires rejecting incompatible scorer identities.

Branch verified: `feat/job-match-real-evidence-comparison-v1`.
All pre-existing Phase 2 uncommitted changes and the unrelated
`coordinated_batch_dashboard_review.md` were preserved. No production code,
UI, policy, scorer version, override, database record or fixture oracle was changed.

## Scope and read-only inspection

The user explicitly identified this file as the SQLite-backup development copy:
`C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver\data\applications.db`.
Only that copy was opened, with `mode=ro`, `PRAGMA query_only=ON` and a read
transaction. The separate original `Job-AI-Helper` database was never opened or
inspected. The pre-Phase-2 backup file was not opened either.

Inspection was limited to application #152, its bound source job/snapshot and
application-owned original analysis, plus aggregate application/analysis counts.
The copy has **77 applications**. Only booleans, counts, safe schema field names,
versions, IDs and hashes were emitted. No raw JD, résumé, evidence, contact,
application title/company or source URL is included here or in diagnostic exports.
No scoring, model, network, refresh, migration or write operation was invoked on
the development copy. Its size and modification time were unchanged across the
inspection. No private payload was copied into fixtures, reports or test databases.

## Exact displayed rejection

`job_discovery/developer_real_comparison.py:112` evaluates:

```python
not app.get('report_json') or json.loads(app['report_json']) == report
```

Here `report` is the application-owned historical Initial Analysis selected by
`entry_binding_json.initial_analysis_id`, not a newest/active analysis. Failure
produces the reported current-report/local-overrides incompatibility message.
The controller then stops **before** checking source/scorer compatibility and the
remaining evidence/projection/allocation conditions. The error therefore does
not mean the original binding was corrupt, and it does not prove all later
checks would pass.

`create_job_finder_application_session` originally stores a sealed full Job Finder
snapshot and raw JD in the entry binding, with a separately persisted owned
initial report/reference. `insert_analysis_snapshot_with_connection` stores those
bytes without replacing them with the application-facing report. Later explicit
analysis/cache operations can replace the current application report and archive
an older row while preserving the original bound receipt. The authoritative
initial loader also selects the bound ID rather than the newest row.

The application-local override handler additionally records `meta.jd_user_inputs`
even for an empty preferred-override list. Thus a harmless later metadata addition
can trip this broad equality check in general. **That alone does not describe
#152:** its current report has materially different inputs as well.

## Observed differences for #152

| Metadata comparison | Result |
|---|---|
| Current report equals frozen initial report | No |
| Raw JD text equals frozen JD | Yes |
| Current requirement identity/text/importance/parent-allocation scope equals frozen scope | Yes |
| Current `stable_analysis`, `jd_profile`, `resume_profile`, `raw_resume_text` equal frozen report | No |
| Current `overall_score`, `summary`, `keyword_match`, `meta` equal frozen report | No |
| Other changed top-level fields | 6; contents not exported |
| Changed known metadata fields | `jd_user_inputs`, `analysis_cache`, `initial_analysis_reference` |
| Current report carries original `initial_analysis_reference` | No; field absent |
| Preferred-override count, current / frozen | 0 / 0 |
| Separate configured-session or résumé-document pointer | None |
| Application `initial_analysis_id` pointer | Null; original identity is carried by the entry binding |

These differences show that the current report is not interchangeable with the
frozen library handoff. They do **not** show that the original evidence changed,
nor establish who/what produced the later report. No audit-log attribution was
invented. No overrides need to be cleared; an empty override list does not make
the current report equal to its historical source.

## Independent frozen-record verification

The following checks passed without consulting the current global evidence library:

* Entry-binding seal and origin; source job **493**, snapshot **44**.
* The separately persisted exact Job Match snapshot equals the entire bound
  snapshot, including all frozen extraction/evidence/result data.
* Exact raw JD matches the source job; source-generation hashes agree across
  records; the original stripped-JD SHA-256 validates.
* Exactly one application-owned original analysis exists for the bound initial
  ID: saved row **55**. There are two analysis rows for the application overall.
  Original row 55 is **archived**, which does not invalidate its explicit binding.
* Original initial input fingerprint equals the entry seal; the frozen report's
  complete `meta.initial_analysis_reference` equals the sealed binding.
* All original report JD/profile/résumé/raw projection and saved stable-result
  fields match the frozen snapshot and its deterministic library projection.
* The **5** frozen library originals have a matching evidence fingerprint and
  replay-verifiable original item/field/occurrence ownership. No missing originals
  or substitute current-library records were needed.
* All **17** original canonical rows retain the same current parser scope and
  requirement/parent allocation fields. No reweighting or text-based join was used.
* No conflicting initial pointer, separate document pointer or configured-session
  scope was found.

This is corroboration against distinct persisted snapshot/owned-receipt records,
not reliance on a self-seal alone. It is not a claim of external immutable archival
authentication or proof of the candidate's real-world claims.

Safe identity receipts:

| Receipt | SHA-256 / fingerprint |
|---|---|
| Entry binding | `b80befddaa1de24bc3ae20ffa0eede2a4c6c26c7ab52a107e4893d43cfbd1cb0` |
| Frozen JD (existing handoff stripping contract) | `cb4c6b5ecee03a22ee40d53845d09d27688e19c25adff39352d2380da970acb4` |
| Frozen evidence | `b889b82a89503963c792eda04ff4e53d1485504d23184dc9e755348b8a00c07e` |
| Frozen report, canonical JSON identity | `38a2a1e667f2d74617bb8919b91d80acbfc7377a9504cd93d43a1e818946538a` |
| Current report, canonical JSON identity | `ff27956c0e1167a72766ba09fd5b31da083cb17ace0e9781d080ed563c094c07` |

## Compatibility blocker and conditional decision

| Identity | Frozen snapshot and original result | Required published pipeline |
|---|---|---|
| Match | `job-match-snapshot-v2.3.0\|registry=technology-registry-v1.3` | Same |
| Scorer | `stable-evidence-v1.16-phase6d20` | `stable-evidence-v1.17-phase6d21` |
| Capability taxonomy | `phase6d-capability-taxonomy-v1.5` | `phase6d-capability-taxonomy-v1.6` |
| Technology registry | `technology-registry-v1.3` | Same |

The current application report is also v1.16/v1.5; it is not a newer compatible
receipt. Both the controller's frozen snapshot-version predicate and its original
stable-result version predicate fail. Removing the whole-current-report guard
would merely expose `STALE: saved match/scorer/taxonomy versions are incompatible`.

The original **input binding is verifiable**, but the requested **admission is
not compatible**. Identical requirement geometry does not establish scorer or
taxonomy equivalence. Relabeling the old saved output as v1.17, treating it as a
current Session/Phase 8 result, or silently regenerating/rebinding it would violate
the task. Accordingly there is no new UI mode, bypass, refresh, fallback or
automatic comparison. Broader document support remains outside scope.

## Changes and focused validation

Only two new files belong to Phase 2B:

* `tests/test_frozen_handoff_compatibility.py`: six admission-only synthetic
  disposable-fixture controls. They establish that benign later metadata can trip
  the report guard, that it can mask an additional historical-version blocker,
  that historical identities fail even without a later report, and that corrupted
  original bindings, original input changes and conflicting receipts remain
  rejected. File bytes remain unchanged during every admission attempt and no
  scorer is invoked for blocked cases. Historical-identity rows are explicitly
  admission fixtures, not recreated v1.16 research outputs or a scoring oracle.
* This report.

Existing Phase 2 controls cover missing original ownership, substantive source/JD
changes, explicit comparison, gate OFF, source races, no rerender scoring, nulls,
privacy and read-only main-app behavior. Those tests are rerun under the strict
offline launcher using synthetic/disposable data only. The development database
is not admitted to the offline test lane.

**173 focused tests passed**, with zero failures, errors or skips:

| Run | Result | Time |
|---|---|---|
| New Phase 2B admission controls | 6/6 PASS | 8.052 s |
| Existing Phase 2 / Phase 1 / batch UI regressions | 60/60 PASS | 203.884 s |
| Related binding, currentness, persistence, source and historical contracts | 107/107 PASS | 142.420 s |

Commands use the supported Python 3.13 runtime:

```powershell
$testPython = 'venv/evidence-completeness-runtime/environment/Scripts/python.exe'
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2b_frozen tests.test_frozen_handoff_compatibility
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2b_regression_ui tests.test_developer_real_comparison tests.test_developer_comparison tests.test_developer_batch_audit
& $testPython -B scripts/run_offline_release_checks.py --scratch-root reports/phase2b_regression_contracts tests.test_application_session_first_analysis_binding tests.test_application_session_analysis_currentness tests.test_initial_analysis_explainer tests.test_shared_application_session_identity tests.test_job_finder_v17_batch_ui tests.test_job_match_batch_matching tests.test_analysis_cache_manager tests.test_phase8_score_explainability tests.test_coordinated_job_match_preview tests.test_coordinated_library_sources tests.test_historical_source_fixtures tests.test_predicate_historical_fixtures
git diff --check
git diff --cached --check
```

Both whitespace checks passed. Protected production/database/parser/scoring,
taxonomy/registry, scripts and historical fixture paths show no diff against HEAD.
The existing Phase 2 app/controller/UI files and unrelated review file also retained
their task-start bytes; their pre-existing uncommitted state was preserved. No
existing oracle or assertion was modified. Disposable test runtime files remain
local and ignored; no full CI was run.

## Recommendation

**Manual v1.17/v1.21 comparison for #152 cannot proceed under this task's
compatibility rules.** No database correction or override clearing is warranted.
The precise user-visible error is explained, and its hidden version blocker is
now established independently.

A separate explicit decision would be needed to design fresh v1.17/v1.21
diagnostics from historical v1.16/v1.5 input packets, preserving the old result
and clearly distinguishing input provenance from output-generation compatibility.
That would require its own compatibility contract and independent regressions;
it was not authorized as an exception to this task's rejection rule. Alternatively,
use an already compatible v1.17/v1.6 frozen handoff if one exists; no new handoff
was created or assumed here.

Final verdict: original frozen-record integrity **VERIFIED**; requested historical
mode/admission **BLOCKED**; current application/Phase 8 equivalence **NOT CLAIMED**;
production promotion **NO**. No staging, commit, push, merge or full CI run.
