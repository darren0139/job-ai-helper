# Existing-predicate resolver investigation V2

**Research only. Analyst interpretations are not independent gold decisions. No production fix implemented.**

## Cohort and result

Exact V1 active_same_hash inventory reconstructed with the original analyzer, latest-snapshot selection, whole-parent/near-text benchmark quarantine and privacy filters. All active inventory statistics matched the sealed V1 report. Thirteen requirements / thirteen distinct texts / nine jobs, including overlapping predicate observations counted once. Manifest was sealed before per-predicate probes.

```json
{
  "cases": 13,
  "jobs": 9,
  "applicability_counts": {
    "NOT_APPLICABLE": 2,
    "PARTIALLY_APPLICABLE": 9,
    "FULLY_APPLICABLE": 2
  },
  "current_unresolved": 13,
  "comparisons": {
    "UNCHANGED_UNRESOLVED": 13
  },
  "confirmed_current_defects": 0,
  "confirmed_source_defects": 0,
  "legitimate_abstentions_without_fix_recommendation": 11,
  "semantic_full_cases_needing_policy_review": 2,
  "interpretation": "All thirteen comply with the existing literal selector; two full semantic fits warrant separate policy review, not a proven violated rule"
}
```

All thirteen violate no existing literal matcher rule: none contains an approved native any_term. The report-only observer accepts a final plural s; production _contains does not. This explains the current path, but not a confirmed contract violation. Two complete semantic fits deserve human policy review. Eleven other cases are partial or non-applicable; lowering unresolved counts is not justification.

## Native path and historical limits

Production resolver calls classify_requirement_diagnostics on the exact text plus atomic_focus. No approved any_term matches for any observed candidate; all all_terms/all_groups are empty. API contextual web-services variants also do not match these inputs. The selector returns no_taxonomy_requirement_rule_matched. Registry fallback matches complete candidate terms with bounded wrappers, not arbitrary technology substrings: all thirteen report no_exact_registry_alias_match. That is not proof of missing identities. Identity scope subsequently fails complete-identity qualification (seven MIXED_SCOPE, five TECHNOLOGY_PLUS_ACTIVITY, one PARSER_OR_DECOMPOSITION_BLOCKED).

Historical snapshots record unresolved/unrecognised and the same registry fallback reason. Eight older rows lack recorded knowledge/identity diagnostics; historical per-term causality cannot be reconstructed. Five newer rows retain identity scopes, which agree with current scopes. No previous implementation was executed or checked out. UNCHANGED_UNRESOLVED means recorded knowledge outcome agreement, not proof that every historical implementation branch was identical. Versions alone establish no causality.

Shadow capability retrieval follows resolution in cap_requirement_with_taxonomy. Eight rows have retrieval disabled; five retain lexical candidates. Retrieval never influences scoring/selection. A retrieved API/stakeholder candidate does not bypass native predicates. No retrieval was run here.

Empty evidence in the pure helper is not an applicant qualification assessment. Current decision labels remain diagnostics only; no evidence credits, scores, rankings, eligibility or tailoring were recomputed.

## All thirteen decisions

| Case | Exact requirement | Candidate predicates | Historical / current | Applicability | Finding | Supported function | Fix justified? | Concrete risk |
|---|---|---|---|---|---|---|---|---|
| Job 45 / req_f1535cbe7edd | Those with relevant skillsets and interests may apply | motivation.subjective | UNRESOLVED / UNRESOLVED | NOT_APPLICABLE | VALID_UNRESOLVED | _contains → classify_requirement_diagnostics | NO | Turning invitation boilerplate into an explicit subjective qualification. |
| Job 48 / req_89ae867baae9 | You will explore data, design data models, apply statistics, machine learning models for descriptive and diagnostic analysis, create, test, and implement visual dashboards that are relevant to different groups of college stakeholders | collaboration.stakeholder, database.design | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | One database or stakeholder term crediting the complete analytics/dashboard obligation. |
| Job 48 / req_b50b5ed998f8 | Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time | collaboration.stakeholder | UNRESOLVED / UNRESOLVED | NOT_APPLICABLE | VALID_UNRESOLVED | _contains → classify_requirement_diagnostics | NO | Beneficiary nouns being treated as collaboration; silently repairing an unknown original character. |
| Job 146 / req_9270e95898c8 | Design and develop RESTful APIs | backend.api_development | UNRESOLVED / UNRESOLVED | FULLY_APPLICABLE | VALID_UNRESOLVED, CONTEXT_OR_RELATIONSHIP_INVESTIGATION | _contains → classify_requirement_diagnostics | NEEDS_MORE_EVIDENCE | A global stemming change could match product names or credit incomplete REST/gRPC requirements. |
| Job 158 / req_07301e1d0303 | Build good relations and workflows with internal and external stakeholders | collaboration.stakeholder | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | Collaboration proof granting workflow implementation credit. |
| Job 158 / req_5e1c1de91a3c | Collaborate with various stakeholders to build mission-ready tools and platforms | collaboration.stakeholder | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | A stakeholder match completing tools/platform implementation. |
| Job 163 / req_44c51cdd0d6c | Engage and update Stakeholders (management and users) on pain-points and requirements for forward planning | collaboration.stakeholder | UNRESOLVED / UNRESOLVED | FULLY_APPLICABLE | VALID_UNRESOLVED, CONTEXT_OR_RELATIONSHIP_INVESTIGATION | _contains → classify_requirement_diagnostics | NEEDS_MORE_EVIDENCE | Recognizing arbitrary stakeholder mentions as active collaboration. |
| Job 240 / req_51d8311de0cb | Strong ability to influence stakeholders and collaborate across engineering, product, and policy teams, including at the senior leadership level | collaboration.stakeholder | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | Basic collaboration credit proving senior influence or all cross-functional scope. |
| Job 360 / req_db0a9e351a71 | resolve performance, safety, and reliability issues in both development and production environments | operations.live_environment | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | Live-environment handling implying complete safety/reliability troubleshooting. |
| Job 562 / req_cc010ff84b86 | Assist in validating AI model deployments and AI application performance in test and production environments | operations.live_environment | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | Environment mention substituting for AI deployment validation or game-domain evidence. |
| Job 562 / req_e275bf93ddcb | work closely with customers and internal stakeholders to develop and deliver end-to-end SATCOM solutions that meet operational and business requirements | collaboration.stakeholder | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | Collaboration evidence proving SATCOM development, integration and delivery. |
| Job 619 / req_0987348575fd | Implement backend services, REST APIs, data models, and business rules using technologies such as Java and Spring Boot, and integrate them reliably with order, supply chain, finance/settlement, mapping, and route-planning systems | backend.api_development, database.design | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | API/database proof crediting business rules, language/framework and all integration domains. |
| Job 619 / req_66b8a305bdf8 | Hands-on development experience with Java and Spring Boot, including REST APIs, relational databases, SQL, data modelling, and common transaction-processing patterns | backend.api_development, database.design | UNRESOLVED / UNRESOLVED | PARTIALLY_APPLICABLE | VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY | _contains → classify_requirement_diagnostics | NO | API/database recognition granting hands-on Java/Spring Boot or transaction-processing qualification. |

