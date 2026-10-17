# Bulk Unresolved V1 Stage 2B — evidence completeness and scoring safety

## Verdict

**PASS for the investigation; BLOCKED for direct production implementation of Stage 2.**
Retaining the full text does not enforce all requested actions. Independently grounded
atomic children do not fix that problem by themselves either. Coordinated-action
evidence completeness must accompany any production decomposition change.

No production parser, scoring policy, version constant, taxonomy, registry, résumé,
published snapshot or existing investigation file was changed. No historical/live
Job Match impact is asserted. This report supersedes only the evidence-safety part
of Stage 2's implementation recommendation, while preserving its parsing findings.

## Scope and method

Verified repository `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`,
branch `feat/bulk-unresolved-resolution-v1`, HEAD
`5756d5f840dd09e3c0c48c6fcfc9298246a8790b`. Worktree listing was read from this
checkout; no separate checkout was accessed. Entry dirt was one modified tracked
file and six untracked Stage 2 files; the index was empty.

The 30-job raw-JD fixture is replayed explicitly as UTF-8. The Stage 2B preview uses
only raw JD fields from that fixture; it does not evaluate stored candidate rows. There are 76
synthetic parent scenarios and 16 focused controls. Hypothetical project bullets
are attributable to `resume_profile.projects[0].bullets[i]`; they are neither
real candidate claims nor verified candidate gold. No model, network or live DB
calls, complete runner or quick runner were used.

The companion JSON records exact rows, IDs, action/object character offsets in the
original raw parent, source occurrence receipts, recognition decisions, selected
synthetic evidence IDs/sources, stage labels, recovery receipts, and both deterministic
keyword and initially-missing keyword inputs. Key ordering and content are deterministic;
there are no timestamps, timings or generated overall Job Match scores.

In each result, `evaluator_label`/`evaluator_reason` are an independent resolver probe
over the supplied synthetic text (newline-delimited for multiple bullets). They do
not drive selection or replace the native result. `native_label`, `labels_by_stage`
and `selected_evidence` come from the executed single-source scoring path. Separate
`forced_api_evaluator_only` controls explicitly bypass recognition for diagnosis.

**A_full native** is Stage 2's isolated full-parent representation passed through the
unchanged scorer. **A diagnostic gate** additionally checks fixture-declared ownership
against the actions required by that parent. This is an executable test oracle, not
an implemented natural-language ownership detector. An incomplete native DIRECT is
marked `REVIEW_REQUIRED_NO_APPROVED_PARTIAL_RULE`, with a null effective label. It is
not silently converted to WEAK or NONE. Native lower labels are displayed unchanged
for diagnosis; this does not approve their partial-obligation credit.

**B_atomic native** uses three preview-only children, each with the exact original
shared object and its modifiers. Their action and inherited-object offsets are
explicitly grounded in the original JD. Source parent IDs, raw spans, atomic groups,
importance and eligibility remain intact. Each child gets one third of the original
allocation (the final float receives the residual to total exactly one). Child text
is explicitly a derivation, not falsely claimed to be a contiguous original span.
The same oracle is applied separately to each selected row and action. It never
unions three evidence rows to complete a single full parent. No B rewrite is applied
to optional, negative, alternative or mixed-protocol controls outside the finite
five-parent admission; they retain the native representation and behavior.

## Actual scoring/evidence path

Source references below are repository-relative for readability; all reside under
the verified absolute checkout above.

1. `analysis_stability/stable_evidence_scoring.py::canonicalise_requirements` forms
   requirements, focus keys, parent occurrence receipts and groups. Stage 2's isolated
   namespace modifies only preview parsing. Stage 2B derives B rows in fresh copies.
2. `build_deterministic_keyword_match` retrieves résumé rows and proposes lexical
   labels. `link_requirement_matches` verifies evidence against the current synthetic
   profile; `apply_structured_requirement_matches` and `validate_linked_matches`
   apply the existing structured and evidence constraints.
3. `_apply_capability_single_row_reselection` selects a single attributable source.
   `tailoring/phase6d_stable_scoring_adapter.py::cap_requirement_with_taxonomy`
   resolves the capability and caps preliminary credit. An unrecognized requirement
   has no taxonomy cap; a high-overlap unresolved requirement can still be DIRECT.
