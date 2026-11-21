# Semantic Layer 1 and evidence relevance investigation V1

Report-only investigation on `feat/llm-unresolved-requirement-adjudication-v1`.
No scoring, parsing, knowledge, project ranking, résumé, database or gold-label
changes. The machine companion is
`reports/unresolved_semantic_layer1_evidence_relevance_v1.json`.

## Finding

The available evidence does **not** establish an excessively strict matcher or
an omitted Job AI Helper project. Three of the four unresolved-knowledge cases
already receive transferable evidence matches. Unresolved knowledge is not the
same as no applicant evidence. The ROS case has no documented ROS evidence.

Small source-scope annotations and better evidence explainability are justified
as an investigation pilot. A replacement taxonomy, parser, scorer or project
selection engine is not justified. Human review must establish whether the
additional candidate connections are useful before changing retrieval behavior.

## Sources and reproducibility

The V4 source-first packet supplies exact frozen IDs, wording, fingerprints,
verified parents/headings, native structure and taxonomy/registry candidates.
The original manifest and V3 source evidence remain unchanged; previous AI
recommendations are not decisions or gold. The audited multidimensional report
and route comparison are protected inputs, not new ground truth.

Saved Job Match snapshots were loaded with
`database.job_match_manager.list_latest_job_match_corpus_snapshots`, which reads
SQLite in read-only mode and accepts raw JDs only with matching snapshot hashes.
Exact JD hashes were also checked against V4. Additional SQLite reads use
`mode=ro` and `PRAGMA query_only=ON`. No schema initialization or write manager
was called. Reports persist native evidence IDs, source locations, technical
tokens and hashes rather than raw private résumé/profile text.

Current pure matcher probes use the exact saved canonical row, the native
`build_profile_evidence_context` projection and `build_resume_evidence_index`.
They call the production keyword matcher and Phase9E keyword selection with an
empty acronym map. They are bounded discovery probes, **not** a whole analysis,
a new Job Match score, a saved blueprint ranking or a tailoring simulation.

| Identity | Value |
|---|---|
| Installed scorer | stable-evidence-v1.16-phase6d20 |
| Taxonomy | phase6d-capability-taxonomy-v1.5 |
| Registry | technology-registry-v1.3 |
| Historical saved snapshots | stable-evidence-v1.10-phase6d16 |
| Frozen reviewed accounting | confirmed_taxonomy_coverage.json, separately fingerprinted |

Historical snapshot scores are Job146=15, Job50=23, Job45=16. Frozen reviewed
fixture scores are Job146=17, Job50=18, Job45=16. These reflect different saved
analysis generations; this task does not reconcile or re-score them. Current
pure discovery agrees with the saved match labels below. Current frozen rows
are shown separately, including their importance, rather than silently
substituting historical importance/score for current scoring.

