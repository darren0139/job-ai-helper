# Bulk Unresolved V1 Stage 1 — source-aware export contract

2026-10-17. **Stage 1 implementation: PASS for review. Full pipeline/historical replay:
BLOCKED by missing inputs. Stage 2 has not started.**

Worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch: `feat/bulk-unresolved-resolution-v1`.
HEAD remains `d37dbb5231d7211efc7b0c0297a20e34d6f597bf`.
The five Stage 0 files were already staged at entry. Their bytes and the staged diff
are preserved; this task did not stage anything or create a branch.

Scoring remains `stable-evidence-v1.17-phase6d21`, capability taxonomy v1.6 and registry
v1.3. No production parsing, matching, evidence or publication code was changed.

## A. Versioned schema and field definitions

Full export schema: `taxonomy_discovery/source_aware_inventory.schema.json`, JSON Schema
2020-12, `$id = urn:job-ai-helper:source-aware-unresolved-inventory:v1`.
Contract version: `source-aware-unresolved-inventory-v1`.

The implementation is an offline inventory adapter, not a resolver, publisher or
database schema. It calls the existing `canonicalise_requirements`,
`resolve_requirement_with_production_knowledge`, `technology_requirement_structure`
and `offline_execution`. It consumes the same fixture/regression-corpus shape already
used by Stage 0. Native taxonomy, registry, identity-scope and rejected-rule diagnostics
are retained without approving triage routes or creating governance drafts.

### Envelope and views

| Field | Definition |
|---|---|
| `schema_version` | Export contract identity, independent of scoring/taxonomy versions. |
| `schema_fingerprint` | SHA-256 of the exact local schema file bytes. |
| `export_fingerprint` | SHA-256 of canonical sorted-key JSON of the entire exported payload except this field. No timestamp or absolute machine path. This is integrity/reproducibility metadata, not an approval signature. |
| `knowledge_identity` | Current native versions plus hashes of taxonomy, registry, resolver, scope, structured matching and scorer sources used for diagnostics. |
| `counts.unique_jobs` | Distinct job identifiers across all views. Alternate views are not independent jobs. |
| `counts.distinct_source_views` | Unique input views after exact complete-view deduplication. |
| `counts.records` | Export records across explicitly separate cohorts; not a count of independent requirements or jobs. |
| `counts.duplicate_input_views` | Repeated identical input views excluded from record/allocation counts. Physical references are retained without duplicate references. |
| `views[].view_id` | Stable digest of the original complete input view, including its cohort, rows, versions and available raw JD. Different scopes/receipts remain different views. |
| `views[].cohort` | `saved_primary`, `saved_alternate`, or `raw_jd_only`. Saved rows never receive raw-only provenance. |
| `views[].references` | Allowlisted tracked fixture, file SHA-256, zero-based job index and row-container description. Derived references explicitly name `canonicalise_requirements({}, frozen_inputs.raw_jd_text).requirements`. |
| `views[].source_versions` | Versions actually supplied by the saved view, or current match plus native canonicalization versions for a derived view. An empty historical version map remains empty. |
| `views[].raw_jd_reference` | Availability in this view, SHA-256 of exact UTF-8 raw JD text, and its fixture location. Full raw documents are not duplicated into the export. |
| `views[].record_ids` | Records belonging to this view only. |
| `views[].source_allocations` | Native per-parent `source_group_fraction` sums across contributing occurrences, plus explicit accounting status. No new scoring weights. |

### Requirement records

