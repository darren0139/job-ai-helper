# Unresolved backlog clustering V1

**Descriptive investigation only. No requirements were fixed. No clusters are approved routes or root causes.**

This development report is not a V5 reviewer packet; do not distribute it as independent review material.

## Source selection

SQLite mode=ro/query_only in one read transaction, without schema initialization. Latest Job Finder snapshot means maximum ID per discovered job, matching the existing corpus API. Active backlog requires an active existing job and equal snapshot/current JD content hashes. Expired, changed-source and superseded snapshots are separate history. Current knowledge is rechecked using the existing pure production resolver on stored canonical inputs. Stored match labels/eligibility remain historical metadata, not newly calculated scores.

Application views select the maximum active version ID per existing application. Exact transport-normalized JD fingerprints group these into document views, not guessed Job Finder job IDs. Repeated application views are collapsed while preserving provenance. Archived/orphaned analyses and unversioned reports are separately counted, not silently current. Missing source/analysis means unknown backlog. No resume evidence or full JD export.

```json
{
  "source_inventory": {
    "analysis_versions": 58,
    "archived_analysis_versions": 3,
    "orphaned_analysis_versions": 0,
    "unversioned_application_reports": 18,
    "database_user_version": 0,
    "sqlite_runtime": "3.50.4",
    "journal_mode": "delete",
    "query_only": 1,
    "snapshot_rows_total": 54,
    "snapshot_invalid_json": 0
  },
  "selection": {
    "inactive_job": 12,
    "active_same_hash": 26
  },
  "latest_snapshot_job_count": 38,
  "active_jobs_without_selected_snapshot": 299,
  "application_latest_active_analysis_count": 55,
  "application_distinct_jd_documents": 17,
  "application_version_distribution": [
    {
      "scoring_version": "stable-evidence-v1.10-phase6d15",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
      "cache_version": "analysis-cache-v1",
      "pipeline_contract_version": "analysis-pipeline-v2-title-stability-phase6d6",
      "analyses": 2
    },
    {
      "scoring_version": "stable-evidence-v1.16-phase6d20",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.5",
      "cache_version": "analysis-cache-v1",
      "pipeline_contract_version": "analysis-pipeline-v2-title-stability-phase6d6",
      "analyses": 4
    },
    {
      "scoring_version": "stable-evidence-v1.3-phase6d6",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.2",
      "cache_version": "analysis-cache-v1",
      "pipeline_contract_version": "analysis-pipeline-v2-title-stability-phase6d6",
      "analyses": 3
    },
    {
      "scoring_version": "stable-evidence-v1.3-phase6d7",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.2",
      "cache_version": "analysis-cache-v1",
      "pipeline_contract_version": "analysis-pipeline-v2-title-stability-phase6d6",
      "analyses": 26
    },
    {
      "scoring_version": "stable-evidence-v1.3-phase6d7",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.2",
      "cache_version": "analysis-cache-v1",
      "pipeline_contract_version": "phase9f-d-existing-application-baseline-v1",
      "analyses": 17
    },
    {
      "scoring_version": "stable-evidence-v1.4-phase6d8",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.3",
      "cache_version": "analysis-cache-v1",
      "pipeline_contract_version": "analysis-pipeline-v2-title-stability-phase6d6",
      "analyses": 2
    },
    {
      "scoring_version": "stable-evidence-v1.7-phase6d12",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
      "cache_version": "analysis-cache-v1",
      "pipeline_contract_version": "analysis-pipeline-v2-title-stability-phase6d6",
      "analyses": 1
    }
  ],
  "snapshot_history_counts": {
    "canonical_records": 1197,
    "stored_unresolved_records": 893,
    "distinct_job_requirement_text_occurrences": 956,
    "repeated_snapshot_record_views": 241,
    "superseded_snapshot_rows": 16,
    "stored_unresolved_distinct_occurrences": 719,
    "stored_unresolved_duplicate_snapshot_views": 174
  },
  "latest_snapshot_versions": [
    {
      "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.1",
      "scoring_version": "stable-evidence-v1.9-phase6d14",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
      "jobs": 2
    },
    {
      "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2",
      "scoring_version": "stable-evidence-v1.10-phase6d16",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
      "jobs": 24
    },
    {
      "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2",
      "scoring_version": "stable-evidence-v1.10-phase6d16",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.5",
      "jobs": 1
    },
    {
      "match_version": "job-match-snapshot-v2.3.0|registry=technology-registry-v1.3",
      "scoring_version": "stable-evidence-v1.16-phase6d20",
      "taxonomy_version": "phase6d-capability-taxonomy-v1.5",
      "jobs": 11
    }
  ]
}
```

## Backlog scopes — do not sum them

| Scope | Canonical views | Knowledge unresolved | Distinct occurrences | Unique wording | Development occurrences | Development jobs/JD documents |
|---|---:|---:|---:|---:|---:|---:|
| active_same_hash | 656 | 501 | 501 | 494 | 449 | 26 |
| application_latest_active | 928 | 425 | 221 | 166 | 215 | 17 |
| inactive_job | 296 | 202 | 202 | 202 | 178 | 12 |

Occurrences use job/JD key + requirement ID + normalized text. This includes professional/credential requirements and is NOT the old meaningful-technical denominator or proven taxonomy-gap count. Analysis-only NFKC/case folding/whitespace/zero-width normalization preserves punctuation/C#/C++; production is unchanged.

## Quarantine and wording grouping

Forty protected keys derive from blinded V5 IDs and existing protected-control IDs, with text/family data from the frozen canonical source only. No reviewer decisions, gold answers or previous recommendations are used. Keys, shared parents, exact/near texts and protected parent surfaces are removed before descriptions or examples. Only exclusion counts are reported. Protected content is not used to design improvements.

The hash-pinned recovery cache supplies only verified original parent surfaces and occurrence IDs. No recommendation or reviewer-decision field is accessed. A clause of at least three tokens contained in a protected parent is quarantined even when length differences defeat fuzzy thresholds.

Quarantine: exact normalization; whole-boundary short protected phrases; token Jaccard >=0.70 or character ratio >=0.88, token-length ratio >=0.60. It intentionally overexcludes. Development near groups use complete-link comparisons, identical technology-candidate/negative-scope signatures, Jaccard >=0.82 or character ratio >=0.92, token-length ratio >=0.75. No transitive chaining or shared-defect inference.

### active_same_hash

```json
{
  "quarantine_excluded_record_counts": {
    "protected_key": 24,
    "shared_protected_parent": 16,
    "protected_parent_clause_containment": 3,
    "protected_near_text_or_parent": 6,
    "privacy_sensitive_text": 3
  },
  "knowledge_counts": {
    "UNRESOLVED": 501,
    "CAPABILITY_RESOLVED": 152,
    "TECHNOLOGY_IDENTITY_RESOLVED": 3
  },
  "knowledge_resolved_but_stored_applicant_none": 69,
  "counts": {
    "canonical_records": 656,
    "stored_knowledge_unresolved": 500,
    "stored_applicant_none": 504,
    "current_knowledge_unresolved_records": 501,
    "eligible_unresolved_records": 501,
    "unresolved_with_stored_positive_match": 66,
    "duplicate_current_record_views": 0
  }
}
```

### application_latest_active

```json
{
  "quarantine_excluded_record_counts": {
    "protected_near_text_or_parent": 4,
    "protected_exact_text": 2
  },
  "knowledge_counts": {
    "CAPABILITY_RESOLVED": 503,
    "UNRESOLVED": 425
  },
  "knowledge_resolved_but_stored_applicant_none": 384,
  "counts": {
    "canonical_records": 928,
    "stored_knowledge_unresolved": 559,
    "stored_applicant_none": 731,
    "current_knowledge_unresolved_records": 425,
    "eligible_unresolved_records": 425,
    "unresolved_with_stored_positive_match": 78,
    "duplicate_current_record_views": 204
  }
}
```

