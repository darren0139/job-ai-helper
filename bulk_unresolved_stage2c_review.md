# Bulk Unresolved V1 Stage 2C — grounded ownership detector and policy readiness

## Recommendation

**PASS for this bounded offline investigation; BLOCKED for coordinated Option A
production implementation.** The text detector closes the demonstrated partial-action
DIRECT paths within its admitted language, without using fixture-declared ownership
as an input. Its conservative language coverage and the unapproved partial-credit
dispositions prevent a production-readiness claim. Zero observed false positives on
this finite corpus is not a guarantee about unseen résumé prose.

Worktree verified: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch: `feat/bulk-unresolved-resolution-v1`. HEAD:
`5756d5f840dd09e3c0c48c6fcfc9298246a8790b`. Entry status was one modified tracked
file and ten untracked Stage 2/2B files, all preserved. No branch/index/commit change.
The attached Stage 2C request, rather than older checkpoint prompts, governs this work.

## Implemented research artifacts and trust boundaries

- `taxonomy_discovery/coordinated_ownership_preview.py`: isolated text-to-obligation
  extraction and single-record text ownership detector. Production code does not
  import it. Policy identity is explicitly `PREVIEW-ONLY-grounded-coordinated-ownership-v1`.
- `scripts/preview_coordinated_ownership_v1.py`: clones native Python functions into
  a disposable namespace, inserts a shared compatibility predicate and captures native
  selection/cap/recovery stages. It stops before overall alignment or persistence.
- `tests/test_coordinated_ownership_preview.py`: detector, oracle independence,
  ownership/source constraints, stage bypass, currentness and reproducibility checks.
- `bulk_unresolved_stage2c_preview.json`: deterministic full receipts, two confusion
  matrices, 30-job raw replay, independent API controls and protected hashes.

Only `tests/fixtures/per_jd_scoring_audit.json`'s original raw JD fields are replayed.
The Stage 2B artifact supplies
unchanged hypothetical evidence strings and independently specified oracle expectations;
the detector does not receive those expected action labels. Each five-parent row is
also checked against a fresh native Stage 2 Option A raw-JD replay (ID, text, source
provenance, atomic group and allocation), avoiding silent trust in a copied projection.
No real candidate résumé is used or rescored. Independent existing unit fixtures and
new synthetic snapshot tests are not historical/live Job Match projections.

There are 201 parent/scenario integration comparisons across five parents: 76 original
Stage 2B scenarios, 105 new adversarial scenarios, 15 missing/forged/tampered-source
comparisons, and five initially-missing-keyword zero-overlap controls. The oracle
evaluation covers 196 individual evidence records in 181 textual scenarios. Repeated
source-fault and recovery controls are excluded from confusion counts. Sixteen separate
API/DSA/Boolean controls and five additional obligation controls are reported separately.
No model, embedding, Tavily, Ollama, external transport, live DB or project-wide runner
is used. New SQLite files, if used by compatibility tests, are disposable synthetic
test files under the ignored Stage 2C scratch directory.

## Grounded obligation extraction

The admitted AND form is the finite `Design, develop|build [,] and maintain|deploy
<shared object>` grammar. All five original parents match. A separate bounded two-action
`Design or develop|build <shared object>` control demonstrates true alternative semantics;
it is not rewritten to AND or included in the five-parent production proposal.

Admitted object families are data pipelines, embedded software modules, full-stack
applications, cloud-based applications and backend services and API. The complete exact
modifier string is retained. A trailing `preferably using ...` qualifier is recorded with
its original span and excluded from mandatory action/object proof. The original raw
parent, source occurrence ID, grounding span/line/sentence, action spans, object span,
conjunction, explicit negation/alternative observations and optional qualifier spans are
retained. Offsets are half-open Unicode character offsets in unmodified parent text,
not invented offsets in a reconstructed child. The five parent obligations additionally
include absolute raw-JD parent/object/action spans, verified against the unique exact
substring in the original document. Missing or duplicate exact document occurrences
are explicitly unsupported rather than guessed. Parent source allocation stays 1.0.

Mixed AND/OR, negative requirements, object alternatives, multiple source occurrences,
unrecognized objects or another ownership action inside the supposed object are
UNSUPPORTED. They require review; they are not broadened or assigned credit by this
preview. The synthetic Boolean controls carry explicitly synthetic provenance rather
than borrowing a real job's span. No omitted JD object is manufactured.

## Evidence ownership detection

`detect_ownership(obligation, record, verified_index)` accepts one actual attributable
record and the current evidence index. Its source, evidence ID, exact text and section
must match that index. Project/experience records are admitted; forged IDs, missing
sources, changed text and education claims cannot establish responsibility ownership.
The integration additionally retains native `_evidence_source_is_requirement_compatible`
checks before any new admission. No independent bullets are concatenated.

Reviewed action forms are design/designed/designing, develop/developed/developing,
build/built/building, implement/implemented/implementing, maintain/maintained/maintaining,
and deploy/deployed/deploying, with conservative tense/subject checks. Build/develop/
implement are equivalent only for affirmative creation of the same explicitly bound
software artifact in this preview. They do not establish endpoint authorship from
integration, SQL policies, or expertise in a named technology. Maintain and deploy
remain distinct. Design is never supplied by implementation ownership alone.