4. `tailoring/capability_taxonomy.py::_evaluate_capability_record` uses topic evidence
   tiers for embedded firmware, full-stack integration and data processing. Those
   tiers do not require design/development/maintenance/deployment ownership separately.
   Embedded firmware's `any_terms` tier accepts ESP32/GPIO/interrupts; full-stack needs
   frontend/React/UI plus backend/API/database/Supabase/PostgREST terms.
5. `_api_evidence_label` separately implements the approved API authorship/design
   correction. Consumption cannot prove endpoint implementation. Protocol-specific
   guards operate only when that capability is actually resolved/evaluated.
6. `_apply_capability_none_recovery` can replace NONE with DIRECT from one canonical
   capability receipt even at zero lexical overlap. Weak zero-overlap recovery is
   normally prohibited, with the existing bounded API implementation-without-design
   exception. A completeness cap only before recovery would be bypassable.
7. The preview stops before `compute_deterministic_alignment`. Code inspection of
   `_weighted_coverage` shows the downstream consequence: it dynamically uses
   `1 / eligible_row_count_in_atomic_group`, not stored fraction metadata, then
   multiplies by the native match value. Thus a maintenance-only [.5 NONE, .5 DIRECT]
   becomes a full-allocation DIRECT under unchecked A; B's three DIRECT rows also
   consume the entire allocation. These are synthetic parent-allocation observations,
   not historical or live job scores. A focused regression verifies this group-count
   behavior using synthetic rows.

## Corpus and recognition observations (no candidate credit)

| Raw-JD requirements | Baseline | A full | B atomic |
|---|---:|---:|---:|
| All 30 jobs | 716 | 711 | 721 |
| Job 16 | 35 | 34 | 36 |
| Job 359 | 30 | 29 | 31 |
| Job 479 | 34 | 33 | 35 |
| Job 566 | 29 | 27 | 31 |

The other 26 jobs have unchanged representation counts. Exactly the same five source
parents are admitted. Baseline object-free design fragments remain unresolved. A and
all B children recognize embedded.firmware (359), fullstack.integration (479) and
data.processing (566 cloud); pipelines (16) and backend services/API (566) remain
UNRESOLVED. Recognition is not evidence support.

For all five parents, group and source allocation are 1 -> 1 -> 1, original source
grounding is preserved and canonical identities change. B's lifecycle child retains
the old object-bearing child's ID; its two object-grounded siblings are new. A gets
a new full-parent ID. Reused fragment IDs in different jobs never imply shared source
identity. JSON preserves each `(job_id, parent_occurrence_id)` boundary. No globally
merged B corpus is fabricated: counts are a bounded per-source replacement preview.
Future production merging/deduplication must retain every occurrence and prevent
cross-parent allocation duplication; group metadata alone does not prove that.

## Five actual source parents and synthetic candidate labels

In the following tables D=direct, T=transferable, W=weak, N=none. Ordered labels
correspond to the displayed rows in each representation. `BLOCK` means incomplete
native DIRECT is withheld pending policy review; `keep` is a diagnostic native-label
display, not approval of a lower partial-credit tier. B has three gate entries.
Exact hypothetical evidence strings and initially-missing-input comparisons are in
the companion JSON. Build/develop equivalence in ownership receipts is explicitly
fixture-declared, not a new production synonym or credit rule. Cloud's third action
is DEPLOY, not MAINTAIN; both maintenance-only and deployment-only controls are included.

### Job 16 — srcgrp_e822a3bdbba5

> Design, build, and maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds.

| Representation | Requirement text | Weight | Canonical ID | Native recognition |
|---|---|---:|---|---|
| A_full | Design, build, and maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds | 1 | `req_acdd8f777d09` | UNRESOLVED |
| B_atomic | Design scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds | 0.333333 | `req_0ca573a5ffc5` | UNRESOLVED |
| B_atomic | Build scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds | 0.333333 | `req_fc0b5a402494` | UNRESOLVED |
| B_atomic | Maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds | 0.333333 | `req_191dd0c2eef9` | UNRESOLVED |
| baseline | Design, build | 0.5 | `req_fd6f5ea4f9bf` | UNRESOLVED |
| baseline | maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds | 0.5 | `req_191dd0c2eef9` | UNRESOLVED |