### inactive_job

```json
{
  "quarantine_excluded_record_counts": {
    "protected_key": 14,
    "protected_parent_clause_containment": 5,
    "shared_protected_parent": 1,
    "protected_near_text_or_parent": 2,
    "privacy_sensitive_text": 2
  },
  "knowledge_counts": {
    "UNRESOLVED": 202,
    "CAPABILITY_RESOLVED": 90,
    "TECHNOLOGY_IDENTITY_RESOLVED": 4
  },
  "knowledge_resolved_but_stored_applicant_none": 52,
  "counts": {
    "canonical_records": 296,
    "stored_knowledge_unresolved": 208,
    "stored_applicant_none": 233,
    "current_knowledge_unresolved_records": 202,
    "eligible_unresolved_records": 202,
    "unresolved_with_stored_positive_match": 21,
    "duplicate_current_record_views": 0
  }
}
```

## Overlapping descriptions and investigation order

Sort: distinct jobs/JD documents, unique wording, verified-parent count, stable dimension name. No opaque impact score or invented score gains. Counts overlap. Aliases are not resolved identities; word cues are not affirmative duties; predicate observations reuse the existing report-only observer, including conjunction/exclusion/custom-policy boundaries, and are not production resolution or evidence credits.

### active_same_hash

| Rank | Description | Occurrences | Unique wording | Jobs/JD documents | Verified parent | Inspect first |
|---:|---|---:|---:|---:|---:|---|
| 1 | activity cues | 158 | 157 | 26 | 151 | Capability predicates/native resolver; verify activity and exclusions |
| 2 | generic technical cues | 154 | 154 | 25 | 150 | Source-scope/provenance review before narrower diagnosis |
| 3 | no specific cue | 103 | 101 | 25 | 103 | Manual source investigation; no forced route |
| 4 | optional or alternative cues | 54 | 53 | 23 | 54 | JD extraction/decomposition and nonmandatory scope |
| 5 | parent scope differs | 108 | 105 | 22 | 101 | Source-scope/decomposition; difference alone is not a defect |
| 6 | familiarity exposure cues | 75 | 74 | 19 | 75 | Identity scope and qualification boundaries |
| 7 | professional behavior cues | 48 | 47 | 17 | 47 | Professional requirement handling; not automatic technical capabilities |
| 8 | credential or duration cues | 18 | 18 | 16 | 18 | Credential/eligibility handling |
| 9 | technology alias candidates | 19 | 19 | 12 | 18 | Technology registry/identity scope; candidates are not full resolution |
| 10 | existing predicate observations | 13 | 13 | 9 | 13 | Existing capability predicates/native selector; no credit inferred |
| 11 | parent not verified | 15 | 15 | 6 | 0 | Provenance preservation/source recovery |
| 12 | technology:sql | 7 | 7 | 6 | 6 | Technology registry/identity scope; candidates are not full resolution |
| 13 | predicate:collaboration.stakeholder | 7 | 7 | 5 | 7 | Existing capability predicates/native selector; no credit inferred |
| 14 | technology:python | 5 | 5 | 5 | 5 | Technology registry/identity scope; candidates are not full resolution |
| 15 | technology activity cooccurrence | 5 | 5 | 4 | 4 | Contextual relationships/native resolver; not an approved mapping |
| 16 | predicate:backend.api development | 3 | 3 | 2 | 3 | Existing capability predicates/native selector; no credit inferred |
| 17 | predicate:database.design | 3 | 3 | 2 | 3 | Existing capability predicates/native selector; no credit inferred |
| 18 | technology:csharp | 3 | 3 | 2 | 3 | Technology registry/identity scope; candidates are not full resolution |
| 19 | predicate:operations.live environment | 2 | 2 | 2 | 2 | Existing capability predicates/native selector; no credit inferred |
| 20 | technology:angular | 2 | 2 | 2 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 21 | technology:node.js | 2 | 2 | 2 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 22 | technology:react | 2 | 2 | 2 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 23 | technology:java | 2 | 2 | 1 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 24 | negative scope cues | 1 | 1 | 1 | 1 | Requirement exclusions/source-scope preservation |
| 25 | normalization artifacts | 1 | 1 | 1 | 1 | Native normalization/source preservation |
| 26 | predicate:motivation.subjective | 1 | 1 | 1 | 1 | Existing capability predicates/native selector; no credit inferred |
| 27 | technology:javascript | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 28 | technology:jenkins | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |

#### activity cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 102, 'PARSER_OR_DECOMPOSITION_BLOCKED': 39, 'MIXED_SCOPE': 11, 'AMBIGUOUS': 6}. Parent available 156/158; verified 151. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> You will also be guiding the development team through the implementation of robust deployment pipelines while referring to technical standards, enterprise governance frameworks, and agile best practices

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_03d7f10bed8c]`; job/JD `job:141`; requirement `req_03d7f10bed8c`.

> You will be analysing complex business requirements, software architectures, and diverse codebases

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_dfb77dd505ae]`; job/JD `job:141`; requirement `req_dfb77dd505ae`.

> Collaborate closely with development and platform engineering teams to ensure the reliability and quality of our software applications

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_2e64599b8822]`; job/JD `job:144`; requirement `req_2e64599b8822`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### generic technical cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 67, 'TECHNOLOGY_PLUS_CAPABILITY': 1, 'PARSER_OR_DECOMPOSITION_BLOCKED': 68, 'MIXED_SCOPE': 10, 'AMBIGUOUS': 8}. Parent available 152/154; verified 150. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> You will also be guiding the development team through the implementation of robust deployment pipelines while referring to technical standards, enterprise governance frameworks, and agile best practices

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_03d7f10bed8c]`; job/JD `job:141`; requirement `req_03d7f10bed8c`.

> review, enhance, and recommend new engineering processes to ensure applications are in compliance with established enterprise architecture and control frameworks

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_4da5abe81932]`; job/JD `job:141`; requirement `req_4da5abe81932`.

> You will be analysing complex business requirements, software architectures, and diverse codebases

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_dfb77dd505ae]`; job/JD `job:141`; requirement `req_dfb77dd505ae`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### no specific cue

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 53, 'AMBIGUOUS': 42, 'TECHNOLOGY_PLUS_ACTIVITY': 8}. Parent available 103/103; verified 103. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Fresh graduates are welcomed to apply

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_42cb1e3f6838]`; job/JD `job:141`; requirement `req_42cb1e3f6838`.

> Champion a culture of quality and reliability across teams, sharing knowledge and promoting best practices

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_0d81ed5178da]`; job/JD `job:144`; requirement `req_0d81ed5178da`.

> Contribute to strengthen DevOps methodologies, processes, and best practices within the organization

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_870ae701fa09]`; job/JD `job:144`; requirement `req_870ae701fa09`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### optional or alternative cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 14, 'PARSER_OR_DECOMPOSITION_BLOCKED': 37, 'AMBIGUOUS': 1, 'MIXED_SCOPE': 2}. Parent available 54/54; verified 54. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Bachelor's degree in Computer Science, Engineering, or related field (or equivalent work experience)

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_09059367ecbc]`; job/JD `job:144`; requirement `req_09059367ecbc`.

> (c) Front-end frameworks such as React, Node.js, or Angular 2