Past-tense résumé bullets have an implicit candidate subject. Explicit first-person
present/ongoing clauses are admitted. Team-only, vendor, collective `we`, future,
learning/planning, questions and explicitly hypothetical or retracted claims are
not proven ownership. Invalid passive-like subjects such as `I am designed ...` are
ambiguous. Bare imperative/present résumé fragments, passive-by-me wording and relative
ownership clauses remain unsupported rather than inferred.

Adjacent reviewed verbs can share the following exact object only through a bounded
comma/AND connector. Otherwise each verb must bind its own object. Several affirmative
clauses or sentences inside the same verified record may collectively establish its
mandatory actions. Negation remains locally attached; same-object denial cancels an
affirmative action. Explicit `without owning its design/maintenance` tails are also
denial receipts. A record-level retraction or question withholds all proof. Each
receipt identifies the original evidence ID/source and original action/object character
spans. Denial-tail receipts identify the full ownership-denial clause span rather than
claiming it is a finite affirmative verb. Unknown subject, modality, tense or object
binding is not affirmative evidence.

This is intentionally a finite grammar, not a comprehensive résumé NLU system. Exact
normalized modifier equality, punctuation segmentation and reviewed attribution patterns
leave significant paraphrase/passive/relative-clause gaps. Unsupported constructions
must go to review rather than an overlap fallback. A complete action proof is only a
necessary condition; underlying taxonomy/technology/protocol rules still apply.

## Computed detector versus independent oracle

Counts are binary action-ownership judgments, not scoring labels or match scores.
The build/develop aliases in the oracle are normalized into the one reviewed creation
dimension for comparison; original Stage 2B expectations remain unedited. The detector
is run before the evaluator reads any expected actions. A regression supplies a
deliberately incorrect oracle and verifies the detector output does not change.

| Evaluation | TP | TN | FP | FN |
|---|---:|---:|---:|---:|
| All action judgments | 169 | 377 | 0 | 42 |
| Unchanged Stage 2B action oracle | 67 | 191 | 0 | 0 |
| New adversarial action expectations | 102 | 186 | 0 | 42 |
| All complete-obligation records | 32 | 150 | 0 | 14 |
| Unchanged Stage 2B complete records | 6 | 80 | 0 | 0 |

Observed action precision is 100%; recall is 80.1%. Complete-obligation recall is
69.6% (32/46). The 42 missed action judgments correspond to 14 missed complete records.
No oracle was changed to obtain agreement. These rates describe this synthetic corpus
only, not accuracy on real résumé evidence. Full-obligation completeness is separate
from whether the native scorer ultimately recognizes/credits the capability.

| Breakdown | TP | TN | FP | FN |
|---|---:|---:|---:|---:|
| action:deploy | 10 | 26 | 0 | 3 |
| action:design | 47 | 135 | 0 | 14 |
| action:develop | 62 | 120 | 0 | 14 |
| action:maintain | 50 | 96 | 0 | 11 |
| job:16 | 33 | 75 | 0 | 9 |
| job:359 | 33 | 75 | 0 | 9 |
| job:479 | 36 | 75 | 0 | 9 |
| job:566 | 67 | 152 | 0 | 15 |
| parent:srcgrp_8ac40e9b5dc4 | 31 | 77 | 0 | 9 |
| parent:srcgrp_af665d2ba39b | 33 | 75 | 0 | 9 |
| parent:srcgrp_b729779d18ec | 36 | 75 | 0 | 9 |
| parent:srcgrp_e822a3bdbba5 | 33 | 75 | 0 | 9 |
| parent:srcgrp_ff65d3ef26a4 | 36 | 75 | 0 | 6 |

| Evidence category | TP | TN | FP | FN |
|---|---:|---:|---:|---:|
| affirmative_clauses | 15 | 0 | 0 | 0 |
| all_actions_explicit_layers | 3 | 0 | 0 | 0 |
| all_requested_actions | 15 | 0 | 0 | 0 |
| ambiguous_we | 0 | 15 | 0 | 0 |
| api_consumption | 0 | 15 | 0 | 0 |
| collaboration_no_ownership | 0 | 15 | 0 | 0 |
| complete_alternative_row | 19 | 11 | 0 | 0 |
| contradiction | 10 | 5 | 0 | 0 |
| design_development_no_lifecycle | 10 | 5 | 0 | 0 |
| design_only | 5 | 10 | 0 | 0 |
| development_only | 5 | 10 | 0 | 0 |
| explicit_personal | 15 | 0 | 0 | 0 |
| future_intent | 0 | 15 | 0 | 0 |
| generic_software | 0 | 15 | 0 | 0 |
| global_hypothetical | 0 | 15 | 0 | 0 |
| global_retraction | 0 | 15 | 0 | 0 |
| hypothetical | 0 | 15 | 0 | 0 |
| incomplete_design | 5 | 10 | 0 | 0 |
| java_rest_authorship | 0 | 15 | 0 | 0 |
| lifecycle_action_only | 5 | 10 | 0 | 0 |
| maintenance_only | 4 | 11 | 0 | 0 |
| negated_ownership | 0 | 15 | 0 | 0 |
| ongoing_personal | 15 | 0 | 0 | 0 |
| owned_relative_clause | 0 | 0 | 0 | 15 |
| passive_attribution | 0 | 0 | 0 | 15 |
| postgrest_supabase_integration | 0 | 15 | 0 | 0 |
| present_personal | 15 | 0 | 0 | 0 |
| question | 0 | 15 | 0 | 0 |
| quoted_requirement | 0 | 15 | 0 | 0 |
| shortened_object | 3 | 0 | 0 | 12 |
| team_only | 0 | 15 | 0 | 0 |
| technology_usage_no_ownership | 0 | 15 | 0 | 0 |
| third_party | 0 | 15 | 0 | 0 |
| three_actions_separate_rows | 15 | 30 | 0 | 0 |
| usage_only | 0 | 15 | 0 | 0 |
| wrong_object_design | 10 | 5 | 0 | 0 |
| zero_overlap_topic | 0 | 15 | 0 | 0 |

