# V3.7 complete-development WIP checkpoint

This is a preservation checkpoint on the Phase9F feature branch, following
`612218de51cc5fa8c6b5a11b69ec7a06d5891722`. It is **not release approval** and
must not be merged wholesale into master. No new optimization or policy design
was performed to create it; it preserves the existing working source.

## Preserved development

- V2.7 combined Base/Library normal selection, versioned generation settings,
  source provenance, decision-time allocation traces and supporting UI/tests.
- Existing normal-generation frozen Selected Base DOCX handoff, freshness
  checks, additional approval-floor integration and genuine-DOCX test fixtures.
- Additional pre-fit, final, multi-project and legacy native comparison views.
- C1 Firefox/Chromium extension and local application capture bridge source,
  alongside the previously committed extension-free UI Review Capture service.
- Remaining public B3/B4, Best-of, exact proxy, lead, receipt and safety tests.
- JD parser/importance-policy development and its regression tests.
- Research-only ATS, testing-gate, SQL, corpus, source-neutral and
  Supporting/Preferred experiments, their scripts and shareable tests.
- Existing development documentation and shareable audit/browser harness
  source. Harness source is not disposable browser storage or screenshot data.

## Private/local exclusions

The original `data/bullet_choice_benchmark/v1.json` remains local and unchanged.
Public `v1_public.json` and `validation_v1.json` are already committed; missing
private20 cases must remain explicitly unavailable. See
`docs/v37_code_checkpoint.md` for local fixture installation and pinned hash.

Local databases, original/fitted résumés, private case JSON/CSV, browser profiles,
screenshots, ZIP bundles, backups, virtual environments, secrets and disposable
application/source-copy workspaces are excluded. Existing local files are not
deleted or rewritten.

Privacy review also excluded these source/doc files from this WIP commit:

- `scripts/v37_supporting_validation.py`: embedded real résumé wording.
- `tests/test_phase9f_evidence_optimizer_v33.py`: embedded real résumé wording.
- `tests/test_v37_sql_evidence.py`: embedded real résumé phrase.
- `docs/unresolved_evidence_explainability_review_v1_1.md`: applicant excerpts.
- `docs/governed_requirement_review_ui_v1_2_1.md`: personal reviewer identity.

These files remain unchanged locally with hashes in the local checkpoint
manifest. They need a separate privacy-safe fixture/interface review before
Git inclusion; this checkpoint does not rewrite them or alter expectations.

## Known incomplete verification

This checkpoint does not require a green full regression. No full runner was
executed for it. The preceding exact612218de audit found59 release tests passed,
four stale compatibility tests failed, and additional contract probes had25
passes/two failures/one missing-helper error. This WIP includes the current
compatibility fixes and additional helper source, but does not claim those
issues were all revalidated. GroupA/B integration/testing was interrupted before
any source edits and remains the first release-review task.

Some preserved test modules import the privacy-excluded V3.3 test fixture and
will fail import on a fresh checkout until that dependency is safely resolved.
The real-quality owner-packet tests require local private cases; absent data is
not a pass. Those tests currently do not implement an optional-data skip.
Research scripts/harnesses may require ignored local receipts, corpus snapshots,
fixture workspaces or browser executables. They are preserved as WIP, not
advertised as portable or ordinary application runtime.

The controlled benchmark baseline remains90/96, with six known frozen failures;
20 real comparisons are independently unlabelled. Installed sidebar Firefox
automation acceptance remains open. Playwright/managed Firefox, optional SciPy
MILP and LibreOffice setup need an explicit release dependency review. Local
Python3.14 checks do not replace supported Python3.13 owner regression.

The development tree includes parser/importance and mixed-source behavior that
differs from the narrower release checkpoint. Do not imply that preserving it
has validated native scoring compatibility, canonical lead ordering or419
policy migration. No historical receipts or live data were migrated.

## Recommended release groups

1. A/B compatibility, coverage and Selected Base safety integration first,
   tested from a deliberately selected release tree with no C policy leakage.
2. C mixed-source generation/cache/lead behavior and D additional diagnostics
   as separately reviewed, complete dependency groups.
3. E extension permissions, signing and newer-master compatibility separately.
4. F parser/importance changes behind source/whole-JD confirmation and explicit
   regression gates; no wholesale419 migration.
5. Research tools remain research-only. Supporting/Preferred and SQL experiments
   are not authority to activate new production objectives or scoring.

The owner runs `run_tests` after release scope and UI acceptance. This WIP commit
alone is not a merge candidate. No merge, push, branch switch or cleanup occurs
as part of preservation.