Source `job_match_snapshots[id=40].stable_analysis_json::canonical_requirements[requirement_id=req_8068b2faffec]`; job/JD `job:146`; requirement `req_8068b2faffec`.

> Experience in gathering user’s requirements – clarifying them with Product Owners and Designers through high fidelity mock-ups or prototypes

Source `job_match_snapshots[id=40].stable_analysis_json::canonical_requirements[requirement_id=req_8f8aaa236fc2]`; job/JD `job:146`; requirement `req_8f8aaa236fc2`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### parent scope differs

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 32, 'PARSER_OR_DECOMPOSITION_BLOCKED': 43, 'TECHNOLOGY_PLUS_CAPABILITY': 2, 'AMBIGUOUS': 27, 'MIXED_SCOPE': 4}. Parent available 107/108; verified 101. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> review, enhance, and recommend new engineering processes to ensure applications are in compliance with established enterprise architecture and control frameworks

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_4da5abe81932]`; job/JD `job:141`; requirement `req_4da5abe81932`.

> Experience with agile methodologies

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_04f30d212c80]`; job/JD `job:144`; requirement `req_04f30d212c80`.

> Experience with frameworks (jest, pytest, playwright, Selenium, etc.)

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_199774cf1c82]`; job/JD `job:144`; requirement `req_199774cf1c82`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### familiarity exposure cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 15, 'PARSER_OR_DECOMPOSITION_BLOCKED': 29, 'TECHNOLOGY_PLUS_CAPABILITY': 2, 'AMBIGUOUS': 27, 'MIXED_SCOPE': 2}. Parent available 75/75; verified 75. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Experience with agile methodologies

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_04f30d212c80]`; job/JD `job:144`; requirement `req_04f30d212c80`.

> Experience with frameworks (jest, pytest, playwright, Selenium, etc.)

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_199774cf1c82]`; job/JD `job:144`; requirement `req_199774cf1c82`.

> Knowledge of cloud platform is a plus

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_4f98ecd531dd]`; job/JD `job:144`; requirement `req_4f98ecd531dd`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### professional behavior cues

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 18, 'MIXED_SCOPE': 28, 'TECHNOLOGY_PLUS_ACTIVITY': 2}. Parent available 48/48; verified 47. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Collaborate closely with development and platform engineering teams to ensure the reliability and quality of our software applications

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_2e64599b8822]`; job/JD `job:144`; requirement `req_2e64599b8822`.

> Collaborate with development teams to ensure seamless integration of quality practices into the software development lifecycle

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_3cf0a2821a01]`; job/JD `job:144`; requirement `req_3cf0a2821a01`.

> Strong analytical and problem-solving skills, with the ability to troubleshoot complex technical issues

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_fb37db79ac88]`; job/JD `job:144`; requirement `req_fb37db79ac88`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### credential or duration cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 5, 'PARSER_OR_DECOMPOSITION_BLOCKED': 10, 'AMBIGUOUS': 3}. Parent available 18/18; verified 18. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Bachelor's degree in Computer Science, Engineering, or related field (or equivalent work experience)

Source `job_match_snapshots[id=24].stable_analysis_json::canonical_requirements[requirement_id=req_09059367ecbc]`; job/JD `job:144`; requirement `req_09059367ecbc`.

> Diploma or degree in Computer Science, Computer or Electronics Engineering, Information Technology or related disciplines

Source `job_match_snapshots[id=40].stable_analysis_json::canonical_requirements[requirement_id=req_a4790f76c7d8]`; job/JD `job:146`; requirement `req_a4790f76c7d8`.

> Operate with a high degree of autonomy

Source `job_match_snapshots[id=26].stable_analysis_json::canonical_requirements[requirement_id=req_4f0b0618a097]`; job/JD `job:240`; requirement `req_4f0b0618a097`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### technology alias candidates

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 13, 'AMBIGUOUS': 2, 'TECHNOLOGY_PLUS_ACTIVITY': 4}. Parent available 19/19; verified 18. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> (c) Front-end frameworks such as React, Node.js, or Angular 2

Source `job_match_snapshots[id=40].stable_analysis_json::canonical_requirements[requirement_id=req_8068b2faffec]`; job/JD `job:146`; requirement `req_8068b2faffec`.

> Scripting, programming, and automation languages (e.g. Ansible, PowerShell, Python)

Source `job_match_snapshots[id=25].stable_analysis_json::canonical_requirements[requirement_id=req_1c8deffcd417]`; job/JD `job:158`; requirement `req_1c8deffcd417`.

> Advanced proficiency in at least one analytical tool such as Python, SQL, Power BI, Tableau, or equivalent tools

Source `job_match_snapshots[id=41].stable_analysis_json::canonical_requirements[requirement_id=req_0c8cc53a6b76]`; job/JD `job:187`; requirement `req_0c8cc53a6b76`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### existing predicate observations

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 1, 'MIXED_SCOPE': 7, 'TECHNOLOGY_PLUS_ACTIVITY': 5}. Parent available 13/13; verified 13. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Design and develop RESTful APIs

Source `job_match_snapshots[id=40].stable_analysis_json::canonical_requirements[requirement_id=req_9270e95898c8]`; job/JD `job:146`; requirement `req_9270e95898c8`.

> Build good relations and workflows with internal and external stakeholders

Source `job_match_snapshots[id=25].stable_analysis_json::canonical_requirements[requirement_id=req_07301e1d0303]`; job/JD `job:158`; requirement `req_07301e1d0303`.

> Collaborate with various stakeholders to build mission-ready tools and platforms

Source `job_match_snapshots[id=25].stable_analysis_json::canonical_requirements[requirement_id=req_5e1c1de91a3c]`; job/JD `job:158`; requirement `req_5e1c1de91a3c`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### parent not verified

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 6, 'TECHNOLOGY_PLUS_ACTIVITY': 7, 'AMBIGUOUS': 2}. Parent available 7/15; verified 0. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: PARENT_PROVENANCE_VERIFICATION_NEEDED.

> acquire niche expertise in cybersecurity practices to meet high standards, rigorously challenge assumptions, and significantly reduce attack surfaces before deployment

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_1fe3445f9749]`; job/JD `job:141`; requirement `req_1fe3445f9749`.