### 1. Job 45 — req_f1535cbe7edd

> Those with relevant skillsets and interests may apply

Application invitation permits relevant skillsets and interests; it does not demand explicit motivation. The observer pluralizes interest into interests.

**Applicability:** NOT_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED.

Source: `job_match_snapshots[id=21].stable_analysis_json::canonical_requirements[requirement_id=req_f1535cbe7edd]`; snapshot 21, 2026-10-02T22:42:40. Importance required; content hash `48261f3773ee8fc80e6f431ea39911550e66cead2738ee6c4584dbb0d3c24745`. Input fingerprint `6b5b8ef552e1287e2843ab240a55ab44a632f00b1490ed3494b41678cd51dcaa`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:42:40"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "motivation.subjective", "exact_spans": ["interests"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"motivation.subjective": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope PARSER_OR_DECOMPOSITION_BLOCKED: Complete scope not bounded by native identity structure. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_f1535cbe7edd", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Those with relevant skillsets and interests may apply.

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 23, "section": "requirements", "section_detection": "exact", "section_heading": "Requirements", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Those with relevant skillsets and interests may apply", "span_id": "jdspan_8fea1e881106"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: Turning invitation boilerplate into an explicit subjective qualification.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 2. Job 48 — req_89ae867baae9

> You will explore data, design data models, apply statistics, machine learning models for descriptive and diagnostic analysis, create, test, and implement visual dashboards that are relevant to different groups of college stakeholders

