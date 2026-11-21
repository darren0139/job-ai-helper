# Independent human gold-label review — frozen 40-case selection

No new gold labels have been assigned. Two NAC expectations are inherited; 38 exact routes remain pending.

Historical buckets, resolver diagnostics and token-overlap candidates are evidence to review, not human gold. A text-ready case can support a human decision or explicit deferral; it is not automatically actionable.

Parent manifest: `e264f159cf0ef216020d5fc5a775c0bd169b331cd6a10833a7f59043e06a2a5f`. Source: `tests/fixtures/confirmed_taxonomy_coverage.json`; `e993ed6df531967df30289602fe772b930021520a9d83e71407c7e39e8baf1a7`.

The frozen corpus has no independent exact-route reviewer ledger (reviewed_requirement_keys is empty). Original reviewer name/date are unavailable for inherited expectations; none have been invented. Full JD/nearby source lines are unavailable. Parent/list context must be reviewed separately when noted. No applicant evidence, predictions or synthetic answers are used.

## Route choices

| Route | Human decision boundary |
|---|---|
| CAPABILITY | Explicit bounded activity fits an existing capability predicate; identify it and check exclusions. |
| TECH_ID | Identity-only knowledge route; preserve parent scope; identity cannot imply capability. |
| RELATIONSHIP | Named technology plus bounded activity requires governed mapping review, not global mapping. |
| STRUCTURAL | Parent/child, alternatives, normalization or mixed obligations block safe atomic interpretation. |
| NOT_TAXONOMY_ADDRESSABLE | Not a bounded technical-taxonomy obligation; does not change scoring eligibility. |
| TRUE_GAP_CANDIDATE | Bounded reusable activity with existing predicates shown insufficient; never publication. |
| UNKNOWN | Evidence cannot support a route; explicitly defer rather than force a category. |

## Review method

Review before seeing model predictions. Read exact text, native scope and historical proof. Record primary route first, reviewed alternatives only, exact supporting substrings, rationale, reviewer identity, timezone-aware timestamp and source reference. A blank decision stays pending. If additional JD context is necessary, retrieve it through human source review, record its reference in the rationale, and defer until confirmed. Source text changes require a new frozen input, not editing v1.

The JSON receipt template has blank reviewer/time/rationale fields and no proposed gold routes. Only completed explicitly reviewed receipts should be imported. Validation checks provenance structure and grounding; it cannot authenticate the reviewer or prove an independence attestation is truthful.

## Priority inventory

| # | Job / requirement | Review readiness | Proposed discussion routes (NOT gold) |
|---:|---|---|---|
| 1 | 31 / req_2410dfcbbf45 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | RELATIONSHIP / STRUCTURAL |
| 2 | 163 / req_2f6aedb603aa | TEXT_READY_FOR_HUMAN_DECISION | TRUE_GAP_CANDIDATE |
| 3 | 163 / req_6677d37f660c | TEXT_READY_FOR_HUMAN_DECISION | TRUE_GAP_CANDIDATE |
| 4 | 15 / req_2b6f4ea8fdb3 | TEXT_READY_FOR_HUMAN_DECISION | NOT_TAXONOMY_ADDRESSABLE / UNKNOWN |
| 5 | 15 / req_71321f9eff59 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | NOT_TAXONOMY_ADDRESSABLE / CAPABILITY / UNKNOWN |
| 6 | 15 / req_7b667a24f1e0 | TEXT_READY_FOR_HUMAN_DECISION | NOT_TAXONOMY_ADDRESSABLE |
| 7 | 158 / req_0c34f8e720fe | TEXT_READY_FOR_HUMAN_DECISION | NOT_TAXONOMY_ADDRESSABLE / CAPABILITY |
| 8 | 158 / req_60119945897e | TEXT_READY_FOR_HUMAN_DECISION | NOT_TAXONOMY_ADDRESSABLE / UNKNOWN |
| 9 | 493 / req_74e080b49b36 | TEXT_READY_FOR_HUMAN_DECISION | NOT_TAXONOMY_ADDRESSABLE |
| 10 | 146 / req_ba405c092a55 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | STRUCTURAL / TECH_ID |
| 11 | 16 / req_b451ce69ddd0 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / RELATIONSHIP |
| 12 | 144 / req_6c3b74434db5 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / TECH_ID |
| 13 | 493 / req_cfc6614dce69 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / TECH_ID |
| 14 | 44 / req_55269def7b17 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / TECH_ID |
| 15 | 50 / req_12004e0f666c | FURTHER_SOURCE_OR_PREDICATE_REVIEW | RELATIONSHIP / STRUCTURAL / UNKNOWN |
| 16 | 50 / req_b01957201b40 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL |
| 17 | 146 / req_36e64f19f57a | FURTHER_SOURCE_OR_PREDICATE_REVIEW | TECH_ID / STRUCTURAL |
| 18 | 146 / req_e5e239560bc1 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | TECH_ID / STRUCTURAL |
| 19 | 158 / req_19ace2467250 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / UNKNOWN |
| 20 | 15 / req_a8fc7690ed6f | FURTHER_SOURCE_OR_PREDICATE_REVIEW | RELATIONSHIP / CAPABILITY / STRUCTURAL |
| 21 | 15 / req_e33272d9bf25 | TEXT_READY_FOR_HUMAN_DECISION | RELATIONSHIP / CAPABILITY |
| 22 | 31 / req_05c5e7fc5dd5 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | CAPABILITY / RELATIONSHIP / STRUCTURAL |
| 23 | 45 / req_83ab15340c75 | TEXT_READY_FOR_HUMAN_DECISION | CAPABILITY / RELATIONSHIP / STRUCTURAL |
| 24 | 479 / req_61217e45f716 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | TECH_ID / RELATIONSHIP / STRUCTURAL |
| 25 | 556 / req_2502c9c4d2fe | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / RELATIONSHIP |
| 26 | 15 / req_2e581717a7ab | FURTHER_SOURCE_OR_PREDICATE_REVIEW | UNKNOWN / CAPABILITY / TRUE_GAP_CANDIDATE |
| 27 | 16 / req_191dd0c2eef9 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / CAPABILITY |
| 28 | 44 / req_4c055b99aecf | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / CAPABILITY / UNKNOWN |
| 29 | 44 / req_6e081bd46d54 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | UNKNOWN / CAPABILITY |
| 30 | 45 / req_7140ec72373b | FURTHER_SOURCE_OR_PREDICATE_REVIEW | CAPABILITY / RELATIONSHIP / STRUCTURAL |
| 31 | 45 / req_90583b43be1b | FURTHER_SOURCE_OR_PREDICATE_REVIEW | CAPABILITY / RELATIONSHIP / STRUCTURAL |
| 32 | 31 / req_8d47527c8f34 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / TECH_ID |
| 33 | 31 / req_bc26569100e0 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / RELATIONSHIP |
| 34 | 31 / req_d0a20edbb7ae | TEXT_READY_FOR_HUMAN_DECISION | CAPABILITY / STRUCTURAL |
| 35 | 45 / req_076aaad11115 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / CAPABILITY / TECH_ID |
| 36 | 15 / req_36f5f1f102a6 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | CAPABILITY / UNKNOWN |
| 37 | 15 / req_423f39c746ef | FURTHER_SOURCE_OR_PREDICATE_REVIEW | NOT_TAXONOMY_ADDRESSABLE / CAPABILITY / UNKNOWN |
| 38 | 15 / req_97717be0fa85 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | CAPABILITY / UNKNOWN |
| 39 | 15 / req_bc4d89199fb0 | TEXT_READY_FOR_HUMAN_DECISION | STRUCTURAL / CAPABILITY / NOT_TAXONOMY_ADDRESSABLE |
| 40 | 15 / req_dcc530bf4685 | FURTHER_SOURCE_OR_PREDICATE_REVIEW | CAPABILITY / UNKNOWN |