> maintain oversight of the software development lifecycle

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_4ebe283a83bc]`; job/JD `job:141`; requirement `req_4ebe283a83bc`.

> Secure coding practices

Source `job_match_snapshots[id=32].stable_analysis_json::canonical_requirements[requirement_id=req_5a2fe56ceb02]`; job/JD `job:141`; requirement `req_5a2fe56ceb02`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### technology:sql

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 3, 'AMBIGUOUS': 2, 'TECHNOLOGY_PLUS_ACTIVITY': 2}. Parent available 7/7; verified 6. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Advanced proficiency in at least one analytical tool such as Python, SQL, Power BI, Tableau, or equivalent tools

Source `job_match_snapshots[id=41].stable_analysis_json::canonical_requirements[requirement_id=req_0c8cc53a6b76]`; job/JD `job:187`; requirement `req_0c8cc53a6b76`.

> Familiarity with SQL databases will be an advantage

Source `job_match_snapshots[id=53].stable_analysis_json::canonical_requirements[requirement_id=req_f965161ec832]`; job/JD `job:364`; requirement `req_f965161ec832`.

> Experience with database access (SQL/NoSQL) and USB Host/device driver development to support software functionality

Source `job_match_snapshots[id=54].stable_analysis_json::canonical_requirements[requirement_id=req_0722e1cf21ff]`; job/JD `job:425`; requirement `req_0722e1cf21ff`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.

### application_latest_active

| Rank | Description | Occurrences | Unique wording | Jobs/JD documents | Verified parent | Inspect first |
|---:|---|---:|---:|---:|---:|---|
| 1 | parent scope differs | 136 | 109 | 16 | 9 | Source-scope/decomposition; difference alone is not a defect |
| 2 | activity cues | 97 | 72 | 16 | 23 | Capability predicates/native resolver; verify activity and exclusions |
| 3 | generic technical cues | 66 | 52 | 15 | 23 | Source-scope/provenance review before narrower diagnosis |
| 4 | professional behavior cues | 25 | 20 | 15 | 5 | Professional requirement handling; not automatic technical capabilities |
| 5 | parent not verified | 166 | 130 | 13 | 0 | Provenance preservation/source recovery |
| 6 | familiarity exposure cues | 34 | 27 | 13 | 4 | Identity scope and qualification boundaries |
| 7 | optional or alternative cues | 31 | 23 | 10 | 2 | JD extraction/decomposition and nonmandatory scope |
| 8 | technology alias candidates | 22 | 16 | 7 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 9 | existing predicate observations | 8 | 8 | 5 | 0 | Existing capability predicates/native selector; no credit inferred |
| 10 | no specific cue | 12 | 6 | 5 | 9 | Manual source investigation; no forced route |
| 11 | credential or duration cues | 5 | 4 | 5 | 1 | Credential/eligibility handling |
| 12 | technology:python | 10 | 6 | 4 | 0 | Technology registry/identity scope; candidates are not full resolution |
| 13 | technology:react | 4 | 3 | 4 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 14 | technology activity cooccurrence | 7 | 4 | 3 | 0 | Contextual relationships/native resolver; not an approved mapping |
| 15 | technology:sql | 2 | 2 | 2 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 16 | predicate:backend.api development | 2 | 2 | 2 | 0 | Existing capability predicates/native selector; no credit inferred |
| 17 | predicate:frontend.ui development | 2 | 2 | 2 | 0 | Existing capability predicates/native selector; no credit inferred |
| 18 | technology:amazon.web.services | 2 | 2 | 2 | 0 | Technology registry/identity scope; candidates are not full resolution |
| 19 | technology:javascript | 2 | 2 | 2 | 0 | Technology registry/identity scope; candidates are not full resolution |
| 20 | technology:csharp | 2 | 1 | 2 | 0 | Technology registry/identity scope; candidates are not full resolution |
| 21 | technology:angular | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 22 | technology:node.js | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 23 | predicate:data.processing | 1 | 1 | 1 | 0 | Existing capability predicates/native selector; no credit inferred |
| 24 | predicate:database.design | 1 | 1 | 1 | 0 | Existing capability predicates/native selector; no credit inferred |
| 25 | predicate:domain.recent shooter | 1 | 1 | 1 | 0 | Existing capability predicates/native selector; no credit inferred |
| 26 | predicate:game.engine systems | 1 | 1 | 1 | 0 | Existing capability predicates/native selector; no credit inferred |
| 27 | technology:amazon.s3 | 1 | 1 | 1 | 0 | Technology registry/identity scope; candidates are not full resolution |
| 28 | technology:fastapi | 1 | 1 | 1 | 0 | Technology registry/identity scope; candidates are not full resolution |
| 29 | technology:typescript | 1 | 1 | 1 | 0 | Technology registry/identity scope; candidates are not full resolution |

#### parent scope differs

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 73, 'TECHNOLOGY_PLUS_ACTIVITY': 48, 'MIXED_SCOPE': 15}. Parent available 136/136; verified 9. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> coding, calling into our software stack and creating applications which utilise our software stack to meet the needs of clients

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_4bb74f3c4202]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_4bb74f3c4202`.

> working with clients to understand their needs and in turn, implement their requirements accordingly

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_db5cba792b43]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_db5cba792b43`.

> performing software integration for specific use cases

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_f2466e29a079]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_f2466e29a079`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### activity cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 57, 'PARSER_OR_DECOMPOSITION_BLOCKED': 33, 'MIXED_SCOPE': 7}. Parent available 97/97; verified 23. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Lead the test of applications and software integration works you create

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_5e956691a726]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_5e956691a726`.

> Comfortable in writing and debugging high performance native code

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_84fb490e471b]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_84fb490e471b`.

> working with clients to understand their needs and in turn, implement their requirements accordingly

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_db5cba792b43]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_db5cba792b43`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### generic technical cues

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 28, 'MIXED_SCOPE': 10, 'TECHNOLOGY_PLUS_ACTIVITY': 27, 'AMBIGUOUS': 1}. Parent available 66/66; verified 23. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> coding, calling into our software stack and creating applications which utilise our software stack to meet the needs of clients

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_4bb74f3c4202]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_4bb74f3c4202`.

> Lead the test of applications and software integration works you create

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_5e956691a726]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_5e956691a726`.

> Able to do technical communication to understand and explain the needs of end-users

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_9c8ea29ec6ed]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_9c8ea29ec6ed`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### professional behavior cues

Native scopes: {'MIXED_SCOPE': 22, 'PARSER_OR_DECOMPOSITION_BLOCKED': 3}. Parent available 25/25; verified 5. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Able to do technical communication to understand and explain the needs of end-users

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_9c8ea29ec6ed]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_9c8ea29ec6ed`.

> Collaborate with other developers and engineers to specify, design, build, and maintain software applications

Source `application_analysis_versions[id=56].report_json::stable_analysis.canonical_requirements[requirement_id=req_26d895b9a27f]`; job/JD `application-jd:86f10cba77ed9375eeb810d0e80312f747e916912f599e4d72980f509f072bdc`; requirement `req_26d895b9a27f`.

> Candidates with critical thinking, analytical and creative problem-solving skills is highly desired

Source `application_analysis_versions[id=56].report_json::stable_analysis.canonical_requirements[requirement_id=req_b57c19e5162c]`; job/JD `application-jd:86f10cba77ed9375eeb810d0e80312f747e916912f599e4d72980f509f072bdc`; requirement `req_b57c19e5162c`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### parent not verified

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 99, 'TECHNOLOGY_PLUS_ACTIVITY': 46, 'MIXED_SCOPE': 18, 'MULTIPLE_NATIVE_SCOPE_OBSERVATIONS': 3}. Parent available 164/166; verified 0. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: PARENT_PROVENANCE_VERIFICATION_NEEDED.

> Build and maintain asset-loading and asset-management functionality

Source `application_analysis_versions[id=43].report_json::stable_analysis.canonical_requirements[requirement_id=req_3d9611a79e90]`; job/JD `application-jd:52c3150ed6dc4506f24fd3a3685e2e9104d49aec11bccdb9c07a38172f36e937`; requirement `req_3d9611a79e90`.

> Integrate gameplay systems across engine components

Source `application_analysis_versions[id=43].report_json::stable_analysis.canonical_requirements[requirement_id=req_b823640ff50b]`; job/JD `application-jd:52c3150ed6dc4506f24fd3a3685e2e9104d49aec11bccdb9c07a38172f36e937`; requirement `req_b823640ff50b`.

> Collaborate with other engineers on a shared codebase

Source `application_analysis_versions[id=43].report_json::stable_analysis.canonical_requirements[requirement_id=req_d70d7b216b97]`; job/JD `application-jd:52c3150ed6dc4506f24fd3a3685e2e9104d49aec11bccdb9c07a38172f36e937`; requirement `req_d70d7b216b97`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### familiarity exposure cues

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 29, 'MIXED_SCOPE': 1, 'MULTIPLE_NATIVE_SCOPE_OBSERVATIONS': 1, 'AMBIGUOUS': 3}. Parent available 33/34; verified 4. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Familiarity with Nvidia CUDA

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_114b8916fb46]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_114b8916fb46`.