There are 55 records with explicit ambiguity receipts; 15 have record-level AMBIGUOUS
status (questions, global retractions and hypothetical qualifications). The other
record statuses are 32 COMPLETE and 149 INCOMPLETE. In the 201 integration comparisons,
108 have REVIEW_REQUIRED for unapproved partial-credit disposition, 61 retain existing
native NONE, and 32 have an existing native label on an admissible complete source.
Not all 32 receive DIRECT: native topic caps may still give NONE.

### Exact false-negative counterexamples (all instances are in JSON)

- Job 16 / pipeline / shortened_object: `I designed, developed, maintained scalable data pipelines.` Exact JD modifier scope is missing. The independent action-ownership oracle expects support on the artifact family; this detector conservatively withholds it. That oracle expectation does not independently certify all omitted JD modifiers.
- Job 16 / pipeline / passive_attribution: `scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds were designed, developed, maintained by me.` The candidate appears as a passive by-me agent; the bounded active-voice subject/object detector does not admit this construction.
- Job 16 / pipeline / owned_relative_clause: `Used scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds which I designed, developed, maintained.` Ownership is asserted inside a relative clause; the usage-led outer clause is not an admitted affirmative subject prefix.
- Job 359 / embedded / shortened_object: `I designed, developed, maintained embedded software modules.` Exact JD modifier scope is missing. The independent action-ownership oracle expects support on the artifact family; this detector conservatively withholds it. That oracle expectation does not independently certify all omitted JD modifiers.
- Job 359 / embedded / passive_attribution: `embedded software modules supporting waveform processing systems were designed, developed, maintained by me.` The candidate appears as a passive by-me agent; the bounded active-voice subject/object detector does not admit this construction.
- Job 359 / embedded / owned_relative_clause: `Used embedded software modules supporting waveform processing systems which I designed, developed, maintained.` Ownership is asserted inside a relative clause; the usage-led outer clause is not an admitted affirmative subject prefix.
- Job 479 / fullstack / shortened_object: `I designed, developed, maintained scalable full-stack applications.` Exact JD modifier scope is missing. The independent action-ownership oracle expects support on the artifact family; this detector conservatively withholds it. That oracle expectation does not independently certify all omitted JD modifiers.
- Job 479 / fullstack / passive_attribution: `scalable full-stack applications using React, TypeScript and Python technologies were designed, developed, maintained by me.` The candidate appears as a passive by-me agent; the bounded active-voice subject/object detector does not admit this construction.
- Job 479 / fullstack / owned_relative_clause: `Used scalable full-stack applications using React, TypeScript and Python technologies which I designed, developed, maintained.` Ownership is asserted inside a relative clause; the usage-led outer clause is not an admitted affirmative subject prefix.
- Job 566 / backend / passive_attribution: `scalable backend services and API were designed, developed, maintained by me.` The candidate appears as a passive by-me agent; the bounded active-voice subject/object detector does not admit this construction.
- Job 566 / backend / owned_relative_clause: `Used scalable backend services and API which I designed, developed, maintained.` Ownership is asserted inside a relative clause; the usage-led outer clause is not an admitted affirmative subject prefix.
- Job 566 / cloud / shortened_object: `I designed, developed, deployed cloud-based applications.` Exact JD modifier scope is missing. The independent action-ownership oracle expects support on the artifact family; this detector conservatively withholds it. That oracle expectation does not independently certify all omitted JD modifiers.
- Job 566 / cloud / passive_attribution: `cloud-based applications with large-scale data processing capabilities were designed, developed, deployed by me.` The candidate appears as a passive by-me agent; the bounded active-voice subject/object detector does not admit this construction.
- Job 566 / cloud / owned_relative_clause: `Used cloud-based applications with large-scale data processing capabilities which I designed, developed, deployed.` Ownership is asserted inside a relative clause; the usage-led outer clause is not an admitted affirmative subject prefix.

These misses are deliberately reported rather than reclassified as true negatives.
Passive and relative-clause examples demonstrate actual language coverage loss.
Shortened-object cases additionally expose a distinction between action ownership and
full modifier proof. A future extension needs independently reviewed scope semantics,
not removal of the exact-object guard to improve recall. Unseen contradiction or
attribution language can also defeat a finite pattern set; this study is not a general
semantic-safety proof.

## Native integration and effective-credit preview

The local namespace wraps the existing compatibility predicate used by native lexical
selection, linking, single-row reselection and NONE recovery. It filters the candidate
pool to verified complete records, then leaves native ranking, tie order, capability
requirements and ceilings unchanged. The best admissible complete record is therefore
preferred through the existing selector; no unrelated second selector or score formula
is introduced. Complete alternative records keep their original evidence IDs and source
paths. Existing opt-in and source constraints are never relaxed in the actual preview.