Database design covers design data models only. Statistics, ML, analysis and dashboards remain distinct obligations. Stakeholders are dashboard beneficiaries, not a stated collaboration activity.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=22].stable_analysis_json::canonical_requirements[requirement_id=req_89ae867baae9]`; snapshot 22, 2026-10-02T22:43:03. Importance core; content hash `80d311bea68326230218fefeb3551842a31a5569db4b4df49b991ba67aaa7271`. Input fingerprint `af31ae6760148c3d082f301a8bf6d5940ee1cb40caa7992562f84b4c73b8f8af`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:43:03"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "collaboration.stakeholder", "exact_spans": ["stakeholders"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}, {"capability_id": "database.design", "exact_spans": ["data models"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"collaboration.stakeholder": false, "database.design": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope MIXED_SCOPE: Behavioral and technical scope. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_89ae867baae9", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> You are expected to build scripts to extract, prepare, transform and load data into an analytics software; build AI models with clustering and predictive capabilities. You will work closely with our team to gather user requirement and translate them into data requirement and insights. You will explore data, design data models, apply statistics, machine learning models for descriptive and diagnostic analysis, create, test, and implement visual dashboards that are relevant to different groups of college stakeholders. These dataset and dashboards may reside in our enterprise data lake and platforms, using Power BI as the visualization tool which is rendered to our end users.

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 4, "section": "responsibilities", "section_detection": "exact", "section_heading": "Responsibilities", "section_reason": "controlled_exact_heading", "sentence_index": 3, "sentence_text": "You will explore data, design data models, apply statistics, machine learning models for descriptive and diagnostic analysis, create, test, and implement visual dashboards that are relevant to different groups of college stakeholders", "span_id": "jdspan_458eb932a737"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: One database or stakeholder term crediting the complete analytics/dashboard obligation.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 3. Job 48 — req_b50b5ed998f8

> Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time

Helping lecturers and stakeholders obtain learning insights is an analysis deliverable, not an affirmative stakeholder collaboration requirement. U+FFFD is already in original stored JD/source; no current parser corruption is proved.

**Applicability:** NOT_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED.

Source: `job_match_snapshots[id=22].stable_analysis_json::canonical_requirements[requirement_id=req_b50b5ed998f8]`; snapshot 22, 2026-10-02T22:43:03. Importance core; content hash `80d311bea68326230218fefeb3551842a31a5569db4b4df49b991ba67aaa7271`. Input fingerprint `8b54b676814a298284f607b57b5aadeecec734b0f2ab36ade670c53c0a85e568`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:43:03"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "collaboration.stakeholder", "exact_spans": ["stakeholders"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"collaboration.stakeholder": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope MIXED_SCOPE: Behavioral and technical scope. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_b50b5ed998f8", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 6, "section": "responsibilities", "section_detection": "exact", "section_heading": "Responsibilities", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time", "span_id": "jdspan_c50b4b4c57ff"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: Beneficiary nouns being treated as collaboration; silently repairing an unknown original character.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 4. Job 146 — req_9270e95898c8

> Design and develop RESTful APIs

One bounded RESTful API design/development obligation fits the capability meaning, with no distributed-architecture or product-name exclusion. Native restful api is not a whole match for RESTful APIs. No approved plural-equivalence rule was found.

**Applicability:** FULLY_APPLICABLE. **Fix:** NEEDS_MORE_EVIDENCE. Findings: VALID_UNRESOLVED, CONTEXT_OR_RELATIONSHIP_INVESTIGATION.

Source: `job_match_snapshots[id=40].stable_analysis_json::canonical_requirements[requirement_id=req_9270e95898c8]`; snapshot 40, 2026-10-02T22:51:17. Importance core; content hash `8925a25e5c847c728ddabc189a2152f17dafe04aa335feb5ae60139d31ab9605`. Input fingerprint `0f38eebb3d76a46c976945a9a26d3aee9c5207bb1d8c69f67fb4b67564b9cab1`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:51:17"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "backend.api_development", "exact_spans": ["RESTful APIs"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"backend.api_development": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope TECHNOLOGY_PLUS_ACTIVITY: Named activity requires independent capability resolution. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_9270e95898c8", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Design and develop RESTful APIs

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 14, "section": "responsibilities", "section_detection": "exact", "section_heading": "Responsibilities", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Design and develop RESTful APIs", "span_id": "jdspan_2950a0993bda"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: Approved bounded plural recognition and human complete-scope confirmation.
Regression risk: A global stemming change could match product names or credit incomplete REST/gRPC requirements.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 5. Job 158 — req_07301e1d0303

> Build good relations and workflows with internal and external stakeholders

Relations with named internal/external stakeholders fit collaboration, but building workflows remains an additional obligation. Recognizing a collaboration facet must not qualify the entire workflow requirement.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=25].stable_analysis_json::canonical_requirements[requirement_id=req_07301e1d0303]`; snapshot 25, 2026-10-02T22:44:22. Importance core; content hash `fc7499429193d00b3887627ce53c4b035eae660128115211c4d1ee121a5e870b`. Input fingerprint `e20ff1eedfd570a72c15da097d2d73ff6e383a31c8912e48a6785bc87938f671`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:44:22"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "collaboration.stakeholder", "exact_spans": ["stakeholders"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"collaboration.stakeholder": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope MIXED_SCOPE: Behavioral and technical scope. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_07301e1d0303", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Build good relations and workflows with internal and external stakeholders

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 11, "section": "responsibilities", "section_detection": "exact", "section_heading": "Responsibilities", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Build good relations and workflows with internal and external stakeholders", "span_id": "jdspan_5c18eeec668e"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: Collaboration proof granting workflow implementation credit.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 6. Job 158 — req_5e1c1de91a3c

> Collaborate with various stakeholders to build mission-ready tools and platforms