| Field | Definition |
|---|---|
| `record_id` | Digest of view identity, canonical requirement ID and original allowlisted requirement payload. Distinct from the original canonical requirement ID. |
| `job_id`, `requirement_id`, `view_id` | Original job/canonical identity and explicit source-view linkage. Same canonical ID in another job or cohort does not merge records. |
| `requirement.text`, `atomic_focus`, `atomic_focus_key` | Exact supplied fields. Missing atomic focus is not filled in and presented as historical fact. |
| `requirement.parent_text`, `sources`, `source_provenance` | Exact available native parent/source data. Every supplied parent occurrence is retained, including non-contributing occurrences; no representative-parent collapse. |
| Each parent occurrence | Original `parent_occurrence_id`, `parent_text`, `raw_parent_text`, `source`, `profile_field`, `source_group_fraction`, `grounding`, and `contributes_scoring_allocation`, when present. |
| `grounding` | Complete supplied native grounding object, including kind, raw span/line/sentence indices, sentence text, section, section heading/detection/reason and structure version. Absent metadata remains absent. |
| Parent/atomic fields | Original `parent_requirement_id`, `atomic_group_id`, `scoring_parent_occurrence_id`, `is_atomic`, `decomposition`, `scope`, `group_weight_fraction`. No decomposition or identity repair. |
| Importance/eligibility fields | Original `importance`, semantic type, scoring/evidence/tailoring eligibility, rule, credential policy and explicit-only flag, when available. |
| Structured-match fields | Existing required terms, group mode and match kind, when supplied. They are not reconstructed from a historical label. |
| `native_structure` | Exact current `technology_requirement_structure` result. `mode` is `all`, `any`, or null. Null remains unknown/unavailable; examples are not promoted to mandatory children. |
| `qualifier_observations` | Lexical optional/negative cues only. They do not replace native importance, ALL/ANY semantics or modality policy. Mixed obligations retain their original complete wording and native scope diagnostics. |
| `original_requirement_fingerprint` | Digest of original allowlisted source input before privacy redaction. |
| `exported_requirement_fingerprint` | Digest of the actually exported, potentially redacted requirement. |
| `native_resolution` | Current knowledge status, capability/technology identity, resolution source and recognition reason, with native taxonomy/registry/identity diagnostics. No evidence decision from empty evidence is presented as a recognition failure. |
| `evidence.stored_receipt` | Optional historical label/value/selected-row count, explicitly marked as a stored receipt. No selected resume text, candidate profile or full evidence payload is exported. |
| `evidence.evaluation` | `NOT_RUN`. Historical credit is not current verification. The tracked fixture adapter cannot certify complete candidate inputs. |
| `source_completeness` | Presence of parent provenance and required occurrence fields, plus locating available raw parent text within this view's raw JD after whitespace normalization. Missing inputs/conflicts are explicit blockers. |
| `readiness` | Separate current native probe, source-complete recognition readiness, current full-pipeline readiness and historical reproduction readiness. See below. |
| `privacy` | Whether exported text was redacted; diagnostics were computed locally from original JD input before redaction. Identifiers remain intact. |
| `stage2_diagnostic` | Diagnostic flag for finite coordinated-verb fragments. It does not change their text, source, weight, identity or resolution. |

JD and parent fields use explicit allowlists. Candidate evidence, raw resume text,
profiles and arbitrary unknown payload fields are not exported. The contract preserves
the available native JD fields; it is not a lossless archive of the entire saved analysis.

### Readiness and conservation semantics

- `source_completeness.status = COMPLETE_AVAILABLE_SOURCE` means the specified source
  checks passed for available JD provenance. It does not assert a complete original
  extracted profile, complete semantic understanding or any candidate knowledge.
- Every record can carry the result of a current native probe on its available input.
  Partial saved input is still flagged `PARTIAL_SOURCE_CONTEXT`; a successful or
  unsuccessful probe does not make historical provenance complete.
- `READY_CURRENT_INPUT` means the exported source-bearing input is available for
  current recognition-only diagnostics, not that its identity is recognized.
- `BLOCKED_REDACTED_EXPORT` prevents a redacted payload from being advertised as an
  exact replayable copy. Trusted originals are needed to repeat that input exactly.
- `current_full_pipeline` remains BLOCKED when original extracted profile, full frozen
  candidate evidence/context, or the view's raw JD is absent.
- `historical_reproduction` additionally records missing original version identity,
  differing historical implementation, or the derived raw-only view's nonhistorical
  nature. Re-running current code is never represented as executing the old algorithm.
