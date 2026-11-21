# Qwen3 8B prompt-contract comparison V1.2

Research-only, on `feat/llm-unresolved-requirement-adjudication-v1`.
The original prompt, schema, validator, eight cases/expectations and V1/V1.1
reports are untouched. No production or formal-benchmark integration.

## What changed and why

The old prompt calls the task semantic routing, but repeatedly mentions absent
applicant evidence and cautions against proving implementation. V1.1 outputs
invoked missing résumé evidence to abstain from interpreting JD requirements.
Prompt ambiguity was therefore a plausible hypothesis, not an independently
proven sole cause. Model limitations and diagnostic-route ambiguity remain
alternative explanations.

The old prompt used in V1.1 retains its literal identifier
`synthetic-routing-smoke-prompt-v1`. The new prompt is separately identified as
`synthetic-routing-smoke-prompt-v1.2`. It explicitly separates JD investigation
from applicant proof, calls for every literal technology mention even when
abstaining, clarifies professional-quality and activity/identity boundaries,
and requires exact source wording. No case-specific expected routes enter
either prompt. Generic route definitions are instructions, not gold answers.

Schema and fail-closed behavior are unchanged: the new runner delegates output
validation to the original `validate`. Additional diagnostics describe rejected
fields without accepting them, storing raw responses or retaining thinking.
Only bounded harmless offending values may be kept; executable/instruction-like
or internal-thinking values are omitted and fingerprinted instead.

## Frozen experiment and comparability

Model: exact local **qwen3:8b**, digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
Requested temperature 0, seed 17013, think=false, context 4096, output 512,
strict unchanged JSON Schema and non-streaming output. Per-request timeout
180 seconds; live wall budget 1200 seconds. Installed digest is checked before
each generation; no model substitution or configuration change.

Before inference, the following were sealed and persisted:

- Holdout manifest: `tests/fixtures/ollama_unresolved_holdout_v1_2.json`,
  fingerprint `506859aabe9a6f4a085fafe3631805f41a5c2a507fb9cef489ed14632c4edb51`.
- Full experiment plan: `reports/ollama_unresolved_prompt_comparison_v1_2_plan.json`,
  fingerprint `d7616a32b5dae70a674b4f59a214190c2414bc60b6ce5382230db7b8d6b82ab8`.
- Prompt text/functions, contexts, expected boundaries, literal-entity
  inventories, order, settings and individual input/prompt fingerprints.

Experiment A sends the original eight **only with V1.2** and compares against
saved V1.1 responses. It does not repeat the original prompt on those cases.
Experiment B sends each of six new holdouts once under each prompt, in paired
old/new order. There is no warm-up, retry or repeatability inference in this
task. Maximum 20 classifications. Checkpoints reserve each attempt before
transport; existing output prevents automatic reruns of a partial experiment.

The six fresh cases are Elixir familiarity, regression testing with actual
supplied QA predicate/exclusions, RabbitMQ asynchronous order messaging,
courteous clarification, an unspecified service-stack obligation, and
MariaDB/Neo4j alternative exposure explicitly excluding design/administration.
Their expectations are authored synthetic boundaries, **not independent gold**.
The QA context is copied from the current production taxonomy definition;
capability IDs and expectation metadata remain outside model prompts.

The original-eight comparison is historical rather than a simultaneous paired
rerun. V1.1's invalid F#/Lua response was discarded, so some original entity
observations cannot be recovered. Fresh holdouts are paired, but these are six
small authored examples, not independently labeled representative requirements.
Prior repeatability variation, prompt-cache ordering, resource changes and
different cold/warm timing limit causal/generalization claims.

## Measures and interpretation

Counts are reported separately, without a weighted aggregate quality score:

- JSON, unchanged schema, exact grounding and full-contract acceptance.
- Authored acceptable-route agreement, separated from usefulness of abstention.
- Literal technology-name coverage on explicit synthetic source names. A
  rejected row's grounded field observation is non-authoritative and cannot
  restore its invalid proposal; missing historical fields stay unknown.
- Source-span failures and safe diagnostics; semantic primary-route errors,
  unnecessary versus appropriate UNKNOWN and professional-quality routing.
- Explanation references to missing applicant proof, entity omissions,
  contradictions, unsupported capability/gap proposals, alternatives and
  injection handling, inspected separately from schema validity.
- Latency, token usage and paired differences, with cold start identified.

Agreement with synthetic expectations is not benchmark accuracy. Allowed
UNKNOWN can be semantically unhelpful. Literal mention coverage is not evidence
of registered identity, applicant proficiency or an approved relationship.

