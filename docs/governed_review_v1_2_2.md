# Governed Review V1.2.2 — post-publication compatibility

## Diagnosis

The live v1.6 publication is correct and was preserved. The original command
was reproduced before editing: **19 tests; 12 errors, one failure, six passes**.
The two modules accidentally used the mutable production artifact as their
pre-publication fixture. Copying that artifact into a temporary directory did
not isolate its semantics: the copy already contained the published rule.

| Previously failing test | Exact cause |
|---|---|
| `ActivationTests.test_atomic_failure_preserves_native_artifact` | Local draft creation reached the existing duplicate/conflict guard before atomic-failure injection. |
| `ActivationTests.test_real_persist_preview_approve_publish_reload_rollback` | The supposedly pre-publication copy already contained the fallback; governed draft creation correctly rejected it. |
| `ActivationTests.test_unapproved_rejected_stale_and_missing_controls_fail_closed` | Same duplicate draft-creation guard prevented reaching the intended approval controls. |
| `ActivationTests.test_legacy_resolutions_preserved_and_unknown_rule_rejected` | Preview overlay correctly rejected an already-published fallback. |
| `ActivationTests.test_unseen_complete_scope_and_negatives` | Same duplicate preview guard. |
| `ActivationTests.test_streamlit_actual_isolated_validation_approval_and_publication` | Investigated independently: Preview/Validate failed on the published fixture first. No governed regression existed, so the UI correctly omitted Reviewer. The selector was not renamed or removed. With the isolated v1.5 fixture the complete selector-driven flow passed unchanged. |
| `GovernedResolutionTests.test_native_before_after_and_no_default_activation` | Its unresolved baseline assertion ran against the now-correctly-resolved live release. |
| `GovernedResolutionTests.test_approval_cannot_bypass_existing_governor` | Duplicate preview guard prevented reaching the approval-bypass assertions. |
| `GovernedResolutionTests.test_controls_generalize_without_job_ids_and_fail_closed` | Duplicate preview guard. |
| `GovernedResolutionTests.test_exact_v2_source_case_only_one_of_thirteen_changes` | Duplicate preview guard prevented the historical before/after comparison. |
| `GovernedResolutionTests.test_native_evidence_caps_do_not_promote_unproven_implementation` | Duplicate preview guard prevented entering the temporary scope. |
| `GovernedResolutionTests.test_native_version_and_knowledge_currentness_use_existing_contract` | Duplicate preview guard. |
| `GovernedResolutionTests.test_scoring_formula_runs_natively_not_in_preview` | Duplicate preview guard prevented constructing the temporary taxonomy. |

The expanded focused run exposed two additional stale test assumptions:

- Resolver Inspector hard-coded v1.5 as the current production version. It now
  compares against native taxonomy/registry objects and the scorer constant.
- The NAC UI test used its reviewed v1.5 coverage receipt with the live v1.6
  artifact. The currentness boundary correctly withheld its two historical gap
  labels. That test now runs against the matching isolated v1.5 artifact; both
  original gap/direct-evidence assertions remain intact.

These were fixture/expectation defects. No production recognition, scoring or
publication-authorization behavior was changed.

## Isolation

`tests/fixtures/governed_requirement_taxonomy_v1_5.json` is a 65 KB test-owned
historical baseline with SHA256
`da7b5e6952935a7dda88347c5af41eba65784b45da1c5b68f45a8768f605563e`.
It matches the recorded publication's before-artifact hash exactly.
`tests/governed_review_fixtures.py` writes disposable native artifacts from that
fixed file, constructs v1.6 using the existing finite rule constant, patches the
native taxonomy path and clears/restores resolver knowledge caches on exit.
Its v1.6 bytes match the real published artifact hash exactly. LF bytes are
explicitly preserved on Windows. No tests read a Documents backup or construct
their baseline from the user's current taxonomy. Unpublished approval/UI tests
use v1.5; post-publication controls use v1.6 and real disposable governor stores.

## Publication recovery

The old UI applied unpublished-draft currentness to a completed release, so the
release's own v1.5 → v1.6 transition appeared stale. Recovery now checks durable
publication receipts before the existing strict unpublished approval preflight.
It checks exact source linkage, saved research integrity, draft/regression and
approval fingerprints, receipt IDs, reviewer/timestamps, artifact path, SHA256,
native version, exact capability/rule and existing native publication presence.
It also reports the actual current native resolution. No rule alone proves a
publication, and no writer or score replay is called during recovery.