| Synthetic scenario | Baseline | A native | A gate | B native | B gates |
|---|---|---|---|---|---|
| maintenance_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/keep |
| development_only | N/D | D | BLOCK | D/D/D | BLOCK/keep/BLOCK |
| design_only | D/D | D | BLOCK | D/D/D | keep/BLOCK/BLOCK |
| design_development_no_lifecycle | D/D | D | BLOCK | D/D/D | keep/keep/BLOCK |
| all_requested_actions | D/D | D | keep | D/D/D | keep/keep/keep |
| generic_software | N/N | N | keep | N/N/N | keep/keep/keep |
| technology_usage_no_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| api_consumption | N/N | N | keep | N/N/N | keep/keep/keep |
| postgrest_supabase_integration | N/N | N | keep | N/N/N | keep/keep/keep |
| java_rest_authorship | N/N | N | keep | N/N/N | keep/keep/keep |
| incomplete_design | D/D | D | BLOCK | D/D/D | BLOCK/keep/BLOCK |
| negated_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| zero_overlap_topic | N/N | N | keep | N/N/N | keep/keep/keep |
| lifecycle_action_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/keep |
| three_actions_separate_rows | D/D | D | BLOCK | D/D/D | keep/BLOCK/keep |

### Job 359 — srcgrp_af665d2ba39b

> Design, develop, and maintain embedded software modules supporting waveform processing systems.

| Representation | Requirement text | Weight | Canonical ID | Native recognition |
|---|---|---:|---|---|
| A_full | Design, develop, and maintain embedded software modules supporting waveform processing systems | 1 | `req_1933523263de` | embedded.firmware |
| B_atomic | Design embedded software modules supporting waveform processing systems | 0.333333 | `req_4f9d6a4ed126` | embedded.firmware |
| B_atomic | Develop embedded software modules supporting waveform processing systems | 0.333333 | `req_9c17aae739ff` | embedded.firmware |
| B_atomic | Maintain embedded software modules supporting waveform processing systems | 0.333333 | `req_bda00d6856dc` | embedded.firmware |
| baseline | Design, develop | 0.5 | `req_95479a28180a` | UNRESOLVED |
| baseline | maintain embedded software modules supporting waveform processing systems | 0.5 | `req_bda00d6856dc` | embedded.firmware |

| Synthetic scenario | Baseline | A native | A gate | B native | B gates |
|---|---|---|---|---|---|
| maintenance_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/keep |
| development_only | D/D | D | BLOCK | D/D/D | BLOCK/keep/BLOCK |
| design_only | D/D | D | BLOCK | D/D/D | keep/BLOCK/BLOCK |
| design_development_no_lifecycle | D/D | D | BLOCK | D/D/D | keep/keep/BLOCK |
| all_requested_actions | D/D | D | keep | D/D/D | keep/keep/keep |
| generic_software | N/N | N | keep | N/N/N | keep/keep/keep |
| technology_usage_no_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| api_consumption | N/N | N | keep | N/N/N | keep/keep/keep |
| postgrest_supabase_integration | N/N | N | keep | N/N/N | keep/keep/keep |
| java_rest_authorship | N/N | N | keep | N/N/N | keep/keep/keep |
| incomplete_design | D/D | D | BLOCK | D/D/D | BLOCK/keep/BLOCK |
| negated_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| zero_overlap_topic | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| lifecycle_action_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/keep |
| three_actions_separate_rows | D/D | D | BLOCK | D/D/D | keep/keep/keep |

### Job 479 — srcgrp_b729779d18ec

> Design, develop and maintain scalable full-stack applications using React, TypeScript and Python technologies.