Each comparison records linked, structured, validated lexical cap, reselected,
taxonomy-capped, recovered and final-invariant stages, including selected record,
computed ownership receipts, native stage label and provisional quarantine state.
Initial deterministic-keyword selection and the three selector loops are instrumented
by stage. Recovery is inspected before the final invariant, so late regained credit
cannot escape the last check.

Provisional NONE is internal quarantine plumbing, **not a proposed effective partial
score**. If unchecked native credit was positive but no complete attributable record
is available, the effective preview label is null with REVIEW_REQUIRED. That is an
out-of-band policy review disposition, never a production match label. If native already
gave NONE it is retained; a complete record remains subject to the unchanged native
capability caps. No overall Job Match score is generated.

Actual compatibility events cover keyword selection, linking and NONE recovery. None
of these five capabilities enables `allow_stronger_single_row_reselection`, so the
native reselection stage is invoked and recorded but its replacement loop does not
activate here. API tests independently protect the native opt-in reselection contract.
This absence is not claimed as dynamic branch coverage of a newly enabled reselection
policy; any future such opt-in needs its own coordinated-completeness regression.
The same shared predicate is the exact source-level loop boundary in that function.

A separate fault-injection unit test deliberately bypasses the recovery compatibility
filter for zero-overlap firmware text. Native recovery then awards DIRECT. The final
post-recovery invariant quarantines it. This diagnostic bypass is not used by the
normal artifact comparisons and is not an authorized production escape hatch.

## Five actual parents: source, identities, conservation and outcomes

The 30-job raw replay remains baseline 716 -> Option A 711 requirements. The same five
parents in four jobs change identity; the other 26 jobs retain counts. Every parent
allocation is conserved at 1.0. Native coverage dynamically divides by eligible atomic
group count; therefore collapsing .5/.5 to one row really exposes the whole parent to
that row's label. No stored-fraction edit can independently make that safe. Original
source occurrence/group/grounding fields remain byte-equivalent in the derived A rows.
There is no Option B production change in this stage.

In the following tables, U=unchecked native label, P=filtered provisional label,
E=effective preview label. REVIEW means null effective label pending policy approval,
not NONE, WEAK or a new production label. Full character receipts and selected source
IDs for each stage are in JSON. Synthetic source-fault controls are explicitly labeled.

### Job 16 — pipeline

> Design, build, and maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds.

Parent `srcgrp_e822a3bdbba5`; A canonical ID `req_acdd8f777d09`; atomic group `grp_b52c8b7f9646`. Baseline IDs: `req_fd6f5ea4f9bf`, `req_191dd0c2eef9`.

| Scenario | U | P | E |
|---|---|---|---|
| maintenance_only | direct | none | REVIEW |
| development_only | direct | none | REVIEW |
| design_only | direct | none | REVIEW |
| design_development_no_lifecycle | direct | none | REVIEW |
| all_requested_actions | direct | direct | direct |
| generic_software | none | none | none |
| technology_usage_no_ownership | direct | none | REVIEW |
| api_consumption | none | none | none |
| postgrest_supabase_integration | none | none | none |
| java_rest_authorship | none | none | none |
| incomplete_design | direct | none | REVIEW |
| negated_ownership | direct | none | REVIEW |
| zero_overlap_topic | none | none | none |
| lifecycle_action_only | direct | none | REVIEW |
| three_actions_separate_rows | direct | none | REVIEW |
| explicit_personal | direct | direct | direct |
| affirmative_clauses | direct | direct | direct |
| present_personal | direct | direct | direct |
| ongoing_personal | direct | direct | direct |
| team_only | direct | none | REVIEW |
| third_party | direct | none | REVIEW |
| ambiguous_we | direct | none | REVIEW |
| future_intent | direct | none | REVIEW |
| hypothetical | direct | none | REVIEW |
| quoted_requirement | direct | none | REVIEW |
| question | direct | none | REVIEW |
| global_retraction | direct | none | REVIEW |
| global_hypothetical | direct | none | REVIEW |
| wrong_object_design | direct | none | REVIEW |
| contradiction | direct | none | REVIEW |
| usage_only | direct | none | REVIEW |
| collaboration_no_ownership | direct | none | REVIEW |
| shortened_object | none | none | none |
| passive_attribution | direct | none | REVIEW |
| owned_relative_clause | direct | none | REVIEW |
| complete_alternative_row | direct | direct | direct |
| missing_source | direct | none | REVIEW |
| forged_id | direct | none | REVIEW |
| tampered_text | none | none | none |
| zero_overlap_missing_keyword_input | none | none | none |

### Job 359 — embedded

> Design, develop, and maintain embedded software modules supporting waveform processing systems.

Parent `srcgrp_af665d2ba39b`; A canonical ID `req_1933523263de`; atomic group `grp_a2d7ffc7f970`. Baseline IDs: `req_95479a28180a`, `req_bda00d6856dc`.

