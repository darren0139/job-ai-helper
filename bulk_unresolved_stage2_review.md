# Bulk Unresolved V1 Stage 2 — coordinated-action investigation

2026-10-17. **Investigation and bounded preview: PASS for review. Production parser
implementation: NOT AUTHORIZED. Full candidate-impact replay: BLOCKED by missing inputs.**

## Repository and scope

Worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch remains `feat/bulk-unresolved-resolution-v1`.

Actual entry HEAD is `5756d5f840dd09e3c0c48c6fcfc9298246a8790b`, not the prompt's
`d37dbb5231d7211efc7b0c0297a20e34d6f597bf`. Git verifies it is the direct descendant
that commits the Stage 0/1 work (`add bulk unresolved investigation and source-aware
inventory`). The worktree/index were clean. No reset or branch change was performed;
the newer checkpoint is preserved. The 808-file protection ledger pins this actual HEAD.

Scoring remains `stable-evidence-v1.17-phase6d21`, capability taxonomy v1.6 and technology
registry v1.3. No production parser, matcher, evidence policy, native version, published
taxonomy or registry was modified. No live database, model, embedding, search, Chroma,
resume or saved-snapshot operation was performed.

## A. Stage 1 export-safety review and tightening

The existing JSON schema closes top-level records but leaves some nested objects open:
requirements, parent grounding, native diagnostic components and historical receipts.
Before this change, a caller could insert unknown sensitive fields in those objects
and recompute the hashes. Fingerprints alone are not an allowlist or authentication.

`taxonomy_discovery/source_inventory_safety.py` now closes those documented native
shapes recursively, and `source_aware_inventory.validate_export` calls it after JSON
schema validation. The semantic validator rejects:

- Unknown `resume_text` inside requirements, including payloads with resealed hashes.
- Selected-evidence text or arbitrary fields inside historical receipts.
- Unknown nested parent-grounding, native-component and diagnostic fields.
- Objects/arrays smuggled into scalar fields such as scope or receipt value.
- Missing receipt fields, invalid receipt labels/counts/values and unexpected version
  or knowledge-artifact keys.
- Incomplete required records and tampered export/requirement fingerprints, alongside
  the existing source-count, allocation, readiness and view-integrity checks.

The input builder still omits excluded top-level source fields, including actual stored
candidate evidence, rather than exporting them. It now fails closed if an otherwise
retained native nested object contains unsupported fields. New native nested shapes
need explicit reviewed support; they are not an extension channel for arbitrary data.

**No JSON schema file or schema identity changed.** This strengthens enforcement of
the documented V1 field meanings rather than adding/changing exported fields. All
2,170 legitimate Stage 1 view records validate. A fresh compact export is semantically
identical to the existing Stage 1 summary, with the same full-export fingerprint:

`6eea250344de01911932ef554e0efeddab5be7c7205dae18040a0ff2797862c6`.

No Stage 1 report, summary, fixture or schema was regenerated in place. Compatibility
output stayed in ignored task scratch. Existing canonical identities, native recognition,
readiness counts and evidence status are unchanged.

Limit: valid free-text JD fields can themselves contain arbitrary prose. This validator
cannot determine whether text placed in an allowed JD field is truly a JD rather than
a fabricated resume statement. Source provenance, trusted fixture bindings and privacy
review remain necessary. Hashes are not proof of authenticity or human approval.

## B. Exact parser failure mechanism

The execution path in `analysis_stability/stable_evidence_scoring.py` is:

1. `canonicalise_requirements` (2713) obtains sources through `_requirement_sources`
   (2581) and its raw-JD source helpers.
2. `_split_single_requirement_clause` (1679) normalizes the statement and preserves
   its original parent and preference context.
3. `_split_non_preference_clause` (1479) checks coherent/example scopes, named terms
   and shared-head lists, then calls `_split_safe_independent_and_pair` (1353).
4. The pair helper splits at the **first** whitespace-delimited `and`, strips edge
   punctuation, checks the second clause's permitted prefix and requires two tokens
   in each clause. It does not prove an independent object in the first clause.
5. `Design, develop, and maintain embedded software modules ...` therefore yields
   `Design, develop` and `maintain embedded software modules ...`. The first fragment
   passes the two-token check. `_clause_record` (1306) then marks it as an atomic child.
6. Canonicalization assigns IDs, source occurrences and .5 child fractions. It retains
   the raw parent in provenance, but cannot restore the missing object to that child.

The object is not deleted from the raw source; it is assigned only to the second
child. The defect is treating coordinated verbs with one shared object as independent
object-bearing obligations. Native recognition appropriately declines the object-free
fragment; adding an alias for that fragment would fix the wrong stage.

### Authoritative source receipts