Regenerate a new report at a new path, using the existing local database only
when available:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
$env:CAPABILITY_RAG_MODE='off'
.venv\Scripts\python.exe -B -m scripts.investigate_unresolved_semantic_evidence --db data/applications.db --output reports/semantic_evidence_review_copy.json
```

The command refuses to overwrite a report. Without `--db`, source semantics
remain available and evidence/downstream observations fail closed as unavailable.
There is no timestamp dependency. Identical source records produce identical
output. Concurrent external database writers are not controlled; whole-database
immutability is not claimed.

## Four-case findings and full pipeline traces

### #10: Job146 / req_ba405c092a55

Exact frozen input:

> (b) Relational and non-relational databases, such as MS SQL, PostgreSQL, MongoDB etc

| Stage | Observation / boundary |
|---|---|
| JD → canonical | Verified `Proficiency in:` heading is absent from this child. It is additional verified context, not appended frozen benchmark input. |
| Structure | Native coherent example parent; no scoring children. `srcgrp_60c959b87238` allocation totals 1. Examples are not three mandatory technologies. |
| Knowledge | Native whole requirement remains unresolved. Registry alias candidates do not resolve broad database proficiency. Existing database.design is not universal querying/admin competence. |
| Evidence | Snapshot40, item2 QueryAI: actual PostgreSQL-backed workflows, PostgREST access, RLS and frontend/service integration. Item6 also records SQLite sessions and ChromaDB RAG. These are different bounded database activities. |
| Match / score | PostgreSQL tool row `ev_db375a2c7c8c`, `resume_profile.skills.evidence_2_tools[2]`, already transferable, value .55. Current keyword and Phase9E probes retain that citation. No new credit. |
| Phase8 | No exact linked application verification established. Other saved QueryAI/Job AI Helper source lineage cannot substitute for this JD's verification. |
| Phase9E / tailoring | No exact saved decision, linked application or generation established for this JD hash. No observed project omission or selection effect. |

Nine bounded surface connections include five implementation-bearing records;
that is discovery coverage, not five independently proven competencies. The
three QueryAI bullets are relational implementation assertions. SQLite session
storage is also relational but does not prove advanced querying. ChromaDB is
non-relational vector storage, not MongoDB proficiency or broad non-relational
administration. No saved SQL-querying achievement was established from these
records. RLS is specifically recorded; generic SQL does not imply security.

**Verified limitation:** source heading is missing from frozen child scope.
**Hypothesis:** broad competency annotation could improve bounded relevance
explanation. **Not proven:** native matcher demands exact products exclusively,
misses documented SQL querying, or suppresses useful database projects.

### #15: Job50 / req_12004e0f666c

Exact frozen input:

> maintain ROS-based robotics solutions to enhance visitor experiences and operational efficiency as well as educational programs

| Stage | Observation / boundary |
|---|---|
| JD → canonical | Child preserves maintain; verified parent adds develop and deployment context. Parent-only context remains separately marked. |
| Structure | Atomic child fraction .5; native members of `srcgrp_662f4316db1d` total 1. No new components or allocations. |
| Knowledge | ROS has no established native registry identity. No ID is minted. Generic Python/C++ or messaging capability does not establish ROS maintenance. |
| Evidence | Snapshot30 contains C++ engine work and Python/tool surfaces; no documented ROS nodes, ROS messaging, robotics maintenance, SLAM, navigation or perception implementation was found. |
| Match / score | Saved and current discovery return none; current frozen match value 0. This is justified for ROS proof. Six surface adjacency candidates are not six ROS achievements. |
| Phase8 | No exact application verification established. General source lineage remains available, not a ROS verification. |
| Phase9E / tailoring | No exact decision/generation trace. Whether adjacent engine engineering could usefully appear in a tailored résumé remains untested. |

**Verified:** identity knowledge is absent and exact ROS evidence is absent.
**Hypothesis:** governed identity/scope investigation and a truthful adjacency
explanation may be useful. **Not proven:** an evidence-discovery false negative.
No ROS installation, framework familiarity or Python listing may imply robotics
development, production deployment, navigation or SLAM.

### #16: Job50 / req_b01957201b40

Exact frozen input:

> Advantageous qualifications include a GitHub portfolio demonstrating your work, experience with AI or ML technologies, expertise in SLAM and Motion Planning, or familiarity with CI or CD pipelines and simulation environments

| Stage | Observation / boundary |
|---|---|
| JD → canonical | One coherent preferred statement is preserved. Internal OR has not created mandatory independent children. |
| Structure | `srcgrp_66930ef0a713` totals 1. Native structured components are unavailable. This alone is not a parser failure. |
| Semantic hypothesis | Portfolio OR AI/ML OR (SLAM AND motion planning) OR (CI/CD AND simulation); boundaries require human confirmation. CI or CD is an internal alternative, not two obligatory technologies. |
| Knowledge | Whole mixed qualification unresolved; portfolio is not a technical capability by itself. |
| Evidence | Snapshot30: Job AI Helper's LLM/RAG and CI assertions; GitHub listings. No saved SLAM, motion planning or simulation achievement established. A GitHub listing does not prove a substantive portfolio. |
| Match / score | GitHub `ev_1ed99e6bbe97`, `resume_profile.skills.evidence_2_tools[6]`, already transferable (.55); both current probes retain it. Nine diagnostic candidates include two implementation-bearing records. |
| Phase8 / Phase9E / tailoring | No exact linked verification, selection or generation established. Additional branch candidates do not demonstrate an actual ranking omission. |

**Verified:** scope and parent weight are conserved; partial evidence is already
recognized. **Hypothesis:** nested branch explainability is useful. **Not proven:**
parser inflation, mandatory alternative matching, or suppressed projects.
Transferable credit is not proof that every alternative or conjunction is met.

### #35: Job45 / req_076aaad11115

Exact frozen input:

> Familiarity with Generative AI tools, AI/LLM application development, APIs or system integration is advantageous

| Stage | Observation / boundary |
|---|---|
| JD → canonical | Mixed advantageous sentence remains one parent, not independent mandatory skills. Exact top-level alternative scope is a human-review hypothesis. |
| Structure | `srcgrp_dbc74bf57638` totals 1; native structured representation unavailable. OR alone is not evidence of parser failure. |
| Knowledge | Whole statement unresolved. Existing ai.rag_application/backend.api_development/integration predicates have narrower contracts; no universal AI or API capability mapping. |
| Evidence | Snapshot21 item6 Job AI Helper explicitly records creating a multi-step LLM analysis pipeline and integrating ChromaDB RAG. Item2 QueryAI has PostgREST implementation relevant to an API branch, not LLM proof. |
| Match / score | `ev_9f12a3603f0d`, `resume_profile.skills.evidence_6_skills[0]`, AI application development is already transferable (.55). Current keyword/Phase9E probes retain that citation. Ten candidates include three implementation-bearing records. |
| Phase8 | Nine saved Job AI Helper blueprint candidates have matching actual source-verification records/fingerprints. Bounded bullet receipts for app analysis, RAG and SQLite are available; checks are lineage/source-based, not independent code-execution verification. |
| Phase9E / tailoring | None of those records establishes a selection decision for this exact Job45 JD. No actual omission, replacement project or selection-effect estimate is claimed. |

Real saved implementation statements were found; this conclusion comes from
applicant evidence and stored source receipts, not this repository's feature
code. `manual` is the library source type. LLM extraction/analysis/tailoring and
RAG integration are documented. OpenAI API and LiteLLM are explicit tools.
The records do not independently document model-response validation or API
failure handling. They do not prove model training or every GenAI capability.
Downstream saved lineage verifies source-supported app/RAG/SQLite bullets;
these were not rewritten or approved in this task.

**Verified:** relevant Job AI Helper evidence is already accessible and receives
transferable recognition. **Hypothesis:** show the implementation record alongside
the broad skill citation. **Not proven:** project retrieval, strength, blueprint
selection or tailoring prioritization defects.

## Prototype contract and trade-offs

`taxonomy_discovery.unresolved_semantic_evidence` is a bounded investigation
helper, not a general semantic parser. Four curated, exact-span annotations
preserve technologies, activities, proficiency observations, examples,
alternative/conjunctive groups, parents, allocations and both frozen/context
fingerprints. Every observation is explicit-frozen, verified-parent-only,
diagnostic interpretation or not established. Existing technology candidates
remain distinct from full native resolution. No capability candidate becomes
a match, and no new scoring child is created.

Evidence discovery uses small exploratory surface profiles and native evidence
IDs/locations. Implementation verbs and technical surfaces are observations
in individual saved records. They never aggregate fragments into proof. This
is deliberately inclusive and can over-retrieve; it requires human relevance
review and is not calibrated for production. Negated/planned records fail
closed. Parent-needed annotations do not become child-only benchmark answers.

Relevance states: DIRECT_RELEVANCE_CANDIDATE,
TRANSFERABLE_RELEVANCE_CANDIDATE, ADJACENT_RELEVANCE_CANDIDATE,
NO_SUPPORTED_RELEVANCE, UNKNOWN. Irrelevant records are omitted from the
candidate set, rather than treated as proven absence of candidate experience.

Claim states: EXACT_CLAIM_SUPPORTED, BOUNDED_CLAIM_SUPPORTED,
INSUFFICIENT_EVIDENCE, CONTRADICTED_OR_UNSUPPORTED, UNKNOWN.
The prototype **never emits exact full-requirement proof**. Bounded support means
only a recorded source assertion; all `claim_authorized` values remain false.
No numerical relevance scores, recall/precision/accuracy estimates or model
quality claims are produced. This is not independent human-label evidence.

## Controls

The machine report includes ten **synthetic, non-gold** controls and native
capability/keyword comparisons. None is substituted for the real applicant.

| Control | Discovery / claim boundary |
|---|---|
| Documented SQL querying → database proficiency | Relational relevance; no universal proficiency, schema/security/admin inference |
| SQL Server → PostgreSQL | Transferable relational experience, not exact product proficiency |
| Robotics software → ROS | Adjacent, not ROS; explicit `without ROS` fails closed to review |
| LLM API implementation → LLM app | Bounded direct relevance, no model training or all-branch proof |
| ChatGPT usage → GenAI | Tool adjacency/familiarity surface, not application implementation |
| Docker/CI/CD → Kubernetes | Deployment adjacency, not Kubernetes expertise |
| Node.js listing → API | Runtime adjacency, no API implementation claim |
| AWS listing → architecture | Platform adjacency, no architecture claim |
| REST implementation → API | Bounded API relevance, not gRPC or distributed architecture |

False-negative concerns remain hypotheses: useful implementation records may
not be displayed beside terse citations; adjacent engineering may not appear in
a tailored résumé. False-positive risks are demonstrated by the unsafe-inference
controls: products, verbs, related languages and branch overlap cannot justify
full proficiency, conjunction completeness or unrecorded achievements. No
production false-positive regression is established by synthetic probes alone.

## Existing owners and proposed narrow next stage

| Existing component | Reuse / potential future owner |
|---|---|
| stable_evidence_scoring.canonicalise_requirements | Source scope and conserved allocations; no replacement extraction |
| production_requirement_resolver.resolve_requirement_with_production_knowledge | Native knowledge status remains authoritative |
| technology_registry / governed identity workflow | Investigate ROS identity separately, with human governance |
| contextual_relationship_validation.context | Bounded relationships; never universal technology mappings |
| requirement_scope / phase6d6_structured_matching | Parent headings, examples and nested alternatives, after source review |
| matching.build_profile_evidence_context / build_resume_evidence_index | Native evidence projection and exact source references |
| capability_taxonomy.evaluate_evidence | Existing claim/evidence boundaries, no keyword substitute for predicates |
| phase9e_blueprint_selection.build_phase9e_keyword_match | Existing single-record reselection and preliminary ceilings |
| stable_tailoring_ranking._unrecognised_single_record_match / _build_project_relevance_summary | Existing transferable/weak relevance, support records and fallback suitability; unresolved does not automatically remove projects |
| phase8_verification.audit_claim_lineage / build_phase8_verification | Source identity, before/after reconciliation and claim verification |
| evidence_grounded_bullet_tailoring.prepare_bullet_target / evaluate_grounded_bullet | Exact source records and support ceilings before truthful tailoring |
| unresolved source review / multidimensional triage / V4 packet | Context provenance and human review, no imported predictions |

Recommendation: **existing-subsystem source/explainability improvements plus
a small bounded semantic/relevance review pilot**, not a large new architecture.
Inspect exact saved project-selection records when an application for these
JDs becomes available. Compare observed selection with human-reviewed evidence
connections before alleging a Phase9E omission. Relevant projects can already
contribute transferable/weak coverage or fallback suitability under the native
ranking contract; direct-only ranking is not the current contract.

The next approval point is human review of source scope, alternative grouping
and the bounded evidence connections. A separately approved stage may add
source-heading preservation or implementation-record explainability, with
version/currentness and regression tests. Do not change matching thresholds,
ranking, claims or production mappings on these observations alone.

## Validation and preservation

Focused command:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_unresolved_semantic_evidence tests.test_unresolved_multidimensional_triage tests.test_unresolved_review_packet tests.test_unresolved_source_review tests.test_phase9e_deterministic_evidence_precision tests.test_phase9e_single_row_evidence_selection_v4
```