| Representation | Requirement text | Weight | Canonical ID | Native recognition |
|---|---|---:|---|---|
| A_full | Design, develop and maintain scalable full-stack applications using React, TypeScript and Python technologies | 1 | `req_7cf592b15461` | fullstack.integration |
| B_atomic | Design scalable full-stack applications using React, TypeScript and Python technologies | 0.333333 | `req_cf3471e38f5a` | fullstack.integration |
| B_atomic | Develop scalable full-stack applications using React, TypeScript and Python technologies | 0.333333 | `req_27725e4222ec` | fullstack.integration |
| B_atomic | Maintain scalable full-stack applications using React, TypeScript and Python technologies | 0.333333 | `req_533286e95145` | fullstack.integration |
| baseline | Design, develop | 0.5 | `req_95479a28180a` | UNRESOLVED |
| baseline | maintain scalable full-stack applications using React, TypeScript and Python technologies | 0.5 | `req_533286e95145` | fullstack.integration |

| Synthetic scenario | Baseline | A native | A gate | B native | B gates |
|---|---|---|---|---|---|
| maintenance_only | N/N | N | keep | N/N/N | keep/keep/keep |
| development_only | D/N | N | keep | N/N/N | keep/keep/keep |
| design_only | D/N | N | keep | N/N/N | keep/keep/keep |
| design_development_no_lifecycle | D/N | N | keep | N/N/N | keep/keep/keep |
| all_requested_actions | D/N | N | keep | N/N/N | keep/keep/keep |
| generic_software | N/N | N | keep | N/N/N | keep/keep/keep |
| technology_usage_no_ownership | D/N | N | keep | N/N/N | keep/keep/keep |
| api_consumption | N/N | N | keep | N/N/N | keep/keep/keep |
| postgrest_supabase_integration | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| java_rest_authorship | N/N | N | keep | N/N/N | keep/keep/keep |
| incomplete_design | D/N | N | keep | N/N/N | keep/keep/keep |
| negated_ownership | D/N | N | keep | N/N/N | keep/keep/keep |
| zero_overlap_topic | N/N | N | keep | N/N/N | keep/keep/keep |
| lifecycle_action_only | N/N | N | keep | N/N/N | keep/keep/keep |
| all_actions_explicit_layers | D/D | D | keep | D/D/D | keep/keep/keep |
| three_actions_separate_rows | D/N | N | keep | N/N/N | keep/keep/keep |

### Job 566 — srcgrp_ff65d3ef26a4

> · Design, build and maintain scalable backend services and API.

| Representation | Requirement text | Weight | Canonical ID | Native recognition |
|---|---|---:|---|---|
| A_full | · Design, build and maintain scalable backend services and API | 1 | `req_3a7798a7fae0` | UNRESOLVED |
| B_atomic | Design scalable backend services and API | 0.333333 | `req_eea71bebe395` | UNRESOLVED |
| B_atomic | Build scalable backend services and API | 0.333333 | `req_a9f801ec51d7` | UNRESOLVED |
| B_atomic | Maintain scalable backend services and API | 0.333333 | `req_86462bb5cd2a` | UNRESOLVED |
| baseline | · Design, build | 0.5 | `req_fd6f5ea4f9bf` | UNRESOLVED |
| baseline | maintain scalable backend services and API | 0.5 | `req_86462bb5cd2a` | UNRESOLVED |

| Synthetic scenario | Baseline | A native | A gate | B native | B gates |
|---|---|---|---|---|---|
| maintenance_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/keep |
| development_only | N/D | T | keep | D/D/D | BLOCK/keep/BLOCK |
| design_only | D/D | D | BLOCK | D/D/D | keep/BLOCK/BLOCK |
| design_development_no_lifecycle | D/D | D | BLOCK | D/D/D | keep/keep/BLOCK |
| all_requested_actions | D/D | D | keep | D/D/D | keep/keep/keep |
| generic_software | N/N | N | keep | N/N/N | keep/keep/keep |
| technology_usage_no_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| api_consumption | N/N | N | keep | N/N/N | keep/keep/keep |
| postgrest_supabase_integration | N/N | N | keep | N/N/N | keep/keep/keep |
| java_rest_authorship | N/N | N | keep | N/N/N | keep/keep/keep |
| incomplete_design | D/D | D | BLOCK | D/D/D | BLOCK/keep/BLOCK |
| negated_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| zero_overlap_topic | N/N | N | keep | N/N/N | keep/keep/keep |
| lifecycle_action_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/keep |
| three_actions_separate_rows | D/D | D | BLOCK | D/D/D | keep/BLOCK/keep |