Every entry below comes from UTF-8 `tests/fixtures/per_jd_scoring_audit.json`,
`snapshot.audit.corpus.jobs[*].frozen_inputs.raw_jd_text`, then current native raw-only
canonicalization. The preview JSON includes the original fixture SHA-256, zero-based
job index, exact section grounding, raw parent, parent/group identities and every old
and proposed child receipt. Saved historical analyses are not run through the proposal.

| Job | Raw parent | Parent occurrence | Span / line / sentence |
|---|---|---|---|
| 359 | Design, develop, and maintain embedded software modules supporting waveform processing systems. | `srcgrp_af665d2ba39b` | `jdspan_6bf448904ec3` / 6 / 1 |
| 479 | Design, develop and maintain scalable full-stack applications using React, TypeScript and Python technologies. | `srcgrp_b729779d18ec` | `jdspan_6dc32ab3a3a0` / 4 / 1 |
| 16 | Design, build, and maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds. | `srcgrp_e822a3bdbba5` | `jdspan_bf5abacb8d88` / 8 / 1 |
| 566 | U+00B7 bullet + Design, develop and deploy cloud-based applications with large-scale data processing capabilities. | `srcgrp_8ac40e9b5dc4` | `jdspan_1c9b6902206f` / 5 / 1 |
| 566 | U+00B7 bullet + Design, build and maintain scalable backend services and API. | `srcgrp_ff65d3ef26a4` | `jdspan_9ffbf61cae4a` / 4 / 1 |

All five sections are responsibilities. Section headings/detection, original sentence
text and raw span identity are preserved, not rebuilt from an incomplete child.

## C. Proposed bounded correction — isolated preview only

The preview uses a new globals dictionary and copies native-defined function code
objects into that isolated namespace. Imported native helpers retain existing policy.
Only that namespace's `_split_non_preference_clause` entry is replaced. No production
module global, function or source file is patched, and no proposed namespace is used
to produce a Job Match or persisted snapshot.

Candidate admission is deliberately finite:

- The native pair helper must already propose two children.
- The first child must contain only two or more comma-coordinated verbs from a finite
  design/develop/build/implement/create/maintain/test/deploy set, optionally preceded
  by the existing ordinary bullet. No independent first object may be removed.
- The second child must begin with a named action and contain a bounded application,
  module, pipeline, service, infrastructure, system, tool, endpoint/API, software or code
  object within the first twelve words.
- Explicit OR, negation and further independent action tails are outside this proposal.
  Unknown object forms retain baseline behavior. This is a conservative investigation
  hypothesis, not independently approved gold or a general sentence parser.
- Existing coherent/example/alternative handling takes precedence. No framework is
  promoted from an example into a mandatory standalone technology.

For an admitted shared-object obligation, the caller emits one full native
`_clause_record` with the original parent, importance and group; it does not merely
discard the object-free fragment or give its credit to an unrelated capability.
For every other case it executes the original native function unchanged.

The caller location is necessary. A prototype that only declined the pair split let
Job 16 fall through into the later `from ...` enumeration branch and create different
unwanted children. Retaining the full obligation before both branches avoids that
failure while leaving unrelated decomposition in place.

The original fixture is UTF-8. An early preview-loader mistake used Windows' default
encoding, introduced a false `Â·` prefix and produced a wrong 661-row baseline. That
loader and its tests were corrected to explicit UTF-8; the delivered preview rejects
any corpus-count disagreement with Stage 1's fixture hash and 716-row manifest. The
delivered sources retain U+00B7, contain no loader-introduced `Â·`, and were rerun.

### Before/after native recognition and canonical IDs

All listed children have unchanged native core importance and evidence eligibility.
Each baseline parent has two .5 children; the proposed parent has one 1.0 child.
The proposed text is the complete original obligation, with native display punctuation
handling; it retains all actions, objects, protocol and framework qualifiers.

| Job | Baseline child IDs | Proposed complete-obligation ID | Recognition before → after |
|---|---|---|---|
| 16 | `req_fd6f5ea4f9bf`, `req_191dd0c2eef9` | `req_acdd8f777d09` | UNRESOLVED + UNRESOLVED → UNRESOLVED |
| 359 | `req_95479a28180a`, `req_bda00d6856dc` | `req_1933523263de` | UNRESOLVED + `embedded.firmware` → `embedded.firmware` |
| 479 | `req_95479a28180a`, `req_533286e95145` | `req_7cf592b15461` | UNRESOLVED + `fullstack.integration` → `fullstack.integration` |
| 566, deploy | `req_95479a28180a`, `req_9f75638e8bda` | `req_490d136c0a8a` | UNRESOLVED + `data.processing` → `data.processing` |
| 566, backend | `req_fd6f5ea4f9bf`, `req_86462bb5cd2a` | `req_3a7798a7fae0` | UNRESOLVED + UNRESOLVED → UNRESOLVED |

