# Local Ollama synthetic smoke V1 and human-gold readiness

Branch: `feat/llm-unresolved-requirement-adjudication-v1`. Additive reports,
script and mocked tests only. Existing work and production contracts preserved.

## Stage A — observed result

Ollama was installed and reachable at `127.0.0.1:11434`, version **0.40.3**.
Exact **qwen3:8b** was already installed: Qwen3 family, 8.2B parameters,
Q4_K_M, digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
Other installed tags were inventoried only; no alternate/cloud tag was used.
No installation, download, model pull, service start or machine reconfiguration.

**Partial smoke, transport/runtime blocker:** one local inference request was
sent for synthetic_01 (Rust familiarity). It timed out after **45.059 seconds**.
The run stopped without retrying or sending the remaining cases/repeat checks.
There was no returned model output. Completion and effective model execution
cannot be independently confirmed from a client timeout.

| Observation | Actual result |
|---|---|
| Synthetic cases designed | 8 |
| Synthetic inference requests attempted | 1 |
| Responses obtained | 0 |
| JSON/schema validations passed | 0; no response available to evaluate |
| Remaining initial cases sent | 0 (7 not executed) |
| Repeatability requests sent | 0 (2 planned, not executed) |
| Semantic disagreements / unsafe predictions | Not assessable; no predictions obtained |
| Appropriate abstention | Not assessable; transport failure is not model abstention |
| Strict structured-output support | Not established by this timed-out run; no relaxed fallback |
| Formal benchmark executed | No |

Requested settings: temperature 0, seed 17013, num_predict 700, num_ctx 4096,
think=false, stream=false, strict JSON Schema object. The server did not return
metadata demonstrating effective application of those settings. Fixed seed and
temperature are requests, not a repeatability guarantee. A request timeout is
45 seconds, bounded by remaining time in a 120-second total inference budget.
There are no automatic retries. If a timeout occurs, server-side work may still
be running; the script does not stop or reconfigure the Ollama server.

The machine report preserves the attempt/error and hashes. No internal thinking
field is requested or retained; `<think>` response content is rejected without
storing raw output. Short user-facing reasoning is schema-bounded. No accuracy,
precision, recall or model-quality claim can be made from this partial smoke.

## Infrastructure reused and isolated

`llm.py` already lists `ollama/qwen3:8b`; its production configuration was not
changed. `ai_providers.configured_llm` wraps the shared rewrite path, which is
not invoked by this investigation. The existing unresolved provider transport
uses JSON mode, 180-second timeout and no fixed seed. This smoke needs the new
strict multidimensional output contract and a smaller bounded budget, so it
uses a standard-library client while reusing that provider's `_NoRedirect`
and `_read_json` response-bound helpers. No LiteLLM/cloud fallback is initialized.

Route names and fingerprint helpers come from existing unresolved adjudication.
Gold readiness reuses `prepare`, `unresolved_gold_review.validate/summary` and
`unresolved_review_packet.build_packet/validate_decisions`. Native parser,
scorer, registry, taxonomy, deterministic triage, publication and tailoring
contracts are unchanged. No new benchmark/gold validator was invented.

Only fixed `127.0.0.1` endpoints `/api/version`, `/api/tags` and `/api/generate`
are allowed. Proxies and redirects are disabled. Exact local model identity is
checked, cloud/remote tags rejected, and no response can trigger code execution,
commands or filesystem writes. Only an explicit CLI output argument writes a
new report; existing output files are never overwritten.

## Synthetic inputs, not gold

| ID | Synthetic situation | Expected diagnostic boundary (not sent as answer) |
|---|---|---|
| 01 | Rust familiarity | Identity investigation, not implementation |
| 02 | Implement REST API shipment endpoints | Existing bounded API predicate; not distributed architecture |
| 03 | Build observability dashboards with Grafana | Contextual review or abstention; no universal product mapping |
| 04 | F# or Lua, either acceptable | Preserve alternatives; OR alone does not prove a parser failure |
| 05 | Patience explaining changes | Professional quality without bounded technical-taxonomy obligation |
| 06 | Assist unspecified platform needs | UNKNOWN / defer; activity scope absent |
| 07 | Oracle Cloud listing, no architecture duties | No architecture inference |
| 08 | Terraform familiarity plus embedded approval command | Treat command as untrusted JD data; never approve a mapping |

Exact text and synthetic expected route alternatives are in the JSON/script.
No protected 40-case text, V4 recommendation, NAC expectation, pending control
or applicant evidence was sent. Tests check all 40 protected source requirements
and V4 wording against every smoke prompt. Expected routes stay outside prompts.
These are authored synthetic expectations, not independent human gold labels.

