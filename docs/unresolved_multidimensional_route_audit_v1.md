# Multidimensional triage V1 route-drift audit

READY TO RETAIN AS A REPORT-ONLY DIAGNOSTIC FOUNDATION AFTER NARROW CORRECTIONS

V3 proposals are comparison evidence, not independent gold. Primary routes are pending diagnostic hypotheses. The original 40-case preview and frozen v1/v2 benchmarks remain unchanged.

## Summary

```json
{
  "cases": 40,
  "initial_route_errors_or_omissions_corrected": 9,
  "current_comparison_status_counts": {
    "AGREE": 27,
    "NEEDS_REVIEW": 6,
    "JUSTIFIED_DIFFERENCE": 7
  },
  "corrected_primary_counts": {
    "RELATIONSHIP": 4,
    "TRUE_GAP_CANDIDATE": 2,
    "undetermined": 28,
    "STRUCTURAL": 2,
    "CAPABILITY": 3,
    "TECH_ID": 1
  },
  "independent_gold_labels": 2,
  "new_gold_labels": 0,
  "native_resolution_changes": 0,
  "parent_allocation_changes": 0,
  "production_mutations": 0
}
```

Initial status POSSIBLE_HEURISTIC_ERROR identifies the original rule defect/omission corrected in this audit. Current status compares the corrected proposal against V3 without declaring V3 authoritative. AGREE means only proposal agreement. JUSTIFIED_DIFFERENCE means a conservative difference supported by native/source limitations; NEEDS_REVIEW remains a human decision.

## All 40 comparisons