These are native capability-recognition results, not candidate credit. `data.processing`
is distinct from Data Structures and Algorithms; no generic-data-to-DSA rule is added.
Remaining unresolved complete obligations are not force-resolved by this correction.

Across 30 raw JDs: **716 → 711 requirements**, exactly five changed parents in the
four requested jobs. Every changed parent loses one child. The other 26 jobs' native
canonicalization remains unchanged. Baseline and proposed runs repeat deterministically.

### Allocation, provenance and compatibility effects

- All five source-parent occurrence identities, raw spans, headings and sentence
  grounding remain unchanged. No source occurrence is lost or borrowed from history.
- Each contributing source-parent sum is **1.0 → 1.0**. Every native atomic-group total
  remains conserved. Distribution changes from .5/.5 to 1.0; this is not a claim that
  individual child allocations remain identical.
- Old child identities are replaced by new full-obligation identities. The preview
  JSON records all old/proposed group IDs, fractions, child removals/additions and native
  diagnostics, including every changed source receipt.
- Importance and evidence-eligibility value sets do not change in these five cases.
  Existing flags are recomputed by native code on the proposed text, not forged.
- Consolidation changes requirement count and potentially evidence-strength populations
  and the share of a parent assigned to a recognized capability. Equal parent totals
  therefore do not imply an unchanged match score. No numeric score was computed.
- Duplicate/overlapping-parent tests preserve unique canonical IDs, all native parent
  occurrences and contributing/non-contributing allocation boundaries. Existing native
  no-duplicate-credit regression tests pass. This is not a claim about an unavailable
  full candidate match replay.

## D. Regression coverage and limits

The 11 Stage 2 tests cover the four actual jobs, three-or-more coordinated verbs,
independent clauses, optional frameworks, AND/OR, negation, incomplete/unknown-object
inputs, duplicate/overlapping parents, source fractions, harmless whitespace/line wrap,
repeat output, unchanged production namespace/version and the UTF-8 corpus manifest.
The six new safety tests include multiple nested injections and resealed-hash attacks.

`Design REST endpoints and develop database migrations` continues to produce two
independent native children. The user example with `implement database migrations`
also retains its baseline behavior: the current safe-second-prefix list lacks
`implement`, so native code currently keeps it as one requirement. That is a separate
coverage limitation, not permission to broaden independent-clause splitting here.

Explicit negations, OR scopes, unknown objects and additional independent-action tails
remain outside the candidate grammar. Their baseline output is preserved even where
baseline parsing is imperfect. No global stemming, generic mapping, alias expansion,
framework inference or taxonomy change is included.

Existing V1.1 API, capability recovery, DSA negative, source selection, native
decomposition, historical accounting and exact fingerprint tests also pass. Historical
fixtures remain immutable; disposable snapshot round trips preserve saved receipts
and currentness failures without rewriting them under the preview.

## E. Versioning/currentness assessment

If approved for production, this is an intentional decomposition and scoring-contract
change, even though parent totals are conserved and taxonomy recognition is unchanged.
It changes canonical IDs, child counts and per-child weight distribution.

Recommend the next scorer identity **`stable-evidence-v1.18-phase6d22`**, provided v1.17
is still the production baseline at approval time, and advance decomposition metadata
from **`jd-atomic-requirement-decomposition-v1.1` to v1.2**. Neither change is applied here.

`build_stable_analysis` builds input identity from raw resume/JD text, taxonomy/registry
and scoring/recovery versions, not parser source bytes. `current_match_versions` and
snapshot lookup likewise rely on published identity. Updating only decomposition code,
or only its debug metadata, is insufficient to invalidate all existing match caches.
The scorer increment is required. Taxonomy v1.6 and registry v1.3 need no publication
for this parser-only correction; candidate evidence fingerprints need no redefinition.

Old snapshots keep their original child IDs, allocations, labels and versions. No
retroactive reinterpretation, migration or automatic refresh is authorized. The preview
has its own DRY_RUN_ONLY identity and must not be stored as a valid v1.17 match.
Complete frozen extracted profiles and candidate evidence remain unavailable, so full
current/historical score impact is blocked and no new Job Match totals are presented.

## F. Minimal production patch plan — pending approval

1. Add a finite shared-object predicate beside `_split_safe_independent_and_pair` in
   `analysis_stability/stable_evidence_scoring.py`, with reviewed verbs/object boundaries
   and explicit exclusion of negation, OR and independent-action tails.
2. In `_split_non_preference_clause`, after existing coherent-scope protection and before
   paired/from-enumeration branches, retain one complete `_clause_record` only when that
   predicate proves the bounded shared-object form. Reuse native parent/group creation.