Explicit collaboration is present, together with building mission-ready tools/platforms. Stakeholder collaboration alone does not prove those deliverables.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=25].stable_analysis_json::canonical_requirements[requirement_id=req_5e1c1de91a3c]`; snapshot 25, 2026-10-02T22:44:22. Importance core; content hash `fc7499429193d00b3887627ce53c4b035eae660128115211c4d1ee121a5e870b`. Input fingerprint `5a361f0ec30ee0bba7764c1a3893af36800fa81ecb32163252a1d9ee364e40e2`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:44:22"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "collaboration.stakeholder", "exact_spans": ["stakeholders"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"collaboration.stakeholder": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope MIXED_SCOPE: Behavioral and technical scope. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_5e1c1de91a3c", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Collaborate with various stakeholders to build mission-ready tools and platforms

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 6, "section": "responsibilities", "section_detection": "exact", "section_heading": "Responsibilities", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Collaborate with various stakeholders to build mission-ready tools and platforms", "span_id": "jdspan_3f3da3105be5"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: A stakeholder match completing tools/platform implementation.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 7. Job 163 — req_44c51cdd0d6c

> Engage and update Stakeholders (management and users) on pain-points and requirements for forward planning

Engaging/updating management and users about pain-points and requirements describes a bounded stakeholder interaction. Native stakeholder does not match Stakeholders. Forward planning supplies purpose; no independent implementation is named. Human confirmation of this scope and plural policy remains required.

**Applicability:** FULLY_APPLICABLE. **Fix:** NEEDS_MORE_EVIDENCE. Findings: VALID_UNRESOLVED, CONTEXT_OR_RELATIONSHIP_INVESTIGATION.

Source: `job_match_snapshots[id=33].stable_analysis_json::canonical_requirements[requirement_id=req_44c51cdd0d6c]`; snapshot 33, 2026-10-02T22:47:56. Importance core; content hash `b90fdad01376f09d9f560ec2701100c85ef60864a0a19bd5b4a173c74be03a5f`. Input fingerprint `60300f6972b301619145d464ec4649db4326002973168169fccac059f7d93943`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:47:56"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "collaboration.stakeholder", "exact_spans": ["Stakeholders"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"collaboration.stakeholder": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope MIXED_SCOPE: Behavioral and technical scope. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_44c51cdd0d6c", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Engage and update Stakeholders (management and users) on pain-points and requirements for forward planning

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 20, "section": "responsibilities", "section_detection": "exact", "section_heading": "Responsibilities", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Engage and update Stakeholders (management and users) on pain-points and requirements for forward planning", "span_id": "jdspan_aef1b4bfe13f"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: Approved bounded plural recognition and human complete-scope confirmation.
Regression risk: Recognizing arbitrary stakeholder mentions as active collaboration.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 8. Job 240 — req_51d8311de0cb

> Strong ability to influence stakeholders and collaborate across engineering, product, and policy teams, including at the senior leadership level

Stakeholder influence and cross-team collaboration fit a facet; influence at senior-leadership level and the engineering/product/policy qualification exceed that facet. The strict cross-functional whole-sentence grammar is not satisfied.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=26].stable_analysis_json::canonical_requirements[requirement_id=req_51d8311de0cb]`; snapshot 26, 2026-10-02T22:44:52. Importance required; content hash `b2089e41d72bd2dbc4380bcf113cf80586bd2e03c7a919f4d628fcd3f2b12db9`. Input fingerprint `48f98f2a9d88d76ef1408fefa4ca602da4b9a182d27b80c19a06d50189c4f8a0`.