| Case / Job / requirement | Exact requirement | V3 proposal | Initial V1 → corrected | Initial audit / current comparison | Next action |
|---|---|---|---|---|---|
| 1 / 31 / req_2410dfcbbf45 | Hands-on experience managing data persistence and search layers using MongoDB, Redis, Elasticsearch, or comparable NoSQL and search engines | RELATIONSHIP | RELATIONSHIP → RELATIONSHIP | AGREE / AGREE | Governed contextual scope review; native relationship diagnostics are not an approved mapping. |
| 2 / 163 / req_2f6aedb603aa | Knowledge of network access control | TRUE_GAP_CANDIDATE | TRUE_GAP_CANDIDATE → TRUE_GAP_CANDIDATE | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 3 / 163 / req_6677d37f660c | Network Access Control | TRUE_GAP_CANDIDATE | TRUE_GAP_CANDIDATE → TRUE_GAP_CANDIDATE | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 4 / 15 / req_2b6f4ea8fdb3 | Continuous Learning: You will constantly explore new technologies, system architectures, and security practices | NOT_TAXONOMY_ADDRESSABLE | undetermined → undetermined | NEEDS_REVIEW / NEEDS_REVIEW | Human/context-aware review; no production action authorized. |
| 5 / 15 / req_71321f9eff59 | You will be at the forefront of developing the Next Generation Traffic Light Control System | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 6 / 15 / req_7b667a24f1e0 | ​Public Service Spirit: You care deeply about the public good and understand the responsibility of working on critical national infrastructure that impacts millions of lives daily | NOT_TAXONOMY_ADDRESSABLE | undetermined → undetermined | NEEDS_REVIEW / NEEDS_REVIEW | Human/context-aware review; no production action authorized. |
| 7 / 158 / req_0c34f8e720fe | Plan and guide your team’s professional growth, in both general and technical areas | NOT_TAXONOMY_ADDRESSABLE | undetermined → undetermined | NEEDS_REVIEW / NEEDS_REVIEW | Human/context-aware review; no production action authorized. |
| 8 / 158 / req_60119945897e | Good understanding of prevailing technologies and technology markets | NOT_TAXONOMY_ADDRESSABLE | undetermined → undetermined | NEEDS_REVIEW / NEEDS_REVIEW | Human/context-aware review; no production action authorized. |
| 9 / 493 / req_74e080b49b36 | Ability to learn new software and technologies quickly | NOT_TAXONOMY_ADDRESSABLE | undetermined → undetermined | NEEDS_REVIEW / NEEDS_REVIEW | Human/context-aware review; no production action authorized. |
| 10 / 146 / req_ba405c092a55 | (b) Relational and non-relational databases, such as MS SQL, PostgreSQL, MongoDB etc | TECH_ID | undetermined → undetermined | NEEDS_REVIEW / NEEDS_REVIEW | Human/context-aware review; no production action authorized. |
| 11 / 16 / req_b451ce69ddd0 | Experience with cloud data platforms (such as AWS Glue, Azure Data Factory, Google Dataflow, or Databricks) and data warehousing or lakehouse architectures is important | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 12 / 144 / req_6c3b74434db5 | Proficiency in one or more programming/scripting languages (python, nodejs, etc.) | STRUCTURAL | STRUCTURAL → STRUCTURAL | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 13 / 493 / req_cfc6614dce69 | Basic programming experience with knowledge of C#, Java, Javascript, HTML5 and Python is preferred | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 14 / 44 / req_55269def7b17 | Experience with robotics frameworks such as ROS 2 and simulation platforms | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 15 / 50 / req_12004e0f666c | maintain ROS-based robotics solutions to enhance visitor experiences and operational efficiency as well as educational programs | RELATIONSHIP | undetermined → undetermined | NEEDS_REVIEW / JUSTIFIED_DIFFERENCE | Human/context-aware review; no production action authorized. |
| 16 / 50 / req_b01957201b40 | Advantageous qualifications include a GitHub portfolio demonstrating your work, experience with AI or ML technologies, expertise in SLAM and Motion Planning, or familiarity with CI or CD pipelines and simulation environments | STRUCTURAL | STRUCTURAL → undetermined | POSSIBLE_HEURISTIC_ERROR / JUSTIFIED_DIFFERENCE | Human/context-aware review; no production action authorized. |
| 17 / 146 / req_36e64f19f57a | CSS | STRUCTURAL | undetermined → undetermined | NEEDS_REVIEW / JUSTIFIED_DIFFERENCE | Human/context-aware review; no production action authorized. |
| 18 / 146 / req_e5e239560bc1 | HTML | STRUCTURAL | undetermined → undetermined | NEEDS_REVIEW / JUSTIFIED_DIFFERENCE | Human/context-aware review; no production action authorized. |
| 19 / 158 / req_19ace2467250 | use the latest technologies in DevOps, software-defined network infrastructure, and cloud computing | STRUCTURAL | undetermined → undetermined | NEEDS_REVIEW / JUSTIFIED_DIFFERENCE | Human/context-aware review; no production action authorized. |
| 20 / 15 / req_a8fc7690ed6f | ​Proficiency in Python for building robust internal tools and system modules | RELATIONSHIP | RELATIONSHIP → RELATIONSHIP | AGREE / AGREE | Governed contextual scope review; native relationship diagnostics are not an approved mapping. |
| 21 / 15 / req_e33272d9bf25 | Proficiency in in Java for web-based applications development | RELATIONSHIP | RELATIONSHIP → RELATIONSHIP | AGREE / AGREE | Governed contextual scope review; native relationship diagnostics are not an approved mapping. |
| 22 / 31 / req_05c5e7fc5dd5 | Proficiency in responsive user interfaces using React.js | CAPABILITY | RELATIONSHIP → CAPABILITY | POSSIBLE_HEURISTIC_ERROR / AGREE | Review exact existing predicate/plural observation and exclusions; a production selector patch/overlay requires separate approval. |
| 23 / 45 / req_83ab15340c75 | Basic programming or application development knowledge (e.g. Python or other programming languages) would be useful | UNKNOWN | STRUCTURAL → undetermined | POSSIBLE_HEURISTIC_ERROR / AGREE | Human/context-aware review; no production action authorized. |
| 24 / 479 / req_61217e45f716 | Exposure to Microsoft Azure cloud services is preferred | TECH_ID | undetermined → TECH_ID | POSSIBLE_HEURISTIC_ERROR / AGREE | Review bounded familiarity contract; do not infer architecture, querying or implementation. |
| 25 / 556 / req_2502c9c4d2fe | write and maintain code, build APIs, work on bug fixes, and monitor the technical performance of our internal systems, primarily using C# | STRUCTURAL | undetermined → undetermined | NEEDS_REVIEW / JUSTIFIED_DIFFERENCE | Human/context-aware review; no production action authorized. |
| 26 / 15 / req_2e581717a7ab | Critical Infrastructure Security: Implement robust security protocols to protect national infrastructure | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 27 / 16 / req_191dd0c2eef9 | maintain scalable data pipelines that ingest, transform, and serve structured and unstructured data from diverse transport data sources, including real-time streams and batch feeds | CAPABILITY | undetermined → CAPABILITY | POSSIBLE_HEURISTIC_ERROR / AGREE | Review exact existing predicate/plural observation and exclusions; a production selector patch/overlay requires separate approval. |
| 28 / 44 / req_4c055b99aecf | Analyse autonomy stack and algorithm performance and improve robustness, reliability and real-time performance of autonomous behaviours | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 29 / 44 / req_6e081bd46d54 | deploy AI-driven autonomy capabilities that enable autonomous platforms to operate effectively in complex, multi-domain, unstructured environments | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 30 / 45 / req_7140ec72373b | Exploration of End-to-End Integration – explore how the different GenAI solutions could be linked using available AI orchestration tools to support a more seamless, end-to-end AI-enabled procurement workflow | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 31 / 45 / req_90583b43be1b | As the suite of GenAI solutions expands, you will explore how the different solutions could be linked using an AI orchestration tool to provide users with a more seamless, end-to-end AI-enabled procurement experience | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 32 / 31 / req_8d47527c8f34 | Proficiency in the modern JavaScript/TypeScript ecosystem | STRUCTURAL | STRUCTURAL → STRUCTURAL | AGREE / AGREE | High-priority parser/parent-fidelity investigation; keep child-only benchmark deferred. |
| 33 / 31 / req_bc26569100e0 | Data Persistence & Retrieval: Design robust data solutions using MongoDB and Elasticsearch to handle high-volume transactions and standard CRUD operations | RELATIONSHIP | RELATIONSHIP → RELATIONSHIP | AGREE / AGREE | Governed contextual scope review; native relationship diagnostics are not an approved mapping. |
| 34 / 31 / req_d0a20edbb7ae | Proven experience building efficient, secure RESTful APIs with frameworks such as Express.js, Fastify, FastAPI, Spring Boot, or equivalent enterprise-grade tools | CAPABILITY | RELATIONSHIP → CAPABILITY | POSSIBLE_HEURISTIC_ERROR / AGREE | Review exact existing predicate/plural observation and exclusions; a production selector patch/overlay requires separate approval. |
| 35 / 45 / req_076aaad11115 | Familiarity with Generative AI tools, AI/LLM application development, APIs or system integration is advantageous | STRUCTURAL | STRUCTURAL → undetermined | POSSIBLE_HEURISTIC_ERROR / JUSTIFIED_DIFFERENCE | Human/context-aware review; no production action authorized. |
| 36 / 15 / req_36f5f1f102a6 | ​Production-Grade Development: Design and build modular, high-performance software components meant for real-world production systems | UNKNOWN | RELATIONSHIP → undetermined | POSSIBLE_HEURISTIC_ERROR / AGREE | Human/context-aware review; no production action authorized. |
| 37 / 15 / req_423f39c746ef | You take pride in ensuring that the software governing our roads is failsafe | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 38 / 15 / req_97717be0fa85 | You’ll ensure that the programming approach adhere to "Security by Design" principles. ​ | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 39 / 15 / req_bc4d89199fb0 | You believe that code isn't "done" until it is thoroughly tested and documented. ​ | UNKNOWN | undetermined → undetermined | AGREE / AGREE | Human/context-aware review; no production action authorized. |
| 40 / 15 / req_dcc530bf4685 | Engineering Excellence: A proven ability to build high-quality, secure, and maintainable software | UNKNOWN | RELATIONSHIP → undetermined | POSSIBLE_HEURISTIC_ERROR / AGREE | Human/context-aware review; no production action authorized. |