3. Leave the independent pair helper/prefix list, shared-head list logic, taxonomy,
   registry, API evidence, source selectors, formulas and weights unchanged. Do not add
   an alias for `Design, develop` or remove only the fragment and discard an obligation.
4. Advance the approved scorer/decomposition identities together, then update only
   directly affected identity fixtures after inspecting actual native results.
5. Promote the reviewed actual-source and counterexample tests to production regression
   coverage; obtain complete frozen inputs before claiming full match impact. Request
   any later release gates/refresh separately. Do not deploy this temporary namespace.

The preview's finite object/verb admission is a proposal requiring review. It is not
a recommendation to solve every coordinated-action grammar variation in one patch.

## Performance

Three paired warm-namespace samples over the four affected raw JDs: baseline median
**0.6245 s**, proposed **0.6208 s**. The small difference is noise, not a claimed speedup.
No material overhead is observed in these samples. The predicate adds bounded vocabulary
checks and linear clause scans; cold namespace construction, model work and evidence
matching are outside this measurement. Samples were local and machine-specific; no
cache redesign, fuzzy clustering or broad normalizer optimization was attempted.

## G. Validation, hash ledger and Git diff

Final focused selection: **97 tests passed**, zero failures/errors. This includes the
existing 80-test focused scope plus six security and eleven preview tests. Smaller
safety/preview runs also passed; their counts overlap. The final UTF-8 loader regression
pins the baseline to the Stage 1 source manifest. The last added Job 16/566 assertion
also explicitly requires one retained child rather than allowing enumeration fallback.

Commands use the existing isolated Python 3.13.12 interpreter:

```text
python -B -m unittest tests.test_source_inventory_export_safety tests.test_source_aware_inventory -v
python -B -m unittest tests.test_coordinated_action_preview -v
python -B -m unittest tests.test_source_inventory_export_safety tests.test_source_aware_inventory tests.test_coordinated_action_preview tests.test_bulk_unresolved_v1 tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_jd_atomic_requirement_decomposition tests.test_post_publication_accounting tests.test_jd_structure_fingerprint_compat -v
python -B -m scripts.preview_coordinated_actions_v1 --protected-baseline venv/evidence-completeness-runtime/bulk_stage2_before.json --output NEW_preview.json
python -B -m scripts.export_source_aware_inventory_v1 --output NEW_compatibility_summary.json
git diff --check
git diff --cached --check
```

The ignored `venv/evidence-completeness-runtime/bulk_stage2.ps1` launcher configures
disposable TEMP/TMP/database paths, retrieval off, local cost metadata and the existing
startup external-network/non-disposable-SQLite audit guard. Native preview scopes also
forbid connections. Only focused historical tests needed owner context for Windows temp
ACLs. Logs are `bulk_stage2_safety.log`, `bulk_stage2_previewtests.log`,
`bulk_stage2_focused.log`, `bulk_stage2_report.log`, `bulk_stage2_compat.log` in that runtime.
No full/quick suite, package installation or external execution was performed.

The JSON ledger covers all **808** pre-existing tracked Python/JSON/Markdown files.
**807 are byte-identical.** The sole intentional exception is
`taxonomy_discovery/source_aware_inventory.py`, which adds the two-line semantic
validation call. Production policy sources, published schema/taxonomy/registry,
Stage 0/1 reports/tests and historical fixtures remain unchanged. HEAD and branch are
unchanged; no index changes, staging, commit, push, merge or other-worktree operation.
Live databases were not read or hashed. Both Git whitespace checks pass.

| File | Change |
|---|---|
| `taxonomy_discovery/source_aware_inventory.py` | Invoke closed nested semantic validation; no serialized field, native recognition or version change. |
| `taxonomy_discovery/source_inventory_safety.py` | New recursive closed-shape and historical-receipt validation. |
| `tests/test_source_inventory_export_safety.py` | Six rejection tests, including nested and resealed payloads. |
| `scripts/preview_coordinated_actions_v1.py` | New isolated native-namespace preview, raw-source comparisons, conservation, timing and protection ledger. |
| `tests/test_coordinated_action_preview.py` | Eleven actual-source and negative-control preview tests. |
| `bulk_unresolved_stage2_preview.json` | Correct UTF-8 before/after receipts for every changed parent, all-job summary and protected hashes. |
| `bulk_unresolved_stage2_review.md` | This root-cause, compatibility, safety and implementation-plan report. |

**Recommendation: PASS for investigation review.** Approve the bounded grammar and
scoring/decomposition version changes before a production patch. Full candidate-impact
validation remains BLOCKED by unavailable frozen inputs. Stop here for review.