67 tests passed in 43.017s, including 15 new tests. The new module initially
passed 15/15 as the smallest relevant check. Expected argparse errors in the
diagnostic tests exercise forbidden/unbounded CLI inputs; they are not failures.
Final changed Python AST and Git whitespace checks are recorded in the handover.
The 15 new tests were rerun after final report/metadata changes: 15/15 passed
in 0.668s. Three changed Python AST checks, all five new artifact whitespace
checks and `git diff --check` passed. An import-reference search found only the
new report script and tests; no production references to this helper exist.
No full gate/discovery or frozen scoring replay: production isolation and
protected byte hashes were checked instead, as permitted by this task.

Protected hashes, unchanged during generation and focused tests:

- Scorer SHA256: `16cbd0096e228356aade8d495d66e5135332c6e7ebff7e077ac8394e877afb98`
- Taxonomy SHA256: `da7b5e6952935a7dda88347c5af41eba65784b45da1c5b68f45a8768f605563e`
- Registry SHA256: `56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675`
- Production implementation fingerprint: `080aacaed958b108ae118b926f9cba2fb88265c8c0ebc491538fc2974b431c26`

The machine report carries the complete protected-artifact byte-hash map,
including production modules and gold/benchmark records. Scoring version,
protected 40-case inputs, original NAC expectations, V4 receipts, and pending
Job15 traffic-light control are unchanged. #32 remains deferred for child-only
evaluation and high priority for parent-fidelity investigation. The independent
gold prerequisite remains unsatisfied; no live benchmark or label import.

Zero models/embeddings/network/provider calls, database writes, publication,
production changes, claim authorizations, commits, pushes or merges. Stop for
review before any production remediation.