Text-ready for human decision: 23; further source/predicate review: 17.

Prioritize explicit alternatives/mixed obligations (STRUCTURAL), bounded activity predicates (CAPABILITY/RELATIONSHIP), and motivation/familiarity boundaries (NOT_TAXONOMY_ADDRESSABLE), alongside NAC. Twenty actionable labels across four categories is a review target, not a claim established by this worksheet. Pure CSS/HTML and Azure cases need parent provenance; do not force TECH_ID to reach category coverage.

## 1. Job 31 — req_2410dfcbbf45

Exact stored requirement (JSON string preserves invisible characters):

```json
"Hands-on experience managing data persistence and search layers using MongoDB, Redis, Elasticsearch, or comparable NoSQL and search engines"
```

Importance: core. Input fingerprint: `d0225739ef0d530e788b661bfa135784e25860eb9e606ee11f6869eb48796055`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Explicit MongoDB relationship hypothesis/non-gap control; exact route needs reviewer adjudication.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: True; non-gap control: True.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: RELATIONSHIP / STRUCTURAL.
Persistence, search and alternative products are different scopes. MongoDB identity cannot establish database.design. Review original JD scope before choosing a primary route.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "ai.rag_application",
    "label": "RAG application development",
    "requirement_terms": "rag retrieval-augmented generation vector retrieval vector search grounded llm"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "elasticsearch",
    "label": "Elasticsearch",
    "matched_aliases": [
      "Elasticsearch"
    ]
  },
  {
    "technology_id": "mongodb",
    "label": "MongoDB",
    "matched_aliases": [
      "MongoDB"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 2. Job 163 — req_2f6aedb603aa

Exact stored requirement (JSON string preserves invisible characters):

```json
"Knowledge of network access control"
```

Importance: core. Input fingerprint: `ae2f988f70d2c4d6c788059b1211774497be38eb84d46871134bc0927d0807d4`.

Confirmed expectation: ['TRUE_GAP_CANDIDATE'].
Original provenance: Explicit user-reviewed NAC positive control; proposal only, never proven publication.

Historical classification: TRUE_CAPABILITY_TAXONOMY_GAP / ACTUAL_CAPABILITY_TAXONOMY_GAP.
Critical control: True; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: TRUE_GAP_CANDIDATE.
Previously confirmed NAC control. Historical gap contract distinguishes network admission from database authorization, packet capture and DNS/DHCP. Native provenance diagnostic conflicts with historical semantic adjudication; do not silently relabel it.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  },
  {
    "capability_id": "domain.game_knowledge",
    "label": "Gaming-domain knowledge",
    "requirement_terms": "gaming industry game industry game product knowledge knowledge of games"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "experience.duration",
    "label": "Experience duration",
    "requirement_terms": "year of experience years of experience month of experience months of experience"
  },
  {
    "capability_id": "network.packet_analysis",
    "label": "Network packet analysis",
    "requirement_terms": "packet analysis wireshark network troubleshooting packet capture"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{
  "profile": {
    "canonical_concept": "network access control",
    "aliases": [
      "NAC",
      "network access control"
    ],
    "failure_type": "capability_missing",
    "closest_capability_ids": [
      "database.access_control",
      "network.packet_analysis",
      "network.dns_dhcp"
    ],
    "why_existing_insufficient": "Network admission and access policy is distinct from database authorization, packet analysis, and DNS/DHCP fundamentals.",
    "new_capability": {
      "capability_id": "network.access_control",
      "label": "Network access control",
      "domain": "networking",
      "definition": "Designing, administering, or enforcing network admission, segmentation, authentication, and device-access policy.",
      "requirement_terms": [
        "network access control",
        "network admission control"
      ],
      "does_not_prove": [
        "Database role policy",
        "Packet capture without access-policy work"
      ],
      "boundaries": [
        "Excludes application and database authorization unless network admission is explicit"
      ],
      "overlap_risks": [
        "database.access_control",
        "network.packet_analysis",
        "network.dns_dhcp"
      ]
    }
  },
  "gap_contract": {
    "meaningful_activity": "Designing, administering, or enforcing network admission, segmentation, authentication, and device-access policy.",
    "bounded_scope": "network access control",
    "reusable": "network access control",
    "evidence_predicate_to_research": "Designing, administering, or enforcing network admission, segmentation, authentication, and device-access policy.",
    "negative_boundary_to_research": [
      "Database role policy",
      "Packet capture without access-policy work"
    ],
    "existing_insufficient": "Network admission and access policy is distinct from database authorization, packet analysis, and DNS/DHCP fundamentals.",
    "not_identity_only": true,
    "not_primary_parser_or_decomposition": true,
    "not_primary_relationship": true,
    "not_vague": true,
    "review_only": true,
    "authority_or_publication_claim": false
  }
}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 3. Job 163 — req_6677d37f660c

Exact stored requirement (JSON string preserves invisible characters):

```json
"Network Access Control"
```

Importance: core. Input fingerprint: `3eb95ee9e5ab303b9c70eb9049fe3cb9da1f344c2eb6f402188c47af9d524b5e`.

Confirmed expectation: ['TRUE_GAP_CANDIDATE'].
Original provenance: Explicit user-reviewed NAC positive control; proposal only, never proven publication.

Historical classification: TRUE_CAPABILITY_TAXONOMY_GAP / ACTUAL_CAPABILITY_TAXONOMY_GAP.
Critical control: True; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: TRUE_GAP_CANDIDATE.
Previously confirmed NAC control. Historical gap contract distinguishes network admission from database authorization, packet capture and DNS/DHCP. Native provenance diagnostic conflicts with historical semantic adjudication; do not silently relabel it.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  },
  {
    "capability_id": "network.packet_analysis",
    "label": "Network packet analysis",
    "requirement_terms": "packet analysis wireshark network troubleshooting packet capture"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{
  "profile": {
    "canonical_concept": "network access control",
    "aliases": [
      "NAC",
      "network access control"
    ],
    "failure_type": "capability_missing",
    "closest_capability_ids": [
      "database.access_control",
      "network.packet_analysis",
      "network.dns_dhcp"
    ],
    "why_existing_insufficient": "Network admission and access policy is distinct from database authorization, packet analysis, and DNS/DHCP fundamentals.",
    "new_capability": {
      "capability_id": "network.access_control",
      "label": "Network access control",
      "domain": "networking",
      "definition": "Designing, administering, or enforcing network admission, segmentation, authentication, and device-access policy.",
      "requirement_terms": [
        "network access control",
        "network admission control"
      ],
      "does_not_prove": [
        "Database role policy",
        "Packet capture without access-policy work"
      ],
      "boundaries": [
        "Excludes application and database authorization unless network admission is explicit"
      ],
      "overlap_risks": [
        "database.access_control",
        "network.packet_analysis",
        "network.dns_dhcp"
      ]
    }
  },
  "gap_contract": {
    "meaningful_activity": "Designing, administering, or enforcing network admission, segmentation, authentication, and device-access policy.",
    "bounded_scope": "Network Access Control",
    "reusable": "network access control",
    "evidence_predicate_to_research": "Designing, administering, or enforcing network admission, segmentation, authentication, and device-access policy.",
    "negative_boundary_to_research": [
      "Database role policy",
      "Packet capture without access-policy work"
    ],
    "existing_insufficient": "Network admission and access policy is distinct from database authorization, packet analysis, and DNS/DHCP fundamentals.",
    "not_identity_only": true,
    "not_primary_parser_or_decomposition": true,
    "not_primary_relationship": true,
    "not_vague": true,
    "review_only": true,
    "authority_or_publication_claim": false
  }
}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 4. Job 15 — req_2b6f4ea8fdb3

Exact stored requirement (JSON string preserves invisible characters):

```json
"Continuous Learning: You will constantly explore new technologies, system architectures, and security practices"
```

Importance: core. Input fingerprint: `6806858c138412943c2d9316489a4a5cc977aa2be8172d9b248fc67c4141825b`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: NOT_TAXONOMY_ADDRESSABLE / MANUAL_REVIEW.
Critical control: True; non-gap control: True.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: NOT_TAXONOMY_ADDRESSABLE / UNKNOWN.
Learning aspiration versus a concrete architecture/security obligation; do not equate the historical bucket with an exact route.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "network.dns_dhcp",
    "label": "DNS and DHCP fundamentals",
    "requirement_terms": "dns dhcp domain name system dynamic host configuration protocol"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 5. Job 15 — req_71321f9eff59

Exact stored requirement (JSON string preserves invisible characters):

```json
"You will be at the forefront of developing the Next Generation Traffic Light Control System"
```

Importance: core. Input fingerprint: `f89acefa17bd9598692deb244037b8e71ce42324412fe492eef9873fa8edda2a`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: NOT_TAXONOMY_ADDRESSABLE / MANUAL_REVIEW.
Critical control: True; non-gap control: True.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: NOT_TAXONOMY_ADDRESSABLE / CAPABILITY / UNKNOWN.
Project context may hide a real development obligation; retrieve original responsibility section.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "ai.rag_application",
    "label": "RAG application development",
    "requirement_terms": "rag retrieval-augmented generation vector retrieval vector search grounded llm"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  },
  {
    "capability_id": "domain.game_knowledge",
    "label": "Gaming-domain knowledge",
    "requirement_terms": "gaming industry game industry game product knowledge knowledge of games"
  },
  {
    "capability_id": "experience.duration",
    "label": "Experience duration",
    "requirement_terms": "year of experience years of experience month of experience months of experience"
  },
  {
    "capability_id": "integration.client_software",
    "label": "Client-facing software integration",
    "requirement_terms": "software integration system integration systems integration integrate software integrating software integrate systems integrate functionality"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 6. Job 15 — req_7b667a24f1e0

Exact stored requirement (JSON string preserves invisible characters):

```json
"\u200bPublic Service Spirit: You care deeply about the public good and understand the responsibility of working on critical national infrastructure that impacts millions of lives daily"
```

Importance: core. Input fingerprint: `4b48ad7754770fb5ca702a94e0eca493dc0963af84886915c418e8b320e94c27`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: NOT_TAXONOMY_ADDRESSABLE / MANUAL_REVIEW.
Critical control: True; non-gap control: True.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: NOT_TAXONOMY_ADDRESSABLE.
Public-service motivation, not a bounded technical capability.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Corrupted or ambiguous normalization"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "devops.kubernetes",
    "label": "Kubernetes orchestration",
    "requirement_terms": "kubernetes k8s container orchestration orchestrate container workloads container workloads across clustered environments kubernetes deployment manifests service and ingress manifests cluster service routing ingress rules"
  },
  {
    "capability_id": "devops.observability",
    "label": "Monitoring and observability",
    "requirement_terms": "monitoring observability prometheus grafana alerting service metrics application metrics operational metrics telemetry metrics"
  },
  {
    "capability_id": "operations.daily",
    "label": "Daily product operations",
    "requirement_terms": "daily operations operate and maintain product operations"
  },
  {
    "capability_id": "backend.api_development",
    "label": "Backend API development",
    "requirement_terms": "backend api rest api restful api api development web service"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 7. Job 158 — req_0c34f8e720fe

Exact stored requirement (JSON string preserves invisible characters):

```json
"Plan and guide your team\u2019s professional growth, in both general and technical areas"
```

Importance: core. Input fingerprint: `d3a172882a21a324257668b1162b9e9ced027796c62628137e301a5739fc31c7`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: NOT_TAXONOMY_ADDRESSABLE / MANUAL_REVIEW.
Critical control: True; non-gap control: True.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: NOT_TAXONOMY_ADDRESSABLE / CAPABILITY.
Professional-growth responsibility may be leadership; review technical-taxonomy boundary, not scoring eligibility.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "credential.certification",
    "label": "Professional certification",
    "requirement_terms": "certification certifications certified professional certification cloud certification kubernetes certification cka ckad cks"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 8. Job 158 — req_60119945897e

Exact stored requirement (JSON string preserves invisible characters):

```json
"Good understanding of prevailing technologies and technology markets"
```

Importance: core. Input fingerprint: `e504732eb8518914ab2157aa19d10b41c5d60fcbe6d51b31313b826f25d1e198`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: NOT_TAXONOMY_ADDRESSABLE / MANUAL_REVIEW.
Critical control: True; non-gap control: True.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: NOT_TAXONOMY_ADDRESSABLE / UNKNOWN.
Broad market familiarity has no bounded technical predicate in this text.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "devops.kubernetes",
    "label": "Kubernetes orchestration",
    "requirement_terms": "kubernetes k8s container orchestration orchestrate container workloads container workloads across clustered environments kubernetes deployment manifests service and ingress manifests cluster service routing ingress rules"
  },
  {
    "capability_id": "devops.observability",
    "label": "Monitoring and observability",
    "requirement_terms": "monitoring observability prometheus grafana alerting service metrics application metrics operational metrics telemetry metrics"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 9. Job 493 — req_74e080b49b36

Exact stored requirement (JSON string preserves invisible characters):

```json
"Ability to learn new software and technologies quickly"
```

Importance: supporting. Input fingerprint: `6d7837d05b82a472aabbc353b16d19480c67e31d70c2751d9cdebba21ce271af`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: NOT_TAXONOMY_ADDRESSABLE / MANUAL_REVIEW.
Critical control: True; non-gap control: True.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: NOT_TAXONOMY_ADDRESSABLE.
Learning speed is not a named technical capability.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "quality.qa_testing",
    "label": "Quality assurance and testing",
    "requirement_terms": "quality assurance qa testing test cases regression testing defect verification defect investigation investigate software defects reproduce failures verify fixes fix verification bug reproduction defect reproduction"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 10. Job 146 — req_ba405c092a55

Exact stored requirement (JSON string preserves invisible characters):

```json
"(b) Relational and non-relational databases, such as MS SQL, PostgreSQL, MongoDB etc"
```

Importance: core. Input fingerprint: `5add8e5222c79ad5e9efba4e963e4cba8e3d4526ce557bf4f200b1d81e38d50e`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: STRUCTURAL / TECH_ID.
Leading list item and database examples: original parent and AND/OR intent are needed. SQL does not imply querying; MongoDB does not imply schema design.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "database.design",
    "label": "Database design",
    "requirement_terms": "database design data model schema design relational database"
  },
  {
    "capability_id": "devops.kubernetes",
    "label": "Kubernetes orchestration",
    "requirement_terms": "kubernetes k8s container orchestration orchestrate container workloads container workloads across clustered environments kubernetes deployment manifests service and ingress manifests cluster service routing ingress rules"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "mongodb",
    "label": "MongoDB",
    "matched_aliases": [
      "MongoDB"
    ]
  },
  {
    "technology_id": "sql",
    "label": "SQL",
    "matched_aliases": [
      "SQL"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 11. Job 16 — req_b451ce69ddd0

Exact stored requirement (JSON string preserves invisible characters):

```json
"Experience with cloud data platforms (such as AWS Glue, Azure Data Factory, Google Dataflow, or Databricks) and data warehousing or lakehouse architectures is important"
```

Importance: core. Input fingerprint: `8f85e4cfb41b73df1d2cd39047efc01546001441adff6c36bbe1297fef66c39d`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / RELATIONSHIP.
Example cloud services plus warehousing/lakehouse activity: distinguish examples from obligations. AWS identity cannot imply architecture.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "credential.certification",
    "label": "Professional certification",
    "requirement_terms": "certification certifications certified professional certification cloud certification kubernetes certification cka ckad cks"
  },
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "amazon.web.services",
    "label": "Amazon Web Services",
    "matched_aliases": [
      "AWS"
    ]
  },
  {
    "technology_id": "microsoft.azure",
    "label": "Microsoft Azure",
    "matched_aliases": [
      "Azure"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 12. Job 144 — req_6c3b74434db5

Exact stored requirement (JSON string preserves invisible characters):

```json
"Proficiency in one or more programming/scripting languages (python, nodejs, etc.)"
```

Importance: core. Input fingerprint: `f8ba77e5a91d4325d2787acb6e4a7c9f2ff58565853df9352c0d94f532f3d59f`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / TECH_ID.
Explicit one-or-more alternatives; Node.js identity cannot imply API implementation.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "operations.configuration",
    "label": "Product or system configuration",
    "requirement_terms": "configuration configure configured settings operational settings"
  },
  {
    "capability_id": "security.ci_cd",
    "label": "Security integrated into CI/CD",
    "requirement_terms": "security into ci/cd security in ci/cd ci/cd security secure ci/cd pipeline security security pipeline vulnerability scanning in ci/cd integrating security into ci/cd"
  },
  {
    "capability_id": "systems.data_oriented_programming",
    "label": "Data-oriented programming",
    "requirement_terms": "data oriented programming data-oriented programming data oriented design data-oriented design"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "node.js",
    "label": "Node.js",
    "matched_aliases": [
      "NodeJS"
    ]
  },
  {
    "technology_id": "python",
    "label": "Python",
    "matched_aliases": [
      "Python"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 13. Job 493 — req_cfc6614dce69

Exact stored requirement (JSON string preserves invisible characters):

```json
"Basic programming experience with knowledge of C#, Java, Javascript, HTML5 and Python is preferred"
```

Importance: preferred. Input fingerprint: `a9713c74d1004d47498557e4782178bf95397a4f541deda4e30f5b43b492b7e4`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / TECH_ID.
Multiple language examples plus programming activity; C# cannot imply backend development. Reviewer must decide parent versus component route.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "domain.game_knowledge",
    "label": "Gaming-domain knowledge",
    "requirement_terms": "gaming industry game industry game product knowledge knowledge of games"
  },
  {
    "capability_id": "experience.duration",
    "label": "Experience duration",
    "requirement_terms": "year of experience years of experience month of experience months of experience"
  },
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "csharp",
    "label": "C#",
    "matched_aliases": [
      "C#"
    ]
  },
  {
    "technology_id": "java",
    "label": "Java",
    "matched_aliases": [
      "Java"
    ]
  },
  {
    "technology_id": "javascript",
    "label": "JavaScript",
    "matched_aliases": [
      "JavaScript"
    ]
  },
  {
    "technology_id": "python",
    "label": "Python",
    "matched_aliases": [
      "Python"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 14. Job 44 — req_55269def7b17

Exact stored requirement (JSON string preserves invisible characters):

```json
"Experience with robotics frameworks such as ROS 2 and simulation platforms"
```

Importance: core. Input fingerprint: `a79eeacbdfeb82301755cd3eb4937d2b2701c4e3b27d8034a3a39fc75a38c8c2`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / TECHNOLOGY_IDENTITY_GAP.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / TECH_ID.
ROS 2 plus simulation platforms: whole requirement is not a pure identity. Separate named identity from example/compound scope.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "devops.kubernetes",
    "label": "Kubernetes orchestration",
    "requirement_terms": "kubernetes k8s container orchestration orchestrate container workloads container workloads across clustered environments kubernetes deployment manifests service and ingress manifests cluster service routing ingress rules"
  },
  {
    "capability_id": "devops.observability",
    "label": "Monitoring and observability",
    "requirement_terms": "monitoring observability prometheus grafana alerting service metrics application metrics operational metrics telemetry metrics"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 15. Job 50 — req_12004e0f666c

Exact stored requirement (JSON string preserves invisible characters):

```json
"maintain ROS-based robotics solutions to enhance visitor experiences and operational efficiency as well as educational programs"
```

Importance: core. Input fingerprint: `bcc32a59c56f150bf2bcb218027e1e2c478702b1924b2aaa2bb3d7472cac789c`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / TECHNOLOGY_IDENTITY_GAP.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: RELATIONSHIP / STRUCTURAL / UNKNOWN.
ROS-based maintenance may be robotics implementation, not an identity gap alone; original activity/parent source needed.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "devops.observability",
    "label": "Monitoring and observability",
    "requirement_terms": "monitoring observability prometheus grafana alerting service metrics application metrics operational metrics telemetry metrics"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "operations.daily",
    "label": "Daily product operations",
    "requirement_terms": "daily operations operate and maintain product operations"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 16. Job 50 — req_b01957201b40

Exact stored requirement (JSON string preserves invisible characters):

```json
"Advantageous qualifications include a GitHub portfolio demonstrating your work, experience with AI or ML technologies, expertise in SLAM and Motion Planning, or familiarity with CI or CD pipelines and simulation environments"
```

Importance: preferred. Input fingerprint: `469d96f5d4f0d6dc40d227fe2609a324140f1679cc8d5612c7e36366e6f510ff`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / TECHNOLOGY_IDENTITY_GAP.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL.
Explicit OR across portfolio, AI/ML, SLAM/motion planning, CI/CD and simulation. Identity bucket alone is misleading.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "devops.ci_cd",
    "label": "CI/CD automation",
    "requirement_terms": "ci/cd continuous integration continuous delivery github actions pipeline automation"
  },
  {
    "capability_id": "security.ci_cd",
    "label": "Security integrated into CI/CD",
    "requirement_terms": "security into ci/cd security in ci/cd ci/cd security secure ci/cd pipeline security security pipeline vulnerability scanning in ci/cd integrating security into ci/cd"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "devops.kubernetes",
    "label": "Kubernetes orchestration",
    "requirement_terms": "kubernetes k8s container orchestration orchestrate container workloads container workloads across clustered environments kubernetes deployment manifests service and ingress manifests cluster service routing ingress rules"
  },
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "ai.model_evaluation",
    "label": "ML/LLM model evaluation",
    "requirement_terms": "model evaluation llm evaluation evaluation harness benchmarking eval dataset benchmark set benchmark sets pass-rate metrics pass rate metrics model response evaluation assess language-model responses assess llm responses regression checks f"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 17. Job 146 — req_36e64f19f57a

Exact stored requirement (JSON string preserves invisible characters):

```json
"CSS"
```

Importance: core. Input fingerprint: `7be11bbe67b6074cca47200c59feb024a7ab5e0055e2060ca8306f69f427da3e`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / TECHNOLOGY_IDENTITY_GAP.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: TECH_ID / STRUCTURAL.
CSS is recognizable but native parent provenance is missing. Review parent before treating a decomposed child as atomic.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 18. Job 146 — req_e5e239560bc1

Exact stored requirement (JSON string preserves invisible characters):

```json
"HTML"
```

Importance: core. Input fingerprint: `748d6071ad54dda7eee6bfcf31079a4759c3594c9a3b96793646eadf959f1be7`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / TECHNOLOGY_IDENTITY_GAP.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: TECH_ID / STRUCTURAL.
HTML is recognizable but native parent provenance is missing. Identity recognition alone cannot establish frontend work.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 19. Job 158 — req_19ace2467250

Exact stored requirement (JSON string preserves invisible characters):

```json
"use the latest technologies in DevOps, software-defined network infrastructure, and cloud computing"
```

Importance: core. Input fingerprint: `8d3387e9f25110cde10d00fd67849c69d440a9aa40062d525132f51ebef71c5b`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / TECHNOLOGY_IDENTITY_GAP.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / UNKNOWN.
DevOps, networking and cloud are broad mixed activity families, not one technology identity.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "quality.qa_testing",
    "label": "Quality assurance and testing",
    "requirement_terms": "quality assurance qa testing test cases regression testing defect verification defect investigation investigate software defects reproduce failures verify fixes fix verification bug reproduction defect reproduction"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "credential.certification",
    "label": "Professional certification",
    "requirement_terms": "certification certifications certified professional certification cloud certification kubernetes certification cka ckad cks"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 20. Job 15 — req_a8fc7690ed6f

Exact stored requirement (JSON string preserves invisible characters):

```json
"\u200bProficiency in Python for building robust internal tools and system modules"
```

Importance: core. Input fingerprint: `54745af4cd9cb1bc05bf0a604206afddf97a47324cbf594992f79b9796616272`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / CONTEXTUAL_RELATIONSHIP_GAP.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: RELATIONSHIP / CAPABILITY / STRUCTURAL.
Python identity exists; internal tools/modules are not a universal backend mapping. Resolve parent/source provenance first.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Corrupted or ambiguous normalization"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "network.dns_dhcp",
    "label": "DNS and DHCP fundamentals",
    "requirement_terms": "dns dhcp domain name system dynamic host configuration protocol"
  },
  {
    "capability_id": "ai.model_evaluation",
    "label": "ML/LLM model evaluation",
    "requirement_terms": "model evaluation llm evaluation evaluation harness benchmarking eval dataset benchmark set benchmark sets pass-rate metrics pass rate metrics model response evaluation assess language-model responses assess llm responses regression checks f"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "python",
    "label": "Python",
    "matched_aliases": [
      "Python"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 21. Job 15 — req_e33272d9bf25

Exact stored requirement (JSON string preserves invisible characters):

```json
"Proficiency in in Java for web-based applications development"
```

Importance: core. Input fingerprint: `1601ce33a11c1026458d37de1eed4a9c6b3fb4806221285c79d4820b3c474516`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / CONTEXTUAL_RELATIONSHIP_GAP.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: RELATIONSHIP / CAPABILITY.
Java identity exists and web application activity is explicit; verify the exact existing capability predicate, not Java-to-backend universally.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "backend.api_development",
    "label": "Backend API development",
    "requirement_terms": "backend api rest api restful api api development web service"
  },
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  },
  {
    "capability_id": "frontend.ui_development",
    "label": "Frontend and UI development",
    "requirement_terms": "frontend development ui development user interface react frontend web frontend"
  },
  {
    "capability_id": "ai.model_evaluation",
    "label": "ML/LLM model evaluation",
    "requirement_terms": "model evaluation llm evaluation evaluation harness benchmarking eval dataset benchmark set benchmark sets pass-rate metrics pass rate metrics model response evaluation assess language-model responses assess llm responses regression checks f"
  },
  {
    "capability_id": "ai.rag_application",
    "label": "RAG application development",
    "requirement_terms": "rag retrieval-augmented generation vector retrieval vector search grounded llm"
  },
  {
    "capability_id": "embedded.firmware",
    "label": "Embedded firmware development",
    "requirement_terms": "firmware embedded software microcontroller esp32 gpio"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "java",
    "label": "Java",
    "matched_aliases": [
      "Java"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 22. Job 31 — req_05c5e7fc5dd5

Exact stored requirement (JSON string preserves invisible characters):

```json
"Proficiency in responsive user interfaces using React.js"
```

Importance: core. Input fingerprint: `e47d585c4fe36bbb42d0ade80d3caf9627eb105b8399f3f31a109783f7f42b0c`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / CONTEXTUAL_RELATIONSHIP_GAP.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: CAPABILITY / RELATIONSHIP / STRUCTURAL.
UI activity is explicit with React, but native provenance blocks scope. Inspect parent and frontend predicate before labeling recovery.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "frontend.ui_development",
    "label": "Frontend and UI development",
    "requirement_terms": "frontend development ui development user interface react frontend web frontend"
  },
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  },
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "security.ci_cd",
    "label": "Security integrated into CI/CD",
    "requirement_terms": "security into ci/cd security in ci/cd ci/cd security secure ci/cd pipeline security security pipeline vulnerability scanning in ci/cd integrating security into ci/cd"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "react",
    "label": "React",
    "matched_aliases": [
      "React",
      "React.js"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 23. Job 45 — req_83ab15340c75

Exact stored requirement (JSON string preserves invisible characters):

```json
"Basic programming or application development knowledge (e.g. Python or other programming languages) would be useful"
```

Importance: core. Input fingerprint: `513af11bcdc9c94d6b0f6261a8026f3c6cfb6dd558b5d8d46b0d7f6c9cb2f0a6`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / CONTEXTUAL_RELATIONSHIP_GAP.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: CAPABILITY / RELATIONSHIP / STRUCTURAL.
Programming/application knowledge is explicit; Python is an example, not a universal capability relationship.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "ai.rag_application",
    "label": "RAG application development",
    "requirement_terms": "rag retrieval-augmented generation vector retrieval vector search grounded llm"
  },
  {
    "capability_id": "mobile.android_development",
    "label": "Android application development",
    "requirement_terms": "android"
  },
  {
    "capability_id": "backend.api_development",
    "label": "Backend API development",
    "requirement_terms": "backend api rest api restful api api development web service"
  },
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "devops.containerisation",
    "label": "Containerisation",
    "requirement_terms": "docker containerisation containerization containerized application containerised application"
  },
  {
    "capability_id": "devops.observability",
    "label": "Monitoring and observability",
    "requirement_terms": "monitoring observability prometheus grafana alerting service metrics application metrics operational metrics telemetry metrics"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "python",
    "label": "Python",
    "matched_aliases": [
      "Python"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 24. Job 479 — req_61217e45f716

Exact stored requirement (JSON string preserves invisible characters):

```json
"Exposure to Microsoft Azure cloud services is preferred"
```

Importance: preferred. Input fingerprint: `d325939b6ca5c5610f7c06a0d6d67c4af3cb469b27b1e928af17fb0c99374b1d`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / CONTEXTUAL_RELATIONSHIP_GAP.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: TECH_ID / RELATIONSHIP / STRUCTURAL.
Azure familiarity does not prove cloud architecture. Native scope provenance is blocked; inspect parent/source.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "credential.certification",
    "label": "Professional certification",
    "requirement_terms": "certification certifications certified professional certification cloud certification kubernetes certification cka ckad cks"
  },
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "operations.live",
    "label": "Live operations",
    "requirement_terms": "live operations live ops live service operations incident response production incident outage response outage recovery service restoration restore affected systems restore disrupted services"
  },
  {
    "capability_id": "quality.attention_detail",
    "label": "Attention to detail",
    "requirement_terms": "attention to detail meticulous precision accuracy"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "microsoft.azure",
    "label": "Microsoft Azure",
    "matched_aliases": [
      "Azure",
      "Microsoft Azure"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 25. Job 556 — req_2502c9c4d2fe

Exact stored requirement (JSON string preserves invisible characters):

```json
"write and maintain code, build APIs, work on bug fixes, and monitor the technical performance of our internal systems, primarily using C#"
```

Importance: core. Input fingerprint: `09994d9d3d9bc3ae8ec2ae4597947a8c48a53e88ad527387726328940896a5e6`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / CONTEXTUAL_RELATIONSHIP_GAP.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / RELATIONSHIP.
Code, APIs, bug fixes and monitoring are multiple obligations. C# supports identity only; no universal backend mapping.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "quality.qa_testing",
    "label": "Quality assurance and testing",
    "requirement_terms": "quality assurance qa testing test cases regression testing defect verification defect investigation investigate software defects reproduce failures verify fixes fix verification bug reproduction defect reproduction"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "operations.daily",
    "label": "Daily product operations",
    "requirement_terms": "daily operations operate and maintain product operations"
  },
  {
    "capability_id": "realtime.messaging_streaming",
    "label": "Real-time messaging and streaming",
    "requirement_terms": "real-time messaging real time messaging real-time communication real time communication streaming systems real-time streaming event-driven communication websocket messaging real-time telemetry event-driven streaming"
  },
  {
    "capability_id": "security.bug_hack_handling",
    "label": "Bug, exploit and hack handling",
    "requirement_terms": "bugs and hacks bug handling hack handling exploit handling incident triage"
  },
  {
    "capability_id": "systems.memory_cache_performance",
    "label": "Memory allocation and cache performance",
    "requirement_terms": "memory allocation memory management memory allocator cache performance cache locality cache optimization cache optimisation memory performance"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "csharp",
    "label": "C#",
    "matched_aliases": [
      "C#"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 26. Job 15 — req_2e581717a7ab

Exact stored requirement (JSON string preserves invisible characters):

```json
"Critical Infrastructure Security: Implement robust security protocols to protect national infrastructure"
```

Importance: core. Input fingerprint: `9a20eea1cb7ddc66efddeaa59cd62a84ae1e0504b9d49902d03e3017490d65e5`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / NEEDS_DECOMPOSITION_OR_MIXED_SCOPE.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: UNKNOWN / CAPABILITY / TRUE_GAP_CANDIDATE.
Security protocols are too broad to establish a reusable missing capability; need bounded activity and overlap review.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  },
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "quality.attention_detail",
    "label": "Attention to detail",
    "requirement_terms": "attention to detail meticulous precision accuracy"
  },
  {
    "capability_id": "security.ci_cd",
    "label": "Security integrated into CI/CD",
    "requirement_terms": "security into ci/cd security in ci/cd ci/cd security secure ci/cd pipeline security security pipeline vulnerability scanning in ci/cd integrating security into ci/cd"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 27. Job 16 — req_191dd0c2eef9

Exact stored requirement (JSON string preserves invisible characters):

```json
"maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds"
```

Importance: core. Input fingerprint: `3a4a4b5407ba2fcf1a354c98197d57ad1a8b91793ee4a800282a409453c6ac7d`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / NEEDS_DECOMPOSITION_OR_MIXED_SCOPE.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / CAPABILITY.
Ingest, transform and serve with stream/batch context; decide coherent pipeline scope versus independent obligations.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "realtime.messaging_streaming",
    "label": "Real-time messaging and streaming",
    "requirement_terms": "real-time messaging real time messaging real-time communication real time communication streaming systems real-time streaming event-driven communication websocket messaging real-time telemetry event-driven streaming"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "operations.daily",
    "label": "Daily product operations",
    "requirement_terms": "daily operations operate and maintain product operations"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 28. Job 44 — req_4c055b99aecf

Exact stored requirement (JSON string preserves invisible characters):

```json
"Analyse autonomy stack and algorithm performance and improve robustness, reliability and real-time performance of autonomous behaviours"
```

Importance: core. Input fingerprint: `f39d7ae063c0d1ea4477efac25c1fe2d3472fd00f5aa96db1e0a154b9dc5c67d`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / NEEDS_DECOMPOSITION_OR_MIXED_SCOPE.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / CAPABILITY / UNKNOWN.
Performance analysis and robustness/reliability improvement: adjudicate coherent autonomy scope versus decomposition.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "realtime.messaging_streaming",
    "label": "Real-time messaging and streaming",
    "requirement_terms": "real-time messaging real time messaging real-time communication real time communication streaming systems real-time streaming event-driven communication websocket messaging real-time telemetry event-driven streaming"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "systems.memory_cache_performance",
    "label": "Memory allocation and cache performance",
    "requirement_terms": "memory allocation memory management memory allocator cache performance cache locality cache optimization cache optimisation memory performance"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 29. Job 44 — req_6e081bd46d54

Exact stored requirement (JSON string preserves invisible characters):

```json
"deploy AI-driven autonomy capabilities that enable autonomous platforms to operate effectively in complex, multi-domain, unstructured environments"
```

Importance: core. Input fingerprint: `3065e39da2605c4423cd96a767f982c2814087f79287692704335d090b021be4`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / NEEDS_DECOMPOSITION_OR_MIXED_SCOPE.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: UNKNOWN / CAPABILITY.
Broad autonomy deployment needs bounded activity/source scope; cannot infer a missing reusable capability.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "devops.kubernetes",
    "label": "Kubernetes orchestration",
    "requirement_terms": "kubernetes k8s container orchestration orchestrate container workloads container workloads across clustered environments kubernetes deployment manifests service and ingress manifests cluster service routing ingress rules"
  },
  {
    "capability_id": "domain.game_knowledge",
    "label": "Gaming-domain knowledge",
    "requirement_terms": "gaming industry game industry game product knowledge knowledge of games"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "network.dns_dhcp",
    "label": "DNS and DHCP fundamentals",
    "requirement_terms": "dns dhcp domain name system dynamic host configuration protocol"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 30. Job 45 — req_7140ec72373b

Exact stored requirement (JSON string preserves invisible characters):

```json
"Exploration of End-to-End Integration \u2013 explore how the different GenAI solutions could be linked using available AI orchestration tools to support a more seamless, end-to-end AI-enabled procurement workflow"
```

Importance: core. Input fingerprint: `5dffcaf3028cea4115137f92ed4fc43c7b393de5628f978e527d549331cc699d`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / NEEDS_DECOMPOSITION_OR_MIXED_SCOPE.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: CAPABILITY / RELATIONSHIP / STRUCTURAL.
Exploratory GenAI orchestration versus implementation; original parent/source and existing integration predicate needed.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "collaboration.cross_functional",
    "label": "Cross-functional collaboration",
    "requirement_terms": "cross-functional cross functional multiple functions different disciplines"
  },
  {
    "capability_id": "coordination.interoffice",
    "label": "Interoffice coordination",
    "requirement_terms": "between different offices cross-office cross office interoffice inter-office"
  },
  {
    "capability_id": "devops.ci_cd",
    "label": "CI/CD automation",
    "requirement_terms": "ci/cd continuous integration continuous delivery github actions pipeline automation"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 31. Job 45 — req_90583b43be1b

Exact stored requirement (JSON string preserves invisible characters):

```json
"As the suite of GenAI solutions expands, you will explore how the different solutions could be linked using an AI orchestration tool to provide users with a more seamless, end-to-end AI-enabled procurement experience"
```

Importance: core. Input fingerprint: `0ea55fb183f3e7f909f708f0be3342a31a573af8e65f6a4f69ecefc79a2fe8e3`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / NEEDS_DECOMPOSITION_OR_MIXED_SCOPE.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: CAPABILITY / RELATIONSHIP / STRUCTURAL.
Exploratory integration statement may be coherent scope; need original source and predicate review.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "experience.duration",
    "label": "Experience duration",
    "requirement_terms": "year of experience years of experience month of experience months of experience"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "collaboration.cross_functional",
    "label": "Cross-functional collaboration",
    "requirement_terms": "cross-functional cross functional multiple functions different disciplines"
  },
  {
    "capability_id": "coordination.interoffice",
    "label": "Interoffice coordination",
    "requirement_terms": "between different offices cross-office cross office interoffice inter-office"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 32. Job 31 — req_8d47527c8f34

Exact stored requirement (JSON string preserves invisible characters):

```json
"Proficiency in the modern JavaScript/TypeScript ecosystem"
```

Importance: core. Input fingerprint: `35ec941462913c1da8610ccafa83ca1d97a4702bfce59c2c088ffbd97802e372`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / TECH_ID.
JavaScript/TypeScript ecosystem: preserve paired scope. JavaScript does not imply frontend development.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "security.ci_cd",
    "label": "Security integrated into CI/CD",
    "requirement_terms": "security into ci/cd security in ci/cd ci/cd security secure ci/cd pipeline security security pipeline vulnerability scanning in ci/cd integrating security into ci/cd"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "javascript",
    "label": "JavaScript",
    "matched_aliases": [
      "JavaScript"
    ]
  },
  {
    "technology_id": "typescript",
    "label": "TypeScript",
    "matched_aliases": [
      "TypeScript"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 33. Job 31 — req_bc26569100e0

Exact stored requirement (JSON string preserves invisible characters):

```json
"Data Persistence & Retrieval: Design robust data solutions using MongoDB and Elasticsearch to handle high-volume transactions and standard CRUD operations"
```

Importance: core. Input fingerprint: `9a4f06fade7dfa70734da7ccdd7e5884e6502280bc75fff9ce6094a0c89872cf`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / RELATIONSHIP.
Persistence, retrieval, transactions and CRUD do not prove schema design; preserve MongoDB/Elasticsearch activity boundaries.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "database.design",
    "label": "Database design",
    "requirement_terms": "database design data model schema design relational database"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "operations.daily",
    "label": "Daily product operations",
    "requirement_terms": "daily operations operate and maintain product operations"
  },
  {
    "capability_id": "systems.data_oriented_programming",
    "label": "Data-oriented programming",
    "requirement_terms": "data oriented programming data-oriented programming data oriented design data-oriented design"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "elasticsearch",
    "label": "Elasticsearch",
    "matched_aliases": [
      "Elasticsearch"
    ]
  },
  {
    "technology_id": "mongodb",
    "label": "MongoDB",
    "matched_aliases": [
      "MongoDB"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 34. Job 31 — req_d0a20edbb7ae

Exact stored requirement (JSON string preserves invisible characters):

```json
"Proven experience building efficient, secure RESTful APIs with frameworks such as Express.js, Fastify, FastAPI, Spring Boot, or equivalent enterprise-grade tools"
```

Importance: core. Input fingerprint: `87da7401215c05b5ad3243ebb88719aaa59617b65f9aecb3feb932913f56bcc9`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: CAPABILITY / STRUCTURAL.
Explicit RESTful API building; framework alternatives are examples, not independent API obligations. Check backend.api_development predicate.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "backend.api_development",
    "label": "Backend API development",
    "requirement_terms": "backend api rest api restful api api development web service"
  },
  {
    "capability_id": "experience.duration",
    "label": "Experience duration",
    "requirement_terms": "year of experience years of experience month of experience months of experience"
  },
  {
    "capability_id": "operations.configuration",
    "label": "Product or system configuration",
    "requirement_terms": "configuration configure configured settings operational settings"
  },
  {
    "capability_id": "security.ci_cd",
    "label": "Security integrated into CI/CD",
    "requirement_terms": "security into ci/cd security in ci/cd ci/cd security secure ci/cd pipeline security security pipeline vulnerability scanning in ci/cd integrating security into ci/cd"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[
  {
    "technology_id": "fastapi",
    "label": "FastAPI",
    "matched_aliases": [
      "FastAPI"
    ]
  }
]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 35. Job 45 — req_076aaad11115

Exact stored requirement (JSON string preserves invisible characters):

```json
"Familiarity with Generative AI tools, AI/LLM application development, APIs or system integration is advantageous"
```

Importance: preferred. Input fingerprint: `cd5a52f5373e448dfa38554537de0092803d8ac073bad6a40c1404cd33296dd4`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / JD_PARSING_CANONICALISATION_PROBLEM.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / CAPABILITY / TECH_ID.
Explicit OR between tools, application development, APIs and integration; do not convert examples into simultaneous obligations.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "ai.rag_application",
    "label": "RAG application development",
    "requirement_terms": "rag retrieval-augmented generation vector retrieval vector search grounded llm"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "integration.client_software",
    "label": "Client-facing software integration",
    "requirement_terms": "software integration system integration systems integration integrate software integrating software integrate systems integrate functionality"
  },
  {
    "capability_id": "mobile.android_development",
    "label": "Android application development",
    "requirement_terms": "android"
  },
  {
    "capability_id": "operations.configuration",
    "label": "Product or system configuration",
    "requirement_terms": "configuration configure configured settings operational settings"
  },
  {
    "capability_id": "ai.model_evaluation",
    "label": "ML/LLM model evaluation",
    "requirement_terms": "model evaluation llm evaluation evaluation harness benchmarking eval dataset benchmark set benchmark sets pass-rate metrics pass rate metrics model response evaluation assess language-model responses assess llm responses regression checks f"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 36. Job 15 — req_36f5f1f102a6

Exact stored requirement (JSON string preserves invisible characters):

```json
"\u200bProduction-Grade Development: Design and build modular, high-performance software components meant for real-world production systems"
```

Importance: core. Input fingerprint: `f595e1e0cb1c3ac3316304f67eb5de4e201833245dd182ae317c44e572d185d3`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / MANUAL_REVIEW.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: CAPABILITY / UNKNOWN.
Generic production software quality needs exact existing predicate/parent review, not a new gap by default.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Corrupted or ambiguous normalization"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "realtime.messaging_streaming",
    "label": "Real-time messaging and streaming",
    "requirement_terms": "real-time messaging real time messaging real-time communication real time communication streaming systems real-time streaming event-driven communication websocket messaging real-time telemetry event-driven streaming"
  },
  {
    "capability_id": "embedded.firmware",
    "label": "Embedded firmware development",
    "requirement_terms": "firmware embedded software microcontroller esp32 gpio"
  },
  {
    "capability_id": "frontend.ui_development",
    "label": "Frontend and UI development",
    "requirement_terms": "frontend development ui development user interface react frontend web frontend"
  },
  {
    "capability_id": "game.engine_systems",
    "label": "Game-engine systems development",
    "requirement_terms": "game engine custom engine engine systems asset manager fmod"
  },
  {
    "capability_id": "integration.client_software",
    "label": "Client-facing software integration",
    "requirement_terms": "software integration system integration systems integration integrate software integrating software integrate systems integrate functionality"
  },
  {
    "capability_id": "operations.live",
    "label": "Live operations",
    "requirement_terms": "live operations live ops live service operations incident response production incident outage response outage recovery service restoration restore affected systems restore disrupted services"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 37. Job 15 — req_423f39c746ef

Exact stored requirement (JSON string preserves invisible characters):

```json
"You take pride in ensuring that the software governing our roads is failsafe"
```

Importance: core. Input fingerprint: `9a48158a8ee0042f6ab11d4e2d5e854bca6c66cdef5d101bcdbc981dbd0973cc`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / MANUAL_REVIEW.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: NOT_TAXONOMY_ADDRESSABLE / CAPABILITY / UNKNOWN.
Pride/failsafe aspiration versus testable safety obligation: original context needed.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Missing, activity-bearing, or unverifiable parent provenance"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "embedded.firmware",
    "label": "Embedded firmware development",
    "requirement_terms": "firmware embedded software microcontroller esp32 gpio"
  },
  {
    "capability_id": "integration.client_software",
    "label": "Client-facing software integration",
    "requirement_terms": "software integration system integration systems integration integrate software integrating software integrate systems integrate functionality"
  },
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  },
  {
    "capability_id": "quality.qa_testing",
    "label": "Quality assurance and testing",
    "requirement_terms": "quality assurance qa testing test cases regression testing defect verification defect investigation investigate software defects reproduce failures verify fixes fix verification bug reproduction defect reproduction"
  },
  {
    "capability_id": "security.ci_cd",
    "label": "Security integrated into CI/CD",
    "requirement_terms": "security into ci/cd security in ci/cd ci/cd security secure ci/cd pipeline security security pipeline vulnerability scanning in ci/cd integrating security into ci/cd"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 38. Job 15 — req_97717be0fa85

Exact stored requirement (JSON string preserves invisible characters):

```json
"You\u2019ll ensure that the programming approach adhere to \"Security by Design\" principles. \u200b"
```

Importance: core. Input fingerprint: `f3ddf3fd7d1ebbf4b5af260a9f0959ac8ca56c540ca0bc6a6de002943ad0f948`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / MANUAL_REVIEW.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: CAPABILITY / UNKNOWN.
Security by Design needs explicit boundary and existing security predicate review.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Corrupted or ambiguous normalization"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "systems.data_oriented_programming",
    "label": "Data-oriented programming",
    "requirement_terms": "data oriented programming data-oriented programming data oriented design data-oriented design"
  },
  {
    "capability_id": "database.access_control",
    "label": "Database access control",
    "requirement_terms": "row-level security row level security rls database access control authorization policy user-scoped access policies user scoped access policies restricted data access role-based data access database authorization record-level access control "
  },
  {
    "capability_id": "database.design",
    "label": "Database design",
    "requirement_terms": "database design data model schema design relational database"
  },
  {
    "capability_id": "delivery.end_to_end_application",
    "label": "End-to-end application delivery",
    "requirement_terms": "initial setup from scratch from setup end-to-end delivery end to end delivery user-facing application"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "language.modern_cpp",
    "label": "C and C++ programming",
    "requirement_terms": "c c programming programming in c modern c c language c11 c17 c23 c++ c++11 c++14 c++17 c++20 c++23"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 39. Job 15 — req_bc4d89199fb0

Exact stored requirement (JSON string preserves invisible characters):

```json
"You believe that code isn't \"done\" until it is thoroughly tested and documented. \u200b"
```

Importance: core. Input fingerprint: `2daaabc2b85faf5d2f6a571049a53174a23036cffaaf6686913193e5241881ae`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / MANUAL_REVIEW.
Critical control: False; non-gap control: False.

Readiness: TEXT_READY_FOR_HUMAN_DECISION.
Proposed discussion routes, NOT gold: STRUCTURAL / CAPABILITY / NOT_TAXONOMY_ADDRESSABLE.
Testing and documentation are named; determine technical obligations versus engineering ethos, not a new capability by default.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "PARSER_OR_DECOMPOSITION_BLOCKED",
  "scope_reason": "Corrupted or ambiguous normalization"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  },
  {
    "capability_id": "devops.kubernetes",
    "label": "Kubernetes orchestration",
    "requirement_terms": "kubernetes k8s container orchestration orchestrate container workloads container workloads across clustered environments kubernetes deployment manifests service and ingress manifests cluster service routing ingress rules"
  },
  {
    "capability_id": "devops.observability",
    "label": "Monitoring and observability",
    "requirement_terms": "monitoring observability prometheus grafana alerting service metrics application metrics operational metrics telemetry metrics"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______

## 40. Job 15 — req_dcc530bf4685

Exact stored requirement (JSON string preserves invisible characters):

```json
"Engineering Excellence: A proven ability to build high-quality, secure, and maintainable software"
```

Importance: core. Input fingerprint: `cc02ef4f7a1de23a30db364544dc966e7137c9d78ab0f1c386f57e32d9cb7ab9`.

Confirmed expectation: NONE — human decision pending.
Original provenance: Existing bucket is provenance only. Exact acceptable routes/scope/entity expectations need independent human review.

Historical classification: UNDETERMINED_NEEDS_SCOPE_REVIEW / MANUAL_REVIEW.
Critical control: False; non-gap control: False.

Readiness: FURTHER_SOURCE_OR_PREDICATE_REVIEW.
Proposed discussion routes, NOT gold: CAPABILITY / UNKNOWN.
Broad quality/security/maintainability requires predicate/source review; no missing capability proven.

Native deterministic resolver:

```json
{
  "status": "unresolved",
  "knowledge_status": "UNRESOLVED",
  "source": "unresolved",
  "reason": "unrecognised_capability",
  "taxonomy_status": null,
  "registry_reason": "no_exact_registry_alias_match",
  "scope_category": "TECHNOLOGY_PLUS_ACTIVITY",
  "scope_reason": "Named activity requires independent capability resolution"
}
```

Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):

```json
[
  {
    "capability_id": "quality.qa_testing",
    "label": "Quality assurance and testing",
    "requirement_terms": "quality assurance qa testing test cases regression testing defect verification defect investigation investigate software defects reproduce failures verify fixes fix verification bug reproduction defect reproduction"
  },
  {
    "capability_id": "algorithms.data_structures_algorithms",
    "label": "Data structures and algorithms",
    "requirement_terms": "data structures algorithms algorithmic complexity runtime analysis running time of algorithms a* pathfinding dijkstra binary search"
  },
  {
    "capability_id": "fullstack.integration",
    "label": "Full-stack integration",
    "requirement_terms": "full-stack full stack frontend and backend end-to-end application"
  },
  {
    "capability_id": "collaboration.stakeholder",
    "label": "Stakeholder collaboration",
    "requirement_terms": "stakeholder local and global global stakeholders customer collaboration client collaboration"
  },
  {
    "capability_id": "communication.written_verbal",
    "label": "Written and verbal communication",
    "requirement_terms": "written and verbal communication written communication verbal communication"
  },
  {
    "capability_id": "data.processing",
    "label": "Data processing and cleaning",
    "requirement_terms": "data processing data cleaning etl data pipeline data transformation"
  }
]
```

Exact alias-mentioned registry identities (not capability mappings):

```json
[]
```

Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):

```json
{}
```

Original review proof:

```json
{}
```

Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______