Pending drafts, sealed current validation receipts without approval, current
approved drafts, stale unpublished approvals, completed releases and mismatches
are separate states. Historical published approval and validation remain visible;
their old knowledge fingerprints are historical receipts, not a demand to
reapprove. The existing governor still rejects stale *unpublished* approval and
duplicate/conflicting rules. An explicit repeated publication in a disposable
test returns the same idempotent receipt without a second file replacement.

The UI shows **Published — taxonomy v1.6 active** and **Already published —
correction active**, disables Preview/Validate/Approve/Publish, and keeps native
Inspect available. Metadata and the actual receipt are displayed; historical
details remain collapsed. Recovery caching includes the DB/WAL and exact native
artifact file identity, so even a formatting-only artifact change invalidates
the cached success and fails closed on the hash mismatch.

## Validation and artifacts

The original 19 tests passed after isolation (19.262 seconds). The additional
Inspector/NAC failures passed their direct two-test check (3.201 seconds).
The final combined run passed **111/111 tests, zero failures/errors/skips, in
76.305 seconds**. Final focused totals and exact module names are in
`reports/governed_review_v1_2_2_test_results.json`; complete output is in
`reports/governed_review_v1_2_2_focused_tests_final.log`.
Tests ran via the venv Python unittest loader with external calls disabled.
This sandbox needs a process-local inherited-permissions temporary-directory
adapter before imports; no installed Python or Streamlit dependency was edited.
No full suite or project gate was run.

A fresh read-only AppTest using the actual Inspector snapshot-40 row recovered
`tqd3pub_255e05c5cf48abd5f3f623cc`, showed the published state and disabled all
duplicate actions, then passed Inspect, rerender and Reload saved review with
all live writers and preview/scoring validation blocked. The native result was
`CAPABILITY_RESOLVED`, `backend.api_development`,
`approved_complete_rest_api_development_obligation`.
See `reports/governed_review_v1_2_2_actual_recovery.json`.

Protected before/after hashes are recorded in
`reports/governed_review_v1_2_2_protected_before.json` and
`reports/governed_review_v1_2_2_protected_after.json`.
The live taxonomy hash remains
`a8c4600445ae9d444f41801e47fc4e6895b97b8f58114042dcaf27de55f6b2c8`.
All **14 protected before/after hashes are identical**. The live registry,
scorer/resolver/governor code, approval/publication store,
application database (including historical snapshot 40) and frozen benchmarks
are protected by the same comparison. No live approval, republishing, rollback,
database write, scoring change, model/network call, commit, push or merge.

## Files changed in this iteration

- `tailoring/unresolved_requirement_review_ui.py`: completed-release rendering and disabled duplicate actions.
- `taxonomy_discovery/governed_review_recovery.py`: verified published/validated/pending recovery and artifact-aware cache token.
- `tests/governed_review_fixtures.py`, `tests/fixtures/governed_requirement_taxonomy_v1_5.json`: deterministic disposable pre/post artifacts.
- `tests/test_governed_requirement_activation_v1_1.py`, `tests/test_governed_requirement_resolution.py`, `tests/test_unresolved_requirement_review_ui.py`, `tests/test_governed_review_recovery_v1_2_1.py`: isolate historical tests; cover pending/current validation without approval.
- `tests/test_governed_review_post_publication_v1_2_2.py`: native post-release, durable recovery, mismatches, cache drift, duplicate safety and read-only checks.
- `tests/test_tqd3_production_resolver_inspector.py`, `tests/test_initial_analysis_explainer.py`: the two independently diagnosed stale expectations.
- This handover and the scoped validation reports/logs named above.

## Manual acceptance

1. Restart Streamlit. Open Production Resolver Inspector → Saved Job Match and
   inspect **Discovered job ID 146**. Confirm EDB, snapshot **40**, and select
   **req_9270e95898c8**, Design and develop RESTful APIs.
2. Unresolved Requirement Review should immediately show **Published — taxonomy
   v1.6 active** and receipt **tqd3pub_255e05c5cf48abd5f3f623cc**. Confirm Darren,
   the approval timestamp and actual publication timestamp. Historical approval
   and validation should be completed, not pending or requiring revalidation.
3. Preview should say **Already published — correction active**. Preview,
   Validate, Approve and Publish must be disabled. Do not attempt a live release.
4. Inspect diagnostics should show the current resolved capability and approved
   REST API obligation reason, separately from the saved historical analysis.
5. Reload saved review or restart again. The same receipt must recover without
   new approval/draft rows, scoring replay or snapshot refresh. Historical
   snapshot-40 metadata remains historical and unchanged.

Stop for user review.
