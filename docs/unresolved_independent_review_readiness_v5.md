# V5 maintainer readiness audit — do not distribute to blinded reviewers

Reviewer distribution is limited to docs/unresolved_independent_review_packet_v5.md, reports/unresolved_independent_review_packet_v5.json and its blank V5 receipt template. This audit deliberately discusses prior artifacts/controls and is not blinded material.

## Verified current state

Prepared 38 pending cases; no new human decisions. Current gold: 2 inherited, 38 pending. Need at least 18 more actionable independent labels, four non-UNKNOWN categories, and all seven pending critical controls. Neither coverage nor actionability is guaranteed.

V4 had 20 cases (two inherited controls and 18 blank reviews). V5 supplies 20 additional pending cases, including the traffic-light control. Existing NAC controls are excluded from the new reviewer packet/template; their original receipts/answers remain unchanged. No reapproval is requested.

### V4 blinding audit

V4 was NOT genuinely blinded. Source-specific questions suggested routes and rejected mappings; an appendix exposed V3 AI and deterministic proposals; inherited control fields exposed expected answers; parent wording/headings were visible beside frozen children. Moving recommendations later in the file did not isolate them. Activity/structure annotations and predicate shortlists also carried editorial judgments.

- prior_ai_assisted_recommendations_appendix
- cases[].review_question
- cases[].inherited_control
- cases[].additional_verified_parent_context
- cases[].activity / structure / applicable_predicate_ids (editorial diagnostics)

### V5 leakage and evidence boundaries

V5 reconstructs its packet from an exact allowlist of the frozen input. Native resolver outputs (including production scope codes) are displayed as recorded facts, not gold root causes. Candidate lists retain original bounded token/alias facts with a uniform warning; no V3 predicate shortlists, multidimensional routes, historic buckets, prior conclusions, case questions or expected answers are copied. Exact canonical wording, fingerprints, source locators, source hashes and numeric allocations remain distinct. No original-JD/parent/sibling/heading excerpts are included. References do not authorize opening contaminated reports or expanding source scope. Packet integrity rejects extra fields even if resealed.

The blank receipt has no preselected route, origin, reviewer, timestamp, sufficiency or independence attestation. A prepared case is not an actionable label. A reviewer who saw AI suggestions must truthfully choose AI-assisted review, which cannot enter independent gold. Software cannot prove a reviewer is blind.

### Reviewability and source limits

All 38 pending cases have frozen child text, IDs and original input fingerprints and are available for source-only decision or explicit deferral. There are 37 potential frozen decision attempts after excluding the already deferred child #32; this is NOT 37 independently supportable actionable labels. Recovered-source status is verified for 34 pending cases and partial for 4. These are provenance availability counts, not route labels.

