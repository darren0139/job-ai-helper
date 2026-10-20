# v1.23 original-span audit

Generated observations plus separately authored analyst judgments. Native output is not an oracle. The 83 v1.22 ambiguous lines and eight additional required boundary controls are all included. No real candidate evidence is used. Character intervals are zero-based, end-exclusive; line numbers are one-based.

## Job 16 · line 1 · [0, 82)

> [LTA-TRO] Senior/ Executive/ Data Engineer - Transport AI Programme, LTA Singapore

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **TITLE**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; short_unheaded_role_title.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [34, 34], "allocations": [25.999999, 25.999999]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 35 · line 1 · [0, 220)

> As a Governance Risk and Compliance Specialist & Application Security Engineer, this role is crucial in developing and maintaining a robust culture of technology and cybersecurity risk governance across our organization.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ROLE_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; organisation_or_role_purpose_without_candidate_obligation.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [16, 20], "allocations": [12.0, 16.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 35 · line 42 · [4319, 4328)

> Skillset:

- Source: `raw_jd.lines[42]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 31, "text": "Requirements", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Following section: null.
- Immediately preceding line: "Relevant experience in data visualisation and analytics.".
- Immediately following line: "Strong analytical, reasoning and problem-solving skills.".
- Native spans: [{"line": 42, "section": "requirements", "heading": "Requirements", "detection": "exact"}].
- v1.22: **AMBIGUOUS_HEADING**; unknown_boundary.
- Analyst judgment: **STRUCTURAL_HEADING**; Skillset names candidate competencies; four adjacent qualification statements corroborate it.
- v1.23: **STRUCTURAL_HEADING**; corroborated_local_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_6acc4cee02d0", "text": "Skillset", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_7c0cc524bb7f"}], "v20": [{"id": "req_6acc4cee02d0", "text": "Skillset", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_7c0cc524bb7f"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [16, 20], "allocations": [12.0, 16.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 35 · line 43 · [4329, 4385)

> Strong analytical, reasoning and problem-solving skills.

- Source: `raw_jd.lines[43]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 42, "text": "Skillset:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: null.
- Immediately preceding line: "Skillset:".
- Immediately following line: "Meticulous with an eye for detail.".
- Native spans: [{"line": 43, "section": "requirements", "heading": "Requirements", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **CANDIDATE_QUALIFICATION**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **CANDIDATE_QUALIFICATION**; child_of_corroborated_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_6490dec3cf56", "text": "Strong analytical, reasoning and problem-solving skills", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_0e067eb48e27"}], "v20": [{"id": "req_6490dec3cf56", "text": "Strong analytical, reasoning and problem-solving skills", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_0e067eb48e27"}], "v22": [], "v23": [{"id": "req_6490dec3cf56", "text": "Strong analytical, reasoning and problem-solving skills", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_0e067eb48e27"}]}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [16, 20], "allocations": [12.0, 16.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 35 · line 44 · [4386, 4420)

> Meticulous with an eye for detail.

- Source: `raw_jd.lines[44]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 42, "text": "Skillset:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: null.
- Immediately preceding line: "Strong analytical, reasoning and problem-solving skills.".
- Immediately following line: "Good oral and written communication skills".
- Native spans: [{"line": 44, "section": "requirements", "heading": "Requirements", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **CANDIDATE_QUALIFICATION**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **CANDIDATE_QUALIFICATION**; child_of_corroborated_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_a8d4a07cfa80", "text": "Meticulous with an eye for detail", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_9d63969ae1f6"}], "v20": [{"id": "req_a8d4a07cfa80", "text": "Meticulous with an eye for detail", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_9d63969ae1f6"}], "v22": [], "v23": [{"id": "req_a8d4a07cfa80", "text": "Meticulous with an eye for detail", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_9d63969ae1f6"}]}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [16, 20], "allocations": [12.0, 16.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 35 · line 45 · [4421, 4463)

> Good oral and written communication skills

- Source: `raw_jd.lines[45]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 42, "text": "Skillset:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: null.
- Immediately preceding line: "Meticulous with an eye for detail.".
- Immediately following line: "Ability to work independently and assume responsibility for project deliverables.".
- Native spans: [{"line": 45, "section": "requirements", "heading": "Requirements", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **CANDIDATE_QUALIFICATION**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **CANDIDATE_QUALIFICATION**; child_of_corroborated_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_bf70f248eb74", "text": "Good oral and written communication skills", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_4b27f37d0cd7"}], "v20": [{"id": "req_bf70f248eb74", "text": "Good oral and written communication skills", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_4b27f37d0cd7"}], "v22": [], "v23": [{"id": "req_bf70f248eb74", "text": "Good oral and written communication skills", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_4b27f37d0cd7"}]}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [16, 20], "allocations": [12.0, 16.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 35 · line 47 · [4546, 4592)

> Team player who is proactive and collaborative

- Source: `raw_jd.lines[47]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 42, "text": "Skillset:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: null.
- Immediately preceding line: "Ability to work independently and assume responsibility for project deliverables.".
- Immediately following line: "Experience in reporting and dashboard using JIRA is preferred.".
- Native spans: [{"line": 47, "section": "requirements", "heading": "Requirements", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **CANDIDATE_QUALIFICATION**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **CANDIDATE_QUALIFICATION**; child_of_corroborated_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_b1dc2883d493", "text": "Team player who is proactive and collaborative", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_8d4ce6ff6b59"}], "v20": [{"id": "req_b1dc2883d493", "text": "Team player who is proactive and collaborative", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_8d4ce6ff6b59"}], "v22": [], "v23": [{"id": "req_b1dc2883d493", "text": "Team player who is proactive and collaborative", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_8d4ce6ff6b59"}]}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [16, 20], "allocations": [12.0, 16.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 35 · line 50 · [4796, 4949)

> This is a 2-Year Contract. All applicants will be notified on whether they are shortlisted or not within 4 weeks of the closing date of this job posting.

- Source: `raw_jd.lines[50]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 42, "text": "Skillset:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: null.
- Immediately preceding line: "As part of the shortlisting process for this role, you may be required to complete a medical declaration and/or undergo further assessment.".
- Immediately following line: null.
- Native spans: [{"line": 50, "section": "requirements", "heading": "Requirements", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; explicit_contract_duration_and_notification.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_ce48db5c485c", "text": "This is a 2-Year Contract", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_db9df634fc9f"}], "v20": [{"id": "req_ce48db5c485c", "text": "This is a 2-Year Contract", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_db9df634fc9f"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [16, 20], "allocations": [12.0, 16.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 45 · line 1 · [0, 298)

> MINDEF is developing a suite of GenAI solutions to transform how procurement work is carried out across MINDEF/the Singapore Armed Forces (SAF). These include solutions that support users in drafting requirement specifications, evaluating quotations and tenders, and assessing price reasonableness.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 4, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "The next phase will focus on developing GenAI solutions for other identified procurement processes, including the generation of sourcing documents. You will work alongside a team to develop a minimum viable product (MVP), configure the relevant AI workflows, and test and refine the solution based on the intended requirements.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; organisation_or_role_purpose_without_candidate_obligation.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 22], "allocations": [20.999999, 19.999999]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 45 · line 22 · [3209, 3280)

> Period: December 2026/January 2027, extendable and open for discussion.

- Source: `raw_jd.lines[22]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 13, "text": "Requirements", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Following section: null.
- Immediately preceding line: "Supporting Documents Requirements: You may submit examples of relevant school, personal or internship projects, if available.".
- Immediately following line: "Those with relevant skillsets and interests may apply.".
- Native spans: [{"line": 22, "section": "requirements", "heading": "Requirements", "detection": "exact"}].
- v1.22: **ADMINISTRATIVE_METADATA**; administrative_field_syntax.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Explicit administrative contract period, not technical periodic maintenance.
- v1.23: **ADMINISTRATIVE_METADATA**; administrative_field_syntax.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_a72b7dab0e84", "text": "Period: December 2026/January 2027, extendable and open for discussion", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_95da64dd5461"}], "v20": [{"id": "req_a72b7dab0e84", "text": "Period: December 2026/January 2027, extendable and open for discussion", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_95da64dd5461"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 22], "allocations": [20.999999, 19.999999]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 48 · line 5 · [1000, 1031)

> Other responsibilities include:

- Source: `raw_jd.lines[5]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 3, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 10, "text": "Requirements", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "You are expected to build scripts to extract, prepare, transform and load data into an analytics software; build AI models with clustering and predictive capabilities. You will work closely with our team to gather user requirement and translate them into data requirement and insights. You will explore data, design data models, apply statistics, machine learning models for descriptive and diagnostic analysis, create, test, and implement visual dashboards that are relevant to different groups of college stakeholders. These dataset and dashboards may reside in our enterprise data lake and platforms, using Power BI as the visualization tool which is rendered to our end users.".
- Immediately following line: "Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time".
- Native spans: [{"line": 5, "section": "responsibilities", "heading": "Responsibilities", "detection": "exact"}].
- v1.22: **AMBIGUOUS_HEADING**; unknown_boundary.
- Analyst judgment: **STRUCTURAL_HEADING**; Other responsibilities include explicitly introduces three concrete job duties.
- v1.23: **STRUCTURAL_HEADING**; corroborated_local_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_2f5fca11a56e", "text": "Other responsibilities include", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_f6877e2efe57"}], "v20": [{"id": "req_2f5fca11a56e", "text": "Other responsibilities include", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_f6877e2efe57"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [13, 16], "allocations": [10.0, 13.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 48 · line 6 · [1032, 1183)

> Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time

- Source: `raw_jd.lines[6]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 5, "text": "Other responsibilities include:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 10, "text": "Requirements", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Other responsibilities include:".
- Immediately following line: "Provide training and consultancy to lecturers on how to use the dashboards".
- Native spans: [{"line": 6, "section": "responsibilities", "heading": "Responsibilities", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **RESPONSIBILITY**; child_of_corroborated_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_b50b5ed998f8", "text": "Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_421e7dee18af"}], "v20": [{"id": "req_b50b5ed998f8", "text": "Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_421e7dee18af"}], "v22": [], "v23": [{"id": "req_b50b5ed998f8", "text": "Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_421e7dee18af"}]}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [13, 16], "allocations": [10.0, 13.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 48 · line 7 · [1184, 1258)

> Provide training and consultancy to lecturers on how to use the dashboards

- Source: `raw_jd.lines[7]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 5, "text": "Other responsibilities include:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 10, "text": "Requirements", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Support analysis of learning and leaner profile data to help lecturers and stakeholders gain insights into students’ learning behavior during term time".
- Immediately following line: "Conduct knowledge transfer on data analytics and modelling to staff".
- Native spans: [{"line": 7, "section": "responsibilities", "heading": "Responsibilities", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **RESPONSIBILITY**; child_of_corroborated_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_3cd0ae39c4c9", "text": "Provide training and consultancy to lecturers on how to use the dashboards", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_19a32b6c8b67"}], "v20": [{"id": "req_3cd0ae39c4c9", "text": "Provide training and consultancy to lecturers on how to use the dashboards", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_19a32b6c8b67"}], "v22": [], "v23": [{"id": "req_3cd0ae39c4c9", "text": "Provide training and consultancy to lecturers on how to use the dashboards", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_19a32b6c8b67"}]}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [13, 16], "allocations": [10.0, 13.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 48 · line 8 · [1259, 1326)

> Conduct knowledge transfer on data analytics and modelling to staff

- Source: `raw_jd.lines[8]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 5, "text": "Other responsibilities include:", "section": "ambiguous", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 10, "text": "Requirements", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Provide training and consultancy to lecturers on how to use the dashboards".
- Immediately following line: "".
- Native spans: [{"line": 8, "section": "responsibilities", "heading": "Responsibilities", "detection": "exact"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **RESPONSIBILITY**; child_of_corroborated_candidate_list.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_0fe3bc4cc635", "text": "Conduct knowledge transfer on data analytics and modelling to staff", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_5539182dd2d1"}], "v20": [{"id": "req_0fe3bc4cc635", "text": "Conduct knowledge transfer on data analytics and modelling to staff", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_5539182dd2d1"}], "v22": [], "v23": [{"id": "req_0fe3bc4cc635", "text": "Conduct knowledge transfer on data analytics and modelling to staff", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_5539182dd2d1"}]}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [13, 16], "allocations": [10.0, 13.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 50 · line 1 · [0, 231)

> Science Centre Singapore is dedicated to the promotion of interest, learning and creativity in science & technology through imaginative and enjoyable experiences, and to contribute to the nation's development of its human resource.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 5, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "We are seeking a dynamic and driven individual to join the Digital Synthesis department as an Assistant Robotics Engineer/Robotics Engineer to develop and implement robotics solution for both Science Centre Singapore (SCS) and New Science Centre (NSC).".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; organisation_or_role_purpose_without_candidate_obligation.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [12, 12], "allocations": [9.0, 9.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 72 · line 1 · [0, 516)

> HTX is Singapore's Science and Technology agency that brings together diverse scientific and engineering capabilities to develop transformative, operationally ready solutions for public safety. As a statutory board under the Ministry of Home Affairs, HTX works at the forefront of science and technology to empower the Home Team with cutting-edge capabilities. Guided by our mission to amplify, augment and accelerate the Home Team's advantage, we are committed to keeping Singapore the safest place on planet Earth.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "xCloud is dedicated to elevating the enterprise experience through cutting-edge cloud capabilities, including:".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 72 · line 2 · [517, 627)

> xCloud is dedicated to elevating the enterprise experience through cutting-edge cloud capabilities, including:

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "HTX is Singapore's Science and Technology agency that brings together diverse scientific and engineering capabilities to develop transformative, operationally ready solutions for public safety. As a statutory board under the Ministry of Home Affairs, HTX works at the forefront of science and technology to empower the Home Team with cutting-edge capabilities. Guided by our mission to amplify, augment and accelerate the Home Team's advantage, we are committed to keeping Singapore the safest place on planet Earth.".
- Immediately following line: "• Sustainable enterprise data centres".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 72 · line 3 · [628, 665)

> • Sustainable enterprise data centres

- Source: `raw_jd.lines[3]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "xCloud is dedicated to elevating the enterprise experience through cutting-edge cloud capabilities, including:".
- Immediately following line: "• Hybrid cloud platforms".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 72 · line 4 · [666, 690)

> • Hybrid cloud platforms

- Source: `raw_jd.lines[4]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "• Sustainable enterprise data centres".
- Immediately following line: "• Advanced cloud security measures".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 72 · line 5 · [691, 725)

> • Advanced cloud security measures

- Source: `raw_jd.lines[5]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "• Hybrid cloud platforms".
- Immediately following line: "• Integrated Development, Security, and Operations (DevSecOps)".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 72 · line 6 · [726, 788)

> • Integrated Development, Security, and Operations (DevSecOps)

- Source: `raw_jd.lines[6]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "• Advanced cloud security measures".
- Immediately following line: "• Innovative enterprise Software-as-a-Service (SaaS) solutions".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 72 · line 7 · [789, 851)

> • Innovative enterprise Software-as-a-Service (SaaS) solutions

- Source: `raw_jd.lines[7]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "• Integrated Development, Security, and Operations (DevSecOps)".
- Immediately following line: "• AI-powered enterprise applications".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 72 · line 8 · [852, 888)

> • AI-powered enterprise applications

- Source: `raw_jd.lines[8]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 11, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "• Innovative enterprise Software-as-a-Service (SaaS) solutions".
- Immediately following line: "We are looking for an Engineer, Hybrid Cloud Excellence who will work at the intersection of cloud platform engineering and site reliability engineering, with a primary focus on designing and operationalising hybrid cloud integration solutions across diverse hosting environments.".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [21.0, 21.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 81 · line 1 · [0, 81)

> This is a 2-year contract position with the Digital Services & Technology Office.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 4, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "The AI Engineer will be instrumental in implementing NP's AI transformation strategy by developing production-ready AI applications and systems that leverage AI tools and Cloud AI services. This role focuses on building robust, scalable AI solutions using GenAI models, deep learning, neural networks, and other AI technologies to improve NP operations through intelligent automation and advanced analytics. Working in close collaboration with the AI Product Manager, data scientists, and cross-functional teams, the AI Engineer will transition AI models from research to production and embed AI capabilities into NP's administrative and academic support workflows.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; explicit_contract_duration_and_notification.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [22, 22], "allocations": [19.0, 19.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 81 · line 2 · [82, 747)

> The AI Engineer will be instrumental in implementing NP's AI transformation strategy by developing production-ready AI applications and systems that leverage AI tools and Cloud AI services. This role focuses on building robust, scalable AI solutions using GenAI models, deep learning, neural networks, and other AI technologies to improve NP operations through intelligent automation and advanced analytics. Working in close collaboration with the AI Product Manager, data scientists, and cross-functional teams, the AI Engineer will transition AI models from research to production and embed AI capabilities into NP's administrative and academic support workflows.

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 4, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "This is a 2-year contract position with the Digital Services & Technology Office.".
- Immediately following line: "".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [22, 22], "allocations": [19.0, 19.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 146 · line 1 · [0, 530)

> The Singapore Global Network (SGN) is a division in the Economic Development Board tasked to re-energise Singapore’s efforts in building a strong and extensive ecosystem of overseas Family, Friends, Fans (3F) for Singapore. SGN leads the Whole-Of-Government effort to coordinate across agencies and strengthen our collective networks whose skills, affinity and influence could help build linkages to global business and talent communities, and enhance the international mindshare of Singapore as a leading globally-connected city.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [43, 43], "allocations": [28.999999, 28.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 163 · line 1 · [0, 457)

> ISD confronts and addresses threats to Singapore’s internal security and stability. For over 70 years, ISD and its predecessor organisations have played a central role in countering threats such as those posed by foreign subversive elements, spies, racial and religious extremists, and terrorists. A fulfilling and rewarding career awaits those who want to join in ISD’s critical mission of keeping Singapore safe, secure and sovereign for all Singaporeans.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 5, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "We are working on a Digital Transformation Programme to transform how endpoint support is provided to officers through re-engineering work processes and automation. If you are a person passionate about technology, providing excellent customer service support and looking for opportunities to work with a team of IT professionals, we welcome you to join us.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [49, 49], "allocations": [30.999998, 30.999998]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 163 · line 2 · [458, 814)

> We are working on a Digital Transformation Programme to transform how endpoint support is provided to officers through re-engineering work processes and automation. If you are a person passionate about technology, providing excellent customer service support and looking for opportunities to work with a team of IT professionals, we welcome you to join us.

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 5, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "ISD confronts and addresses threats to Singapore’s internal security and stability. For over 70 years, ISD and its predecessor organisations have played a central role in countering threats such as those posed by foreign subversive elements, spies, racial and religious extremists, and terrorists. A fulfilling and rewarding career awaits those who want to join in ISD’s critical mission of keeping Singapore safe, secure and sovereign for all Singaporeans.".
- Immediately following line: "You will be part of a dynamic team responsible for the design, implementation, operations and support of our enterprise endpoints management solutions. You are expected to have strong infrastructure and endpoint background. You will be closely working with peers from other teams like network and security to ensure a holistic view during the design and implementation to achieve the best experience for the end-users in terms of network performance, usability, accessibility, and security.".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **MIXED_PROJECT_AND_RECRUITING_PROSE**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [49, 49], "allocations": [30.999998, 30.999998]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 1 · [0, 421)

> The Government Technology Agency (GovTech) is the lead agency driving Singapore’s Smart Nation initiatives and public sector digital transformation. As the Centre of Excellence for Infocomm Technology and Smart Systems (ICT & SS), GovTech develops the Singapore Government’s capabilities in Data Science & Artificial Intelligence, Application Development, Smart City Technology, Digital Infrastructure, and Cybersecurity.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "At GovTech, we offer you a purposeful career to make lives better. We empower our people to master their craft through continuous and robust learning and development opportunities all year round. Our GovTechies embody our Agile, Bold and Collaborative values to deliver impactful solutions.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; organisation_or_role_purpose_without_candidate_obligation.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 240 · line 2 · [422, 712)

> At GovTech, we offer you a purposeful career to make lives better. We empower our people to master their craft through continuous and robust learning and development opportunities all year round. Our GovTechies embody our Agile, Bold and Collaborative values to deliver impactful solutions.

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Immediately preceding line: "The Government Technology Agency (GovTech) is the lead agency driving Singapore’s Smart Nation initiatives and public sector digital transformation. As the Centre of Excellence for Infocomm Technology and Smart Systems (ICT & SS), GovTech develops the Singapore Government’s capabilities in Data Science & Artificial Intelligence, Application Development, Smart City Technology, Digital Infrastructure, and Cybersecurity.".
- Immediately following line: "GovTech aims to transform the delivery of Government digital services by taking an \"outside-in\" view, putting citizens and businesses at the heart of everything we do.".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 3 · [713, 880)

> GovTech aims to transform the delivery of Government digital services by taking an "outside-in" view, putting citizens and businesses at the heart of everything we do.

- Source: `raw_jd.lines[3]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Immediately preceding line: "At GovTech, we offer you a purposeful career to make lives better. We empower our people to master their craft through continuous and robust learning and development opportunities all year round. Our GovTechies embody our Agile, Bold and Collaborative values to deliver impactful solutions.".
- Immediately following line: "Play a part in Singapore’s vision to build a Smart Nation and embark on your meaningful journey to build tech for public good. Join us to advance our mission and shape your future with us today!".
- Native spans: [{"line": 3, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 4 · [881, 1075)

> Play a part in Singapore’s vision to build a Smart Nation and embark on your meaningful journey to build tech for public good. Join us to advance our mission and shape your future with us today!

- Source: `raw_jd.lines[4]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Immediately preceding line: "GovTech aims to transform the delivery of Government digital services by taking an \"outside-in\" view, putting citizens and businesses at the heart of everything we do.".
- Immediately following line: "Learn more about GovTech at tech.gov.sg.".
- Native spans: [{"line": 4, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 5 · [1076, 1116)

> Learn more about GovTech at tech.gov.sg.

- Source: `raw_jd.lines[5]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Immediately preceding line: "Play a part in Singapore’s vision to build a Smart Nation and embark on your meaningful journey to build tech for public good. Join us to advance our mission and shape your future with us today!".
- Immediately following line: "About the division:".
- Native spans: [{"line": 5, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 7 · [1137, 1586)

> At Singpass, we aim to provide reliable digital identity for Singapore that streamlines transactions, enables businesses, and protects against fraud. This involves improving the online transaction experience with Singpass and Corppass while keeping it secure. It includes everything from building better frontend applications for residents and keeping an eye on fraudulent transactions to improving internal operations and working with our partners.

- Source: `raw_jd.lines[7]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "About the division:".
- Immediately following line: "What you will be working on:".
- Native spans: [{"line": 7, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 9 · [1616, 1671)

> As an Lead Cybersecurity Engineer, your job will be to:

- Source: `raw_jd.lines[9]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "What you will be working on:".
- Immediately following line: "Determine what assurance gaps exist across our product portfolio and decide what assessment approaches best surface real risk and drive meaningful remediation".
- Native spans: [].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **STRUCTURAL_RESPONSIBILITY_INTRODUCER**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 10 · [1672, 1830)

> Determine what assurance gaps exist across our product portfolio and decide what assessment approaches best surface real risk and drive meaningful remediation

- Source: `raw_jd.lines[10]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "As an Lead Cybersecurity Engineer, your job will be to:".
- Immediately following line: "Shape the strategic direction of our cybersecurity assurance programme and prioritise activities based on the threat landscape, product criticality, and organisational risk appetite".
- Native spans: [{"line": 10, "section": "", "heading": "As an Lead Cybersecurity Engineer, your job will be to:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 11 · [1831, 2012)

> Shape the strategic direction of our cybersecurity assurance programme and prioritise activities based on the threat landscape, product criticality, and organisational risk appetite

- Source: `raw_jd.lines[11]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Determine what assurance gaps exist across our product portfolio and decide what assessment approaches best surface real risk and drive meaningful remediation".
- Immediately following line: "Work with people from engineering, product, policy, and operations to ensure security assurance is embedded as a rigorous and trusted function across our digital services".
- Native spans: [{"line": 11, "section": "", "heading": "As an Lead Cybersecurity Engineer, your job will be to:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 12 · [2013, 2183)

> Work with people from engineering, product, policy, and operations to ensure security assurance is embedded as a rigorous and trusted function across our digital services

- Source: `raw_jd.lines[12]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Shape the strategic direction of our cybersecurity assurance programme and prioritise activities based on the threat landscape, product criticality, and organisational risk appetite".
- Immediately following line: "Measure and track the effectiveness of our assurance activities, from assessment coverage and finding severity trends to remediation rates and compliance posture".
- Native spans: [{"line": 12, "section": "", "heading": "As an Lead Cybersecurity Engineer, your job will be to:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 13 · [2184, 2345)

> Measure and track the effectiveness of our assurance activities, from assessment coverage and finding severity trends to remediation rates and compliance posture

- Source: `raw_jd.lines[13]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Work with people from engineering, product, policy, and operations to ensure security assurance is embedded as a rigorous and trusted function across our digital services".
- Immediately following line: "Wear multiple hats to keep our systems honest. You may be leading a penetration test, conducting a secure architecture review, facilitating a threat modelling exercise, or advising on a governance/risk/compliance matter".
- Native spans: [{"line": 13, "section": "", "heading": "As an Lead Cybersecurity Engineer, your job will be to:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 14 · [2346, 2565)

> Wear multiple hats to keep our systems honest. You may be leading a penetration test, conducting a secure architecture review, facilitating a threat modelling exercise, or advising on a governance/risk/compliance matter

- Source: `raw_jd.lines[14]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Measure and track the effectiveness of our assurance activities, from assessment coverage and finding severity trends to remediation rates and compliance posture".
- Immediately following line: "Build a culture of accountability and continuous improvement with the people you work with".
- Native spans: [{"line": 14, "section": "", "heading": "As an Lead Cybersecurity Engineer, your job will be to:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 15 · [2566, 2656)

> Build a culture of accountability and continuous improvement with the people you work with

- Source: `raw_jd.lines[15]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 6, "text": "About the division:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 16, "text": "What we are looking for", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Wear multiple hats to keep our systems honest. You may be leading a penetration test, conducting a secure architecture review, facilitating a threat modelling exercise, or advising on a governance/risk/compliance matter".
- Immediately following line: "What we are looking for".
- Native spans: [{"line": 15, "section": "", "heading": "As an Lead Cybersecurity Engineer, your job will be to:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 46 · [6884, 7077)

> GovTech is an equal opportunity employer committed to fostering an inclusive workplace that values diverse voices and perspectives, as we believe that diversity is the foundation to innovation.

- Source: `raw_jd.lines[46]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 45, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "What we offer you:".
- Immediately following line: "Our employee benefits are based on a total rewards approach, offering a holistic and market-competitive suite of perks. These include leave benefits to meet your work-life needs and employee wellness programs.".
- Native spans: [{"line": 46, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 47 · [7078, 7287)

> Our employee benefits are based on a total rewards approach, offering a holistic and market-competitive suite of perks. These include leave benefits to meet your work-life needs and employee wellness programs.

- Source: `raw_jd.lines[47]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 45, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "GovTech is an equal opportunity employer committed to fostering an inclusive workplace that values diverse voices and perspectives, as we believe that diversity is the foundation to innovation.".
- Immediately following line: "We champion flexible work arrangements (subject to your job role) and trust that you will manage your own time to deliver your best, wherever you are, and whatever works best for you.".
- Native spans: [{"line": 47, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 49 · [7472, 7537)

> Learn more about life inside GovTech at go.gov.sg/GovTechCareers.

- Source: `raw_jd.lines[49]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 45, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "We champion flexible work arrangements (subject to your job role) and trust that you will manage your own time to deliver your best, wherever you are, and whatever works best for you.".
- Immediately following line: "Stay connected with us on social media at go.gov.sg/ConnectWithGovTech".
- Native spans: [{"line": 49, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 240 · line 50 · [7538, 7608)

> Stay connected with us on social media at go.gov.sg/ConnectWithGovTech

- Source: `raw_jd.lines[50]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 45, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "Learn more about life inside GovTech at go.gov.sg/GovTechCareers.".
- Immediately following line: null.
- Native spans: [{"line": 50, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [31, 31], "allocations": [30.0, 30.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 1 · [0, 386)

> GovTech is the lead agency driving Singapore’s Smart Nation initiatives and public sector digital transformation. As the Centre of Excellence for Infocomm Technology and Smart Systems (ICT & SS), GovTech develops the Singapore Government’s capabilities in Data Science & Artificial Intelligence, Application Development, Smart City Technology, Digital Infrastructure, and Cybersecurity.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "At GovTech, we offer you a purposeful career to make lives better where we empower our people to master their craft through robust learning and development opportunities all year round.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; organisation_or_role_purpose_without_candidate_obligation.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 319 · line 2 · [387, 572)

> At GovTech, we offer you a purposeful career to make lives better where we empower our people to master their craft through robust learning and development opportunities all year round.

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Immediately preceding line: "GovTech is the lead agency driving Singapore’s Smart Nation initiatives and public sector digital transformation. As the Centre of Excellence for Infocomm Technology and Smart Systems (ICT & SS), GovTech develops the Singapore Government’s capabilities in Data Science & Artificial Intelligence, Application Development, Smart City Technology, Digital Infrastructure, and Cybersecurity.".
- Immediately following line: "About the team:".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 4 · [589, 982)

> Singpass enables high assurance authentication, digital signatures, and secure data sharing (Myinfo) for millions of users. Working here means building infrastructure where security, reliability, and trust are the foundation of everything we do. We don’t just write code; we solve complex problems to ensure that national digital services are seamless, secure, and resilient for every citizen.

- Source: `raw_jd.lines[4]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 14, "text": "[What we're looking for]", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "About the team:".
- Immediately following line: "[What you will be working on]".
- Native spans: [{"line": 4, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 7 · [1164, 1367)

> Solve End-to-End Problems: Participate in the full software development lifecycle, from brainstorming solutions with product managers and fellow engineers, to deploying and monitoring code in production.

- Source: `raw_jd.lines[7]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 14, "text": "[What we're looking for]", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "As an Android Engineer at Singpass, you won't be confined to a single layer of the stack. We view our engineers as holistic problem solvers. You will:".
- Immediately following line: "Build & Prototype: Develop and iterate on features for Singpass, ensuring they meet our high standards for security and usability.".
- Native spans: [{"line": 7, "section": "", "heading": "[What you will be working on]", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 8 · [1368, 1498)

> Build & Prototype: Develop and iterate on features for Singpass, ensuring they meet our high standards for security and usability.

- Source: `raw_jd.lines[8]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 14, "text": "[What we're looking for]", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Solve End-to-End Problems: Participate in the full software development lifecycle, from brainstorming solutions with product managers and fellow engineers, to deploying and monitoring code in production.".
- Immediately following line: "Write Robust Code: Craft clean, maintainable, and secure-by-design code. You will focus on implementing secure authentication, data sharing features, and reliable mobile experiences.".
- Native spans: [{"line": 8, "section": "", "heading": "[What you will be working on]", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 10 · [1682, 1872)

> Build Modern UI/UX: Develop intuitive, responsive interfaces using native Android UI frameworks and modern Android layout components, ensuring smooth user experiences across diverse devices.

- Source: `raw_jd.lines[10]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 14, "text": "[What we're looking for]", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Write Robust Code: Craft clean, maintainable, and secure-by-design code. You will focus on implementing secure authentication, data sharing features, and reliable mobile experiences.".
- Immediately following line: "Optimize Performance & Architecture: Design and maintain robust, scalable Android app architectures (e.g., MVVM/MVI) and optimize application performance, focusing on memory management, battery efficiency, and network responsiveness.".
- Native spans: [{"line": 10, "section": "", "heading": "[What you will be working on]", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 11 · [1873, 2106)

> Optimize Performance & Architecture: Design and maintain robust, scalable Android app architectures (e.g., MVVM/MVI) and optimize application performance, focusing on memory management, battery efficiency, and network responsiveness.

- Source: `raw_jd.lines[11]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 14, "text": "[What we're looking for]", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Build Modern UI/UX: Develop intuitive, responsive interfaces using native Android UI frameworks and modern Android layout components, ensuring smooth user experiences across diverse devices.".
- Immediately following line: "Learn Cloud Native Engineering: Understand how mobile clients interact with cloud deployments, focusing on system integrity and operational safety.".
- Native spans: [{"line": 11, "section": "", "heading": "[What you will be working on]", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 12 · [2107, 2254)

> Learn Cloud Native Engineering: Understand how mobile clients interact with cloud deployments, focusing on system integrity and operational safety.

- Source: `raw_jd.lines[12]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 14, "text": "[What we're looking for]", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Optimize Performance & Architecture: Design and maintain robust, scalable Android app architectures (e.g., MVVM/MVI) and optimize application performance, focusing on memory management, battery efficiency, and network responsiveness.".
- Immediately following line: "Collaborate Across Disciplines: Work closely with UX designers, cybersecurity specialists, and fellow engineers to understand user needs and technical constraints.".
- Native spans: [{"line": 12, "section": "", "heading": "[What you will be working on]", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 13 · [2255, 2418)

> Collaborate Across Disciplines: Work closely with UX designers, cybersecurity specialists, and fellow engineers to understand user needs and technical constraints.

- Source: `raw_jd.lines[13]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 3, "text": "About the team:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: {"line": 14, "text": "[What we're looking for]", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Learn Cloud Native Engineering: Understand how mobile clients interact with cloud deployments, focusing on system integrity and operational safety.".
- Immediately following line: "[What we're looking for]".
- Native spans: [{"line": 13, "section": "", "heading": "[What you will be working on]", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 27 · [3900, 4093)

> GovTech is an equal opportunity employer committed to fostering an inclusive workplace that values diverse voices and perspectives, as we believe that diversity is the foundation to innovation.

- Source: `raw_jd.lines[27]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 26, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "What we offer you:".
- Immediately following line: "Our employee benefits are based on a total rewards approach, offering a holistic and market-competitive suite of perks. These include leave benefits to meet your work-life needs and employee wellness programs.".
- Native spans: [{"line": 27, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 28 · [4094, 4303)

> Our employee benefits are based on a total rewards approach, offering a holistic and market-competitive suite of perks. These include leave benefits to meet your work-life needs and employee wellness programs.

- Source: `raw_jd.lines[28]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 26, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "GovTech is an equal opportunity employer committed to fostering an inclusive workplace that values diverse voices and perspectives, as we believe that diversity is the foundation to innovation.".
- Immediately following line: "We champion flexible work arrangements (subject to your job role) and trust that you will manage your own time to deliver your best, wherever you are, and whatever works best for you.".
- Native spans: [{"line": 28, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 30 · [4488, 4553)

> Learn more about life inside GovTech at go.gov.sg/GovTechCareers.

- Source: `raw_jd.lines[30]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 26, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "We champion flexible work arrangements (subject to your job role) and trust that you will manage your own time to deliver your best, wherever you are, and whatever works best for you.".
- Immediately following line: "Stay connected with us on social media at go.gov.sg/ConnectWithGovTech".
- Native spans: [{"line": 30, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 319 · line 31 · [4554, 4624)

> Stay connected with us on social media at go.gov.sg/ConnectWithGovTech

- Source: `raw_jd.lines[31]`; v1.22 ambiguity: **True**.
- Preceding section: {"line": 26, "text": "What we offer you:", "section": "ambiguous", "classification": "AMBIGUOUS_HEADING"}.
- Following section: null.
- Immediately preceding line: "Learn more about life inside GovTech at go.gov.sg/GovTechCareers.".
- Immediately following line: null.
- Native spans: [{"line": 31, "section": "", "heading": "What we offer you:", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [12.999999, 12.999999]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 359 · line 1 · [0, 11)

> - Permanent

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "- Up to $7,000 + PB".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; verified_duplicate_posting_value.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_0dd1b6d5c52e", "text": "Permanent", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_a41f0605b80d"}], "v20": [{"id": "req_0dd1b6d5c52e", "text": "Permanent", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_a41f0605b80d"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 359 · line 2 · [12, 31)

> - Up to $7,000 + PB

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "- Permanent".
- Immediately following line: "- Mon–Fri 8am–5:30pm".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; verified_duplicate_posting_value.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 359 · line 4 · [53, 117)

> - Jurong East (Shuttle service provided at selected MRT station)

- Source: `raw_jd.lines[4]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "- Mon–Fri 8am–5:30pm".
- Immediately following line: "Job Responsibilities:".
- Native spans: [{"line": 4, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; verified_duplicate_posting_value.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_9f2612d7a66c", "text": "Jurong East (Shuttle service provided at selected MRT station)", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_dea93c763332"}], "v20": [{"id": "req_9f2612d7a66c", "text": "Jurong East (Shuttle service provided at selected MRT station)", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_dea93c763332"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 359 · line 16 · [1201, 1208)

> Period:

- Source: `raw_jd.lines[16]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 24, "text": "Job Requirements:", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Provide technical guidance and knowledge sharing to junior engineers where applicable.".
- Immediately following line: "Permanent".
- Native spans: [{"line": 16, "section": "responsibilities", "heading": "Job Responsibilities:", "detection": "exact"}].
- v1.22: **ADMINISTRATIVE_METADATA**; administrative_field_syntax.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Field/value or literal weekday schedule in an employment detail block; no candidate obligation.
- v1.23: **ADMINISTRATIVE_METADATA**; administrative_field_syntax.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_514cb13f6034", "text": "Period", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_9a7d6d48c964"}], "v20": [{"id": "req_514cb13f6034", "text": "Period", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_9a7d6d48c964"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 359 · line 17 · [1209, 1218)

> Permanent

- Source: `raw_jd.lines[17]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 24, "text": "Job Requirements:", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Period:".
- Immediately following line: "Location:".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}, {"line": 17, "section": "responsibilities", "heading": "Job Responsibilities:", "detection": "exact"}].
- v1.22: **ADMINISTRATIVE_METADATA**; adjacent_administrative_value.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Field/value or literal weekday schedule in an employment detail block; no candidate obligation.
- v1.23: **ADMINISTRATIVE_METADATA**; adjacent_administrative_value.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_0dd1b6d5c52e", "text": "Permanent", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_a41f0605b80d"}], "v20": [{"id": "req_0dd1b6d5c52e", "text": "Permanent", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_a41f0605b80d"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 359 · line 18 · [1219, 1228)

> Location:

- Source: `raw_jd.lines[18]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 24, "text": "Job Requirements:", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Permanent".
- Immediately following line: "Jurong East (Shuttle service provided at selected MRT station)".
- Native spans: [{"line": 18, "section": "responsibilities", "heading": "Job Responsibilities:", "detection": "exact"}].
- v1.22: **ADMINISTRATIVE_METADATA**; administrative_field_syntax.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Field/value or literal weekday schedule in an employment detail block; no candidate obligation.
- v1.23: **ADMINISTRATIVE_METADATA**; administrative_field_syntax.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_e6eaea18e885", "text": "Location", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_99fa8abc7011"}], "v20": [{"id": "req_e6eaea18e885", "text": "Location", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_99fa8abc7011"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 359 · line 19 · [1229, 1291)

> Jurong East (Shuttle service provided at selected MRT station)

- Source: `raw_jd.lines[19]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 24, "text": "Job Requirements:", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Location:".
- Immediately following line: "Working hours:".
- Native spans: [{"line": 4, "section": "", "heading": "", "detection": ""}, {"line": 19, "section": "responsibilities", "heading": "Job Responsibilities:", "detection": "exact"}].
- v1.22: **ADMINISTRATIVE_METADATA**; adjacent_administrative_value.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Field/value or literal weekday schedule in an employment detail block; no candidate obligation.
- v1.23: **ADMINISTRATIVE_METADATA**; adjacent_administrative_value.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_9f2612d7a66c", "text": "Jurong East (Shuttle service provided at selected MRT station)", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_dea93c763332"}], "v20": [{"id": "req_9f2612d7a66c", "text": "Jurong East (Shuttle service provided at selected MRT station)", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_dea93c763332"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 359 · line 21 · [1307, 1325)

> Mon–Fri 8am–5:30pm

- Source: `raw_jd.lines[21]`; v1.22 ambiguity: **False**.
- Preceding section: {"line": 5, "text": "Job Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Following section: {"line": 24, "text": "Job Requirements:", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Working hours:".
- Immediately following line: "Salary:".
- Native spans: [{"line": 3, "section": "", "heading": "", "detection": ""}, {"line": 21, "section": "responsibilities", "heading": "Job Responsibilities:", "detection": "exact"}].
- v1.22: **ADMINISTRATIVE_METADATA**; adjacent_administrative_value.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Field/value or literal weekday schedule in an employment detail block; no candidate obligation.
- v1.23: **ADMINISTRATIVE_METADATA**; adjacent_administrative_value.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [{"id": "req_e7c28dcb701a", "text": "Mon–Fri 8am–5:30pm", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_dcc46f32fa89"}], "v20": [{"id": "req_e7c28dcb701a", "text": "Mon–Fri 8am–5:30pm", "allocation": 1.0, "importance": "core", "label": "none", "parent_occurrence": "srcgrp_dcc46f32fa89"}], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [24, 24], "allocations": [24.0, 24.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 361 · line 2 · [442, 484)

> Senior Embedded Graphics Software Engineer

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Our client is a leading startup in the semiconductor field and a leader in designing ultra low-power microprocessors. Opportunity to join a dynamic embedded software team developing SDKs and software platforms for next-generation microcontroller and SoC products. You will work closely with hardware, architecture, validation, and customer-facing teams to deliver high-quality software solutions that enable innovative embedded applications.".
- Immediately following line: "Responsibilities:".
- Native spans: [].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **TITLE**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; short_unheaded_role_title.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [13, 13], "allocations": [13.0, 13.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 370 · line 1 · [0, 351)

> ALTEN Group is a world leader in Engineering and Technology consulting services providing outsourced Engineering, R&D, and IT Services for different industries such as Transportation, Defence, Energy and Security with 55,000 engineers in nearly 35 countries. ANOTECH is the subsidiary of the Group delivering ALTEN's Engineering Services in Singapore.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "As a Senior Embedded Software Engineer, you will be responsible for creating and maintaining the technical backbone that enables efficient development, testing, and delivery of embedded systems, including implementation of AI-assisted development workflows.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; organisation_or_role_purpose_without_candidate_obligation.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [19, 19], "allocations": [19.0, 19.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 479 · line 2 · [269, 476)

> We are looking for a software engineer with strong programming fundamentals, excellent problem-solving skills, and the ability to deliver high-quality solutions throughout the software development lifecycle.

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "Key Responsibilities", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Brunel is seeking an experienced Senior Software Engineer (Full Stack) on behalf of our client. In this role, you will develop and enhance modern enterprise applications using React, TypeScript and Python technologies while collaborating within an Agile delivery team.".
- Immediately following line: "Key Responsibilities".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **CANDIDATE_QUALIFICATION**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": false, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [33, 33], "allocations": [32.0, 32.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 493 · line 1 · [0, 20)

> About ST Engineering

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 8, "text": "Be Part of Our Success", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "ST Engineering is a global technology, defence, and engineering group with offices across Asia, Europe, the Middle East, and the U.S., serving customers in more than 100 countries. The Group uses technology and innovation to solve real-world problems and improve lives through its diverse portfolio of businesses across the aerospace, smart city, defence, and public security segments. Headquartered in Singapore, ST Engineering ranks among the largest companies listed on the Singapore Exchange.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [17, 17], "allocations": [15.0, 15.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 493 · line 2 · [21, 517)

> ST Engineering is a global technology, defence, and engineering group with offices across Asia, Europe, the Middle East, and the U.S., serving customers in more than 100 countries. The Group uses technology and innovation to solve real-world problems and improve lives through its diverse portfolio of businesses across the aerospace, smart city, defence, and public security segments. Headquartered in Singapore, ST Engineering ranks among the largest companies listed on the Singapore Exchange.

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 8, "text": "Be Part of Our Success", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "About ST Engineering".
- Immediately following line: "Our history spans more than 50 years, and our strategy is underpinned by our core values – Integrity, Value Creation, Courage, Commitment and Compassion. These 5 core values guide every aspect of our business and are embedded in our ST Engineering culture – from the people we hire, to working with each other, to our partners and customers.".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; organisation_or_role_purpose_without_candidate_obligation.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [17, 17], "allocations": [15.0, 15.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 493 · line 3 · [518, 859)

> Our history spans more than 50 years, and our strategy is underpinned by our core values – Integrity, Value Creation, Courage, Commitment and Compassion. These 5 core values guide every aspect of our business and are embedded in our ST Engineering culture – from the people we hire, to working with each other, to our partners and customers.

- Source: `raw_jd.lines[3]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 8, "text": "Be Part of Our Success", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "ST Engineering is a global technology, defence, and engineering group with offices across Asia, Europe, the Middle East, and the U.S., serving customers in more than 100 countries. The Group uses technology and innovation to solve real-world problems and improve lives through its diverse portfolio of businesses across the aerospace, smart city, defence, and public security segments. Headquartered in Singapore, ST Engineering ranks among the largest companies listed on the Singapore Exchange.".
- Immediately following line: "About our Line of Business – Mission Software & Services".
- Native spans: [{"line": 3, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [17, 17], "allocations": [15.0, 15.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 493 · line 4 · [860, 916)

> About our Line of Business – Mission Software & Services

- Source: `raw_jd.lines[4]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 8, "text": "Be Part of Our Success", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Our history spans more than 50 years, and our strategy is underpinned by our core values – Integrity, Value Creation, Courage, Commitment and Compassion. These 5 core values guide every aspect of our business and are embedded in our ST Engineering culture – from the people we hire, to working with each other, to our partners and customers.".
- Immediately following line: "Our Mission Software & Services business provides leading-edge mission critical command, control, and communications (C3) systems with secured IT infrastructure and managed services. We support our client’s innovation journey through design thinking, analytics, and AI-enabled decision support with our full suite of cloud computing solutions. We provide intelligent, actionable insights and sustainable solutions to our valued partners in diverse industries including defence, government, and commercial sectors.".
- Native spans: [{"line": 4, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [17, 17], "allocations": [15.0, 15.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 493 · line 5 · [917, 1430)

> Our Mission Software & Services business provides leading-edge mission critical command, control, and communications (C3) systems with secured IT infrastructure and managed services. We support our client’s innovation journey through design thinking, analytics, and AI-enabled decision support with our full suite of cloud computing solutions. We provide intelligent, actionable insights and sustainable solutions to our valued partners in diverse industries including defence, government, and commercial sectors.

- Source: `raw_jd.lines[5]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 8, "text": "Be Part of Our Success", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "About our Line of Business – Mission Software & Services".
- Immediately following line: "Together, We Can Make A Significant Impact".
- Native spans: [{"line": 5, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [17, 17], "allocations": [15.0, 15.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 493 · line 6 · [1431, 1473)

> Together, We Can Make A Significant Impact

- Source: `raw_jd.lines[6]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 8, "text": "Be Part of Our Success", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Our Mission Software & Services business provides leading-edge mission critical command, control, and communications (C3) systems with secured IT infrastructure and managed services. We support our client’s innovation journey through design thinking, analytics, and AI-enabled decision support with our full suite of cloud computing solutions. We provide intelligent, actionable insights and sustainable solutions to our valued partners in diverse industries including defence, government, and commercial sectors.".
- Immediately following line: "You will be part of a project team to deliver project objectives based on your role trained. You will work closely with project manager, technical lead and architect as part of the project delivery.".
- Native spans: [{"line": 6, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ORGANISATION_CONTEXT**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [17, 17], "allocations": [15.0, 15.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 551 · line 1 · [0, 17)

> Software Engineer

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 3, "text": "Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "TeleRadio is a developer of vehicle security solutions, and we are seeking a dynamic software engineer with a strong will and a keen desire to take on challenges. This position is suitable for candidates with a strong interest and capability in image processing, software architecture, algorithm design, and AI implementation. Join our team to offer services and support to our clients in protecting people and infrastructure against security threats.".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **TITLE**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **NON_REQUIREMENT_CONTEXT**; short_unheaded_role_title.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": true}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [13, 13], "allocations": [13.0, 13.0]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 556 · line 1 · [0, 43)

> Position: Software Engineer, Backend (.NET)

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "Working Location: Bras Basah Road".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; anchored_posting_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 556 · line 2 · [44, 77)

> Working Location: Bras Basah Road

- Source: `raw_jd.lines[2]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Position: Software Engineer, Backend (.NET)".
- Immediately following line: "Working Hours: 8am to 5pm/8.30am to 5.30pm/9am to 6pm/930am to 630pm (flexi)".
- Native spans: [{"line": 2, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; anchored_posting_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 556 · line 5 · [185, 212)

> Salary Range: $3500 - $4000

- Source: `raw_jd.lines[5]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Working Days: Monday - Friday".
- Immediately following line: "Job Introduction".
- Native spans: [{"line": 5, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **ADMINISTRATIVE_METADATA**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **ADMINISTRATIVE_METADATA**; anchored_posting_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Resolved only by the reported bounded rule; classification does not assert candidate evidence.

## Job 556 · line 6 · [213, 229)

> Job Introduction

- Source: `raw_jd.lines[6]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Salary Range: $3500 - $4000".
- Immediately following line: "We are looking for a Software Engineer, Backend (.NET) to join our Engineering team. In this role, you will write and maintain code, build APIs, work on bug fixes, and monitor the technical performance of our internal systems, primarily using C#, .NET (MVC & Core) and SQL Server.".
- Native spans: [{"line": 6, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **STRUCTURAL_ROLE_INTRODUCER**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 8 · [511, 551)

> KEY ROLE(S), RESPONSIBILITIES AND DUTIES

- Source: `raw_jd.lines[8]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "We are looking for a Software Engineer, Backend (.NET) to join our Engineering team. In this role, you will write and maintain code, build APIs, work on bug fixes, and monitor the technical performance of our internal systems, primarily using C#, .NET (MVC & Core) and SQL Server.".
- Immediately following line: "Attending and contributing to meetings.".
- Native spans: [].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **STRUCTURAL_RESPONSIBILITY_INTRODUCER**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 9 · [552, 591)

> Attending and contributing to meetings.

- Source: `raw_jd.lines[9]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "KEY ROLE(S), RESPONSIBILITIES AND DUTIES".
- Immediately following line: "Learning the codebase and finding ways to improve it.".
- Native spans: [{"line": 9, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 10 · [592, 645)

> Learning the codebase and finding ways to improve it.

- Source: `raw_jd.lines[10]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Attending and contributing to meetings.".
- Immediately following line: "Writing and maintaining code.".
- Native spans: [{"line": 10, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 11 · [646, 675)

> Writing and maintaining code.

- Source: `raw_jd.lines[11]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Learning the codebase and finding ways to improve it.".
- Immediately following line: "Working on bug fixes.".
- Native spans: [{"line": 11, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 12 · [676, 697)

> Working on bug fixes.

- Source: `raw_jd.lines[12]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Writing and maintaining code.".
- Immediately following line: "Monitoring the technical performance of internal systems.".
- Native spans: [{"line": 12, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 13 · [698, 755)

> Monitoring the technical performance of internal systems.

- Source: `raw_jd.lines[13]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Working on bug fixes.".
- Immediately following line: "Responding to requests from the development team.".
- Native spans: [{"line": 13, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 14 · [756, 805)

> Responding to requests from the development team.

- Source: `raw_jd.lines[14]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Monitoring the technical performance of internal systems.".
- Immediately following line: "Gathering information from users about program functionality.".
- Native spans: [{"line": 14, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 15 · [806, 867)

> Gathering information from users about program functionality.

- Source: `raw_jd.lines[15]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Responding to requests from the development team.".
- Immediately following line: "Writing reports, documentation and guides.".
- Native spans: [{"line": 15, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 16 · [868, 910)

> Writing reports, documentation and guides.

- Source: `raw_jd.lines[16]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Gathering information from users about program functionality.".
- Immediately following line: "Conducting development tests.".
- Native spans: [{"line": 16, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 556 · line 17 · [911, 940)

> Conducting development tests.

- Source: `raw_jd.lines[17]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 18, "text": "REQUIREMENTS", "section": "requirements", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: "Writing reports, documentation and guides.".
- Immediately following line: "REQUIREMENTS".
- Native spans: [{"line": 17, "section": "", "heading": "KEY ROLE(S), RESPONSIBILITIES AND DUTIES", "detection": "ambiguous_child_list_boundary"}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **RESPONSIBILITY**; Named actor/action or personal trait in explicit candidate/duty context.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [23, 23], "allocations": [17.000002, 17.000002]}.
- Automation: Unresolved; source is retained and aggregate withheld.

## Job 644 · line 1 · [0, 781)

> As an engineer on the team, you’ll architect and solve complex problems that will directly influence the direction of the digital asset space. There’s a wide range of problems to solve at Gemini – from properly securing millions of dollars worth of customer funds, to developing innovative new blockchain products, to shaving microseconds off our API response times. We have a strong culture of code reviews, and a focus on security, with the end goal of writing and shipping high-quality code by getting things right the first time. We want to continue building the best product we can as we scale and grow our business. If you get excited about solving technical challenges that directly impact our customers, clients, and the rest of the Gemini team, we’d love to hear from you.

- Source: `raw_jd.lines[1]`; v1.22 ambiguity: **True**.
- Preceding section: null.
- Following section: {"line": 2, "text": "Responsibilities:", "section": "responsibilities", "classification": "STRUCTURAL_HEADING"}.
- Immediately preceding line: null.
- Immediately following line: "Responsibilities:".
- Native spans: [{"line": 1, "section": "", "heading": "", "detection": ""}].
- v1.22: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Analyst judgment: **MIXED_ROLE_AND_RECRUITING_PROSE**; Original subject/section context establishes posting information, organisation narrative, title or structural wording; mixed role/recruiting prose remains unresolved as a unit.
- v1.23: **AMBIGUOUS_CONTENT**; no_independent_obligation_or_administrative_field.
- Score-bearing rows (ID, original parent, importance and allocation): {"v17": [], "v20": [], "v22": [], "v23": []}.
- Packet score availability: {"v17": true, "v20": true, "v22": false, "v23": false}.
- v1.22 → v1.23 packet row/allocation change: {"counts": [15, 15], "allocations": [15.0, 15.0]}.
- Automation: Unresolved; source is retained and aggregate withheld.