| Scenario | U | P | E |
|---|---|---|---|
| maintenance_only | direct | none | REVIEW |
| development_only | direct | none | REVIEW |
| design_only | direct | none | REVIEW |
| design_development_no_lifecycle | direct | none | REVIEW |
| all_requested_actions | direct | direct | direct |
| generic_software | none | none | none |
| technology_usage_no_ownership | direct | none | REVIEW |
| api_consumption | none | none | none |
| postgrest_supabase_integration | none | none | none |
| java_rest_authorship | none | none | none |
| incomplete_design | direct | none | REVIEW |
| negated_ownership | direct | none | REVIEW |
| zero_overlap_topic | direct | none | REVIEW |
| lifecycle_action_only | direct | none | REVIEW |
| three_actions_separate_rows | direct | none | REVIEW |
| explicit_personal | direct | direct | direct |
| affirmative_clauses | direct | direct | direct |
| present_personal | direct | direct | direct |
| ongoing_personal | direct | direct | direct |
| team_only | direct | none | REVIEW |
| third_party | direct | none | REVIEW |
| ambiguous_we | direct | none | REVIEW |
| future_intent | direct | none | REVIEW |
| hypothetical | direct | none | REVIEW |
| quoted_requirement | direct | none | REVIEW |
| question | direct | none | REVIEW |
| global_retraction | direct | none | REVIEW |
| global_hypothetical | direct | none | REVIEW |
| wrong_object_design | direct | none | REVIEW |
| contradiction | direct | none | REVIEW |
| usage_only | direct | none | REVIEW |
| collaboration_no_ownership | direct | none | REVIEW |
| shortened_object | transferable | none | REVIEW |
| passive_attribution | direct | none | REVIEW |
| owned_relative_clause | direct | none | REVIEW |
| complete_alternative_row | direct | direct | direct |
| missing_source | direct | none | REVIEW |
| forged_id | direct | none | REVIEW |
| tampered_text | none | none | none |
| zero_overlap_missing_keyword_input | direct | none | REVIEW |

### Job 479 — fullstack

> Design, develop and maintain scalable full-stack applications using React, TypeScript and Python technologies.

Parent `srcgrp_b729779d18ec`; A canonical ID `req_7cf592b15461`; atomic group `grp_d34942ce8533`. Baseline IDs: `req_95479a28180a`, `req_533286e95145`.

| Scenario | U | P | E |
|---|---|---|---|
| maintenance_only | none | none | none |
| development_only | none | none | none |
| design_only | none | none | none |
| design_development_no_lifecycle | none | none | none |
| all_requested_actions | none | none | none |
| generic_software | none | none | none |
| technology_usage_no_ownership | none | none | none |
| api_consumption | none | none | none |
| postgrest_supabase_integration | direct | none | REVIEW |
| java_rest_authorship | none | none | none |
| incomplete_design | none | none | none |
| negated_ownership | none | none | none |
| zero_overlap_topic | none | none | none |
| lifecycle_action_only | none | none | none |
| all_actions_explicit_layers | direct | direct | direct |
| three_actions_separate_rows | none | none | none |
| explicit_personal | none | none | none |
| affirmative_clauses | none | none | none |
| present_personal | none | none | none |
| ongoing_personal | none | none | none |
| team_only | none | none | none |
| third_party | none | none | none |
| ambiguous_we | none | none | none |
| future_intent | none | none | none |
| hypothetical | none | none | none |
| quoted_requirement | none | none | none |
| question | none | none | none |
| global_retraction | none | none | none |
| global_hypothetical | none | none | none |
| wrong_object_design | none | none | none |
| contradiction | none | none | none |
| usage_only | none | none | none |
| collaboration_no_ownership | none | none | none |
| shortened_object | none | none | none |
| passive_attribution | none | none | none |
| owned_relative_clause | none | none | none |
| complete_alternative_row | none | none | none |
| missing_source | none | none | none |
| forged_id | none | none | none |
| tampered_text | none | none | none |
| zero_overlap_missing_keyword_input | none | none | none |

### Job 566 — backend

> · Design, build and maintain scalable backend services and API.

Parent `srcgrp_ff65d3ef26a4`; A canonical ID `req_3a7798a7fae0`; atomic group `grp_def9668b121b`. Baseline IDs: `req_fd6f5ea4f9bf`, `req_86462bb5cd2a`.

| Scenario | U | P | E |
|---|---|---|---|
| maintenance_only | direct | none | REVIEW |
| development_only | transferable | none | REVIEW |
| design_only | direct | none | REVIEW |
| design_development_no_lifecycle | direct | none | REVIEW |
| all_requested_actions | direct | direct | direct |
| generic_software | none | none | none |
| technology_usage_no_ownership | direct | none | REVIEW |
| api_consumption | none | none | none |
| postgrest_supabase_integration | none | none | none |
| java_rest_authorship | none | none | none |
| incomplete_design | direct | none | REVIEW |
| negated_ownership | direct | none | REVIEW |
| zero_overlap_topic | none | none | none |
| lifecycle_action_only | direct | none | REVIEW |
| three_actions_separate_rows | direct | none | REVIEW |
| explicit_personal | direct | direct | direct |
| affirmative_clauses | direct | direct | direct |
| present_personal | direct | direct | direct |
| ongoing_personal | direct | direct | direct |
| team_only | direct | none | REVIEW |
| third_party | direct | none | REVIEW |
| ambiguous_we | direct | none | REVIEW |
| future_intent | direct | none | REVIEW |
| hypothetical | direct | none | REVIEW |
| quoted_requirement | direct | none | REVIEW |
| question | direct | none | REVIEW |
| global_retraction | direct | none | REVIEW |
| global_hypothetical | direct | none | REVIEW |
| wrong_object_design | direct | none | REVIEW |
| contradiction | direct | none | REVIEW |
| usage_only | transferable | none | REVIEW |
| collaboration_no_ownership | direct | none | REVIEW |
| shortened_object | direct | direct | direct |
| passive_attribution | direct | none | REVIEW |
| owned_relative_clause | direct | none | REVIEW |
| complete_alternative_row | direct | direct | direct |
| missing_source | direct | none | REVIEW |
| forged_id | direct | none | REVIEW |
| tampered_text | none | none | none |
| zero_overlap_missing_keyword_input | none | none | none |