### Job 566 — srcgrp_8ac40e9b5dc4

> · Design, develop and deploy cloud-based applications with large-scale data processing capabilities.

| Representation | Requirement text | Weight | Canonical ID | Native recognition |
|---|---|---:|---|---|
| A_full | · Design, develop and deploy cloud-based applications with large-scale data processing capabilities | 1 | `req_490d136c0a8a` | data.processing |
| B_atomic | Design cloud-based applications with large-scale data processing capabilities | 0.333333 | `req_ba0fd2150d94` | data.processing |
| B_atomic | Develop cloud-based applications with large-scale data processing capabilities | 0.333333 | `req_c27c1a8caa81` | data.processing |
| B_atomic | Deploy cloud-based applications with large-scale data processing capabilities | 0.333333 | `req_9f75638e8bda` | data.processing |
| baseline | · Design, develop | 0.5 | `req_95479a28180a` | UNRESOLVED |
| baseline | deploy cloud-based applications with large-scale data processing capabilities | 0.5 | `req_9f75638e8bda` | data.processing |

| Synthetic scenario | Baseline | A native | A gate | B native | B gates |
|---|---|---|---|---|---|
| maintenance_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| development_only | D/D | D | BLOCK | D/D/D | BLOCK/keep/BLOCK |
| design_only | D/D | D | BLOCK | D/D/D | keep/BLOCK/BLOCK |
| design_development_no_lifecycle | D/D | D | BLOCK | D/D/D | keep/keep/BLOCK |
| all_requested_actions | D/D | D | keep | D/D/D | keep/keep/keep |
| generic_software | N/N | N | keep | N/N/N | keep/keep/keep |
| technology_usage_no_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| api_consumption | N/N | N | keep | N/N/N | keep/keep/keep |
| postgrest_supabase_integration | N/N | N | keep | N/N/N | keep/keep/keep |
| java_rest_authorship | N/N | N | keep | N/N/N | keep/keep/keep |
| incomplete_design | D/D | D | BLOCK | D/D/D | BLOCK/keep/BLOCK |
| negated_ownership | D/D | D | BLOCK | D/D/D | BLOCK/BLOCK/BLOCK |
| zero_overlap_topic | N/N | N | keep | N/N/N | keep/keep/keep |
| lifecycle_action_only | N/D | D | BLOCK | D/D/D | BLOCK/BLOCK/keep |
| three_actions_separate_rows | D/D | D | BLOCK | D/D/D | keep/keep/keep |

## Counterexamples and interpretation

- **359 maintenance only:** baseline N/D at .5/.5; A D at 1; B D/D/D at thirds.
  Only maintenance is declared owned. A's oracle blocks full DIRECT; B's oracle blocks
  design and development DIRECT while leaving the actually owned maintenance child.
  Development-only, design-only and design+development similarly fail completeness.
- **359 zero-overlap:** `Configured ESP32 GPIO interrupts.` produces NONE at the capped
  stage, then DIRECT from recovery with overlap_count=0. Baseline recovers only its
  .5 object-bearing row; A and all B children recover full allocation. One real source
  receipt exists, but it does not establish the required three responsibilities.
  Recovery must obey completeness; it is not a legitimate exemption for generic
  coordinated-action ownership.
- **16 pipelines:** no capability is recognized, yet lexical overlap with the long
  shared object makes maintenance-only, design-only, negated ownership and end-user
  usage evidence DIRECT on A and every B child. A taxonomy-only fix misses this path.
- **566 backend:** maintenance-only is N/D -> D -> D/D/D. Development-only is N/D ->
  T -> D/D/D. This is both a possible credit increase and an example of label shifts
  from focus-length/overlap changes. `services and API` does not establish authored
  endpoints or API interface design; the full parent remains unrecognized natively.
- **566 cloud:** maintenance-only and deployment-only both yield full A DIRECT, even
  though the actual requested conjunction is design+develop+deploy. The data.processing
  capability does not certify cloud design, application development or deployment.