> Knowledge of databases (SQL / NoSQL) is an advantage

Source `application_analysis_versions[id=56].report_json::stable_analysis.canonical_requirements[requirement_id=req_c3b362e0255b]`; job/JD `application-jd:86f10cba77ed9375eeb810d0e80312f747e916912f599e4d72980f509f072bdc`; requirement `req_c3b362e0255b`.

> Advanced proficiency in at least one language

Source `application_analysis_versions[id=52].report_json::stable_analysis.canonical_requirements[requirement_id=req_c214c63aa484]`; job/JD `application-jd:9f5b6a801bcefc84589e8f13f99494f2dd769d84c4832ee5668f77689804c1b8`; requirement `req_c214c63aa484`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### optional or alternative cues

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 21, 'TECHNOLOGY_PLUS_ACTIVITY': 9, 'MIXED_SCOPE': 1}. Parent available 31/31; verified 2. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Familiar with concepts of software engineering and Agile Development is preferred

Source `application_analysis_versions[id=56].report_json::stable_analysis.canonical_requirements[requirement_id=req_73ffb410c613]`; job/JD `application-jd:86f10cba77ed9375eeb810d0e80312f747e916912f599e4d72980f509f072bdc`; requirement `req_73ffb410c613`.

> Support your team’s production software by responding to an occasional alert or bug report

Source `application_analysis_versions[id=52].report_json::stable_analysis.canonical_requirements[requirement_id=req_14b079c1b45e]`; job/JD `application-jd:9f5b6a801bcefc84589e8f13f99494f2dd769d84c4832ee5668f77689804c1b8`; requirement `req_14b079c1b45e`.

> Experience building AI applications or LLM-powered software workflows

Source `application_analysis_versions[id=4].report_json::stable_analysis.canonical_requirements[requirement_id=req_0d08d11d5e16]`; job/JD `application-jd:733f817ce4581149bfe15e5083951b1210f2ce9e34c1df9411792bfd1812d43a`; requirement `req_0d08d11d5e16`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### technology alias candidates

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 5, 'PARSER_OR_DECOMPOSITION_BLOCKED': 17}. Parent available 22/22; verified 2. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> comfortable using AngularJS, NodeJS, ReactJS and other common frameworks is an advantage

Source `application_analysis_versions[id=56].report_json::stable_analysis.canonical_requirements[requirement_id=req_67c5d07c55c1]`; job/JD `application-jd:86f10cba77ed9375eeb810d0e80312f747e916912f599e4d72980f509f072bdc`; requirement `req_67c5d07c55c1`.

> Knowledge of databases (SQL / NoSQL) is an advantage

Source `application_analysis_versions[id=56].report_json::stable_analysis.canonical_requirements[requirement_id=req_c3b362e0255b]`; job/JD `application-jd:86f10cba77ed9375eeb810d0e80312f747e916912f599e4d72980f509f072bdc`; requirement `req_c3b362e0255b`.

> Project, internship, or academic experience developing Python applications

Source `application_analysis_versions[id=4].report_json::stable_analysis.canonical_requirements[requirement_id=req_1dce6dd618cc]`; job/JD `application-jd:733f817ce4581149bfe15e5083951b1210f2ce9e34c1df9411792bfd1812d43a`; requirement `req_1dce6dd618cc`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### existing predicate observations

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 4, 'MIXED_SCOPE': 2, 'TECHNOLOGY_PLUS_ACTIVITY': 2}. Parent available 8/8; verified 0. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: PARENT_PROVENANCE_VERIFICATION_NEEDED.

> being familiar with recent shooting games

Source `application_analysis_versions[id=2].report_json::stable_analysis.canonical_requirements[requirement_id=req_f2540cda59f8]`; job/JD `application-jd:56bb074414a90a3eb97798163d74bd2597633730ac6d73555c09c8c029f529d1`; requirement `req_f2540cda59f8`.

> · Hands-on experience with Amazon Web Services (EC2, Cognito, S3, DynamoDB, etc.)

Source `application_analysis_versions[id=25].report_json::stable_analysis.canonical_requirements[requirement_id=req_b34860727bff]`; job/JD `application-jd:78ea53f265cc2eb200f0614579d8859d2bbfe30af2f511fa43ecc9113e5ba475`; requirement `req_b34860727bff`.

> · Collaborate with product managers, designers, and back-end engineers to understand project requirements and translate them into responsive and intuitive user interfaces

Source `application_analysis_versions[id=24].report_json::stable_analysis.canonical_requirements[requirement_id=req_11e25006a55e]`; job/JD `application-jd:947697f272268f32bfe7b0ecd714afac37a9108b1fd27fff58e814200d9f7e26`; requirement `req_11e25006a55e`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### no specific cue

Native scopes: {'MULTIPLE_NATIVE_SCOPE_OBSERVATIONS': 2, 'PARSER_OR_DECOMPOSITION_BLOCKED': 4, 'TECHNOLOGY_PLUS_ACTIVITY': 2, 'AMBIGUOUS': 4}. Parent available 12/12; verified 9. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Able to work independently with some guidance

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_b3627ba2d36d]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_b3627ba2d36d`.

> Good foundation in linear algebra, calculus and geometry

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_d462857dbee4]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_d462857dbee4`.

> Comfortable working on large code bases

Source `application_analysis_versions[id=58].report_json::stable_analysis.canonical_requirements[requirement_id=req_e9d3751f5d53]`; job/JD `application-jd:28c3c01b2b58a55eb5751d1500034dd2d33ec31010c4d85fc82c78331ea2eafb`; requirement `req_e9d3751f5d53`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### credential or duration cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 2, 'PARSER_OR_DECOMPOSITION_BLOCKED': 2, 'AMBIGUOUS': 1}. Parent available 5/5; verified 1. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> At least 8 years of software engineering experience

Source `application_analysis_versions[id=52].report_json::stable_analysis.canonical_requirements[requirement_id=req_f04940b6ea70]`; job/JD `application-jd:9f5b6a801bcefc84589e8f13f99494f2dd769d84c4832ee5668f77689804c1b8`; requirement `req_f04940b6ea70`.

> Bachelor’s degree in Computer Science, Software Engineering, Game Development, or a related technical discipline

Source `application_analysis_versions[id=4].report_json::stable_analysis.canonical_requirements[requirement_id=req_514372c87205]`; job/JD `application-jd:733f817ce4581149bfe15e5083951b1210f2ce9e34c1df9411792bfd1812d43a`; requirement `req_514372c87205`.

> Bachelor’s degree in Computer Science, Software Engineering, Game Development, or a related technical discipline

Source `application_analysis_versions[id=3].report_json::stable_analysis.canonical_requirements[requirement_id=req_514372c87205]`; job/JD `application-jd:8260bdb0b112153ff1c9b0c1392b1d4004175680aed2a81a9d1c4c827c10e766`; requirement `req_514372c87205`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### technology:python

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 4, 'PARSER_OR_DECOMPOSITION_BLOCKED': 6}. Parent available 10/10; verified 0. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: PARENT_PROVENANCE_VERIFICATION_NEEDED.

> Project, internship, or academic experience developing Python applications

Source `application_analysis_versions[id=4].report_json::stable_analysis.canonical_requirements[requirement_id=req_1dce6dd618cc]`; job/JD `application-jd:733f817ce4581149bfe15e5083951b1210f2ce9e34c1df9411792bfd1812d43a`; requirement `req_1dce6dd618cc`.