### Job 566 — cloud

> · Design, develop and deploy cloud-based applications with large-scale data processing capabilities.

Parent `srcgrp_8ac40e9b5dc4`; A canonical ID `req_490d136c0a8a`; atomic group `grp_8afc8cad6acb`. Baseline IDs: `req_95479a28180a`, `req_9f75638e8bda`.

| Scenario | U | P | E |
|---|---|---|---|
| maintenance_only | direct | none | REVIEW |
| development_only | direct | none | REVIEW |
| design_only | direct | none | REVIEW |
| design_development_no_lifecycle | direct | none | REVIEW |
| all_requested_actions | direct | direct | direct |
| generic_software | none | none | none |
| technology_usage_no_ownership | direct | none | REVIEW |
| api_consumption | none | none | none |
| postgrest_supabase_integration | none | none | none |
| java_rest_authorship | none | none | none |
| incomplete_design | direct | none | REVIEW |
| negated_ownership | direct | none | REVIEW |
| zero_overlap_topic | none | none | none |
| lifecycle_action_only | direct | none | REVIEW |
| three_actions_separate_rows | direct | none | REVIEW |
| explicit_personal | direct | direct | direct |
| affirmative_clauses | direct | direct | direct |
| present_personal | direct | direct | direct |
| ongoing_personal | direct | direct | direct |
| team_only | direct | none | REVIEW |
| third_party | direct | none | REVIEW |
| ambiguous_we | direct | none | REVIEW |
| future_intent | direct | none | REVIEW |
| hypothetical | direct | none | REVIEW |
| quoted_requirement | direct | none | REVIEW |
| question | direct | none | REVIEW |
| global_retraction | direct | none | REVIEW |
| global_hypothetical | direct | none | REVIEW |
| wrong_object_design | direct | none | REVIEW |
| contradiction | direct | none | REVIEW |
| usage_only | direct | none | REVIEW |
| collaboration_no_ownership | direct | none | REVIEW |
| shortened_object | none | none | none |
| passive_attribution | direct | none | REVIEW |
| owned_relative_clause | direct | none | REVIEW |
| complete_alternative_row | direct | direct | direct |
| missing_source | direct | none | REVIEW |
| forged_id | direct | none | REVIEW |
| tampered_text | none | none | none |
| zero_overlap_missing_keyword_input | none | none | none |

The main effects remain distinct:

- Job 16 pipelines and Job 566 backend remain natively UNRESOLVED. Their high lexical
  overlap previously yielded full DIRECT from partial responsibilities. Text filtering
  applies even on that unresolved lexical path; taxonomy-only capping would miss it.
- Job 359 firmware's topic tier recovers `Configured ESP32 GPIO interrupts.` with
  zero overlap under unchecked scoring. It cannot bind any of the requested actions
  to the embedded-software object, so filtered recovery cannot add credit.
- Job 566 cloud requires deployment, not maintenance. The detector never substitutes
  maintain for deploy or allows generic data-processing evidence to complete ownership.
- Job 479 full-stack preserves the native frontend+backend topic-evidence requirement.
  Owning design/development/maintenance alone remains NONE without backend topic proof.
  The existing explicit-layer positive stays DIRECT. React+Supabase/PostgREST integration
  does not by itself prove the three requested responsibilities and now requires review
  instead of inheriting full-action DIRECT. It still does not prove endpoint authorship.
- Three separate partial bullets never become a complete single-source obligation.
  Multiple affirmative clauses within one original bullet can complete it.
- Complete alternative records are selected as `resume_profile.projects[0].bullets[1]`
  in the representative embedded case, with the existing native evidence ID. Native
  source constraints, ranking and caps still decide whether the record can receive credit.

## Explicit partial-credit policy decision matrix

| Condition | Existing governed behavior | Conservative preview disposition | Unapproved proposal / review need |
|---|---|---|---|
| All mandatory actions on correct object, one verified source | Native label and capability caps apply; complete ownership is not sufficient for capability credit | Admit to native selectors; retain resulting label | Review the finite ownership grammar before release; do not force DIRECT |
| Some mandatory actions proven | Generic lexical/topic tiers may assign full DIRECT; there is no general governed coordinated partial tier | Withhold unapproved effective change; REVIEW_REQUIRED if native positive | Decide bounded partial labels/ceilings explicitly; no supported-action-count formula |
| Different actions on different objects | Native topic overlap can over-credit | Each action must bind the shared JD object; incomplete positives require review | Do not infer cross-object design or borrow another artifact's lifecycle |
| Ownership negated or contradictory | API has governed denial logic; generic tiers may still be positive | Cancel affirmative proof on the same action/object; review positive native credit | Any mandatory NONE policy outside existing governed cases needs approval |
| Generic topic/usage/integration only | Topic/lexical credit may exist; API consumption does not prove endpoint authorship | No responsibility proof; review native positives | No automatic WEAK/TRANSFERABLE from technology names |
| Ambiguous subject/tense/object or unsupported grammar | Native path may still credit text | Do not prove ownership; unsupported obligations are review-only | Define a reviewed fallback or human review; no overlap bypass |
| Missing/unverifiable source or evidence ID | Existing evidence constraints still apply; fault controls expose missing explicit identity verification | No attributable proof; cannot earn new DIRECT | Review fail-closed handling; do not invent a provenance receipt |
| One complete alternative record available | Existing native ranker and source/cap ceilings govern | Filter incomplete records and let native ranking select the complete eligible record | Review candidate-pool/ceiling changes; do not force an otherwise ineligible row |
| Multiple separate partial records | Existing single-source protections prohibit silent evidence combination | Do not union receipts to complete A | Any multi-source completion contract requires separate review |
| API implementation without required API design | Approved API v1.1 explicitly permits WEAK under its exact conditions | Preserve existing governed WEAK; detector does not override that policy | Do not generalize this exception to other capabilities or missing lifecycle actions |