Historical versions: {"scoring_version": "stable-evidence-v1.10-phase6d16", "taxonomy_version": "phase6d-capability-taxonomy-v1.4", "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2", "created_at": "2026-10-02T22:44:52"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "collaboration.stakeholder", "exact_spans": ["stakeholders"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "disabled", "candidates": [], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"collaboration.stakeholder": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope MIXED_SCOPE: Behavioral and technical scope. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_51d8311de0cb", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Strong ability to influence stakeholders and collaborate across engineering, product, and policy teams, including at the senior leadership level

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 43, "section": "requirements", "section_detection": "inferred_child_list", "section_heading": "Possess the OSCP certification, or other equivalent or advanced certifications", "section_reason": "dominant_child_list_semantics", "sentence_index": 1, "sentence_text": "Strong ability to influence stakeholders and collaborate across engineering, product, and policy teams, including at the senior leadership level", "span_id": "jdspan_32dddcb14599"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: Basic collaboration credit proving senior influence or all cross-functional scope.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 9. Job 360 — req_db0a9e351a71

> resolve performance, safety, and reliability issues in both development and production environments

Production environment handling covers the production facet only; development plus performance, safety and reliability troubleshooting remain obligations. The original troubleshooting parent and both half-weight children are retained, so omission/corruption is not established.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=52].stable_analysis_json::canonical_requirements[requirement_id=req_db0a9e351a71]`; snapshot 52, 2026-10-11T18:38:25. Importance core; content hash `e7000c20d330d1d7cd5a09c64b7a3bca8756bfc6bc84a97115f31fe162aa06ab`. Input fingerprint `6509e49f1a99cf2aaf88bca72073fc12f484d7ca0e688c4a2eb127cf70a58c14`.

Historical versions: {"scoring_version": "stable-evidence-v1.16-phase6d20", "taxonomy_version": "phase6d-capability-taxonomy-v1.5", "match_version": "job-match-snapshot-v2.3.0|registry=technology-registry-v1.3", "created_at": "2026-10-11T18:38:25"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "operations.live_environment", "exact_spans": ["production environments"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "candidates_retrieved", "candidates": ["frontend.ui_development", "language.modern_cpp", "operations.daily", "operations.evaluation", "systems.memory_cache_performance"], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"operations.live_environment": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope TECHNOLOGY_PLUS_ACTIVITY: Named activity requires independent capability resolution. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_76758d22ef97", "group_weight_fraction": 0.5}, {"requirement_id": "req_db0a9e351a71", "group_weight_fraction": 0.5}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Troubleshooting & Debugging: Proactively identify and resolve performance, safety, and reliability issues in both development and production environments

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 32, "section": "responsibilities", "section_detection": "exact", "section_heading": "Responsibilities:", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Troubleshooting & Debugging: Proactively identify and resolve performance, safety, and reliability issues in both development and production environments", "span_id": "jdspan_df2a7020386a"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: Live-environment handling implying complete safety/reliability troubleshooting.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 10. Job 562 — req_cc010ff84b86

> Assist in validating AI model deployments and AI application performance in test and production environments

Production environment is one context of AI deployment/performance validation in both test and production. Live handling does not prove AI validation. Non-game live-environment evidence is capped at weak by the existing contract; no applicant credit is assessed here.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=46].stable_analysis_json::canonical_requirements[requirement_id=req_cc010ff84b86]`; snapshot 46, 2026-10-11T18:29:52. Importance core; content hash `626785d53e96de70680073d3f207880ce48fd730e8285e2b67eef94841a84ca8`. Input fingerprint `3d79f64202ff328484fa00eeb30696c2cf20c9c67399c33c96323176d856089d`.

Historical versions: {"scoring_version": "stable-evidence-v1.16-phase6d20", "taxonomy_version": "phase6d-capability-taxonomy-v1.5", "match_version": "job-match-snapshot-v2.3.0|registry=technology-registry-v1.3", "created_at": "2026-10-11T18:29:52"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "operations.live_environment", "exact_spans": ["production environments"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "candidates_retrieved", "candidates": ["ai.model_evaluation", "ai.rag_application", "operations.evaluation", "quality.qa_testing", "systems.memory_cache_performance"], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"operations.live_environment": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope TECHNOLOGY_PLUS_ACTIVITY: Named activity requires independent capability resolution. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_cc010ff84b86", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Assist in validating AI model deployments and AI application performance in test and production environments

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 14, "section": "responsibilities", "section_detection": "inferred_child_list", "section_heading": "Be Part of Our Success", "section_reason": "dominant_child_list_semantics", "sentence_index": 1, "sentence_text": "Assist in validating AI model deployments and AI application performance in test and production environments", "span_id": "jdspan_ddb7829d274e"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: Environment mention substituting for AI deployment validation or game-domain evidence.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 11. Job 562 — req_e275bf93ddcb

> work closely with customers and internal stakeholders to develop and deliver end-to-end SATCOM solutions that meet operational and business requirements

Customer/stakeholder work is explicit, but delivering end-to-end SATCOM solutions adds substantive technical obligations. The original three-sentence parent and unheaded role-obligation grounding are retained; two contributing children still sum to one.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=46].stable_analysis_json::canonical_requirements[requirement_id=req_e275bf93ddcb]`; snapshot 46, 2026-10-11T18:29:52. Importance core; content hash `626785d53e96de70680073d3f207880ce48fd730e8285e2b67eef94841a84ca8`. Input fingerprint `0f88ec9335981e21beefac4a1dd17dd5203131e79f1f34336b886d152f8a08c9`.

Historical versions: {"scoring_version": "stable-evidence-v1.16-phase6d20", "taxonomy_version": "phase6d-capability-taxonomy-v1.5", "match_version": "job-match-snapshot-v2.3.0|registry=technology-registry-v1.3", "created_at": "2026-10-11T18:29:52"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "collaboration.stakeholder", "exact_spans": ["stakeholders"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "candidates_retrieved", "candidates": ["collaboration.stakeholder", "delivery.end_to_end_application", "devops.observability", "fullstack.integration", "operations.daily"], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"collaboration.stakeholder": true}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope MIXED_SCOPE: Behavioral and technical scope. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_645da6513b86", "group_weight_fraction": 0.5}, {"requirement_id": "req_e275bf93ddcb", "group_weight_fraction": 0.5}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> We are seeking passionate and motivated engineers to join our team in delivering innovative Satellite Communication (SATCOM) solutions who are eager to build their careers in satellite communications and system engineering. As part of our team, you will play a key role in supporting pre-sales activities, solution design, system integration, software development, testing, and project implementation. You will work closely with customers and internal stakeholders to develop and deliver end-to-end SATCOM solutions that meet operational and business requirements.

Grounding: {"admission_method": "explicit_role_obligation_sentence", "kind": "unheaded_explicit_role_obligation", "line_index": 7, "section": "", "sentence_index": 3, "sentence_text": "You will work closely with customers and internal stakeholders to develop and deliver end-to-end SATCOM solutions that meet operational and business requirements", "span_id": "jdspan_f4cfcab8a260"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: Collaboration evidence proving SATCOM development, integration and delivery.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 12. Job 619 — req_0987348575fd

> Implement backend services, REST APIs, data models, and business rules using technologies such as Java and Spring Boot, and integrate them reliably with order, supply chain, finance/settlement, mapping, and route-planning systems

API and data-model design each cover a facet. Java/Spring Boot, business rules and reliable integrations across named systems are not covered by either predicate. Such-as technology wording must not become a universal mapping.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=51].stable_analysis_json::canonical_requirements[requirement_id=req_0987348575fd]`; snapshot 51, 2026-10-11T18:37:50. Importance core; content hash `e474f04aafc22e1dc4eaddbf1e6f261849ad7762addb1384b6cceabf4cc18812`. Input fingerprint `d2c453467c861dbcf734ce91ded4aea8d8cde759690225358d12822f22048467`.

Historical versions: {"scoring_version": "stable-evidence-v1.16-phase6d20", "taxonomy_version": "phase6d-capability-taxonomy-v1.5", "match_version": "job-match-snapshot-v2.3.0|registry=technology-registry-v1.3", "created_at": "2026-10-11T18:37:50"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "backend.api_development", "exact_spans": ["REST APIs"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}, {"capability_id": "database.design", "exact_spans": ["data models"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "candidates_retrieved", "candidates": ["backend.api_development", "delivery.end_to_end_application", "realtime.messaging_streaming", "systems.data_oriented_programming", "systems.memory_cache_performance"], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"backend.api_development": true, "database.design": false}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope TECHNOLOGY_PLUS_ACTIVITY: Named activity requires independent capability resolution. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_0987348575fd", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Implement backend services, REST APIs, data models, and business rules using technologies such as Java and Spring Boot, and integrate them reliably with order, supply chain, finance/settlement, mapping, and route-planning systems.

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 4, "section": "responsibilities", "section_detection": "exact", "section_heading": "Key Responsibilities", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Implement backend services, REST APIs, data models, and business rules using technologies such as Java and Spring Boot, and integrate them reliably with order, supply chain, finance/settlement, mapping, and route-planning systems", "span_id": "jdspan_4e4c1fd2583a"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: API/database proof crediting business rules, language/framework and all integration domains.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.


### 13. Job 619 — req_66b8a305bdf8

> Hands-on development experience with Java and Spring Boot, including REST APIs, relational databases, SQL, data modelling, and common transaction-processing patterns

REST API and relational-database facets do not cover hands-on Java/Spring Boot experience, SQL, data modelling and transaction patterns. Including introduces examples/context; it does not prove independently allocated mandatory children.

**Applicability:** PARTIALLY_APPLICABLE. **Fix:** NO. Findings: VALID_UNRESOLVED, PREDICATE_PARTIAL_ONLY.

Source: `job_match_snapshots[id=51].stable_analysis_json::canonical_requirements[requirement_id=req_66b8a305bdf8]`; snapshot 51, 2026-10-11T18:37:50. Importance core; content hash `e474f04aafc22e1dc4eaddbf1e6f261849ad7762addb1384b6cceabf4cc18812`. Input fingerprint `eb8c70254a58b7e1e8956380b1fd439c0072b84e84bdafc93862bd7fdffed18e`.

Historical versions: {"scoring_version": "stable-evidence-v1.16-phase6d20", "taxonomy_version": "phase6d-capability-taxonomy-v1.5", "match_version": "job-match-snapshot-v2.3.0|registry=technology-registry-v1.3", "created_at": "2026-10-11T18:37:50"}. Recorded cap unrecognised; registry no_exact_registry_alias_match.

Observed exact spans: [{"capability_id": "backend.api_development", "exact_spans": ["REST APIs"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}, {"capability_id": "database.design", "exact_spans": ["relational databases"], "status": "EXISTING_TERM_OR_PLURAL_OBSERVATION_NOT_NATIVE_RESOLUTION"}]. All corresponding native any_term checks are false; see complete trace in JSON.

Stored shadow retrieval: {"status": "candidates_retrieved", "candidates": ["backend.api_development", "data.processing", "database.design", "frontend.ui_development", "realtime.messaging_streaming"], "shadow_only": true, "influences_scoring": false, "observer_candidates_retrieved": {"backend.api_development": true, "database.design": true}, "causality_limit": "Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection"}.

Current knowledge UNRESOLVED; scope TECHNOLOGY_PLUS_ACTIVITY: Named activity requires independent capability resolution. Comparison UNCHANGED_UNRESOLVED.

Parent receipts: [{"requirement_id": "req_66b8a305bdf8", "group_weight_fraction": 1.0}]; allocation sum 1.0. Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. This is JD occurrence corroboration, not Phase8 verified applicant evidence.

Original bounded parent/source:

> Hands-on development experience with Java and Spring Boot, including REST APIs, relational databases, SQL, data modelling, and common transaction-processing patterns.

Grounding: {"jd_structure_inference_version": "jd-structure-inference-v1.0.3", "kind": "explicit_raw_section", "line_index": 11, "section": "requirements", "section_detection": "exact", "section_heading": "Requirements", "section_reason": "controlled_exact_heading", "sentence_index": 1, "sentence_text": "Hands-on development experience with Java and Spring Boot, including REST APIs, relational databases, SQL, data modelling, and common transaction-processing patterns", "span_id": "jdspan_f775873c308a"}.

Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay. Missing evidence / next step: No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation.
Regression risk: API/database recognition granting hands-on Java/Spring Boot or transaction-processing qualification.
Supported current location: tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554). Registry fallback: `taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: `tailoring/requirement_scope.py::technology_identity_scope`.

## Full existing contracts

These are byte-preserved native definitions, not abbreviated observer terms. any_terms is disjunctive; all_terms/all_groups are conjunctive (empty for these records). Evidence conjunctions and does_not_prove are applicant-credit boundaries, not additional exclusions executed by the requirement selector. Backend API product guards apply to contextual variants; REST/gRPC completeness applies to evidence. Subjective motivation requires explicit evidence. Live environments distinguish game evidence from non-game evidence capped at weak. None of those evidence rules was used to grant credit here.

```json
{
  "motivation.subjective": {
    "capability_id": "motivation.subjective",
    "label": "Subjective motivation",
    "domain": "general",
    "priority": 5,
    "explicit_only": true,
    "requirement": {
      "any_terms": [
        "passionate",
        "passion",
        "enthusiasm",
        "interested",
        "interest",
        "motivated"
      ],
      "all_terms": []
    },
    "evidence_concepts": {
      "subjective": [
        "passionate",
        "passion",
        "enthusiasm",
        "enthusiastic",
        "interested",
        "interest",
        "motivated"
      ]
    },
    "evidence_tiers": [
      {
        "label": "direct",
        "any_terms": [
          "passionate",
          "passion",
          "enthusiastic",
          "interested",
          "interest in",
          "motivated"
        ],
        "reason": "explicit_subjective_evidence",
        "concepts": [
          "subjective"
        ]
      }
    ],
    "does_not_prove": [
      "domain experience without an explicit motivation statement"
    ]
  },
  "collaboration.stakeholder": {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "domain": "collaboration",
    "priority": 41,
    "explicit_only": false,
    "requirement": {
      "any_terms": [
        "stakeholder",
        "local and global",
        "global stakeholders",
        "customer collaboration",
        "client collaboration"
      ],
      "all_terms": []
    },
    "evidence_concepts": {
      "stakeholder": [
        "stakeholder",
        "stakeholders",
        "client",
        "clients",
        "customer",
        "customers",
        "local and global",
        "global team",
        "regional team"
      ],
      "collaboration": [
        "collaborate",
        "collaborated",
        "collaboration",
        "team",
        "team members",
        "team of",
        "scrum",
        "coordinate",
        "coordinated"
      ]
    },
    "evidence_tiers": [
      {
        "label": "transferable",
        "all_groups": [
          [
            "stakeholder",
            "stakeholders",
            "client",
            "clients",
            "customer",
            "customers",
            "local and global",
            "global team",
            "regional team"
          ],
          [
            "collaborate",
            "collaboration",
            "coordinate",
            "resolve"
          ]
        ],
        "reason": "explicit_stakeholder_collaboration",
        "concepts": [
          "stakeholder",
          "collaboration"
        ]
      }
    ],
    "does_not_prove": [
      "general teamwork without named stakeholders"
    ]
  },
  "database.design": {
    "capability_id": "database.design",
    "label": "Database design",
    "domain": "database",
    "priority": 103,
    "explicit_only": false,
    "requirement": {
      "any_terms": [
        "database design",
        "data model",
        "schema design",
        "relational database"
      ],
      "all_terms": []
    },
    "evidence_concepts": {
      "database_design": [
        "database",
        "schema",
        "table",
        "postgresql",
        "sqlite",
        "supabase",
        "data model"
      ]
    },
    "evidence_tiers": [
      {
        "label": "direct",
        "all_groups": [
          [
            "designed",
            "created",
            "implemented",
            "built"
          ],
          [
            "database",
            "schema",
            "table",
            "postgresql",
            "sqlite",
            "supabase"
          ]
        ],
        "reason": "explicit_database_design",
        "concepts": [
          "database_design"
        ]
      }
    ],
    "does_not_prove": []
  },
  "backend.api_development": {
    "capability_id": "backend.api_development",
    "label": "Backend API development",
    "domain": "backend",
    "priority": 100,
    "explicit_only": false,
    "requirement": {
      "any_terms": [
        "backend api",
        "rest api",
        "restful api",
        "api development",
        "web service"
      ],
      "all_terms": [],
      "contextual_phrase_variants": [
        {
          "excluded_product_names": [
            "amazon kinesis",
            "amazon kinesis data streams",
            "amazon web services",
            "apache activemq",
            "apache kafka",
            "apache pulsar",
            "azure event hubs",
            "azure service bus",
            "c sharp",
            "c++ programming language",
            "circle ci",
            "configuration manager",
            "confluent platform",
            "docker compose",
            "docker hub",
            "dot net",
            "eclipse mosquitto",
            "express js",
            "github actions",
            "gitlab ci",
            "gitlab ci cd",
            "google cloud platform",
            "google cloud pub sub",
            "google pub sub",
            "ibm mq",
            "message queuing telemetry transport",
            "microsoft azure service bus",
            "microsoft configuration manager",
            "microsoft endpoint configuration manager",
            "microsoft sccm",
            "microsoft sql server",
            "microsoft system center configuration manager",
            "nats io",
            "node js",
            "open telemetry",
            "react js",
            "system center configuration manager",
            "vue js",
            "websphere mq"
          ],
          "guard_contract_version": "native-product-context-guard-v1",
          "phrase": "web services",
          "product_context_guard": "exclude_recognized_multiword_technology_spans"
        }
      ]
    },
    "evidence_concepts": {
      "backend_api": [
        "api",
        "rest api",
        "restful api",
        "endpoint",
        "web service",
        "fastapi",
        "postgrest",
        "backend integration"
      ]
    },
    "evidence_tiers": [
      {
        "label": "direct",
        "all_groups": [
          [
            "built",
            "implemented",
            "developed",
            "created",
            "integrated"
          ],
          [
            "api",
            "rest api",
            "restful api",
            "endpoint",
            "web service",
            "fastapi",
            "postgrest"
          ]
        ],
        "reason": "explicit_backend_api_implementation",
        "concepts": [
          "backend_api"
        ]
      }
    ],
    "does_not_prove": [
      "distributed systems architecture"
    ]
  },
  "operations.live_environment": {
    "capability_id": "operations.live_environment",
    "label": "Live environment handling",
    "domain": "operations",
    "priority": 34,
    "explicit_only": false,
    "requirement": {
      "any_terms": [
        "live environment",
        "production environment",
        "live server",
        "production server"
      ],
      "all_terms": []
    },
    "evidence_concepts": {
      "live_environment": [
        "live environment",
        "production environment",
        "live server",
        "production server"
      ],
      "game_domain": [
        "game",
        "games",
        "gaming",
        "gameplay",
        "unity",
        "unreal",
        "fmod",
        "game engine",
        "custom engine",
        "google play",
        "player"
      ]
    },
    "evidence_tiers": [
      {
        "label": "transferable",
        "all_groups": [
          [
            "live environment",
            "production environment",
            "live server",
            "production server"
          ],
          [
            "game",
            "gaming",
            "game product"
          ]
        ],
        "reason": "explicit_game_live_environment",
        "concepts": [
          "live_environment",
          "game_domain"
        ]
      },
      {
        "label": "weak",
        "any_terms": [
          "live environment",
          "production environment",
          "live server",
          "production server"
        ],
        "reason": "non_game_live_environment_capped_at_weak",
        "concepts": [
          "live_environment"
        ]
      }
    ],
    "does_not_prove": []
  }
}
```

## Shared findings, bounded next decision and proposed controls

Common literal boundary confirmed in all thirteen; common production defect confirmed in zero. Seven stakeholder observations include beneficiaries, explicit interactions and mixed technical delivery. Three API observations comprise one bounded API obligation and two broad mixed requirements. They must not receive one uniform remedy. No source loss is established: raw parent grounding and conserved allocations remain recorded. U+FFFD and wrapped source lines are already present in stored JD; their origin is not proven to be the current parser.

Human review of semantic applicability and bounded REST API plural-recognition policy; separate runtime-change approval required. No YES fixes under current contract.

```json
{
  "status": "Design only; human authorization and version/currentness review before runtime change",
  "direction": "Start with bounded requirement-side REST API / RESTful API plural recognition, not global stemming and not new capability mappings. Stakeholder recognition needs affirmative interaction/scope review separately.",
  "positive": [
    "The frozen Job146 bounded RESTful APIs obligation; singular RESTful API and REST API controls"
  ],
  "negative": [
    "Amazon Web Services product name; API-adjacent distributed architecture; beneficiary-only stakeholder nouns; application interests invitation"
  ],
  "partial": [
    "API plus database/business-rule/integration obligation; collaboration plus implementation; live environment plus AI validation"
  ],
  "scope": [
    "REST and gRPC both mandatory vs REST or gRPC alternatives; familiarity vs implementation; preferred vs required; absent or conflicting parent grounding; negated API work"
  ],
  "stability": [
    "Keep one conserved parent allocation; deterministic output; no evidence promotion from recognition; explicit gRPC completeness; no invented registry relationships; Phase8 verified-claim lineage unchanged; Phase9E project selection unchanged; review existing version/currentness mechanism before behavioral edits"
  ],
  "missing_approval": "Approved plural-equivalence and complete-scope policy. Exact approved terms currently exclude these plurals, so semantic benefit is not proof of a contract violation.",
  "confirmed_development_defect_impact": 0,
  "plausible_development_scope": [
    "Job146 RESTful APIs",
    "Job163 affirmative stakeholder interaction"
  ],
  "broader_impact": "Unknown; do not extrapolate to 449 development occurrences",
  "protected_benchmark_impact": "Unevaluated; protected examples not used as development controls"
}
```

No YES fix is established, so no test asserts an unapproved production promotion. The strongest next review is the exact Job146 plural API obligation, under an explicitly bounded recognition policy rather than modifying _contains globally. Approval must cover source completeness and existing version/currentness identity before behavioral edits. Unknown broader impact; protected benchmark impact unevaluated. This report must not be used as a V5 reviewer packet or human gold.

## Preservation and reproducibility

Manifest fingerprint: `161024a5780a23693b61e4bea21e139ccb60abcc3760d1147adac153d920d04d`. V1 source report: `c33e45563cbbbfd18bed3f0662b583781bcee688ad2ab95e2b705536326684f5`. Protected prior files: 150. Database SHA256: `36ddd0a73d2c15823b23deed3207c92be4971008d411fabeb3c07a2da4d4a9c3`.

Current versions: {"taxonomy": "phase6d-capability-taxonomy-v1.5", "registry": "technology-registry-v1.3", "scorer_identification_only": "stable-evidence-v1.16-phase6d20", "resolver_separate_version": null, "resolver_file_sha256": "09610d229e054169ceb4146b5a8fce924a242b891e9b902ea8655bf76ccce060"}. No separate resolver version exists in this helper; its file hash is recorded as a research diagnostic, not a parallel production version system.

Run `python -B -m scripts.investigate_existing_predicate_backlog_v2 freeze`, then `probe`, then `finalize` only against absent versioned outputs and the exact V1 DB/protected bytes. Each stage fails closed on drift. Existing outputs are retained. JSON records original inputs, source anchors, full contracts, term checks, saved historical provenance and current pure outcomes.

Zero model/network/provider calls; zero DB writes, parser/evidence matching/scoring executions or production edits. No gold reads, labels, benchmark execution, commits, pushes, merges or branch changes.

## Focused validation

- `.venv\Scripts\python.exe -B -m unittest tests.test_existing_predicate_investigation_v2 -v`: 11/11 passed (0.088s).
- `.venv\Scripts\python.exe -B -m unittest tests.test_unresolved_backlog_clustering_v1 -v`: 14/14 passed (0.208s).
- Two Python AST checks and five-file whitespace checks passed.
- All 150 prior protected hashes, SQLite bytes, manifest/report seals, exact source fingerprints, thirteen-case/nine-job cohort, quarantine and parent allocations passed.
- `git diff --check` passed; `git status --short` inspected. Five new untracked V2 files only; all earlier edits preserved. No full suite or project gates run.