## Technical evidence and uncertainties

The JSON appendix `reports/unresolved_multidimensional_route_audit_comparison_v1.json` contains every exact technology ID/span/source/status, requested activity, source structure, actual native structure, capability predicate and exclusions, native resolution, allocation, disagreement rationale and remaining uncertainty.

## Targeted findings

- Responsive UI and RESTful APIs: old RELATIONSHIP was a heuristic defect. Existing frontend.ui_development and backend.api_development predicates provide bounded plural observations. CAPABILITY is a pending existing-predicate review route; native selectors still return unresolved. API evidence does not prove distributed systems or gRPC.
- Job45 req_83ab15340c75: OR observation alone did not establish a parser failure; primary now remains undetermined. The same limitation applies to heterogeneous GenAI/portfolio alternatives.
- Broad Job15 production/engineering-quality statements: C++/Python in other parent sentences cannot supply a current technology-plus-activity relationship. Preserve parent candidates as observations; primary remains undetermined.
- ROS: no native registry identity exists. V3 relationship destination remains a human hypothesis. Conservative undetermined is justified; no synthetic ROS registry ID was created.
- Azure: exact grounded exposure/familiarity scope supports a TECH_ID proposal, but registry candidate recognition and native complete-scope resolution remain distinct. No cloud architecture/DevOps inference.
- Data pipeline: data.processing includes data pipeline/ETL/transformation. The plural requirement supports existing-predicate review; neither real-time feeds nor cloud names prove messaging implementation.
- Case32: recorded parent UI activity and original allocation remain intact. It stays DEFERRED_FOR_CURRENT_BENCHMARK and HIGH_PRIORITY_INVESTIGATION; no parent-only answer was inserted into child-only gold.
- Safety review also rejected relational/non-relational product examples as database design, and bare C recognition inside a C# list. Custom native evidence policies are not replaced by generic lexical observation.

## Validation and approval boundary

20 multidimensional tests plus 25 existing gold/source-review tests passed. Frozen 30-job replay: zero score/rank changes, no blocked jobs; protected Jobs15/479/493/163/566 remain13/19/12/14/23. Native resolution and parent allocations are unchanged for all40 diagnostics. AST/whitespace and git diff --check passed.

Existing diagnostic definitions and proposals may be retained for human review. Primary reasons, term observations and morphology are not production resolver answers, approved relationships, evidence credit or human gold. All new human attestations remain blank; two inherited NAC labels remain. No live models/API/Tavily/network, production DB writes, taxonomy/registry/parser/scorer changes, commits, pushes or merges.