Native NONE retention in the preview is not a new partial-credit rule. Null REVIEW_REQUIRED
results are deliberately excluded from any numeric aggregate. This stage does not resolve
all 108 policy-review comparisons into an effective score or publish a policy label.

## API, protocol, DSA and scope safeguards

| Control | Native labels | Initially-missing-input native labels | Forced API evaluator (not recognition) |
|---|---|---|---|
| api_consume | none | none | none |
| api_postgrest | none | none | none |
| api_java | transferable | direct | direct |
| api_incomplete_design | weak | weak | weak |
| api_complete_design | direct | direct | direct |
| api_negated | none | none | none |
| api_split_sources | weak | weak | none/weak |
| protocol_and | none | none | none |
| protocol_or | none | none | direct |
| protocol_mixed_consumption | transferable | weak | none |
| protocol_both_authored | transferable | weak | direct |
| api_lifecycle_missing | transferable | weak | direct |
| dsa_generic_data | none | none | not probed |
| optional | transferable | weak | not probed |
| and_or_actions | direct | weak | not probed |
| negated_requirement | none/direct | none/weak | not probed |

Actual Java REST endpoint implementation remains DIRECT at governed evaluator/recovery;
design+implementation remains DIRECT when both are proved; implementation without design
retains WEAK; consumption/PostgREST integration stays NONE for endpoint authorship.
One complete alternative or several clauses inside one source never overrides these caps.
The Stage 2B native mixed REST/gRPC recognition boundary remains visible: a forced evaluator
success/failure is not misreported as native recognition. AND requires both authored
protocols; OR can accept an independently supported alternative at the governed evaluator.
No protocol, RLS policy, API authorship or design responsibility is inferred from usage.
Generic data/SQL remains NONE for DSA. Optional technology and Boolean controls preserve
their original semantics or explicitly require review.

## Minimal production integration proposal — not authorized or implemented

1. Keep Stage 2's finite Option A parser admission, but ship it only with a separately
   reviewed `coordinated-action-evidence-completeness-v1` contract. Promote neither this
   research module nor the full grammar indiscriminately. Resolve passive/relative
   coverage and exactly which modifier omissions are review-only before enabling it.
2. At `analysis_stability/stable_evidence_scoring.py::_evidence_source_is_requirement_compatible`,
   add a requirement-specific completeness/admissibility boundary backed by original
   parent and current evidence receipts. Preserve every existing source/credential guard.
   Reuse it from `_best_resume_evidence`, `_apply_capability_single_row_reselection` and
   `_apply_capability_none_recovery`; do not introduce a separate ungoverned selector.
3. Preserve `link_requirement_matches` and structured/validation constraints. Provide
   lexical/taxonomy action ceilings at the shared cap boundary, including unresolved
   lexical positives. At `build_stable_analysis`, enforce a final same-source completeness
   invariant after NONE recovery and before `compute_deterministic_alignment`. Gate all
   label-writing paths; a pre-recovery cap alone is insufficient.
4. Keep `tailoring/capability_taxonomy.py::_api_evidence_label` and the existing API v1.1
   implementation/design/protocol decisions independent. Do not force them into the
   generic action-count logic. Preserve the exact governed implementation-without-design
   WEAK exception and opt-in reselection ceilings.
5. Emit action/object/source receipts in an explicitly reviewed audit schema. Avoid storing
   null effective scores or REVIEW_REQUIRED as production labels without a contract.
   Resolve partial tiers and uncertain grammar before producing a numeric current match.
6. Preserve source occurrences and group allocation through canonical merges/deduplication.
   Promote the five actual-parent regressions, source verification, alternate complete
   selection, zero-overlap bypass, final invariant, Boolean/optional/protocol, API and DSA
   controls before release. Add branch coverage if any capability gains reselection opt-in.

## Version identities, currentness and historical compatibility

Production identities remain scorer `stable-evidence-v1.17-phase6d21`, decomposition
`jd-atomic-requirement-decomposition-v1.1`, taxonomy v1.6, registry v1.3 and
`api-evidence-completeness-v1.1`.

The proposed `stable-evidence-v1.18-phase6d22` +
`jd-atomic-requirement-decomposition-v1.2` can identify one coordinated, unpublished
Option A release after policy approval. A parser-only v1.18 is unsafe. If that scorer
identity ships separately, later completeness changes need another scorer version.
Require a separately identifiable coordinated-action policy and action-receipt schema.
Because candidate eligibility affects native recovery and reselection, recommend advancing
recovery `capability-single-row-none-recovery-v1.1` -> v1.2 and reselection
`capability-single-row-reselection-v1` -> v1.1 for a release that changes those contracts.
These are recommendations, not production constants written by this task. Keep API v1.1
unchanged unless its own behavior changes; no taxonomy/registry publication bump is
justified by detector integration alone.