Job 31 req_8d47527c8f34 (#32) retains DEFERRED_FOR_CURRENT_BENCHMARK and HIGH_PRIORITY_INVESTIGATION for parent fidelity. Its UI-development parent is absent from frozen text; V5 supplies no parent wording or prefilled reviewer answer. An actionable child-only receipt is blocked. Separate context-aware inputs, fingerprints and independent review are required before changing that evaluation contract. The existing 0.333333 allocation and other production allocations are preserved.

Partial-source cases:

- Job 146 / req_36e64f19f57a
- Job 146 / req_e5e239560bc1
- Job 158 / req_19ace2467250
- Job 556 / req_2502c9c4d2fe

CSS/HTML (#17/#18) have source mentions but no corroborated canonical child identity in the recovered snapshot; standalone wording lacks proficiency/list context. Their actual production blocker cannot be established from the missing parent; request source verification or defer causal classification. The #19 and #25 snapshots retain the exact child but not every parent provenance link is verified. They require source/provenance review before a causal structural assertion. Do not automatically classify any of these as STRUCTURAL solely because recovery is partial.

Database-list #10 omits a proficiency heading; #14/#15 robotics and several other canonical children have additional source clauses outside the frozen view. If a decision requires those clauses, it must be deferred or separately context-reviewed. We do not adjudicate frozen-input sufficiency from AI history.

### All pending critical controls

- Job 31 / req_2410dfcbbf45 — included, blank decision.
- Job 15 / req_2b6f4ea8fdb3 — included, blank decision.
- Job 15 / req_71321f9eff59 — included, blank decision.
- Job 15 / req_7b667a24f1e0 — included, blank decision.
- Job 158 / req_0c34f8e720fe — included, blank decision.
- Job 158 / req_60119945897e — included, blank decision.
- Job 493 / req_74e080b49b36 — included, blank decision.

### Semantic content, root cause and investigation route

Semantic content is what the permitted exact source requests. Native facts show what the recorded production resolver did under its frozen versions; an unresolved result does not identify its cause. An investigation route is a governed next destination to examine. A technology/activity link can motivate contextual investigation without establishing a missing registry relationship, canonical identity failure or parser defect. A causal label requires relevant native diagnostic evidence and a reasoned human claim.

The route standards in the source packet preserve existing definitions. They do not silently change the V1–V4 validators or old gold. Label kind is recorded explicitly in new receipts: INVESTIGATION_ROUTE, VERIFIED_ROOT_CAUSE, or DEFERRED. A causal claim must cite exact native facts and declare that native evidence was accessed; validation checks citation structure, not causal truth. Semantic words alone are insufficient.

Existing definitions are NOT fully unambiguous. Human clarification is needed before importing new labels:

- TECH_ID can mean identity investigation or an established identity blocker; alias candidates do not settle full native identity resolution.
- RELATIONSHIP currently describes contextual investigation, not necessarily proved missing mapping. Technology-plus-activity alone cannot settle which subsystem failed.
- CAPABILITY may mean reviewing a bounded existing predicate versus diagnosing a native selector miss. Truncated candidate terms do not reveal every conjunction/exclusion.
- STRUCTURAL requires demonstrated loss, while frozen views often expose only a coarse production scope code. Missing native context is uncertainty, not demonstrated parser failure.
- TRUE_GAP_CANDIDATE requires sufficiently complete contract-insufficiency evidence, which bounded candidate lists do not provide. No new true-gap conclusion is inferred.
- NOT_TAXONOMY_ADDRESSABLE concerns technical-taxonomy scope, not employment relevance or scoring eligibility; optional technology familiarity is not automatically professional-only.
- UNKNOWN/DEFER records missing source/diagnostic information. It is not actionable coverage.

Human approval point: agree whether benchmark targets are investigation routes or verified root causes and whether the bounded evidence suffices, before separately authorizing receipt import or a benchmark. Do not extend definitions merely to achieve four categories. Any new complete predicate/native trace or parent source context outside this frozen contract belongs to a separately versioned review, not an unreported advantage over frozen model inputs.

## Actual reviewer workflow

1. A coordinator distributes only the three blinded V5 files. Recruit an unexposed reviewer per case; a person exposed to previous AI suggestions may provide assisted review, not blind independent gold.
2. Review exact child source and bounded native/candidate facts. Keep source observations separate from native causal evidence. Record a justified route or deferral without considering numeric quotas.
3. Copy only actually completed template entries into a separate JSON list. Fill real identity/reference, actual timezone-aware timestamp, source spans, rationale, evidence-access records and explicit exposure and sufficiency declarations. No identity/date or decision is automatically generated.
4. Evidence records use kind FROZEN_INPUT, NATIVE_FROZEN_DIAGNOSTICS or FROZEN_KNOWLEDGE_CANDIDATES; reference is JobID/RequirementID and fingerprint is the exact input_fingerprint. Native support records have field and exact_value from frozen_input.resolver. A VERIFIED_ROOT_CAUSE claim requires a substantive native reason and a native-access record, but human scrutiny still determines whether it actually establishes causality.
5. If parent or other outside evidence was consulted, decision_scope must be CONTEXT_AWARE_REVIEW and parent_context_consulted must be truthful. Extended evidence uses kind OUTSIDE_FROZEN_CONTRACT, actual reference and SHA256. V5 does not accept parent quotes: a separately versioned source packet is needed. Such records may document review but never enter the child-only independent benchmark.
6. UNKNOWN/DEFER has acceptable_routes=[] and an explicit deferral_rationale. Leave unreviewed entries out of the submitted list. The untouched blank template is intentionally invalid as completed receipts.
7. Run read-only validation first. Resolve route-definition ambiguity and inspect actual provenance before seeking separate human authorization to import eligible independent frozen receipts.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
$env:CAPABILITY_RAG_MODE='off'
.venv\Scripts\python.exe -B -m scripts.prepare_unresolved_independent_review_v5 --validate-only
.venv\Scripts\python.exe -B -m scripts.prepare_unresolved_independent_review_v5 --validate-receipts reports/completed_independent_review_v5.json
```

The second command requires a JSON list written by the actual review process; that file does not exist as a completed ledger in this task. Output separates independent actionable decisions, deferrals, assisted and context-only records. It returns original V5 provenance in eligible_independent_receipts_for_separately_authorized_import. Save only that array after separate authorization; never import the whole validator object or assisted/context-only entries.

V5 prechecks bind evidence/scope and protect #32; they delegate actual receipt provenance, route/spans, timestamps, exposure and hypothetical eligibility to the existing V4 validator through an ephemeral compatibility envelope. That envelope is not saved or represented as a real V4 review. The original V5 receipts are revalidated by existing gold.versioned_manifest in memory and returned unchanged. The original reviewer version/fingerprint and label kind survive a later import. No validator can authenticate an identity, establish actual blinding, or prove a causal claim.

### Separately authorized import (NOT executed here)

After actual review and explicit import authorization, use new output paths with the existing importer:

```powershell
.venv\Scripts\python.exe -B -m scripts.prepare_unresolved_gold_review --receipts reports/eligible_independent_v5.json --manifest-output reports/independently_reviewed_v5_manifest.json --worksheet-output reports/independently_reviewed_v5_source.md --packet-output reports/independently_reviewed_v5_audit.json --template-output reports/independently_reviewed_v5_blank.json
```

Do not overwrite V1/V2. The importer-produced historical worksheet/audit still contains editorial questions: keep it with the coordinator, not future blinded reviewers. This task executes no import. Even satisfied labeling prerequisites do not authorize Qwen or establish model quality.

## Preservation and validation

Protected prior byte hashes: 139. Production/scoring/registry/taxonomy/JD parser versions, frozen 40 fingerprints, parent allocations, V1–V4 and Qwen artifacts remain unchanged. The four requested artifacts and additive preparation/validation code are the only new deliverables. No models, network, application database reads/writes, labels, imports, benchmark execution or publication. No commits, pushes, merges, resets, cleanup or branch switches.

Focused validation: 17 V5 tests passed in 8.684s; 25 existing V4/gold tests passed in 20.728s. An initial 16-test V5 run passed before the source-access/causal-evidence guards were tightened. Preparation and read-only --validate-only passed; three AST checks, seven new-artifact whitespace checks and git diff --check passed. No full suite, project gate or inference was run.

Files added: taxonomy_discovery/unresolved_independent_review.py; scripts/prepare_unresolved_independent_review_v5.py; tests/test_unresolved_independent_review_v5.py; docs/unresolved_independent_review_packet_v5.md; reports/unresolved_independent_review_packet_v5.json; reports/unresolved_independent_review_receipts_template_v5.json; docs/unresolved_independent_review_readiness_v5.md. No existing file was edited.

Source availability, critical-control membership and V4 coverage inventory (coordinator only):

```json
{
  "current_gold": {
    "total_cases": 40,
    "confirmed": 2,
    "pending": 38,
    "coverage": {
      "CAPABILITY": 0,
      "TECH_ID": 0,
      "RELATIONSHIP": 0,
      "STRUCTURAL": 0,
      "NOT_TAXONOMY_ADDRESSABLE": 0,
      "TRUE_GAP_CANDIDATE": 2,
      "UNKNOWN": 0
    },
    "critical_pending": [
      [
        31,
        "req_2410dfcbbf45"
      ],
      [
        15,
        "req_2b6f4ea8fdb3"
      ],
      [
        15,
        "req_71321f9eff59"
      ],
      [
        15,
        "req_7b667a24f1e0"
      ],
      [
        158,
        "req_0c34f8e720fe"
      ],
      [
        158,
        "req_60119945897e"
      ],
      [
        493,
        "req_74e080b49b36"
      ]
    ],
    "labeling_prerequisite_satisfied": false
  },
  "minimum_actionable": 20,
  "minimum_non_unknown_categories": 4,
  "additional_actionable_needed": 18,
  "prepared_pending_cases": 38,
  "independently_actionable_cases_new": 0,
  "actionability_not_determined_by_preparation": true,
  "all_pending_critical_covered": true,
  "pending_critical_keys": [
    [
      31,
      "req_2410dfcbbf45"
    ],
    [
      15,
      "req_2b6f4ea8fdb3"
    ],
    [
      15,
      "req_71321f9eff59"
    ],
    [
      15,
      "req_7b667a24f1e0"
    ],
    [
      158,
      "req_0c34f8e720fe"
    ],
    [
      158,
      "req_60119945897e"
    ],
    [
      493,
      "req_74e080b49b36"
    ]
  ],
  "v4_selected_keys": [
    [
      31,
      "req_2410dfcbbf45"
    ],
    [
      163,
      "req_2f6aedb603aa"
    ],
    [
      163,
      "req_6677d37f660c"
    ],
    [
      15,
      "req_2b6f4ea8fdb3"
    ],
    [
      15,
      "req_7b667a24f1e0"
    ],
    [
      158,
      "req_0c34f8e720fe"
    ],
    [
      158,
      "req_60119945897e"
    ],
    [
      493,
      "req_74e080b49b36"
    ],
    [
      146,
      "req_ba405c092a55"
    ],
    [
      144,
      "req_6c3b74434db5"
    ],
    [
      50,
      "req_12004e0f666c"
    ],
    [
      50,
      "req_b01957201b40"
    ],
    [
      15,
      "req_a8fc7690ed6f"
    ],
    [
      15,
      "req_e33272d9bf25"
    ],
    [
      31,
      "req_05c5e7fc5dd5"
    ],
    [
      479,
      "req_61217e45f716"
    ],
    [
      16,
      "req_191dd0c2eef9"
    ],
    [
      31,
      "req_bc26569100e0"
    ],
    [
      31,
      "req_d0a20edbb7ae"
    ],
    [
      45,
      "req_076aaad11115"
    ]
  ],
  "new_material_not_in_v4": [
    [
      15,
      "req_71321f9eff59"
    ],
    [
      16,
      "req_b451ce69ddd0"
    ],
    [
      493,
      "req_cfc6614dce69"
    ],
    [
      44,
      "req_55269def7b17"
    ],
    [
      146,
      "req_36e64f19f57a"
    ],
    [
      146,
      "req_e5e239560bc1"
    ],
    [
      158,
      "req_19ace2467250"
    ],
    [
      45,
      "req_83ab15340c75"
    ],
    [
      556,
      "req_2502c9c4d2fe"
    ],
    [
      15,
      "req_2e581717a7ab"
    ],
    [
      44,
      "req_4c055b99aecf"
    ],
    [
      44,
      "req_6e081bd46d54"
    ],
    [
      45,
      "req_7140ec72373b"
    ],
    [
      45,
      "req_90583b43be1b"
    ],
    [
      31,
      "req_8d47527c8f34"
    ],
    [
      15,
      "req_36f5f1f102a6"
    ],
    [
      15,
      "req_423f39c746ef"
    ],
    [
      15,
      "req_97717be0fa85"
    ],
    [
      15,
      "req_bc4d89199fb0"
    ],
    [
      15,
      "req_dcc530bf4685"
    ]
  ],
  "source_recovery_verified_pending": [
    [
      31,
      "req_2410dfcbbf45"
    ],
    [
      15,
      "req_2b6f4ea8fdb3"
    ],
    [
      15,
      "req_71321f9eff59"
    ],
    [
      15,
      "req_7b667a24f1e0"
    ],
    [
      158,
      "req_0c34f8e720fe"
    ],
    [
      158,
      "req_60119945897e"
    ],
    [
      493,
      "req_74e080b49b36"
    ],
    [
      146,
      "req_ba405c092a55"
    ],
    [
      16,
      "req_b451ce69ddd0"
    ],
    [
      144,
      "req_6c3b74434db5"
    ],
    [
      493,
      "req_cfc6614dce69"
    ],
    [
      44,
      "req_55269def7b17"
    ],
    [
      50,
      "req_12004e0f666c"
    ],
    [
      50,
      "req_b01957201b40"
    ],
    [
      15,
      "req_a8fc7690ed6f"
    ],
    [
      15,
      "req_e33272d9bf25"
    ],
    [
      31,
      "req_05c5e7fc5dd5"
    ],
    [
      45,
      "req_83ab15340c75"
    ],
    [
      479,
      "req_61217e45f716"
    ],
    [
      15,
      "req_2e581717a7ab"
    ],
    [
      16,
      "req_191dd0c2eef9"
    ],
    [
      44,
      "req_4c055b99aecf"
    ],
    [
      44,
      "req_6e081bd46d54"
    ],
    [
      45,
      "req_7140ec72373b"
    ],
    [
      45,
      "req_90583b43be1b"
    ],
    [
      31,
      "req_8d47527c8f34"
    ],
    [
      31,
      "req_bc26569100e0"
    ],
    [
      31,
      "req_d0a20edbb7ae"
    ],
    [
      45,
      "req_076aaad11115"
    ],
    [
      15,
      "req_36f5f1f102a6"
    ],
    [
      15,
      "req_423f39c746ef"
    ],
    [
      15,
      "req_97717be0fa85"
    ],
    [
      15,
      "req_bc4d89199fb0"
    ],
    [
      15,
      "req_dcc530bf4685"
    ]
  ],
  "source_recovery_partial_pending": [
    [
      146,
      "req_36e64f19f57a"
    ],
    [
      146,
      "req_e5e239560bc1"
    ],
    [
      158,
      "req_19ace2467250"
    ],
    [
      556,
      "req_2502c9c4d2fe"
    ]
  ],
  "frozen_child_existing_deferral": [
    31,
    "req_8d47527c8f34"
  ],
  "potential_frozen_review_attempts_excluding_existing_deferral": 37,
  "v4_genuinely_blinded": false,
  "v4_leak_locations": [
    "prior_ai_assisted_recommendations_appendix",
    "cases[].review_question",
    "cases[].inherited_control",
    "cases[].additional_verified_parent_context",
    "cases[].activity / structure / applicable_predicate_ids (editorial diagnostics)"
  ],
  "protected_hashes": {
    "analysis_stability/__init__.py": "a9a5836c97977886db16374ec62fa7ca1b6e4f6a7df1d6cf0af93a599d384787",
    "analysis_stability/analysis_cache_mode.py": "b7f765d7edbebfcafee52222ae5d35f4c60147cdee327aece2873a77a7ab5684",
    "analysis_stability/evidence_support.py": "4588f40c16cb53805dd50c8ff6038c144ee2386412a644934af6ba6c648cd30b",
    "analysis_stability/jd_section_inference.py": "fdcd777dcbc1ab1aacb29ae4fd0f610bcfda7a9907d7e92974e2039470e500f1",
    "analysis_stability/resume_profile_stability.py": "6966ebd9a6137cf9890c59c1fd07d5764e0eb0cab6db7971797a3400f2b7acb8",
    "analysis_stability/stable_evidence_scoring.py": "16cbd0096e228356aade8d495d66e5135332c6e7ebff7e077ac8394e877afb98",
    "reports/unresolved_gold_decision_review_v3.json": "dd47494f3ebd587fcba33d3c575f1a8a861c4d0e477778b97baa16f259879563",
    "reports/unresolved_gold_review_packet_v4.json": "1731bcb85197139fd85eb7019df760ec97fdc142fba1df39a14eceb3b9d40ad1",
    "reports/unresolved_gold_review_receipts_template_v4.json": "4f39b12dcea666336fa95e7d730661d25d436ba2ff4a620a2673c4fbf6fe67c8",
    "reports/unresolved_gold_review_receipts_v2.json": "54771a3f1345ccc185b14d020a2ccdff7f00923b6150b5e83d2f6a113e3505d9",
    "reports/unresolved_gold_review_v2.json": "1cc0ed1d397c0e4d5be2a9756b3d8825d54ad7ddfb45e82451dd29d08218136c",
    "reports/unresolved_gold_v3_preservation.json": "fa0408a8c37e7437b981ac72d5424565549aa4f7079d6bca946aab423437e7f1",
    "reports/unresolved_multidimensional_route_audit_comparison_v1.json": "11155b8069476f38b93c4724e7572bd807c148e8424f43aec906fdf61725638c",
    "reports/unresolved_multidimensional_triage_audited_v1.json": "0690c5550a99b64f6963b775daeacbd847549bf9a243e5264466bf001e3d0dcf",
    "tailoring/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "tailoring/application_output_integrations_ui.py": "c9f7ef0b3a8d1b6cb7ad15611138c1366d4b73116c3805e990fa9f2e5d87cb73",
    "tailoring/application_profile_ui.py": "add6bb180a408294bc904209e29534698720bd6e3aa60910aeb2b22064a97fed",
    "tailoring/application_tracker_export.py": "d101b1d6254e9f71117c9b7445356b048a2e5c4863b5f1baeab28ab73388c685",
    "tailoring/application_tracker_ui.py": "b2aee67f078739b26210d47201f86fe6509fce8492876b11638208430365883e",
    "tailoring/blueprint_tag_library_ui.py": "fcaa1de8be004d19cdad3f641bc908e945b715cce88e8d8127a4f4103b2f7a0b",
    "tailoring/browser_capture_ui.py": "0e06619b2466a8356fafc59f9b9fbfaac263abc60c639a651d5626785a776f37",
    "tailoring/candidate_context.py": "6c1e429544cdf0382d3818a6b1af5f233fcac5cefe97f0d91f439bf18c985617",
    "tailoring/canonical_bullet_suggester.py": "9b6110f0e593128d72d8c03ec47bda10aee3184e8be669b6420af7e4e467dc98",
    "tailoring/capability_taxonomy.py": "71b9471c3863ed1d857cd80e489cb1ee877c4673c78760f42ad635f27d09fd17",
    "tailoring/capability_taxonomy_research.py": "6d9b2ca7620c8636b1a4556c7263082a89af1d16cb9cc8030d9834e79cadce70",
    "tailoring/capability_taxonomy_tavily.py": "fc035adaa8e6270fd2f1ad47b06b8240de96a339d9057615c2cc9fc563193b1f",
    "tailoring/deterministic_bullet_allocation.py": "779415bfede680769be4b14c2d74c8e1001e47311c07a61d246a7b514020f459",
    "tailoring/deterministic_project_rules.py": "fd62a665e83b8149dac9bac4f0eef293bff8e11916a22532b6cb9d25194251e7",
    "tailoring/document_grounded_analysis.py": "7eb83d33d28217c9db05285fa6eb9316ebad8cf156810293e3ab960f29c4145e",
    "tailoring/evidence_grounded_bullet_tailoring.py": "d60cf30ea74c031a2241d9ad93ce7bfca277d94cee7a5c99f3f5018b851e0ef4",
    "tailoring/evidence_grounded_bullet_ui.py": "6c9c387110327cf68f640b05e3b2c534ca4ff132ae0b6963e09d998a1a542726",
    "tailoring/final_scoring_seed.py": "fbd0f7b7213b50a540532ec16b89758ffc539c1619194a182da5c8c479da07e1",
    "tailoring/fresh_target_evidence_scoring.py": "dd2a189c279ebda4ce49c30048399b941bc2df26158e5b48bdc0920e91b82008",
    "tailoring/generation_cleanup_ui_model.py": "a4dab3d9615159597b49d2c014f239e2b195e7f6adfa31a61bd3dd64d9284295",
    "tailoring/generation_controls_ui.py": "cc309f82f06cdc76cb3552f7fbb5e14932fe99f3899ff45113b159047cb40dee",
    "tailoring/initial_analysis_explainer.py": "7e7fa201e214805530aa8cc4c57d78567a7374147799a1dbf45023725d6520f1",
    "tailoring/initial_analysis_explainer_ui.py": "96ec5835ee2497a5188eb837009ff698d0caad898d3e24ac674e9d7b01f577b6",
    "tailoring/jd_specific_rephrase_preview.py": "1a6e5019ed9300bb931284b08e7694d01b413a66be8c3ed2737d98aca2ac34cd",
    "tailoring/jd_user_input_overrides.py": "aea829497ed3da16173f26709dadd9d0bc16d0e52861db02f2926f6390b80c7c",
    "tailoring/job_match_ab_analysis.py": "c9763504cda2f5723e4550670a7f2cb54bf8e70207b12e941c631a500d3edce0",
    "tailoring/ollama_performance_settings.py": "57f0bed67077ced93e2b6d956a08e5cb6d39cc8354d5f858845c853795a69380",
    "tailoring/phase6d5_retrieval.py": "0f076049d04bb178cf635998c07daa7e8a4c5ba8f3bdb59127792fd33840b822",
    "tailoring/phase6d6_structured_matching.py": "90658676df9bb04e6215345f468c6837b7157c5ddf7decb4abda4aabf100e744",
    "tailoring/phase6d_ranking_adapter.py": "bd16b094a168e3c5d78585de1af39c30be16ebf11b778beb43d023deafd31f4c",
    "tailoring/phase6d_stable_scoring_adapter.py": "499453bf9348383734edd75f310c94bb8f0764fc73b024625718b9d583f1e9e9",
    "tailoring/phase8_auto_verification.py": "d3e6221cf29c711d374c924e87c6a67cc9fe24105bcf7fa13fd32028e26ca621",
    "tailoring/phase8_claim_lineage.py": "1225df350c20b8dcf978f7fad885ebb80b6b3c532d1973b1ce615a60468ef34c",
    "tailoring/phase8_requirement_reconciliation.py": "4cfd376c49f82cda362e01f2343aa498c89f5b261eceed4086ac9e4c0369f7e2",
    "tailoring/phase8_score_explainability.py": "c714f94e4d31437a8ba78d806fe98e169e5131b0fea56ca4348e8bef6ec05d83",
    "tailoring/phase8_score_explainability_ui.py": "18475a22b6382ed1be41e711c273a313cfafec58424d1937818cb3bda32e55be",
    "tailoring/phase8_verification.py": "87e94c30d23c8dc0a07b53b363b65affdd21557113dc4a88fba01cf556e684ba",
    "tailoring/phase8_verification_ui.py": "e7916cca5b294d8249fd86a3824517b78ded545dfe156d2080c32987ed0f7e48",
    "tailoring/phase9a_evidence_opportunity.py": "e506dd1a05c6afaedb329bf0b1f42a4fdd787c410822287f11dd7131b7f905de",
    "tailoring/phase9a_evidence_opportunity_ui.py": "c9f65c009f0169b6eb457d1935b2fcf8df5ff988cde27126eda7f61cd915f366",
    "tailoring/phase9b_blueprint_candidate.py": "8c66fc4f9643732d63974bbce30b7fc5953e599aecbb13f50fd1e5e51fd579fd",
    "tailoring/phase9b_blueprint_ui.py": "037911c038e48a0d4f0dad559eec253d6224762e5170cbbef3587b6e6f136ce5",
    "tailoring/phase9b_role_family.py": "24fdfcdb4bfbb507196f561a271534f87cda4e2751f6b6ffe6c43eb48875e8e8",
    "tailoring/phase9c_blueprint_evaluation.py": "0fb979968c3e0e54e9ac455881d356bf2a7a3d4c02ad062b4c977cc9d87a0ebf",
    "tailoring/phase9c_blueprint_evaluation_ui.py": "fe37d4eaa1eb06d55fda9350cfa8a7391b6bff287d9a4bca328dcffe1de1b627",
    "tailoring/phase9d_blueprint_library_debug.py": "5d9303e46d27aef1858d142911a75e82fa6464a6fd8c462d59cf4720fa457e5f",
    "tailoring/phase9d_global_blueprint.py": "5196b475eeb50752b839b4c3c77fcef517197f2e4b025fa33a90de3cea55f5a8",
    "tailoring/phase9d_global_blueprint_ui.py": "f17cc27c6bebf987018a0bf088b7d2f91d6d215683a7b984ffa366b9d6237028",
    "tailoring/phase9d_variant_tags.py": "92b88cf76febfdcf5b9a60316c09fe456b94a463010c9f6ebdf2f054ab74c894",
    "tailoring/phase9e1_blueprint_lifecycle_ui.py": "eaf9abdff6ae83dc2be75d81d3f2a24c2aae5e5049608016eb61694205ae16ac",
    "tailoring/phase9e1_resume_workspace_ui.py": "e65d3e50df26dc69f221abe2eded801c8206d8fddf63678589439ab7d3a7f1bc",
    "tailoring/phase9e1_workflow_ui.py": "af8b7ff4092405c709a48c3881e7efb40f0845a0ec8041c15fae6f87cac25423",
    "tailoring/phase9e_application_result.py": "36f8da7dba349595bf76aef6866f254f5279e2f3334722059b30a986c12fe2a1",
    "tailoring/phase9e_application_result_ui.py": "5c19f09d463e39586d196a92388c444c8ef794eff9a4beeb65d4b1318b269d7a",
    "tailoring/phase9e_blueprint_selection.py": "c0e2d39bb71349d6070c645e41f5ea05441937c14b74b1ae21483ca0b9366a78",
    "tailoring/phase9e_blueprint_selection_ui.py": "67780650f9d7329300e86c92f63315910c9f8a82ebd8dd53fcde1e32592ff094",
    "tailoring/phase9e_tailoring_base_visual_preview.py": "b0fd8b3ed9cf2713f0bd4b9371a3d1ab6d2ba06b4babbdfc69df36c2471cd096",
    "tailoring/phase9f_application_confirmation.py": "b3e2e25e260f813467a5e3a3a1e43a45f53500e160729ff0c68fcfb6337e7f10",
    "tailoring/phase9f_application_confirmation_ui.py": "af3d0f96e29370078ff43aa07fcd2a1fbd6e7b5c8ba31760f7d3d47efa9fea7a",
    "tailoring/phase9f_application_execution.py": "5594b0c3973f27662495124b2bf7d83206768059e6e8d24cc2f9c7818481b044",
    "tailoring/phase9f_application_execution_ui.py": "f804bef0ab6ce9b62a1c7affad05b55db78615cfc392e0fd47d774f3c6100d02",
    "tailoring/phase9f_exact_verified_reuse.py": "2189883422aff2da6db1e4d376b33de2f8e134c5a92835f78c1d484e177c948a",
    "tailoring/phase9f_jd_intake.py": "f5bf24887bf0421b6180ab1a38f005fedfae98cfe4b09425d5a2467d46a9c22b",
    "tailoring/phase9f_master_resume.py": "dfb75b221ee0f67a091a11684bdcca63c3b42de380443836db395d416ba03b1c",
    "tailoring/phase9f_master_resume_ui.py": "7c05c445cf136c745b9b11cc965a241f70315beffcebb21a69010b528c4bf328",
    "tailoring/phase9f_orchestrator_ui.py": "753d45b32dbde43b752f56344e207281a93a709400d50cdea9329fc185322fdf",
    "tailoring/phase9f_preview_state.py": "3bfab934d03900d12c5daa38faa528b37169a60d1bf413c615aa259355c0632c",
    "tailoring/phase9f_starting_source_artifacts.py": "bf71c8a66874ff44bd71c8f4d8aa713a5c6b42715cdfc390a5f50b83b7bb116c",
    "tailoring/phase9f_starting_source_provenance.py": "c66726e1b60e84482d7013e17421a15e1790a3390c7b6b1e3fa087521710a576",
    "tailoring/phase9f_starting_source_ranking.py": "aeadf8cf17f66baf5d4114f361ff8596f7d50e13e6a8bfe947cb3367c904901e",
    "tailoring/phase9f_starting_source_ranking_ui.py": "3cab391594f00644c6984b3ad6c14cf5a3252bf3a1f74ddaa4f2c719a1700085",
    "tailoring/phase9f_starting_source_transparency.py": "2331f985bfe23a4a17dfd76c3dec563f07240ae40a3bbfd9a9d3d50c4444f12b",
    "tailoring/phase9f_tailoring_execution.py": "19029356952ffab3e29afc00145e1a920aa57a492a71b3c6b8f027412cad5ed0",
    "tailoring/phase9f_tailoring_execution_ui.py": "8e2ae16ba69265bd1547db7e4c8ccd734a16bb886681a03ce8a96b957b6cfb8f",
    "tailoring/phase9f_tailoring_intensity.py": "0cbd6943f875be6594b966d5a6f22d56c884e1eb68d011b283645fdd7ea0e0f3",
    "tailoring/phase9f_tailoring_intensity_ui.py": "6d60ce1c11c217a0ca1985252c1236f9cd7fbb7ca64b6d144c70f1a8979498df",
    "tailoring/production_requirement_resolver.py": "09610d229e054169ceb4146b5a8fce924a242b891e9b902ea8655bf76ccce060",
    "tailoring/project_identity.py": "ba6f2e3c5b587b02b8e17bcd27b452689caafba59967750f3bb4eab0f089a6fb",
    "tailoring/project_section_tailor.py": "d2caf3920d3ec547bfc724f4b95c39a332ee168af3980cd6bd2f49e18317c7a6",
    "tailoring/requirement_scope.py": "e02afbfe3568ee101895c16d5ec2a1fc59df017ce2f6a01eb2d1d87eb93bae1b",
    "tailoring/skills_section_tailor.py": "036f0e9838cc9155a001af184fa0eac09fabc5d018e479f17eab7ed2028d4fec",
    "tailoring/stable_tailoring_ranking.py": "de1da2881d8bb6eaa871a0d1530050b2c1dfe389ad035aa57384a4634d09c755",
    "tailoring/tailoring_debug_ui.py": "bda2775d929188cc5d2b87baacadcafca091a09b76f1dde6e51bb0f407c416f4",
    "tailoring/tailoring_generation_fingerprint.py": "36ee84b8c3481a6bf283e9024c53cd55ba142589a184e8df863b9daceb427492",
    "taxonomy/capability_taxonomy_v1.json": "da7b5e6952935a7dda88347c5af41eba65784b45da1c5b68f45a8768f605563e",
    "taxonomy/technology_registry_v1.json": "56ca633f2beb26cd2d290b7f328f3d59fcd6cb27bc7588d4c075759a3e2a9675",
    "tests/fixtures/confirmed_taxonomy_coverage.json": "6b5edb4287cceaae6b6c49a13fb4b149666a2514aaada34deb89e29ec2b7c299",
    "tests/fixtures/unresolved_adjudication_benchmark_v1.json": "898f494b553bca3283e311ecbbdb89de097fb274beab8c39401dccf346b95b0e",
    "tests/fixtures/unresolved_adjudication_benchmark_v2.json": "502f48b2501d786047adae31a32ba3240478fe4b15084b5433e029609c699d7d",
    "reports/unresolved_semantic_layer1_evidence_relevance_v1.json": "d8d5327ed93d05cc215b3ea263684ee66a6ab88db2f905d80d9cb2bd58d1493d",
    "docs/unresolved_semantic_layer1_evidence_relevance_v1.md": "11048e1766740fbf1f7e809feccd7de2d371bd78e6973ea8d694ca1c54caaabe",
    "reports/unresolved_evidence_explainability_review_v1_1.json": "f646a19c59c2eb11ecc63ff318b02e966f147a049f65d18a703834debbc07f4f",
    "reports/unresolved_multidimensional_route_audit_replay_v1.json": "cf86947c167ffacb269174674012bf7934541ce56676dde63d84cc491a70f62b",
    "reports/unresolved_multidimensional_triage_preview_v1.json": "647cfc9ebb6771f52e82c54e274dc38ef9f8005c6bafa4a88b3baa6909aabf1f",
    "reports/unresolved_multidimensional_triage_route_audit_final_v1.json": "0690c5550a99b64f6963b775daeacbd847549bf9a243e5264466bf001e3d0dcf",
    "reports/unresolved_multidimensional_triage_scoring_replay_v1.json": "cf86947c167ffacb269174674012bf7934541ce56676dde63d84cc491a70f62b",
    "reports/unresolved_qwen.json": "0f7476c79b605b1b2d5a58215364d8b4193d919fe8414cdcf87d6c91d505eb0d",
    "docs/unresolved_adjudication_v1.md": "3fec86b0f535b6d9c5d8a2ca4b7af407fa7fdebc09dd29b7b2ad92354bd34a93",
    "docs/unresolved_evidence_explainability_review_v1_1.md": "91ee9ab704be6bd810b5d153a969a0814d7b83323218a72756a4f4b86405faf0",
    "docs/unresolved_gold_decision_review_v3.md": "d3d855cfb6b365d0e2523a103a1c9235e1a2ec70da7e41443c11bba36f7c4525",
    "docs/unresolved_gold_review_packet_v4.md": "ebf959f254a949644301e72cb4ddb0a019711acffa81405d126f22bce9fdcb80",
    "docs/unresolved_gold_review_v2.md": "72516c792895652ff876cfe4dae6739e810295eaf19c1ba73283a37ac4cd70c4",
    "docs/unresolved_gold_review_workflow.md": "f015b86658011ea707f514590fe69c820476c2d64d8e844e36d051cacc4d7fc9",
    "docs/unresolved_multidimensional_route_audit_v1.md": "2d2455bf226d102fa8747a4cc31b90fca611b0280a677a8f470a59191fedcd88",
    "docs/unresolved_multidimensional_triage_v1.md": "3ac2cec6faf74b13068d052631e58a21c01f982e99d8d95a11f603da2088b6ef",
    "docs/ollama_unresolved_adjudication_smoke_v1.md": "d9ece928ea96cc9673ec6c0f6ea5d17766672becb5dcbb64ac8677ca0308ba74",
    "reports/ollama_unresolved_adjudication_smoke_v1.json": "f553bff0b46422f67eb22ac40af475ceeff3147d5532daa2f2fd2f361be51c44",
    "reports/ollama_unresolved_adjudication_smoke_v1_1.json": "0b7718948d1e5d6a1df6e8ca819638268a6bde81fd1d1e3e0f20856791ff2ce1",
    "docs/ollama_unresolved_adjudication_smoke_v1_1.md": "31308b9d751d17cfa2a827d4d01cdd37784680559780d48ea0754e397786d8a6",
    "scripts/smoke_ollama_unresolved_adjudication_v1.py": "99a4fd3f641df2b64368354a1439ebcc3b2175d12fa5feb2015d43332c1b389b",
    "tests/test_ollama_unresolved_smoke.py": "113af675a62dfb0c53cbfbf3644387ea886d29606032cbdffafe8110d5d7e081",
    "tests/fixtures/ollama_unresolved_holdout_v1_2.json": "d2f93fecdab31050cb4257b166ad5c3f146263f3b818df2b98eb89cb76c725b6",
    "scripts/compare_ollama_unresolved_prompts_v1_2.py": "45cf173b8b48fb6a295a30dca1cb1ed6ee1c05b7ffc7f611318cc1b8188891e5",
    "tests/test_ollama_prompt_comparison.py": "78121b290773b066dd6889c098fb4e6a5dbbdb34d3ae816d9610798309499537",
    "reports/ollama_unresolved_prompt_comparison_v1_2_plan.json": "b96384402b7126e314b0b979ede0c3d814a69694e24b46c4e84e660b9a0d16f6",
    "reports/ollama_unresolved_prompt_comparison_v1_2.json": "f3bede4214b51c84ed3fe27fb9a49c815e54367b5e8c6e6ff8ad993bc216a94c",
    "docs/ollama_unresolved_prompt_comparison_v1_2.md": "62b6dc04631d3cca0e57166ea3bec72b2856a817bf6e15cb64d3c076198a705d",
    "scripts/compare_ollama_unresolved_prompts_v1_3.py": "58679b6bb99952119f53b51a81006218b65441cbad9fa3053e78a0d611742cc2",
    "tests/test_ollama_prompt_comparison_v1_3.py": "a243855306a369ed83dd458a1b92b759299e3d20df6bb899d30b451885543cb4",
    "tests/fixtures/ollama_unresolved_holdout_v1_3.json": "50d003bce359f19682698aaeabfc1dbe948c7767d966bd8e96e5f61ad81b3536",
    "docs/ollama_unresolved_prompt_comparison_v1_3.md": "3c75bd287eff78a15c3abd1b208d55b161bea9cda183ac3dd3306c8050fe545a",
    "reports/ollama_unresolved_prompt_comparison_v1_3.json": "91a97f9cac709bb47c13c179021398b047c600f552add5fc6377328e6fbdf9ca",
    "reports/ollama_unresolved_prompt_comparison_v1_3_plan.json": "59dde3ecbf6e9b899d3a25a8036d796b3829179cf28e71cb910f685c35f07997",
    "scripts/review_ollama_unresolved_comparison_v1_3.py": "84127a38ea1d6f701c87484531a6579a5bb38c6728bfc23fbf662d32172aeb67",
    "tests/test_ollama_prompt_review_v1_3.py": "23ff47ea54b866ca85456fc69bc58d75baa2d6c2eb760dbb9b071a2acdd54b0b"
  }
}
```
