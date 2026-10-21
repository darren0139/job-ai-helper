# CI historical provenance portability — bounded partial repair

## Decision

Groups **A and C are repaired with authentic portable source fixtures**.
Group **B remains BLOCKED**: the two original predicate-investigation assertions
are preserved, but their ignored historical artifacts lack an independently
authenticated provenance anchor. Do not rerun full CI expecting green: a clean
checkout still encounters those two missing-file errors.

This branch includes developer UI checkpoint
`300f55f7310194db4ed4656becda214fe0622ba4`. Verified branch:
`fix/ci-historical-provenance-portability`; worktree:
`C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Initial status contained only the unrelated untracked
`coordinated_batch_dashboard_review.md`, preserved unchanged. Nothing was staged.

## Original CI log and baseline

The supplied `reports/github_actions_windows_ci_39_errors.log` has SHA-256
`94b03efc247e1602ccaff90fa59d0f1fa21ba626d6eb0e8d56151ebebdc5bea0`.
It records Python 3.13.16 on Windows, 690 compiled sources and full discovery
exit 1. Its **39 error records** reconcile exactly:

| Group | Modules | Original error records | Shared prerequisite |
|---|---|---:|---|
| A | coordinated_action_implementation (1), coordinated_evidence_preview (1), coordinated_ownership_preview (10), partial_action_credit_preview (24) | 36 | Stage 2D scorer lookup |
| B | existing_predicate_investigation_v2 | 2 | Ignored report and manifest |
| C | jd_metadata_v123 | 1 | Historical v1.22 scorer/policy checkpoint |

These include class-setup and subtest records; they are not 39 independent
defects or necessarily 39 test methods. Every original record and full traceback
was retained in local `reports/ci_provenance_reconciliation.json`, with original
log line numbers. The record-by-record status table follows below.

The requested six-module **local baseline passed 90/90**, because this checkout
has the old Git objects and both ignored JSON files. This is not portability.
A pre-repair replay denied the historical `git show` calls and the two ignored
files: 72 methods ran, producing 42 error records, including two setup blockers
preventing 18 methods from executing. It reproduced **all 39 supplied records**
and added three records sharing the same Stage 2D dependency:

- `PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='backend_grounded_pair')`
- `PartialActionUnitTests.test_independent_non_count_based_policy_table`
- `PartialActionUnitTests.test_source_integrity_and_no_wrong_object_or_usage_credit`

They are not additional production root causes. No assumption is made about why
those three are absent from the supplied hosted log's recorded error list.
The replay is explicitly labeled simulation, not an original CI execution.

Full baseline/replay tracebacks remain in ignored local logs:
`reports/ci_provenance_before.log` and
`reports/ci_provenance_simulated_before.log`.

## A — Historical scorer source

Commit `3e6ff34501b4d68cbe3e66b55ec8af5b0e288026` exists locally, is reachable
from the current branch, and has tree `32cb6656095bd11a8b0667b9f960f2900c7be263`.
`git --no-replace-objects ls-tree/show` establishes the exact requested path
`analysis_stability/stable_evidence_scoring.py`, blob
`db453efe860f0a561ce132064859f2c194a54738`. No replacement refs exist.
The scorer was originally added at that same path in
`3773169c7c2f7db6b35e4a0228788b55194e236a`; no moved-path explanation is needed.

The source is 156,701 LF bytes, SHA-256
`582863e5e3fe5356d0c8adfdac53dd7ec27b382bb1c45d11caf6b8df192384bd`.
That digest independently matches the existing unchanged Stage 2 ownership
oracle's production source pin. Its frozen five parents, synthetic actions,
source JD fixture hash, and complete Stage 2B/2C semantic digests remain unchanged.
No expected outcome was regenerated from today's scorer.

The original loader used Git only after the current scorer differed from the
frozen source pin, as expected following default-OFF development hooks. A single
lookup failure therefore propagated to many tests. The repaired loader reads
the exact pinned fixture and still compares it to the original oracle hash.
The 30-job OFF-versus-historical test executes the same authenticated old source
in a distinct module and retains its complete analysis equality assertions.

## B — Predicate investigation artifacts: BLOCKED

The report and manifest are intentionally excluded by `/reports/*`:

| Local artifact | Size | Observed raw SHA-256 (not a new trust anchor) |
|---|---:|---|
| unresolved_existing_predicate_investigation_v2_manifest.json | 127,002 | 991adde5976e828b478db2d5d661cb322cfef5a7b72dd109949fa693eea6e2b7 |
| unresolved_existing_predicate_investigation_v2.json | 248,695 | 9b80fab66a860e1b17dde23a2e221742968fda4571ea835e86b5e4a9c0b011ea |

Their internal seals validate locally, and the report links to the manifest
seal. However, self-seals and circular cross-references do not authenticate
historical origin. Neither path appears in reachable `git log --all` history;
tracked files contain no independent report/manifest hash or seal anchor.
The manifest seal was also searched across reachable history without a match.
The only additional matching local hash record found was the earlier ignored
working-tree audit ledger; that is not independent historical evidence.
No external fetch, database reconstruction or current-source regeneration was used.

The companion `docs/unresolved_existing_predicate_investigation_v2.md` is absent
locally and has no reachable tracked history. These two failing tests do not
read it. Their direct inputs are the report and manifest; the recorded
150-entry protected map is asserted structurally, not reloaded from 150 files.
The investigation script's separate historical reconstruction also references
the V1 clustering report/document/script/tests. None is silently regenerated to
manufacture an original V2 artifact for these assertions.

The 13-item / nine-job cohort and all original assertions remain untouched:
requirement-only inputs/fingerprints, original source versions and identities,
allocation receipts, source anchors, 150 protected hashes, no YES promotion,
zero confirmed defects and no gold decisions. The tracked script independently
names the 13 analyst review keys, but it does not supply the complete original
saved input/source-version/protection-map contract, so it cannot substitute for
the missing authenticated reports without changing the historical claim.

Privacy inspection was limited to structure and provenance: input fields are
requirement/source/allocation fields, while historical applicant fields are
filtered by `safe_history`. Nonetheless the artifacts carry saved job/snapshot
IDs, source versions and database/protection fingerprints. They have not been
added to Git or exported. A provenance/privacy review is still required before
any approved historical bundle is introduced.

Required next decision: provide an independently authenticated original bundle
(including an external or reachable immutable anchor), or separately authorize
a redesign that explicitly distinguishes a new current-source 13-item contract
from the original historical assertions. This repair does neither. The two
errors remain visible in fresh-checkout validation; no skip, deletion or empty
success was introduced.

## C — v1.22 checkpoint

`0791248` resolves locally to
`07912485d4803f355a760f2623a4a08f5b729fa2`, tree
`215a7008ec064c2f8d30281ea2a642016970dbea`. Both requested paths exist:

| Original path | Git blob | Bytes | SHA-256 |
|---|---|---:|---|
| analysis_stability/stable_evidence_scoring.py | ae44831634cb3467800b72ea1e2950b0a3cc2fd5 | 159,631 | 222361e6364afbccd2a69fffe448a0547ff801b10df456e698030586a779e65a |
| analysis_stability/jd_metadata_policy.py | f59d01e7f77cc0b3f9f744a959c04e8c61065b74 | 8,610 | 26f645b97bd14ad3c84699c8cf249f800194373b04b07b7c345d4aee4637569b |

The test's meaning remains unchanged: compare the checkpoint policy's exact
LF-normalized bytes with v1.22, then compare current/checkpoint analyses for
Jobs 35, 48 and 359 using the original kwargs. The scorer executes in its
separate historical module. v1.22/v1.23 algorithms, NO-GO status and default-OFF
gates are unchanged. The new source pins preserve the exact old revision/path
selection, not newly generated metadata expectations.

## Checkout diagnosis and portable implementation

CI uses `actions/checkout@v6` without a `fetch-depth` override, hence its default
shallow history. The supplied run-step log shows historical path lookup failure,
not an inventory of hosted Git objects. It does **not** prove whether the hosted
commit object itself was absent or present with an unavailable path/tree. Local
objects prove the references and paths are valid here. Hosted-object availability
cannot be established from this log alone; it has not been claimed as fact.

A deeper checkout might restore reachable history, but it is unnecessary for
these tests after the repair and would not supply ignored reports. No workflow,
trigger, checkout-depth or fetch change was made. Runtime tests now depend on
reviewed source bytes shipped with the checkout, not developer-local Git history.

`scripts/historical_source_fixtures.py` accepts only the three registered **full
revision:path pairs**. Every read verifies byte count, SHA-256 and the Git blob
identity reconstructed from the original bytes. Missing/corrupt/unknown inputs
raise an error before execution. There is no current-source fallback, Git call,
network path, database route or write. `.py.txt` avoids accidental import/test
discovery; `.gitattributes` disables newline conversion for these exact byte
fixtures. The snapshots total 324,942 bytes and contain repository implementation
source, not candidate data or model output.

These unit tests retain their original current-dependency compatibility scope.
They do not establish a historical dependency/runtime recipe or execute the
143 separately archived Ollama assertions. **Current behavioral PASS is not
historical experiment reproduction PASS.**

## Exact changed-file inventory

Modified:

1. `scripts/preview_coordinated_evidence_v1.py` — replace historical Git lookup
   with the authenticated source reader; retain the original oracle hash check.
2. `tests/test_coordinated_action_implementation.py` — use the identical Stage 2D
   bytes from the fixture; retain 30-job full equality and SHA assertions.
3. `tests/test_jd_metadata_v123.py` — replace the two checkpoint Git reads with
   pinned source reads; preserve policy-byte equality and analysis assertions.

Added:

4. `scripts/historical_source_fixtures.py` — explicit provenance pins and real
   fail-closed byte validator.
5. `tests/test_historical_source_fixtures.py` — ten integrity/portability controls.
6. `tests/fixtures/historical_provenance/stage2d_stable_evidence_scoring.py.txt`
7. `tests/fixtures/historical_provenance/v122_stable_evidence_scoring.py.txt`
8. `tests/fixtures/historical_provenance/v122_jd_metadata_policy.py.txt`
9. `tests/fixtures/historical_provenance/.gitattributes` — exact LF preservation.
10. `tests/fixtures/historical_provenance/README.md` — immutable origin and limits.
11. `ci_historical_provenance_portability_report.md` — this report.

The supplied CI log, diagnostic probes, replay ledgers, disposable source exports
and runtime logs stay under ignored `reports/`. The unrelated dashboard report
is unchanged. No production, UI, scoring/version, taxonomy, persistence, ranking,
historical gold/oracle, historical Ollama manifest or workflow file was edited.

## Focused verification

All project-importing tests used the supported interpreter and strict offline
launcher. No full project suite was run.

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ci_provenance_after tests.test_coordinated_action_implementation tests.test_coordinated_evidence_preview tests.test_coordinated_ownership_preview tests.test_partial_action_credit_preview tests.test_existing_predicate_investigation_v2 tests.test_jd_metadata_v123

& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ci_provenance_validator_final tests.test_historical_source_fixtures

& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ci_provenance_adjacent tests.test_coordinated_library_sources tests.test_stable_evidence_scoring tests.test_per_jd_scoring_compatibility tests.test_ollama_test_lanes tests.test_developer_comparison tests.test_developer_batch_audit tests.test_coordinated_job_match_preview

git diff --check
git diff --cached --check
```

Exact local module counts (baseline and repaired local run):

| Module | Before pass/fail/error/skip | After pass/fail/error/skip | Portable status |
|---|---|---|---|
| test_coordinated_action_implementation | 19/0/0/0 | 19/0/0/0 | A repaired |
| test_coordinated_evidence_preview | 12/0/0/0 | 12/0/0/0 | A repaired |
| test_coordinated_ownership_preview | 19/0/0/0 | 19/0/0/0 | A repaired |
| test_partial_action_credit_preview | 14/0/0/0 | 14/0/0/0 | A repaired |
| test_existing_predicate_investigation_v2 | 11/0/0/0 | 11/0/0/0 | Only 9/0/2/0 when ignored reports absent |
| test_jd_metadata_v123 | 15/0/0/0 | 15/0/0/0 | C repaired |

The local baseline took 209.244 s; local after 202.099 s. The ten final validator
controls passed in 0.282 s. The 107 adjacent regressions passed in 142.113 s.
There are **207 distinct local passing methods**, but the two predicate report
passes depend on unproven local artifacts and do not certify CI portability.

After denying history and ignored inputs, all 90 methods execute: **88 pass,
2 error, 0 fail, 0 skip**. The two errors are precisely the unchanged predicate
methods; all original A/C assertions and formerly setup-blocked methods execute.
The replay wrapper itself passes because it checks that a prerequisite failure
is still visible. That wrapper PASS is not a CI or historical reproduction PASS.

## Independent fresh-source verification

A read-only `git archive HEAD` export plus an explicit overlay of only the
intended repair files creates a disposable source checkout under reports. It
contains no `.git`, no ignored predicate reports, no untracked local inputs and
no copied virtual environment. The existing strict launcher runs from that
export with the supported external interpreter, its own disposable runtime and
project-import-root verification. No clone, fetch, branch operation or cleanup
is performed.

The first exported-tree run exposed a bug in the **new test's denial control**:
it rejected every path containing the ancestor directory name `reports`, including
the disposable checkout's own tracked fixtures. Actual A/C tests already passed;
there were two expected B errors and this one new test failure. The control was
corrected to reject paths relative to the checkout's own ignored `reports/`,
retaining the denial of ignored inputs and `.git`. All ten validator tests then
passed again. The final exported-tree run completed **100 methods: 98 passed,
2 errored, 0 failed, 0 skipped**, in 210.422 s. All A/C compatibility assertions
and all ten new provenance controls passed without Git history or ignored inputs.
Only the two original B methods failed on their missing files.

Final exported source root:
`reports/ci_provenance_fresh/checkout-1135f7e1d0694a0397c67806e988a74b/`.
The full tracebacks are in `reports/ci_provenance_fresh_final.log`; the export
inventory and nonzero exit status are in `reports/ci_provenance_fresh_result.json`.
The wrapper returned failure for those two errors; it did not convert them to
successful tests. Platform-hosted Ubuntu/Windows CI has not been executed here.

## Integrity and security

- Git branch and HEAD unchanged; no staging, commit, push, merge or reset.
- Published scorer remains `stable-evidence-v1.17-phase6d21`; all experimental
  and developer comparison execution gates remain default OFF.
- Production source, cache/persistence/ranking and developer UI bytes have no diff.
- Original Stage 2 independent oracle and semantic digest expectations unchanged.
- Historical v1.16 accounting fixture remains SHA-256
  `a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.
- Historical Ollama registration and archive byte checks pass: 169 current
  assertions and 143 archived assertions registered; reproduction NOT RUN.
- Strict guards deny external network, live database and secret access. No
  Ollama/model/provider call, production data read/write or authorization bypass.
- New validator controls check corruption, missing source, wrong revision/path,
  current-source substitution, historical/current module separation, v1.22/v1.23
  isolation, independent oracle pin, alternate CWD, absent history/ignored inputs,
  expected fixture inventory and no evaluation writes.

## Verdict and full-CI strategy

| Criterion | Verdict |
|---|---|
| Historical source portability | PASS — A's genuine pinned source ships in the intended fixture set |
| Existing-predicate artifact portability | BLOCKED — original report/manifest not independently authenticated or shipped |
| Metadata v1.22 checkpoint portability | PASS — exact source/policy bytes, original assertions retained |
| Frozen evidence integrity | PRESERVED |
| Affected regression coverage | PARTIAL — 90/90 local; clean six-module lane 88 pass / 2 B errors |
| Current-source CI compatibility | BLOCKED — two original B prerequisites still missing in fresh checkout |
| Existing UI integration unchanged | PASS — no UI edits, developer comparison/batch regressions pass |
| Production scoring unchanged | PASS |
| Ready for isolated checkpoint | YES for the reviewed A/C-only partial repair; not a full-CI-ready checkpoint |
| Full GitHub Actions CI | NOT RERUN |

Both Git whitespace checks and Python syntax checks passed. The three historical
source fixtures compile and retain their original Git blob/SHA-256 identities.
The original ignored predicate JSON files remain byte-identical to the observed
baseline; neither file was regenerated, promoted or force-added.

No workflow dispatch or network fetch was performed. Group B must remain visible
and be resolved through authenticated prerequisites or a separately approved
historical/current contract decision before expecting the next full-CI run to
pass. Any next hosted run must use a checkpoint containing both these repairs
and developer UI commit `300f55f`. Do not treat the 207 local passes, the replay
wrapper's PASS, or archive registration as a successful full-CI/historical run.

## Every original CI error record

The following table is generated from the supplied log, with exact method or
setup identities and subcase labels. A/C portable PASS is established by
the no-Git export. B remains blocked, despite passing against the existing
ignored files locally. Full original tracebacks are retained in the local
reconciliation JSON rather than copied into Git.

| Record | Group | Exact test/setup identity | Local after | Portable after |
|---:|---|---|---|---|
| 1 | A | tests.test_coordinated_action_implementation.CoordinatedImplementationTests.test_gate_off_matches_hash_pinned_historical_native_on_30_jobs | PASS | PASS (A/C) |
| 2 | A | tests.test_coordinated_evidence_preview.CoordinatedEvidencePreviewTests.test_full_preview_matches_frozen_reviewed_baseline | PASS | PASS (A/C) |
| 3 | A | setUpClass (tests.test_coordinated_ownership_preview.OwnershipIntegrationPreviewTests) | PASS | PASS (A/C) |
| 4 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_bare_present_and_passive_are_explicitly_unsupported | PASS | PASS (A/C) |
| 5 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_contradiction_denial_wrong_object_and_modifier_loss | PASS | PASS (A/C) |
| 6 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_final_invariant_blocks_simulated_recovery_bypass | PASS | PASS (A/C) |
| 7 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_one_record_multiple_clauses_and_receipt_offsets | PASS | PASS (A/C) |
| 8 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_oracle_is_not_a_detector_input | PASS | PASS (A/C) |
| 9 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_prospective_versions_and_disposable_snapshot_read_currentness | PASS | PASS (A/C) |
| 10 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_source_and_evidence_id_must_match_original_index | PASS | PASS (A/C) |
| 11 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_source_offsets_and_full_modifier_scope | PASS | PASS (A/C) |
| 12 | A | tests.test_coordinated_ownership_preview.TextOwnershipUnitTests.test_usage_team_subject_future_and_question_are_not_owned | PASS | PASS (A/C) |
| 13 | B | tests.test_existing_predicate_investigation_v2.InvestigationTests.test_final_report_preserves_source_versions_and_no_promotions | PASS | BLOCKED |
| 14 | B | tests.test_existing_predicate_investigation_v2.InvestigationTests.test_frozen_manifest_has_exact_13_and_requirement_only_inputs | PASS | BLOCKED |
| 15 | C | tests.test_jd_metadata_v123.MetadataV123Tests.test_v22_checkpoint_isolation_and_module_bytes | PASS | PASS (A/C) |
| 16 | A | setUpClass (tests.test_partial_action_credit_preview.PartialActionIntegrationTests) | PASS | PASS (A/C) |
| 17 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_extended_receipt_offsets_remain_original | PASS | PASS (A/C) |
| 18 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='A_maintenance') | PASS | PASS (A/C) |
| 19 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='B_development_maintenance') | PASS | PASS (A/C) |
| 20 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='C_design_development') | PASS | PASS (A/C) |
| 21 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='D_complete') | PASS | PASS (A/C) |
| 22 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='E_usage') | PASS | PASS (A/C) |
| 23 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='F_topic') | PASS | PASS (A/C) |
| 24 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='G_denied_short') | PASS | PASS (A/C) |
| 25 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='H_team') | PASS | PASS (A/C) |
| 26 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='I_wrong_objects') | PASS | PASS (A/C) |
| 27 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='passive_me') | PASS | PASS (A/C) |
| 28 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='passive_vendor') | PASS | PASS (A/C) |
| 29 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='relative_me') | PASS | PASS (A/C) |
| 30 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='relative_vendor') | PASS | PASS (A/C) |
| 31 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='short_scope') | PASS | PASS (A/C) |
| 32 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='denied_lifecycle') | PASS | PASS (A/C) |
| 33 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='contradiction') | PASS | PASS (A/C) |
| 34 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='future') | PASS | PASS (A/C) |
| 35 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='peripheral') | PASS | PASS (A/C) |
| 36 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='passive_not_me') | PASS | PASS (A/C) |
| 37 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='relative_future') | PASS | PASS (A/C) |
| 38 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='cloud_two_dimensions') | PASS | PASS (A/C) |
| 39 | A | tests.test_partial_action_credit_preview.PartialActionUnitTests.test_independent_concrete_examples_and_policy_dispositions (case='fullstack_grounded_pair') | PASS | PASS (A/C) |