The native fingerprint includes scoring/recovery identity but not decomposition identity
directly. A disposable namespace regression verifies decomposition-only v1.2 leaves the
input fingerprint unchanged, while proposed scorer v1.18 changes it. A separate local
copy of `inspect_job_match` uses the real currentness logic with explicit synthetic DB
lookups: the old synthetic snapshot is current at v1.17 and stale at v1.18, and remains
readable and byte-equivalent after the prospective lookup. No live lookup, saved historical
snapshot rewrite, refresh or published fixture edit occurs. Existing structure-fingerprint
compatibility tests additionally retain current production identity.

## Focused validation and protected-file verification

**118 distinct focused tests passed across the completed runs:** 99 existing focused
regressions and 19 Stage 2C tests. The initial combined selection passed 117 tests;
after receipt-offset tightening, the reproducibility test correctly rejected the stale
preview JSON. The artifact was regenerated, the absolute-document grounding regression
was added, and the final Stage 2C selection passed all 19 tests in 35.253 seconds,
including exact reproduction of the final JSON. No oracle or assertion was weakened.
There are no remaining test failures. No complete/quick runner was used.

Commands use the existing isolated Python 3.13.12 interpreter via the ignored
`venv/evidence-completeness-runtime/bulk_stage2c.ps1` launcher:

```text
python -B -m unittest tests.test_coordinated_ownership_preview.TextOwnershipUnitTests -v
python -B scripts/preview_coordinated_ownership_v1.py --protected-baseline venv/evidence-completeness-runtime/tmp/bulk_stage2c/baseline.json --output NEW_STAGE2C_OUTPUT.json
python -B -m unittest tests.test_coordinated_ownership_preview tests.test_coordinated_evidence_preview tests.test_coordinated_action_preview tests.test_source_inventory_export_safety tests.test_source_aware_inventory tests.test_bulk_unresolved_v1 tests.test_api_evidence_completeness tests.test_capability_none_recovery tests.test_jd_atomic_requirement_decomposition tests.test_jd_structure_fingerprint_compat -v
python -B -m unittest tests.test_coordinated_ownership_preview -v
git diff --check
git diff --cached --check
git diff --no-index --check -- NUL EACH_NEW_STAGE2C_FILE
```

Preview generations use distinct scratch paths; only this turn's own final root artifact
is replaced with the regenerated result. Logs are `detector_tests.log`, `focused.log`,
`final_stage2c_tests.log` (stale-artifact rejection) and `verified_stage2c_tests.log` under
the Stage 2C scratch folder. The launcher disables bytecode and retrieval, sets disposable
TEMP/SQLite paths and loads the existing external-network/non-disposable-SQLite guard;
preview scopes additionally block all connections. No owner-context escalation was needed.
Both tracked/index whitespace checks pass; the untracked-file checks report no whitespace
errors (the no-index command's difference exit status is expected for a new file).

All **917** entry-state tracked and pre-existing untracked files are in the before/after
SHA-256 ledger. They include all Stage 2/2B artifacts, the existing two-line Stage 1
security integration and published production policy/version/taxonomy/registry/snapshots.
All 917 are byte-identical after validation. HEAD, branch and empty index are unchanged.
Live database files are not in the hash ledger and were not accessed or hashed.

## Exact Git change classification

| Path | Classification |
|---|---|
| `taxonomy_discovery/source_aware_inventory.py` | Existing tracked modification: two-line Stage 1 security integration, preserved unchanged |
| `taxonomy_discovery/source_inventory_safety.py` | Existing untracked security validator, preserved |
| `tests/test_source_inventory_export_safety.py` | Existing untracked security tests, preserved |
| `scripts/preview_coordinated_actions_v1.py` | Existing untracked Stage 2 isolated parser preview, preserved |
| `tests/test_coordinated_action_preview.py` | Existing untracked Stage 2 regressions, preserved |
| `bulk_unresolved_stage2_preview.json` | Existing untracked Stage 2 artifact, preserved |
| `bulk_unresolved_stage2_review.md` | Existing untracked Stage 2 report, preserved |
| `scripts/preview_coordinated_evidence_v1.py` | Existing untracked Stage 2B preview, preserved |
| `tests/test_coordinated_evidence_preview.py` | Existing untracked Stage 2B regressions, preserved |
| `bulk_unresolved_stage2b_preview.json` | Existing untracked independent oracle/receipts, preserved |
| `bulk_unresolved_stage2b_review.md` | Existing untracked Stage 2B report, preserved |
| `taxonomy_discovery/coordinated_ownership_preview.py` | New Stage 2C research-only text detector |
| `scripts/preview_coordinated_ownership_v1.py` | New Stage 2C isolated native integration and oracle evaluator |
| `tests/test_coordinated_ownership_preview.py` | New Stage 2C focused detector/integration/currentness tests |
| `bulk_unresolved_stage2c_preview.json` | New deterministic Stage 2C receipts and protected hashes |
| `bulk_unresolved_stage2c_review.md` | New Stage 2C comparative report |

No unrelated tracked edits. Ignored task-owned additions are the Stage 2C PowerShell
launcher and `venv/evidence-completeness-runtime/tmp/bulk_stage2c/` scratch, logs,
report builder and disposable synthetic databases; these are not commit candidates.
No production parser/scorer/matching changes, staging, commits, pushes, merges, resets,
stashes, branch switches or bulk resolution implementation. Stop for review.