> Build and improve AI-assisted web applications using Python and Streamlit

Source `application_analysis_versions[id=4].report_json::stable_analysis.canonical_requirements[requirement_id=req_bafd5bd09a79]`; job/JD `application-jd:733f817ce4581149bfe15e5083951b1210f2ce9e34c1df9411792bfd1812d43a`; requirement `req_bafd5bd09a79`.

> Parse PDF and DOCX documents using Python document-processing libraries

Source `application_analysis_versions[id=4].report_json::stable_analysis.canonical_requirements[requirement_id=req_d04302f8653f]`; job/JD `application-jd:733f817ce4581149bfe15e5083951b1210f2ce9e34c1df9411792bfd1812d43a`; requirement `req_d04302f8653f`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.

### inactive_job

| Rank | Description | Occurrences | Unique wording | Jobs/JD documents | Verified parent | Inspect first |
|---:|---|---:|---:|---:|---:|---|
| 1 | generic technical cues | 64 | 64 | 12 | 62 | Source-scope/provenance review before narrower diagnosis |
| 2 | parent scope differs | 44 | 44 | 11 | 42 | Source-scope/decomposition; difference alone is not a defect |
| 3 | activity cues | 78 | 78 | 10 | 77 | Capability predicates/native resolver; verify activity and exclusions |
| 4 | familiarity exposure cues | 27 | 27 | 10 | 27 | Identity scope and qualification boundaries |
| 5 | professional behavior cues | 24 | 24 | 10 | 24 | Professional requirement handling; not automatic technical capabilities |
| 6 | optional or alternative cues | 32 | 32 | 9 | 32 | JD extraction/decomposition and nonmandatory scope |
| 7 | no specific cue | 23 | 23 | 8 | 23 | Manual source investigation; no forced route |
| 8 | credential or duration cues | 11 | 11 | 7 | 11 | Credential/eligibility handling |
| 9 | existing predicate observations | 10 | 10 | 6 | 10 | Existing capability predicates/native selector; no credit inferred |
| 10 | technology alias candidates | 8 | 8 | 6 | 8 | Technology registry/identity scope; candidates are not full resolution |
| 11 | technology:amazon.web.services | 4 | 4 | 4 | 4 | Technology registry/identity scope; candidates are not full resolution |
| 12 | technology activity cooccurrence | 4 | 4 | 3 | 4 | Contextual relationships/native resolver; not an approved mapping |
| 13 | predicate:collaboration.stakeholder | 3 | 3 | 3 | 3 | Existing capability predicates/native selector; no credit inferred |
| 14 | technology:microsoft.azure | 3 | 3 | 3 | 3 | Technology registry/identity scope; candidates are not full resolution |
| 15 | predicate:backend.api development | 3 | 3 | 2 | 3 | Existing capability predicates/native selector; no credit inferred |
| 16 | technology:google.cloud.platform | 2 | 2 | 2 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 17 | technology:python | 2 | 2 | 2 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 18 | parent not verified | 2 | 2 | 2 | 0 | Provenance preservation/source recovery |
| 19 | technology:react | 2 | 2 | 1 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 20 | technology:typescript | 2 | 2 | 1 | 2 | Technology registry/identity scope; candidates are not full resolution |
| 21 | predicate:data.processing | 1 | 1 | 1 | 1 | Existing capability predicates/native selector; no credit inferred |
| 22 | predicate:database.design | 1 | 1 | 1 | 1 | Existing capability predicates/native selector; no credit inferred |
| 23 | predicate:operations.configuration | 1 | 1 | 1 | 1 | Existing capability predicates/native selector; no credit inferred |
| 24 | predicate:operations.live environment | 1 | 1 | 1 | 1 | Existing capability predicates/native selector; no credit inferred |
| 25 | technology:amazon.s3 | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 26 | technology:csharp | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 27 | technology:java | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |
| 28 | technology:javascript | 1 | 1 | 1 | 1 | Technology registry/identity scope; candidates are not full resolution |

#### generic technical cues

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 25, 'TECHNOLOGY_PLUS_ACTIVITY': 27, 'MIXED_SCOPE': 9, 'TECHNOLOGY_PLUS_CAPABILITY': 1, 'AMBIGUOUS': 2}. Parent available 64/64; verified 62. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> We value strong engineering fundamentals and a "production-first" mindset

Source `job_match_snapshots[id=18].stable_analysis_json::canonical_requirements[requirement_id=req_05e0b77d3805]`; job/JD `job:15`; requirement `req_05e0b77d3805`.

> Strong in communication with the ability to explain complex technical concepts clearly to diverse audience

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_1484980f534e]`; job/JD `job:16`; requirement `req_1484980f534e`.

> You will work across LTA's rich transport data ecosystem — spanning real-time sensor feeds, transit operations data, traffic systems, and road infrastructure — to ensure that data is reliably ingested, transformed, governed, and made available for AI development and production use

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_8b2f925b1906]`; job/JD `job:16`; requirement `req_8b2f925b1906`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### parent scope differs

Native scopes: {'AMBIGUOUS': 9, 'TECHNOLOGY_PLUS_ACTIVITY': 14, 'PARSER_OR_DECOMPOSITION_BLOCKED': 15, 'MIXED_SCOPE': 5, 'TECHNOLOGY_PLUS_CAPABILITY': 1}. Parent available 44/44; verified 42. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Proficiency in concurrency

Source `job_match_snapshots[id=18].stable_analysis_json::canonical_requirements[requirement_id=req_3cc95e608a00]`; job/JD `job:15`; requirement `req_3cc95e608a00`.

> Proficiency in with a focus on memory safety

Source `job_match_snapshots[id=18].stable_analysis_json::canonical_requirements[requirement_id=req_7850d3b02948]`; job/JD `job:15`; requirement `req_7850d3b02948`.

> As a Data Engineer in LTA's Transport AI Programme, you will design, build

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_0943d0b3e6a0]`; job/JD `job:16`; requirement `req_0943d0b3e6a0`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### activity cues

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 49, 'PARSER_OR_DECOMPOSITION_BLOCKED': 20, 'MIXED_SCOPE': 7, 'AMBIGUOUS': 2}. Parent available 78/78; verified 77. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> As a Data Engineer in LTA's Transport AI Programme, you will design, build

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_0943d0b3e6a0]`; job/JD `job:16`; requirement `req_0943d0b3e6a0`.

> Implement data governance practices in line with Singapore Government data classification requirements, including access controls, data masking, anonymisation, and audit logging for sensitive transport and personal data

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_1d615bc6f359]`; job/JD `job:16`; requirement `req_1d615bc6f359`.

> Develop and manage data models, data catalogues, and feature stores that support AI model training, evaluation, and inference across transport use cases

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_38b020d3db74]`; job/JD `job:16`; requirement `req_38b020d3db74`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### familiarity exposure cues

Native scopes: {'AMBIGUOUS': 7, 'PARSER_OR_DECOMPOSITION_BLOCKED': 12, 'TECHNOLOGY_PLUS_ACTIVITY': 7, 'TECHNOLOGY_PLUS_CAPABILITY': 1}. Parent available 27/27; verified 27. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Proficiency in concurrency

Source `job_match_snapshots[id=18].stable_analysis_json::canonical_requirements[requirement_id=req_3cc95e608a00]`; job/JD `job:15`; requirement `req_3cc95e608a00`.

> Proficiency in with a focus on memory safety

Source `job_match_snapshots[id=18].stable_analysis_json::canonical_requirements[requirement_id=req_7850d3b02948]`; job/JD `job:15`; requirement `req_7850d3b02948`.

