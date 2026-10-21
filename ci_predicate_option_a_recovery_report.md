# Option A — historical predicate artifact recovery

## Outcome

An independent historical byte anchor **was found** in an existing local Codex
checkpoint Git tree. Both original artifact contents were recovered without
executing the investigation, rebuilding a cohort, accessing a database or
generating current-source outcomes. The original historical test methods remain
unchanged; only their test setup now selects authenticated portable fixtures.

Branch remains `fix/ci-historical-provenance-portability`, HEAD
`300f55f7310194db4ed4656becda214fe0622ba4`. All 12 pre-existing modified/untracked
A/C repair and report files, including `coordinated_batch_dashboard_review.md`,
retain their initial hashes. No staging, commit, push, reset, clean or branch
operation occurred.

Search started 2026-10-21 at approximately 22:47 Singapore time. The targeted
source search found the anchor within about five minutes; the remaining work
was recovery, privacy review and focused verification. No indefinite search or
Option B implementation was undertaken.

## Locations and sources inspected

1. Local Git refs: 134 branch refs, 141 existing remote-tracking refs, four Codex
   capture/checkpoint refs and one stash ref. There were no tag refs. No remote
   was contacted. The two recorded stash entries (2026-09-24 and 2026-08-28) were
   inspected as metadata, never restored.
2. Reachable Git objects: scanned 1,393 relevant text/source/fixture blobs,
   47,033,708 bytes, with no size exclusions. Scope: `scripts/`, `tests/`,
   `docs/`, `reports/`, `historical_tests/`, `ci_fixtures/`, `patches/` and root
   research/config text files. Needles included both raw file hashes, both LF
   hashes, both internal seals and the original artifact name. Exact byte hashes
   were also compared. This scans existing Git data, not unrelated directories.
3. The current ignored report/manifest pair in this checkout, the existing
   investigator script, original test module and governed-resolution preview
   script. Original source fields, allocations and seals were compared; no
   investigation or scoring function was run to reconstruct outcomes.
4. The historical companion document and investigator source in the recovered
   checkpoint tree. The document records the original manifest fingerprint and
   the 13-item/nine-job/150-protected-file contract.
5. Project-local backup/archive locations were inventoried: repository-root
   archive/backup names, `patches/`, `dist/`, `ci_fixtures/`, and relevant
   `reports/`/`docs/` filenames. These contained no needed alternative predicate
   archive; search stopped on the authenticated Git-tree recovery. Application
   `data/`, generated résumé `outputs/`, virtual environments, separate worktrees
   and personal directories were not searched for evidence.
6. Existing local CI/provenance records were inspected: the supplied
   `reports/github_actions_windows_ci_39_errors.log`, earlier reconciliation,
   fresh-checkout result and provenance report. They establish the two prior
   missing-prerequisite errors; they were **not** used as an original historical
   hash anchor. The newer ignored audit ledger/current recovery report similarly
   does not supply independent original provenance.

Detailed inventories and search hits are retained locally under
`reports/ci_predicate_option_a/`, including `ref_inventory.json`,
`git_object_search.json` and `recovery_verification.json`.

## Authentication evidence

The independent record is this pre-existing Codex checkpoint ref:

```text
refs/codex/turn-diffs/checkpoints/eeb316f9cf0a0cd30c53b231388bc77b/214fc88caf939ea78895abc8333dfaf4/1791999727843/cdafcb1e-3e33-4b8f-bc97-f54b165494d3
```

It points directly to **tree**
`0a406ec1799434ed1c66f360191f8bd10c5c3b27`, not a commit. The timestamp encoded
in the existing ref decodes to **2026-10-15 01:42:07.843 +08:00**. This is ref
metadata, not an independently signed timestamp or a claimed published commit.
The tree and file blob identities provide the immutable archived-byte record.
It predates this recovery and the newer A/C report. No ref/object was created
to manufacture provenance during this task.

This explains the earlier missed evidence: `git log --all -- <path>` follows
commit history, whereas this source was a ref directly to a tree. Expanding the
targeted search to reachable object contents found it. The two newer Codex
capture trees, `561d0746b3c213ccae897183a801e0922909e90a` and
`7fcee6c7f7cb17d71bcae0eb0f4951987663bcc1`, do not contain the pair. The newer
provenance report's observed hashes were not mistaken for an original anchor.

`git --no-replace-objects show <tree>:<path>` recovered these exact LF bytes:

| Artifact | Original path | Git blob | Bytes | SHA-256 |
|---|---|---|---:|---|
| Report | reports/unresolved_existing_predicate_investigation_v2.json | edfc2b3d9356cb44628fecfd75e3f9c36af9c3ac | 243,066 | 3f98ef19bc1d6ec32cf71985ec515354cd09c669aae2a7b098282088ed25ca5e |
| Manifest | reports/unresolved_existing_predicate_investigation_v2_manifest.json | a183cd3001530fb52498e575c59c6631d7b0ab12 | 124,310 | 3b0c6891a98ca85ea09068568ee8652eddd5682e66dd460c4328202e56fdaf06 |

The same tree also retains:

- `docs/unresolved_existing_predicate_investigation_v2.md`, blob
  `6eff2c037f768773a45276758adec142f6b5d0f2`, which corroborates manifest seal
  `161024a5780a23693b61e4bea21e139ccb60abcc3760d1147adac153d920d04d`.
- The original investigator source, blob
  `9bc836f8445ce093397cae00536ee02f3a446bf2`.

The independent anchor is the archived Git tree/blob record, **not** a self-seal
or circular hash reference. Internal seals and cross-links were then checked
as additional consistency controls. The original report seal remains
`1ab3fe2c5e73eca47ed4c292e8436806cc41482771150e9c45205dd0a6ad5611`.
This authenticates stored historical artifact bytes; it does not independently
certify the original database, research execution or analyst judgments.

## Classification of evidence and line endings

| Evidence | Classification | Limit |
|---|---|---|
| Recovered Git report and manifest | **AUTHENTICATED ORIGINAL** archived bytes | Tree snapshot, not a published commit or full experiment reproduction |
| Companion document in that same tree | **AUTHENTICATED ORIGINAL** archived supporting record | Corroborates the manifest; not a second independent execution |
| Current ignored CRLF file serializations | **LOCALLY CONSISTENT BUT UNAUTHENTICATED** as distinct raw CRLF byte histories | Parsed objects and LF-normalized bytes exactly match the authenticated archived originals |
| Original database/execution environment and external build attestation | **UNAVAILABLE / NOT REPRODUCED** | Neither needed nor reconstructed for the original artifact-consistency assertions |

The current ignored files' raw hashes remain:

- Report: `9b80fab66a860e1b17dde23a2e221742968fda4571ea835e86b5e4a9c0b011ea`.
- Manifest: `991adde5976e828b478db2d5d661cb322cfef5a7b72dd109949fa693eea6e2b7`.

Both use CRLF locally. The fixtures use the exact LF Git blob bytes. They were
extracted directly from the historical tree, **not** regenerated or normalized
from current reports. The differing raw hashes are documented rather than
restamped or conflated. Neither ignored original file was modified.

## Portable fixture implementation

Added `tests/fixtures/predicate_investigation_v2/`:

- `report.json` and `manifest.json`: complete exact historical Git blobs.
- `provenance.json`: full original ref, tree, paths, blob/SHA-256/size pins and
  timestamp limits, plus the companion document identity.
- `.gitattributes`: preserve those two original LF byte streams on Windows/Unix.
- `README.md`: origin, privacy review and historical claim boundaries.

Added `tests/predicate_historical_fixtures.py`: read-only validator enforcing full
byte count, SHA-256, Git blob identity, original seals and expected pair identity.
Missing, tampered, resealed/substituted or incorrectly identified inputs fail.
There is no fallback to ignored reports, Git history, current resolver output,
database reconstruction or an empty successful result.

Modified only test setup in `tests/test_existing_predicate_investigation_v2.py`:
the authenticated paths temporarily replace the investigator's REPORT/MANIFEST
constants for each test, with automatic restoration. The production/research
script itself is unchanged. AST comparison against HEAD confirms **all 11
original test method bodies are identical**, including the two formerly blocked
historical assertions. They remain in ordinary unittest discovery with no skip.

Added `tests/test_predicate_historical_fixtures.py`: seven focused controls for
exact bytes/provenance, cohort/source/allocation/no-promotion preservation,
same-length tampering, resealed changed inputs, missing fixtures, wrong identity,
absence of Git/ignored-report dependencies, no writes and intended file set.

All 13 original input/source-version pairs and allocation receipts match the
archived data. Both full 150-entry protected-hash maps match, rather than merely
their counts. Original conclusions, zero confirmed defects, no YES promotion,
and no gold decisions remain unchanged. **Option B was not implemented.**