- Native source fractions and `group_weight_fraction` have different meanings. Source
  fractions are diagnostic allocation provenance, never a second weighting engine.
  Parent sums distinguish `CONSERVED`, `NON_CONTRIBUTING_PROVENANCE_ONLY`, partial
  retained allocation, over-allocation and unavailable/invalid fractions. Non-contributing
  merged-parent provenance is retained even if its contributing sum is zero.
- Over-allocation and invalid contributing fractions fail validation. Partial source
  context is reportable, not silently repaired. No missing fraction is invented.

The validator applies the schema, export/requirement fingerprints, unique view/record
identities, canonical-ID linkage, record/view membership, counts, parent accounting
and readiness/blocker consistency. It rejects asserted complete evidence/profile inputs
that this Stage 1 adapter cannot certify. It does not authenticate human authorship,
approval, the original model extraction or unprovided historical execution environments.

## B. Working offline implementation and safe CLI

`taxonomy_discovery/source_aware_inventory.py` provides:

- `fixture_views`: only the two allowlisted tracked fixture formats; separate saved
  and derived raw-only views, never live database access.
- `record_for`, `source_state`, `allocations`: source-aware records and native diagnostics.
- `build_export`: deterministic exact-view deduplication, all parent occurrences and
  source/version identity; refuses conflicting canonical IDs within one view.
- `validate_export`: schema and semantic integrity/accounting checks.
- `compact_summary`: small default artifact with source hashes, cohort counts and
  explicit Stage 2 source references; no full JD/resume corpus copied by default.

`scripts/export_source_aware_inventory_v1.py` checks fixture tracking and writes only
new output paths within this worktree. Existing artifacts, outside paths and overlapping
summary/detail outputs are rejected. No database source option, provider option,
refresh, persistence, approval or publication route is exposed.

```text
python -B -m scripts.export_source_aware_inventory_v1 --output NEW_summary.json
python -B -m scripts.export_source_aware_inventory_v1 --output NEW_summary.json --records-output NEW_records.json
```

The second command explicitly opts into the larger, redacted JD-only records. No
detailed records artifact was added to the repository during Stage 1: the complete
export was built and schema-validated in memory, and only the compact summary was saved.
The summary is identified as `compact_summary_not_full_export`, with its own summary
version and a fingerprint reference to the full export. It is not itself a document
conforming to the full-record schema.

Privacy redaction applies to exported contacts, telephone-like text and common secret
formats throughout free text, including parent/grounding diagnostics. Structured IDs
and hashes are not rewritten. This is a conservative heuristic, not a de-identification
guarantee; allowlisting and omitting candidate payloads are the primary controls.

## C. Before/after completeness and readiness

The improvement is the explicit export contract and validated explanation of what is
available. It is **not** acquisition of missing historical inputs or a recognition-policy fix.

| Cohort | Rows | Original parent provenance available | Stage 1 source-complete records | Exported recognition readiness | Full pipeline/historical reproduction |
|---|---:|---:|---:|---|---|
| Saved primary | 727 | 0 | 0 | 724 partial; 3 redacted/blocked | All blocked |
| Saved alternate | 727 | 0 | 0 | 723 partial; 4 redacted/blocked | All blocked |
| Newly canonicalized raw-only | 716 | 716 | 716 | 711 ready-current-input; 5 redacted/blocked | All blocked |

These are 90 distinct source views of **30 unique jobs**, totaling 2,170 view records.
The alternate 727 rows are not another independent corpus. Exact duplicate input views
produce one record set and do not double parent allocations; all physical source
references remain associated with the view.

Current native status remains 536 unresolved / 191 capability-resolved in each saved
cohort; raw-only remains 519 unresolved / 191 capability-resolved / 6 technology
identities. The source-only exporter grants no evidence credit and changes no result.

Job 632 Node.js/MongoDB/Keycloak, Job 16 Python/SQL and Job 146 JavaScript exercise the
provenance-sensitive identity controls. Historical records remain without provenance.
The raw-only records independently retain native grounding and current recognition.
They are linked for comparison by job/canonical identity, never merged into one claim
about historical source completeness.