- **479 over-credit:** `Integrated React with Supabase PostgREST for CRUD data access
  and authentication.` yields N/D -> D -> D/D/D. It meets full-stack topic tiers but
  does not demonstrate the three requested responsibilities. This is full-stack credit
  leakage, not a restoration of API endpoint-authorship credit.
- **479 under-credit:** the hypothetical `Designed, Developed, Maintained scalable
  full-stack applications using React, TypeScript and Python technologies.` gets A=N,
  B=N/N/N despite all actions being explicitly declared. Its row lacks the backend/API/
  database terms required by the native full-stack tier. Appending an explicit React
  frontend/Python backend ownership statement changes A to DIRECT and passes the oracle.
  Do not broaden the taxonomy incidentally to fix this separate limitation.
- **Negation and usage:** putting the shared object in a denial or end-user usage
  statement still produces native DIRECT for several non-API capabilities and unresolved
  lexical paths. Fixture receipts correctly declare no responsibility ownership.
- **Separate rows:** A selects only one of the three action bullets and the oracle
  does not union them. B could legitimately use distinct independently attributable
  action receipts only under an explicit atomic-obligation contract; it must still
  check the action on each selected row. Merely copying the object preserves the same
  topic-matching vulnerability. Selection/ranking must prefer complete admissible rows
  before credit, not select an incomplete row then hide an available complete one.

## API, design, Boolean, optionality and DSA controls

These controls distinguish forced capability evaluator results from actual native
recognition/selection. A direct evaluator probe is never presented as native recognition.

| Control | Native A labels | Native A with initially missing keywords | Forced API evaluator per source row |
|---|---|---|---|
| api_consume | N | N | N |
| api_postgrest | N | N | N |
| api_java | T | D | D |
| api_incomplete_design | W | W | W |
| api_complete_design | D | D | D |
| api_negated | N | N | N |
| api_split_sources | W | W | N/W |
| protocol_and | N | N | N |
| protocol_or | N | N | D |
| protocol_mixed_consumption | T | W | N |
| protocol_both_authored | T | W | D |
| api_lifecycle_missing | T | W | D |
| dsa_generic_data | N | N | not probed |
| optional | T | W | not probed |
| and_or_actions | D | W | not probed |
| negated_requirement | N/D | N/W | not probed |

Consumption and PostgREST integration stay NONE for endpoint authorship; actual Java
REST endpoint implementation is DIRECT at the evaluator and missing-input recovery.
The deterministic keyword path retains TRANSFERABLE for the shorter Java statement;
taxonomy caps do not upgrade an already positive lower lexical label. That is an
existing selector/threshold result, not evidence that authorship was rejected.
Design+development with implementation only remains the expressly governed WEAK;
explicit API interface design plus implementation is DIRECT. Split API source rows
stay WEAK rather than borrowing a separate design row. API negation stays NONE.

The forced API evaluator requires both authored protocols for AND, accepts the
supported alternative for OR, and rejects borrowing consumed gRPC as authored gRPC.
However, the exact `Develop REST and gRPC APIs` / `Develop REST or gRPC APIs`
native requirements are UNRESOLVED. A mixed authorship/consumption row can retain
native TRANSFERABLE despite the forced evaluator's NONE. This pre-existing recognition
boundary must not be hidden by forced-probe success or broadened incidentally here.
The forced API evaluator also returns DIRECT for design+develop+maintain with design
and implementation only: its approved special policy has no maintenance predicate.
That exact native requirement is unresolved and yields WEAK for this control; neither
result proves full lifecycle completeness.

The OR action control must not be treated as a three-action conjunction. The optional
Python clause retains its native core importance and is not made an additional mandatory
action. A negated requirement remains outside the admitted coordinated-action rewrite
and exposes native negative-text splitting; no language-policy correction is smuggled
into this preview. Generic data/SQL evidence remains NONE for DSA. Existing focused
tests additionally protect API protocol scope, structured logic and source guards.

## Recommended minimal bounded production design (not implemented)

Prefer **A plus explicit mandatory-action completeness**, subject to review of the
ownership detector and partial tiers. It preserves one parent, one allocation, one
selection boundary and fewer new canonical IDs. Adopt Stage 2's finite shared-object
admission only together with the following protections:

1. Derive explicit action/object obligations from the original grounded parent,
   retaining negation, AND/OR, optionality, scope and protocol constraints. Restrict
   admission to the reviewed grammar; uncertain structures keep their current path
   or require review. Do not infer unstated responsibilities or authored endpoints.
2. Require affirmative responsibility ownership for every mandatory action on its
   actual object before DIRECT. Capability topic recognition and technology use are
   insufficient. Preserve the existing bounded API authorship/design evaluator and
   its source/protocol restrictions; add no shortcut for PostgREST or REST consumption.
3. Make completeness a shared admissibility predicate for evidence selection,
   reselection, caps and recovery, with a final invariant after recovery. Apply it
   also to unresolved lexical DIRECT, not just taxonomy-resolved capabilities.
   Do not invent a second source selector, concatenate evidence rows or lift ceilings.
4. Emit required/supported/missing action receipts tied to the selected original
   evidence ID and source. An incomplete DIRECT must not survive. Existing expressly
   governed partial cases (API implementation without required design) keep their
   approved WEAK behavior. Other partial W/T/N dispositions require contract review;
   no universal fraction-of-actions or automatic WEAK rule is approved by this study.
5. Keep atomic B as a documented alternative if independent action credit is explicitly
   desired. It needs the same per-action ownership checks plus grounded inherited
   objects, parent/group preservation, nonduplicating merge behavior and a reviewed
   aggregation contract. One third per action is only a preview of equal allocation;
   it must not silently become a new credit policy or split alternatives into AND.

The oracle is necessary-condition coverage, not a sufficient production proof. It
does not implement tense/action scope, modality, contradictions, cross-object design,
protocol matching or optionality resolution. A lower native label displayed as `keep`
is not a finding that partial credit is safe. Stage 2 cannot be implemented directly
on the strength of retained text or these fixture-declared action receipts alone.

## Versioning, compatibility and release regressions

The proposed `stable-evidence-v1.18-phase6d22` and
`jd-atomic-requirement-decomposition-v1.2` identities can cover ONE reviewed, unreleased
coordinated parser+completeness change. A parser-only v1.18 is not a safe release.
Scorer identity must cover new evidence behavior for either A or B, including unchanged
requirement IDs whose credit changes. If v1.18 ships before completeness, the later
behavior needs a further scoring bump; do not reuse a published identity.

Scoring/cache fingerprints currently include SCORING_VERSION, taxonomy/registry and
recovery identities, but do not directly include decomposition metadata or parser
source. Therefore decomposition v1.2 alone is insufficient. A named coordinated-action
evidence policy and per-row audit metadata are recommended, with its identity covered
transitively by the scorer bump or explicitly added to currentness contracts. Keep the
approved API evidence policy identity unchanged if its implementation remains unchanged;
version recovery/reselection identities too if their governed semantics are revised.
No taxonomy/registry publication bump is justified solely by this parsing/evidence change.

Future production regression gates must assert: partial/missing/negated/non-owned actions
cannot get full DIRECT; complete same-source ownership survives; complete alternative
rows are selected without borrowing partial sources; unresolved lexical paths and
zero-overlap recovery cannot bypass completeness; AND/OR, optionality and REST/gRPC
scope remain intact; PostgREST consumption stays distinct from authored Java endpoints;
API incomplete design retains its governed WEAK; generic data remains distinct from
DSA; source eligibility/provenance and duplicate-parent allocations remain intact.
Promote the exact five-parent span/ID/weight tests and expand selection controls before
release. Exercise historical snapshot read compatibility and cache staleness under the
future version without rewriting stored snapshots. This offline corpus lacks full
frozen original profiles/evidence, so historical candidate-impact validation remains
BLOCKED and no bulk refresh is authorized.

## Focused validation and protected files

**109 distinct focused tests passed across the completed runs.** The initial combined
run executed 109: 99 passed and 10 historical-accounting tests stopped on Windows
temporary-directory ACL errors before assertions. A narrowly scoped owner-context
rerun passed all 11 selected compatibility tests (10 previously blocked plus one
overlapping currentness test). No assertion was weakened. The new preview module
has 12 tests, including exact reproduction of the saved deterministic JSON from a
fresh execution of the native pipeline. The earlier 11-test development run also
passed; its cases overlap and are not added to the unique count.