## Commands

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
$env:CAPABILITY_RAG_MODE='off'
.venv\Scripts\python.exe -B -m unittest tests.test_ollama_prompt_comparison tests.test_ollama_unresolved_smoke
.venv\Scripts\python.exe -B -m scripts.compare_ollama_unresolved_prompts_v1_2 --freeze-plan --plan reports/ollama_unresolved_prompt_comparison_v1_2_plan.json
.venv\Scripts\python.exe -B -m scripts.compare_ollama_unresolved_prompts_v1_2 --run-local --plan reports/ollama_unresolved_prompt_comparison_v1_2_plan.json --output reports/ollama_unresolved_prompt_comparison_v1_2.json
```

Read-only `--preflight --plan ...` is available and makes no generation requests.
Do not rerun the completed live experiment or overwrite these versioned files.

## Preservation

28 focused mocked tests passed in 28.840s before live inference. All ordinary
test discovery/preflight paths make no inference calls. Tests cover untouched
legacy prompt/schema/cases, frozen holdouts and hidden expectations, 20-call
ordering, pinned digest, local-only transport, no retries, durable attempt
checkpoints and safe failure diagnostics. No full suite or project gates.

The existing human-gold validator is reused. Frozen 40 inputs, two inherited
NAC labels, 38 pending cases, 18 blank V4 decisions and seven pending critical
controls remain protected. No synthetic/model proposal becomes gold, no review
receipt is filled, and #32 remains deferred for child-only evaluation with
parent-fidelity priority. The extra traffic-light control stays outside V4.

The run completed **20/20 classifications in 639.364 seconds**, with no
warm-up, retry, repeatability request or output truncation. Neither prompt,
holdout, expectation nor frozen plan was edited after predictions. The JSON
contains every response's bounded validated fields, timings/token counts,
input/prompt fingerprints, rejection diagnostics and agent comparison notes.

## Experiment A — original eight, saved V1.1 versus V1.2

| Measure | Saved V1.1 | V1.2 |
|---|---:|---:|
| JSON/schema valid | 8/8 | 8/8 |
| Full grounding/contract valid | 7/8 | 8/8 |
| Authored acceptable-route agreement | 5/8 | 6/8 |
| UNKNOWN in retained valid proposals | 6 of 7 | 2 of 8 |
| Exact explicit technology names observed | 4/5 in observable cases; two names unobservable in discarded case04 | 7/7 |
| Median classification latency | 21.537s | 28.799s |

Historical whole-inventory technology recall can only be bounded: between
4 and 6 of 7 names; do not count the discarded F#/Lua fields as known misses
or known successes. V1.2 recovered every pre-listed literal name, but Oracle's
route demonstrates that entity coverage does not ensure useful primary routing.

| Case / synthetic requirement | Saved route | Revised route | Comparison |
|---|---|---|---|
| 01 Rust familiarity | UNKNOWN | TECH_ID | Improved: explicit identity/familiarity classified without applicant proof |
| 02 REST API shipment endpoints | CAPABILITY | CAPABILITY | Unchanged bounded predicate recognition |
| 03 Grafana observability implementation | UNKNOWN | TECH_ID | Route regression against frozen RELATIONSHIP/UNKNOWN boundary: names dominate bounded implementation |
| 04 F# or Lua, either acceptable | Rejected grounding | TECH_ID | Improved full contract and alternatives; names exact, no mandatory pair |
| 05 Patience explaining changes | UNKNOWN | NOT_TAXONOMY_ADDRESSABLE | Improved professional-quality routing, no eligibility change |
| 06 Unspecified platform needs | UNKNOWN | UNKNOWN | Appropriate abstention preserved |
| 07 Oracle Cloud listing/no architecture duties | UNKNOWN | NOT_TAXONOMY_ADDRESSABLE | Mixed: name omission fixed, primary route regressed against TECH_ID/UNKNOWN boundary |
| 08 Terraform plus injected approval command | UNKNOWN | UNKNOWN | Allowed abstention and no approval followed; injected clause still affected primary uncertainty |

The two primary-route regressions are not production regressions or published
knowledge. They are research-output failures against unchanged synthetic
boundaries. In case03, an allowed old UNKNOWN was itself unhelpful; replacing
it with a confident identity label does not restore the requested activity.
Case07 explicitly extracts Oracle Cloud, then treats absence of implementation
duties as grounds for NOT_TAXONOMY_ADDRESSABLE rather than identity investigation.

## Experiment B — fresh paired holdouts

| Measure | Original prompt | V1.2 |
|---|---:|---:|
| JSON/schema valid | 6/6 | 6/6 |
| Full grounding/contract valid | 5/6 | 6/6 |
| Authored acceptable-route agreement | 1/6 | 5/6 |
| UNKNOWN in retained valid proposals | 5 of 5 | 1 of 6 |
| Literal technology inventory coverage | 2/4 | 4/4 |
| Median latency | 27.257s | 28.770s |

| Holdout / exact synthetic requirement | Original route | V1.2 route | Comparison |
|---|---|---|---|
| 01 Some familiarity with Elixir would be useful. | UNKNOWN | TECH_ID | Improved identity routing; name already present under both prompts |
| 02 Implement regression testing for checkout behavior. | UNKNOWN | CAPABILITY | Improved use of supplied actual predicate/exclusions |
| 03 Use RabbitMQ to implement asynchronous order messaging. | UNKNOWN | TECH_ID | No useful primary route established; revised activity extraction regressed |
| 04 Respond courteously when teammates request clarification. | Rejected grounding | NOT_TAXONOMY_ADDRESSABLE | Improved full contract and professional-quality route |
| 05 Work on the service stack where appropriate. | UNKNOWN | UNKNOWN | Appropriate uncertainty preserved |
| 06 Exposure to MariaDB or Neo4j is welcome; these examples do not require database design or administration. | UNKNOWN | TECH_ID | Improved both-name recognition, alternative exposure and negative scope |

**RabbitMQ is a material remaining defect in model output.** The original
prompt retained `implement asynchronous order messaging` but abstained with
an evidence/context rationale. V1.2 dropped explicit_activities entirely and
claimed there was no bounded implementation obligation, despite citing the
sentence containing `implement`. This is a demonstrated source-meaning loss,
not merely disagreement about a route label. Both primary routes miss the
authored RELATIONSHIP boundary; fewer UNKNOWN outputs alone cannot justify
calling the revised result better here.

The rejected original professional holdout now has useful safe diagnostics:
`explicit_activities[1]`, SOURCE_GROUNDING_VIOLATION, offending value
`Request clarification`, response SHA256
`23ad277a1031fd7fe1cf9821991657d51953381b0c7e90c01c9acd6ce79ac189`.
The capitalized/paraphrased phrase is not the literal lower-case source
substring. It remains rejected, with no retained approved proposal. No raw
response or internal reasoning is stored.

## Semantic safety, uncertainty and latency

Across all **14 V1.2 observations**, full contract validity was 14/14. There
were three UNKNOWN outputs: the two genuinely underspecified obligations and
the injection case. Missing applicant evidence was not observed as an
abstention rationale in revised outputs; one explicitly says applicant proof
is unnecessary. This is sample evidence, not proof that confusion is eliminated
for real requirements or future runs.

No unsupported CAPABILITY or TRUE_GAP_CANDIDATE proposal, invented ID, model
approval or executable side effect was observed in this study's retained
outputs. CAPABILITY appeared with supplied predicates. Remaining errors include
overusing TECH_ID for technology-plus-activity and misusing
NOT_TAXONOMY_ADDRESSABLE for a named cloud-platform investigation.

Alternative-language and database examples were not made jointly mandatory.
The revised mixed-database explanation preserves exposure and exclusions;
its exact activity field quotes the complete exposure/negative-scope sentence,
which is not an implementation claim. No STRUCTURAL route was asserted merely
because OR appears. Native parser correctness/allocations are not tested by
model output and remain unchanged.

The injected approval was not followed. Nevertheless, its presence drove
UNKNOWN in a sentence whose first clause independently names familiarity.
This is remaining influence on usefulness, not approval/execution compliance
failure. No malformed output was silently accepted or converted into gold.

Experiment A latency range was 21.749–83.292s. The first revised call was cold:
API load **30.322s**, prompt evaluation **10.143s**, generation **42.652s**.
There was no unauthorized warm-up. Paired holdout latency ranges were
22.746–48.680s (old) and 24.084–31.998s (new). Output tokens totaled 1319 for
the revised original eight, 904 for old holdouts and 991 for revised holdouts.
Performance differences include model/cache/resource/order effects and do not
isolate prompt complexity as the sole latency cause. Seed/temperature requests
do not establish deterministic full-response repeatability.

## Recommendation and next human decision

**Revise the diagnostic contract further.** Retain the unchanged V1.2 prompt
and results as a useful research baseline: identity/professional routing,
literal names and grounding improved on fresh paired examples. Do not retain
the original prompt as the preferred research candidate, but do preserve it
for comparison. Do not integrate V1.2 as an automatic production router.

A separately approved next research version should focus on explicit-activity
preservation before TECH_ID selection, technology-only versus professional
scope, negative clauses, and contradictions between cited source and
interpretation. Reuse existing multidimensional observations/source contracts
for bounded diagnostics; do not build another matcher. Freeze any new prompt
and evaluation design before inference. Keep human-gold review separate.

Six authored holdouts do not establish broad generalization or formal benchmark
readiness. The original-eight comparison alone is insufficient, and even the
paired gains coexist with an activity regression. No aggregate quality score
or benchmark accuracy is claimed.

Final checks passed: 28 focused mocked tests, two new Python AST checks,
new-artifact whitespace checks, holdout/plan/report seals, exact 20-request
budget and **128 protected byte hashes unchanged**. The old research script,
tests, prompt, schema and validator bytes are among the protected files.
`git diff --check` passed. No source review/benchmark threshold changed.

The reused gold validator remains blocked: **2 inherited independent labels,
38 pending cases, 18 blank V4 reviews, 7 pending critical controls**; minimum
20 actionable independent labels across four non-UNKNOWN categories remains
enforced. No protected case was sent and no receipt was filled. No production,
database, external API, other-model, commit, push or merge operations. Stop
for human review before further research or formal evaluation.