## D. Missing inputs and blockers

| Blocker | Affected scope | What can still be done |
|---|---|---|
| `SOURCE_PROVENANCE_UNAVAILABLE` | All 727 saved-primary and 727 saved-alternate rows | Current native probe on exactly that partial input; no source-complete or historical claim. |
| `RAW_JD_UNAVAILABLE_IN_THIS_VIEW` | Saved alternate | Inspect existing row/parent fields; do not borrow the primary fixture's raw text into its history. |
| `ORIGINAL_EXTRACTED_JD_PROFILE_UNAVAILABLE` | Every view | Raw-only current canonicalization is possible only where raw JD is supplied; not original extraction replay. |
| `COMPLETE_FROZEN_CANDIDATE_EVIDENCE_UNAVAILABLE` | Every view | Preserve historical label/count as a receipt; no authoritative evidence evaluation or full Job Match recomputation. |
| `ORIGINAL_ANALYSIS_VERSIONS_UNAVAILABLE` | Saved alternate | Current diagnostic identity is recorded separately; original policy execution remains unknown. |
| `HISTORICAL_IMPLEMENTATION_NOT_REPRODUCED_BY_CURRENT_CODE` | Saved primary's v1.16/v1.5 analyses | Probe with explicitly recorded current v1.17/v1.6 code; do not label it historical reproduction. |
| `DERIVED_RAW_ONLY_VIEW_IS_NOT_HISTORICAL_ANALYSIS` | Raw-only cohort | Source-complete current recognition-only diagnostics, subject to redaction. |
| `EXPORTED_JD_TEXT_REDACTED` | 3 saved-primary, 4 alternate and 5 raw-only records | Use source references in a separately trusted/local workflow; exported redacted text is not exact replay input. |

More specific missing-parent-field/raw-grounding blockers are supported and retained
per occurrence. No additional data is necessary to complete Stage 1. Obtaining original
profiles, full candidate inputs or live snapshots is outside this adapter and would
require a separately approved read-only export plan. None was attempted.

## E. Focused acceptance and protection

The final focused selection passes **80 tests**, including 14 Stage 1 contract tests,
existing Stage 0 safeguards, V1.1 API completeness/recovery, native decomposition,
historical accounting and exact fingerprint compatibility. The earlier standalone
Stage 1 run passed 12 tests before two additional rejection tests were added.
These counts overlap; they must not be added as unique tests.

The first ALL/ANY test used a phrase outside the native supported grammar and correctly
received null mode. The test now exercises supported ALL/ANY inputs and separately
asserts that the unsupported phrase remains null. No production parser or existing
assertion was weakened. Multiple parent occurrences, valid conservation, rejected
over-allocation, exact duplicates, alternate views, repeat/reordered exports, privacy,
false completeness, schema tampering and overwrite protection are covered.

The API suite preserves actual Java REST endpoint recognition, design versus development,
PostgREST-only authorship rejection and protocol/source-selection guards. Stage 0's
generic-data versus DSA recognition and evidence negative controls also pass.

Commands use the existing isolated Python 3.13.12 interpreter:

```text
python -B -m unittest tests.test_source_aware_inventory -v
python -B -m unittest tests.test_source_aware_inventory tests.test_bulk_unresolved_v1 tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_jd_atomic_requirement_decomposition tests.test_post_publication_accounting tests.test_jd_structure_fingerprint_compat -v
python -B -m scripts.export_source_aware_inventory_v1 --output NEW_summary.json
git diff --check
git diff --cached --check
```

Interpreter: `venv/evidence-completeness-runtime/environment/Scripts/python.exe`.
The task-owned ignored `bulk_stage1.ps1` launcher and `bulk_stage1_*.log` files are in
that runtime. The existing startup guard blocks external sockets/DNS and non-disposable
SQLite; native offline diagnostic scopes block socket connections as well. Historical
tests use disposable paths and the owner context required by their Windows temp ACLs.
No package installation, full discovery, quick/full suite, model, embedding, Chroma,
Tavily or external network operation was performed.