Commands (existing isolated Python 3.13.12 via the ignored launcher):

```text
python -B scripts/preview_coordinated_evidence_v1.py --protected-baseline venv/evidence-completeness-runtime/tmp/bulk_stage2b/baseline.json
python -B scripts/preview_coordinated_evidence_v1.py --protected-baseline venv/evidence-completeness-runtime/tmp/bulk_stage2b/baseline.json --output venv/evidence-completeness-runtime/tmp/bulk_stage2b/revised.json
python -B -m unittest tests.test_coordinated_evidence_preview -v
python -B -m unittest tests.test_coordinated_evidence_preview tests.test_source_inventory_export_safety tests.test_source_aware_inventory tests.test_coordinated_action_preview tests.test_bulk_unresolved_v1 tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_jd_atomic_requirement_decomposition tests.test_post_publication_accounting tests.test_jd_structure_fingerprint_compat -v
python -B -m unittest tests.test_post_publication_accounting tests.test_jd_structure_fingerprint_compat -v
git diff --check
git diff --cached --check
```

The revised JSON replaced only this turn's initial Stage 2B artifact; pre-existing
Stage 2 artifacts remain byte-identical. The saved-preview test verifies it equals
fresh execution exactly, excluding the separately verified hash ledger. Logs are
`tmp/bulk_stage2b/previewtests.log`, `focused.log` and `compat_owner.log` under the
ignored runtime. Existing compatibility regressions exercise pinned test receipts
and disposable snapshot round-trips; they do not project this change onto real jobs.
The launcher disables bytecode, sets disposable TEMP/SQLite paths and retrieval off,
and loads the existing external-network/non-disposable-SQLite guard. Preview scopes
additionally forbid all connections. No full/quick runner was invoked.

The JSON contains before/after SHA-256 for **913 entry-state files**, including every
tracked file and all six pre-existing untracked Stage 2 artifacts. All 913 must remain
byte-identical (verified after the focused runs as well). This includes the pre-existing two-line Stage 1 security integration
change in `taxonomy_discovery/source_aware_inventory.py`, all production scoring/parser
code, API V1.1, taxonomy v1.6, registry, version sources and historical fixture snapshots.
No database paths are in the hash ledger. Live DBs were neither accessed nor hashed.

## Exact worktree classifications

| Git path | Classification / action this turn |
|---|---|
| `taxonomy_discovery/source_aware_inventory.py` | Existing modified tracked file: two-line closed-payload security validation integration; preserved byte-for-byte. |
| `taxonomy_discovery/source_inventory_safety.py` | Existing untracked Stage 1 export security validator; preserved. |
| `tests/test_source_inventory_export_safety.py` | Existing untracked export-security rejection tests; preserved. |
| `scripts/preview_coordinated_actions_v1.py` | Existing untracked Stage 2 isolated parsing preview; preserved. |
| `tests/test_coordinated_action_preview.py` | Existing untracked Stage 2 preview regressions; preserved. |
| `bulk_unresolved_stage2_preview.json` | Existing untracked Stage 2 raw-source/recognition artifact; preserved. |
| `bulk_unresolved_stage2_review.md` | Existing untracked Stage 2 report; preserved. |
| `scripts/preview_coordinated_evidence_v1.py` | New Stage 2B native-path, grounded B and fixture-oracle preview; investigation only. |
| `tests/test_coordinated_evidence_preview.py` | New Stage 2B counterexample/contract/conservation/reproducibility regressions; investigation only. |
| `bulk_unresolved_stage2b_preview.json` | New deterministic Stage 2B executed receipts and full protected hash ledger. |
| `bulk_unresolved_stage2b_review.md` | New comparative Stage 2B report. |

No unrelated tracked edits are present. Ignored task-owned runtime additions are the
`venv/evidence-completeness-runtime/bulk_stage2b.ps1` launcher and its disposable
`tmp/bulk_stage2b/` ledger, logs, report builder and test scratch. Those are not commit
candidates. No commit, staging, push, merge, reset, stash restoration, branch switch,
production edit or Bulk Resolution implementation was performed. Stop for review.