> Knowledge of metadata management practices will set candidates apart

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_6e2e1815ebcb]`; job/JD `job:16`; requirement `req_6e2e1815ebcb`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### professional behavior cues

Native scopes: {'MIXED_SCOPE': 16, 'PARSER_OR_DECOMPOSITION_BLOCKED': 7, 'TECHNOLOGY_PLUS_ACTIVITY': 1}. Parent available 24/24; verified 24. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Collaborative Mindset: Effective communication is key

Source `job_match_snapshots[id=18].stable_analysis_json::canonical_requirements[requirement_id=req_c0eed5f03f41]`; job/JD `job:15`; requirement `req_c0eed5f03f41`.

> Strong in communication with the ability to explain complex technical concepts clearly to diverse audience

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_1484980f534e]`; job/JD `job:16`; requirement `req_1484980f534e`.

> Inclination to work in a collaborative, fast-moving Agile environment

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_478c32e401c8]`; job/JD `job:16`; requirement `req_478c32e401c8`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### optional or alternative cues

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 21, 'TECHNOLOGY_PLUS_ACTIVITY': 9, 'AMBIGUOUS': 1, 'TECHNOLOGY_PLUS_CAPABILITY': 1}. Parent available 32/32; verified 32. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Experience working in regulated, government, or critical infrastructure environments — particularly where data sensitivity and access controls are paramount — is a plus

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_ccca6193b280]`; job/JD `job:16`; requirement `req_ccca6193b280`.

> Experience building feature stores or data pipelines specifically for ML/AI workloads is highly desirable

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_d4731f7ea539]`; job/JD `job:16`; requirement `req_d4731f7ea539`.

> Knowledge in Computer Science, Data Science, Business Analytics or a related field, with at least 3-6 years of relevant professional experience

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_d89035d2f84f]`; job/JD `job:16`; requirement `req_d89035d2f84f`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### no specific cue

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 8, 'TECHNOLOGY_PLUS_ACTIVITY': 4, 'AMBIGUOUS': 11}. Parent available 23/23; verified 23. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> As AI reshapes what's possible in transport operations, the Land Transport Authority is investing in AI capabilities that will meaningfully improve how the network is sensed, managed, and optimised — for commuters, operators, and public officers alike

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_abc4d7711241]`; job/JD `job:16`; requirement `req_abc4d7711241`.

> Singapore's land transport network moves millions of people every day

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_c97740b53618]`; job/JD `job:16`; requirement `req_c97740b53618`.

> Ability to work independently and assume responsibility for project deliverables

Source `job_match_snapshots[id=37].stable_analysis_json::canonical_requirements[requirement_id=req_04c51b09b11f]`; job/JD `job:35`; requirement `req_04c51b09b11f`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### credential or duration cues

Native scopes: {'PARSER_OR_DECOMPOSITION_BLOCKED': 7, 'TECHNOLOGY_PLUS_ACTIVITY': 2, 'AMBIGUOUS': 2}. Parent available 11/11; verified 11. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Knowledge in Computer Science, Data Science, Business Analytics or a related field, with at least 3-6 years of relevant professional experience

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_d89035d2f84f]`; job/JD `job:16`; requirement `req_d89035d2f84f`.

> Minimum 6 years of professional software development experience

Source `job_match_snapshots[id=35].stable_analysis_json::canonical_requirements[requirement_id=req_aa0ae3a50158]`; job/JD `job:479`; requirement `req_aa0ae3a50158`.

> Bachelor's Degree in Computer Science, Information Technology or a related discipline

Source `job_match_snapshots[id=35].stable_analysis_json::canonical_requirements[requirement_id=req_cf97f24126e5]`; job/JD `job:479`; requirement `req_cf97f24126e5`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### existing predicate observations

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 5, 'MIXED_SCOPE': 3, 'PARSER_OR_DECOMPOSITION_BLOCKED': 2}. Parent available 10/10; verified 10. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Develop and manage data models, data catalogues, and feature stores that support AI model training, evaluation, and inference across transport use cases

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_38b020d3db74]`; job/JD `job:16`; requirement `req_38b020d3db74`.