## Privacy and security

The original artifacts contain requirement/JD wording, analyst capability
observations, historical job/snapshot IDs, software identities, aggregate database
metadata and protection hashes. Review found no applicant résumé/evidence
payloads, credentials, email addresses, absolute local paths or model output.
Keys such as `evidence_concepts` describe capability contracts, not applicant
claims. Existing historical privacy filtering is preserved. The complete fixture
bytes were not redacted or rewritten to manufacture a different original.

No live database was read, copied or changed. No network, Ollama, model or paid
inference was invoked. No production scoring, taxonomy, Job Finder, Initial
Analysis, Phase 8, Developer Diagnostics, gate, cache or persistence code changed.
The prior A/C repair files and unrelated review document are byte-identical to
the start-of-task ledger. Only the new report, the B test setup and the new B
fixture/helper/test files are intended changes from this task. Search diagnostics
and disposable source exports stay ignored under reports.

## Verification and final verdict

Focused command:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ci_predicate_option_a/focused tests.test_existing_predicate_investigation_v2 tests.test_predicate_historical_fixtures tests.test_historical_source_fixtures tests.test_ollama_test_lanes
```

Result: **46 passed, 0 failed, 0 errored, 0 skipped**, 13.690 seconds. This
includes the original 11 predicate tests, seven new controls, ten preserved A/C
controls and 18 historical lane-registration controls. It is not full CI or
historical experiment reproduction.

A fresh source tree was exported from HEAD with only the explicitly intended
A/C+B repair files overlaid. It has no `.git`, no ignored original reports and
no copied virtual environment. The normal strict offline launcher runs from
that tree, including all six originally affected modules and both new provenance
test modules. Result: **107 passed, 0 failed, 0 errored, 0 skipped**, 290.705
seconds. This includes the original 90 affected methods, ten preserved A/C
provenance controls and seven new predicate controls. It is a focused portable
verification, not full CI. The two formerly blocked predicate assertions both
execute and pass; no error is hidden by a wrapper or skip.

Fresh source root:
`reports/ci_predicate_option_a/fresh-3100f8b721374542947d2e3ba197e0a6/`.
The source export has no Git metadata or original ignored report pair. The
launcher returned exit 0. Details are in `fresh.log` and `fresh_result.json`.
The reproducible export/overlay script is `fresh_checkout.py` in the same
diagnostic directory. No unrelated local fixture or copied environment is used.

No full project CI run was started. The existing prior 39-error reconciliation
remains a historical report; this document supersedes its Group B BLOCKED status
because a previously missed independent archive is now available.

Both `git diff --check` and `git diff --cached --check` passed. All three
new/modified Python files parse successfully, and new helper/fixture/report
files have no trailing-whitespace defects. Byte-preserving Git attributes are
active for the two original JSON copies. The final preservation check confirms
all 12 initial repair/unrelated files and both original ignored artifacts are
unchanged. All 11 original test method ASTs remain identical to HEAD.

| Required verdict | Result |
|---|---|
| Option A | **PASS** — authentic original archived Git bytes recovered |
| Independent original provenance anchor | **FOUND** — existing historical Git-tree checkpoint, not self-seals or current regeneration |
| Group B portable | **YES** — both original assertions pass without ignored reports/history |
| Remaining two known CI errors resolved | **YES**, verified in the fresh-source focused run |
| Original historical assertions unchanged | **YES** — all 11 original test method bodies preserved |
| Option B necessary | **NO**; not implemented |
| Ready for full CI | **YES**, after review/checkpoint of the complete A/C+B file set |
| Full CI executed in this investigation | **NO** |

Recommended next action: review the source provenance, privacy notes and fixture
changes, then authorize an isolated checkpoint including the preserved A/C
repair plus this B recovery. After that checkpoint is available to GitHub,
manually run the existing full-CI workflow on the combined branch containing
developer UI commit `300f55f`. Do not dispatch unchanged remote HEAD expecting
these currently uncommitted repairs to be present. Full-CI readiness is not a
claim that hosted full CI has passed; any newly revealed unrelated failure
should be handled separately.

The successful search ended once the targeted archive was authenticated; total
work remained below the 20–30 minute ceiling. No staging, commit, push, merge,
reset, cleanup, feature activation or production change was performed.