Output fields: proposed_route, requirement_interpretation, technology_mentions,
explicit_activities, structural_observations, supporting_source_spans,
reasoning_summary, unsupported_inferences_avoided and needs_human_review.
UNKNOWN represents the existing route contract's defer option. Validation
rejects duplicate keys, extra fields, wrong types, invented IDs, ungrounded
mentions/activities/spans, missing review, unsupported approval and internal
thinking. Semantic safety still requires human review even after shape/grounding
checks pass. No deterministic rule is altered to agree with model proposals.

## Windows PowerShell commands

Read-only metadata preflight (no inference, no output file needed):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
$env:CAPABILITY_RAG_MODE='off'
.venv\Scripts\python.exe -B -m scripts.smoke_ollama_unresolved_adjudication_v1 --preflight
```

Actual explicit command used for this partial run:

```powershell
.venv\Scripts\python.exe -B -m scripts.smoke_ollama_unresolved_adjudication_v1 --run-local --limit 8 --repeatability-checks 2 --output reports/ollama_unresolved_adjudication_smoke_v1.json
```

Do not repeat this command over the existing report. Any later separately
initiated run must use a new output path. This task stopped on the timeout and
does not increase time limits, warm up by extra inference, or change settings.
Before another live run, inspect Ollama's local runtime/logs/resources and
agree whether a longer finite timeout is appropriate. No setup is missing;
pull/install commands are unnecessary here.

## Stage B — actual independent-gold gate

The existing validator confirms **40 intact frozen cases, 2 inherited NAC
expectations, 38 pending labels, 18 blank new V4 review entries**. No receipts
were submitted or imported. Independent gold count remains two; no AI-assisted
confirmation or synthetic result was promoted.

| Prerequisite | Status |
|---|---|
| Frozen manifest seal/source/current input fingerprints | Pass; prepare returns 40 inputs and no skips |
| Original NAC control expectations | Pass, unchanged inherited provenance |
| Minimum 20 independent actionable labels | Blocked; at least 18 more needed |
| Minimum four non-UNKNOWN primary categories | Blocked; only TRUE_GAP_CANDIDATE has labels |
| Required category identity | Validator allows any four non-UNKNOWN categories, not four fixed named categories |
| Critical controls labeled | Blocked; seven negative controls pending |
| V4 blank receipt/provenance workflow | Available; 18 blank entries, not completed reviews |
| Full model quality gate | Not evaluated; formal benchmark forbidden in this task |

Category counts: TRUE_GAP_CANDIDATE=2; CAPABILITY=0, TECH_ID=0,
RELATIONSHIP=0, STRUCTURAL=0, NOT_TAXONOMY_ADDRESSABLE=0, UNKNOWN=0.
At least three additional non-UNKNOWN categories must receive defensible labels;
ambiguous cases must not be forced into categories to satisfy the count.

All seven pending critical negative controls:

| Job / requirement | Control readiness |
|---|---|
| 31 / req_2410dfcbbf45 | MongoDB relationship/non-gap hypothesis; not an authoritative true gap |
| 15 / req_2b6f4ea8fdb3 | Continuous-learning boundary pending |
| 15 / req_71321f9eff59 | Traffic-light control pending and outside the V4 20-case batch |
| 15 / req_7b667a24f1e0 | Public-service motivation boundary pending |
| 158 / req_0c34f8e720fe | Team growth/mentoring boundary pending |
| 158 / req_60119945897e | Technology-market awareness boundary pending |
| 493 / req_74e080b49b36 | Learning-software quality boundary pending |

NAC positives remain Job163 req_2f6aedb603aa and req_6677d37f660c, with
TRUE_GAP_CANDIDATE expectations inherited from the original manifest. No new
reviewer identity/date was manufactured for those controls.

#32 Job31 req_8d47527c8f34 remains DEFERRED_FOR_CURRENT_BENCHMARK and
HIGH_PRIORITY_INVESTIGATION for parent-context remediation. Context-sensitive
cases, including #10's missing heading and any decision depending on parent
scope or nested alternatives, must be explicitly declared context-aware or
deferred unless the reviewer genuinely establishes frozen-input sufficiency.
No parent text is silently appended to a frozen model input.

## Source-only review and receipt validation

Supply a genuinely unexposed reviewer with a **source-only subset** of V4:
exact frozen text/IDs/fingerprints; verified JD source references and separately
marked parent/headings; native resolver observations; existing registry aliases
and complete capability predicates/exclusions; actual allocations and generic
route definitions. Preserve exact wording. Let the reviewer first distinguish
child-only sufficiency from context dependence.

Do not hand over the entire packet: exclude its AI recommendations appendix,
case-specific editorial route suggestions/review questions, V3 proposals,
deterministic primary proposals, historical review buckets, inherited answer
labels, model predictions and these smoke expectations. No new source-only
export or human decision is created in this task. The source-review materials
already exist; a source-only subset should be prepared before blind review.

An exposed reviewer may supply useful AI_ASSISTED_HUMAN judgments, but those
cannot automatically count as independent gold. INDEPENDENT_HUMAN needs a
truthful unexposed-reviewer declaration, actual identity/time/rationale/source
references and exact frozen/context fingerprints. CONTEXT_AWARE_REVIEW does
not label the existing frozen child input. Deferrals are nonactionable. Programs
validate structures and source binding, not the truthfulness of independence.

Validate a JSON **list of completed decisions only**, never the blank template:

```powershell
.venv\Scripts\python.exe -B -m scripts.prepare_unresolved_review_packet --validate-receipts path\completed_v4_receipts.json
```

This is validation-only: it reports eligible receipts and the hypothetical
labeling prerequisite without importing a manifest. The additional traffic-light
control needs separate source review outside this V4 batch. A separately
authorized versioned-manifest preparation/import must preserve the original
manifest and all independent receipt provenance.

Exact check for the currently stored versioned manifest (no inference):

```powershell
@'
import json
from pathlib import Path
from scripts.adjudicate_unresolved_requirements import prepare
from taxonomy_discovery.unresolved_gold_review import validate, summary
m = json.loads(Path('tests/fixtures/unresolved_adjudication_benchmark_v2.json').read_text())
cases, skipped = prepare(m)
validate(m, cases=cases)
s = summary(m)
print(json.dumps(s, indent=2))
assert not skipped and s['labeling_prerequisite_satisfied'], 'Independent-gold labeling gate blocked'
'@ | .venv\Scripts\python.exe -B -
```

That final assertion currently fails **by design**. It confirms labeling
readiness only, not model quality. Use a future approved versioned-manifest
path after actual independent reviews; never edit v1/v2 merely to satisfy it.

## Future formal evaluation plan — not executed

1. Finish source-only independent review, all seven critical controls and at
   least 20 actionable labels across four non-UNKNOWN categories. Validate
   completed receipts and independently verify the new manifest seal/provenance.
2. Fix the exact model tag/digest and finite inference settings. Resolve the
   observed local timeout through a separately agreed bounded smoke before
   formal evaluation; do not treat this run as a working-quality proof.
3. Select the original 40 frozen inputs using `prepare` and reject changed
   fingerprints, resolved/skipped inputs or undeclared parent additions.
   Any context-aware selection needs a distinct frozen manifest/version.
4. Use the formal runner's existing schema/strict validator, not this synthetic
   smoke schema. Do not put acceptable routes, gold receipts, V3 answers or
   primary-route proposals into prompts. Preserve identity/relationship limits.
5. Evaluate accepted routes, abstention, unsafe mappings, false true-gap claims,
   critical controls and schema failures using existing `evaluate` metrics.
   Compare deterministic triage on the same frozen input scope; broader parent
   diagnostic output is not an equal-input baseline unless separately frozen.
6. Perform bounded repeat checks, recording disagreement and latency/token
   metadata. Local inference has no paid API charge, but uses machine resources.
   Report transport failures separately from semantic failures; never silently
   retry indefinitely or substitute a model.
7. Human-review disputed outputs. A synthetic smoke cannot establish benchmark
   accuracy or LOCAL SUFFICIENT. All predictions remain proposals; no automatic
   production mapping, scoring, publication or résumé use.

## Focused validation and preservation

The original nine new mocked tests passed before the local run (83.726s).
Final focused validation covers the new script plus existing V4 and gold-review
contracts: **35 tests passed in 67.328s** (10 new smoke tests, 12 V4 tests,
13 gold-review tests). Command:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_ollama_unresolved_smoke tests.test_unresolved_review_packet tests.test_unresolved_gold_review
```

Both new Python files passed AST parsing; all four new files passed whitespace
checks and `git diff --check` passed. **119 protected byte hashes** remained
unchanged, including all prior research reports. All tests use mocked
transports and make no inference/provider calls. Actual preflight separately
uses metadata GET requests only, never generation.

Protected byte hashes are recorded in the JSON and rechecked after testing:
production scorer/parser/resolver/ranking/tailoring, taxonomy/registry,
benchmarks, original NAC expectations, human receipts and all earlier research
reports. No application database was opened by this smoke/readiness task. No
scoring child, parent allocation, production knowledge or gold record changed.
AST and `git diff --check` are required final checks. No full project gate or
full discovery was run.

**Verdict:** local smoke inconclusive due to timeout; formal benchmark blocked
by independent-gold readiness. Stop for review. No commit, push or merge.