> Strong communication skills to explain technical concepts to both engineers and non-technical stakeholders

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_d1f0f0a2f7f9]`; job/JD `job:16`; requirement `req_d1f0f0a2f7f9`.

> Experience building feature stores or data pipelines specifically for ML/AI workloads is highly desirable

Source `job_match_snapshots[id=39].stable_analysis_json::canonical_requirements[requirement_id=req_d4731f7ea539]`; job/JD `job:16`; requirement `req_d4731f7ea539`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### technology alias candidates

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 3, 'PARSER_OR_DECOMPOSITION_BLOCKED': 4, 'MIXED_SCOPE': 1}. Parent available 8/8; verified 8. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Cloud platforms and services (e.g., AWS, Azure, GCP, or equivalent enterprise platforms)

Source `job_match_snapshots[id=38].stable_analysis_json::canonical_requirements[requirement_id=req_f17d2d634c4f]`; job/JD `job:173`; requirement `req_f17d2d634c4f`.

> Strong proficiency in JavaScript, TypeScript and modern React development

Source `job_match_snapshots[id=35].stable_analysis_json::canonical_requirements[requirement_id=req_957b0d986dc0]`; job/JD `job:479`; requirement `req_957b0d986dc0`.

> develop and enhance modern enterprise applications using React, TypeScript and Python technologies while collaborating within an Agile delivery team

Source `job_match_snapshots[id=35].stable_analysis_json::canonical_requirements[requirement_id=req_9863497d713a]`; job/JD `job:479`; requirement `req_9863497d713a`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### technology:amazon.web.services

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 2, 'PARSER_OR_DECOMPOSITION_BLOCKED': 2}. Parent available 4/4; verified 4. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Cloud platforms and services (e.g., AWS, Azure, GCP, or equivalent enterprise platforms)

Source `job_match_snapshots[id=38].stable_analysis_json::canonical_requirements[requirement_id=req_f17d2d634c4f]`; job/JD `job:173`; requirement `req_f17d2d634c4f`.

> · Hands-on experience with Amazon Web Services (EC2, Cognito, S3, DynamoDB, etc.)

Source `job_match_snapshots[id=43].stable_analysis_json::canonical_requirements[requirement_id=req_b34860727bff]`; job/JD `job:566`; requirement `req_b34860727bff`.

> Proven hands-on experience designing, building, and operating production-level cloud infrastructure across one or more major cloud providers such as AWS, Azure, or GCP, with familiarity across multi-cloud environments preferred

Source `job_match_snapshots[id=23].stable_analysis_json::canonical_requirements[requirement_id=req_27324ba0a7db]`; job/JD `job:72`; requirement `req_27324ba0a7db`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.


#### technology activity cooccurrence

Native scopes: {'TECHNOLOGY_PLUS_ACTIVITY': 3, 'MIXED_SCOPE': 1}. Parent available 4/4; verified 4. RECURRING_DESCRIPTION_REQUIRES_NATIVE_CAUSAL_REVIEW. Source readiness: SOURCE_AVAILABLE_FOR_BOUNDED_INVESTIGATION.

> Strong proficiency in JavaScript, TypeScript and modern React development

Source `job_match_snapshots[id=35].stable_analysis_json::canonical_requirements[requirement_id=req_957b0d986dc0]`; job/JD `job:479`; requirement `req_957b0d986dc0`.

> develop and enhance modern enterprise applications using React, TypeScript and Python technologies while collaborating within an Agile delivery team

Source `job_match_snapshots[id=35].stable_analysis_json::canonical_requirements[requirement_id=req_9863497d713a]`; job/JD `job:479`; requirement `req_9863497d713a`.

> Proven hands-on experience designing, building, and operating production-level cloud infrastructure across one or more major cloud providers such as AWS, Azure, or GCP, with familiarity across multi-cloud environments preferred

Source `job_match_snapshots[id=23].stable_analysis_json::canonical_requirements[requirement_id=req_27324ba0a7db]`; job/JD `job:72`; requirement `req_27324ba0a7db`.

High false-positive risk: similar wording may have different exclusions, scope and causes. Inspect source/native traces before a fix.

## Generalization hypotheses and validation strategy

- Recurrent provenance/parent-scope observations may justify source preservation investigation first. Availability alone is not a parser defect. Inspect exact native traces.
- Recurrent technology/activity cues may justify contextual knowledge review only after identity/activity are verified. Do not approve universal technology mappings.
- Existing predicate observations may justify testing native wording/exclusion boundaries. Frequency does not justify new taxonomy entries or credit for adjacent skills.
- Missing technical recognition, insufficient source evidence, legitimate professional meaning and applicant relevance without full qualification are distinct issues. This audit does not causally adjudicate those families. No applicant evidence is inspected or invented.
- A later approved fix needs independent development JD documents, genuinely unseen requirements, false-positive/negation/alternative controls, native resolver invariants and parent-weight conservation. Reuse deterministic Job Match for exact versioned score/label/cap/ranking comparisons under temporary state. Phase 8 lineage must support claims; Phase 9E project selection needs regression coverage where a later evidence/selection change is relevant. Keep the frozen forty/V5 reserved for independent evaluation.
- No live benchmark, models, embeddings, downloads or research were run.

## Limits and preservation

- Current knowledge rechecked on latest stored canonical inputs; no parser, evidence or scoring replay.
- Job Finder jobs and application JD documents are separate scopes; no invented combined job total.
- Unanalyzed active jobs have unknown requirement backlog; absent snapshots do not mean zero gaps.
- Latest active application analysis is not proof of current selected resume/session binding.
- Knowledge unresolved is not a true taxonomy gap or missing applicant evidence.
- Quarantine is deliberately conservative, not semantic duplicate adjudication.
- Cues are observations, not affirmed duties; negative scope/alternatives require human review.

## Findings and recommended next investigation

- The latest saved active Job Finder analyses record 500 knowledge-unresolved rows; requirement-only current production knowledge recheck yields 501 across 26 active, unchanged-source jobs. This is not a new scorer replay or stored snapshot update.
- Among 501 current-native unresolved occurrences, 494 normalized texts are unique: seven repeated-text excess occurrences (1.40%). The active backlog is largely distinct wording, not dominated by a handful of duplicate defects.
- After 49 benchmark/context exclusions and three privacy exclusions, 449 active development occurrences remain, with 442 unique texts across all 26 jobs. Nine strict wording groups contain 18 occurrences; only two groups contain more than one normalized wording. These are descriptive, not shared defects.
- Activity cues recur in 158 development requirements across 26 jobs; generic technical cues in 154 across 25; optional/alternative cues in 54 across 23; differing parent scope in 108 across 22. These overlapping patterns can inform generalizable source/qualification tests, not automatic mappings.
- Professional-behavior cues occur in 48 requirements across 17 jobs; credential/duration cues in 18 across 16. The 103 no-specific-cue requirements include hiring/process and underspecified language. These must not become technical capabilities merely because they remain unresolved.
- Existing bounded predicate observations occur in 13 development requirements across nine jobs, with all 13 recorded parent strings corroborated. This is enough source material to inspect native selector/exclusion boundaries, not proof a resolver bug exists.
- Fifteen active development requirements across six jobs lack corroborated parent provenance. Of these, seven have candidate parent text present in the JD and eight lack even that containment. Source recovery/verification is needed before causal assertions.
- Knowledge classification and candidate evidence are different: 66 active knowledge-unresolved rows have a stored positive match, while 69 knowledge-resolved rows have stored NONE. No evidence text was inspected, no match was promoted, and these historical labels are not revalidated qualifications.
- The 12 expired jobs contribute 202 current-native unresolved rows and are excluded from the primary active backlog. Fifty-four historical snapshots contain 893 stored unresolved record views, including 174 repeated views across snapshots; none are counted as additional current jobs.
- Application views remain separate: 55 latest active analyses cover 17 normalized JD documents. They have 425 current-native unresolved views, 221 distinct JD/requirement/text occurrences and 166 unique texts; 204 record views repeat. After quarantine there are 215 development occurrences and 160 unique texts. They are not 55 independent jobs.
- Application provenance is weaker: 166 of 215 development occurrences across 13 JD documents lack corroborated parent provenance, and some same-occurrence views retain different scope/provenance signatures. Do not treat repeated analyses or differing source scopes as one confirmed defect.
- There are 299 active discovered jobs without a selected analyzed snapshot. Their requirement backlog is unknown; this investigation cannot estimate it without new extraction, which was not performed.
- Parent corroboration here means stored raw-parent strings occur in the same hash-matched JD under whitespace comparison. It does not prove every native occurrence/allocation, parser decision or Phase 8 claim lineage.
- Lexical/source-family quarantine is conservative but cannot prove isolation against every distant semantic paraphrase. Coordinator review of development examples remains necessary before later improvement design.

Recommended order is descriptive, not a production-remediation plan:

1. Partition the largest activity/generic/no-specific-cue clusters into bounded development scopes using their exact JD source and native diagnostics. Inspect recognition, genuinely insufficient scope, professional meaning and application/process language separately; do not create a frequency-driven taxonomy expansion.
2. Inspect optional/alternative and child/parent fidelity across the 23/22 affected active jobs. Confirm actual native source loss before proposing decomposition changes; preserve parent allocations.
3. Inspect familiarity and professional/credential qualification boundaries across 19/17/16 jobs. Identity, implementation obligation, employment relevance and scoring eligibility must remain distinct; no eligibility change is made here.
4. Inspect the 19 alias-candidate requirements across 12 jobs and the 13 existing-predicate observations across nine jobs with current native contracts. Alias candidates and lexical predicate observations alone cannot justify mappings, capability credits or root-cause labels.
5. Recover/corroborate the 15 weak-provenance active requirements before causal fixes, and keep application-only weak-provenance records in their separate source-validation track.
6. Before any approved implementation, freeze independent development JD documents, obtain genuinely unseen positive/negative controls, and reuse native resolver, parent-conservation, deterministic scoring, Phase 8 lineage and relevant Phase 9E selection checks. Keep the frozen forty/V5 review reserved for independent evaluation.

## Focused validation

{
  "final_tests": 14,
  "passed": 14,
  "failed": 0,
  "final_duration_seconds": 0.226,
  "command": ".venv\\Scripts\\python.exe -B -m unittest tests.test_unresolved_backlog_clustering_v1",
  "preceding_iterations": [
    {
      "tests": 11,
      "seconds": 0.182
    },
    {
      "tests": 13,
      "seconds": 0.137
    },
    {
      "tests": 14,
      "seconds": 0.207
    },
    {
      "tests": 14,
      "seconds": 0.126
    },
    {
      "tests": 14,
      "seconds": 0.225
    }
  ],
  "new_python_ast_checks": 2,
  "protected_hashes_unchanged": 146,
  "benchmark_gold_changes": 0,
  "scoring_changes": 0,
  "full_suite_or_project_gate_run": false
}


Protected prior hashes unchanged: 146; database bytes unchanged: True. No DB writes, scoring/knowledge changes, commits, pushes, merges or branch switches.