All **804** protected pre-existing tracked Python/JSON/Markdown file hashes match the
entry ledger, including the staged Stage 0 artifacts, production sources, taxonomy,
registry and historical fixtures. The entry ledger also pins HEAD and the SHA-256 of
the staged binary diff. The staged diff remains identical. No live database hash or
live snapshot preservation claim is substituted for the fixture/disposable checks.
Both Git whitespace checks pass. No branch, commit, push, merge or staging action.

## F. Stage 2 handover — diagnostic cases only

Both jobs share canonical child `req_95479a28180a`, but have different source parents:

| Job | Current child | Raw parent and exact grounding |
|---|---|---|
| 359 | `Design, develop` | `Design, develop, and maintain embedded software modules supporting waveform processing systems.` Parent `srcgrp_af665d2ba39b`, span `jdspan_6bf448904ec3`, responsibilities line 6 / sentence 1. |
| 479 | `Design, develop` | `Design, develop and maintain scalable full-stack applications using React, TypeScript and Python technologies.` Parent `srcgrp_b729779d18ec`, span `jdspan_6dc32ab3a3a0`, responsibilities line 4 / sentence 1. |

Each fragment's source fraction is .5; the sibling clause retains the same source
parent. Stage 1 preserves both records, full raw parent/section context and allocations.
Other diagnostic variants in Jobs 16 and 566 are listed with explicit fixture/cohort
references in the compact summary, without treating them as independently verified fixes.

Likely function chain for the later investigation:
`canonicalise_requirements` → `_requirement_sources` →
`_split_single_requirement_clause` → `_split_non_preference_clause` →
`_split_safe_independent_and_pair`. The latter checks the second clause's action prefix
and minimum token counts but can leave a first clause with coordinated verbs and no
object. Inspect actual source receipts before selecting any correction. Do not add an
alias for the fragment or infer backend expertise from it.

Stage 2 acceptance must include:

1. The exact two source parents above, preserving canonical provenance and testing
   whether a complete shared-object obligation is retained.
2. A true independent-clause control, which must still split when both obligations
   have independent objects; no blanket disabling of `and` decomposition.
3. Design/implementation and consumption/development distinctions, REST/gRPC mixed
   protocols, optional/alternative examples and negation.
4. Conserved native parent allocations, multiple parent occurrences, no duplicate
   scoring credit and no source-parent collapse.
5. Existing native tests `test_source_group_fraction_is_provenance_not_a_second_weighting_engine`,
   `test_exact_duplicate_compound_parent_does_not_add_second_allocation`,
   `test_partially_overlapping_compound_parents_do_not_transitively_collapse`,
   coherent-example controls and whitespace/line-wrap metamorphic tests.
6. Explicit scoring/decomposition/currentness-version review before any production
   implementation. Full historical/current match-impact claims still require original
   frozen inputs. No Stage 2 production change is authorized by this handover.

## G. Diff summary and recommendation

Six new, unstaged Stage 1 files:

| File | Purpose |
|---|---|
| `taxonomy_discovery/source_aware_inventory.py` | Reusable source-aware fixture adapter, record builder, validator and compact summary. |
| `taxonomy_discovery/source_aware_inventory.schema.json` | Versioned export contract; not a published capability-taxonomy or database schema. |
| `scripts/export_source_aware_inventory_v1.py` | Bounded offline CLI with explicit detailed-output opt-in and overwrite protection. |
| `tests/test_source_aware_inventory.py` | Fourteen focused contract/acceptance tests. |
| `bulk_unresolved_stage1_summary.json` | Compact validated cohort/readiness summary and Stage 2 source references. |
| `bulk_unresolved_stage1_contract.md` | Schema definitions, comparisons, blockers, validation and handover. |

Only task-owned ignored launcher, logs, guard scratch and baseline verification state
were also created. Existing investigation files remain untouched and retain their
original staged state. **Recommend PASS for Stage 1 review**, with full pipeline and
historical replay explicitly BLOCKED by the listed unavailable inputs. Stop before Stage 2.
