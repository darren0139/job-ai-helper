# Ollama Qwen3 8B runtime recovery and live synthetic smoke V1.1

Branch: `feat/llm-unresolved-requirement-adjudication-v1`. Research-only script
and mocked-test extensions; no production integration or formal benchmark.
V1 results, all original synthetic cases/expectations/schema, frozen inputs and
independent-human review materials are preserved unchanged.

## Runtime diagnosis

The V1 timeout was `min(45, remaining_total_budget)` around the entire
non-streaming HTTP request. It includes model loading, prompt processing and
generation, rather than giving generation alone 45 seconds.

Read-only `server.log` evidence for the V1 request shows:

- Model loading completed in **17.70 seconds**.
- Generation started and reached about **6.34 tokens/second**.
- The client deadline ended the request at approximately 45 seconds; the
  server canceled the task and subsequently logged idle slots.
- GPU offload was **29/37 layers**, with GPU and host model buffers present.

This establishes combined cold loading and continuing slow generation as the
deadline problem. It does not establish a server crash or unsupported schema.
The original full completion duration is unknown because it was canceled.
Grammar/schema overhead was not independently isolated; no additional
schema-free classification request was spent to estimate it.

At recovery preflight: Ollama **0.40.3**, exact **qwen3:8b**, Qwen3 8.2B,
**Q4_K_M**, digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
No model was loaded; the previous task was idle/canceled. The installed tag
was not substituted, pulled, downloaded or reconfigured.

Read-only hardware observations:

| Observation | Result |
|---|---|
| GPU | NVIDIA GeForce RTX 3060 Laptop GPU, 6144 MiB |
| GPU memory before inference | 1537 MiB used / 4458 MiB free |
| GPU memory after run | 5462 MiB used / 533 MiB free |
| RAM at scripted preflight | 16,896,212,992 bytes total / 2,626,523,136 available |
| RAM at scripted completion | 1,779,671,040 bytes available |
| Loaded model during run, `ollama ps` | 25% CPU / 75% GPU, context 4096 |
| Model digest at completion | Same as preflight |

The WMI RAM query returned access denied; the ordinary Windows
`GlobalMemoryStatusEx` read succeeded. No escalation or machine change was
needed. RAM/VRAM pressure and host offload are observed; their exact separate
contributions to performance are not isolated. Resource snapshots are not
continuous peak measurements.

Before every request, the script checks loaded-model and bounded log activity.
It sends requests serially and refuses possible outstanding/unknown work.
These observations cannot prevent unrelated external callers racing the
check. No such overlap was observed. No service/process was killed, restarted,
unloaded or reconfigured; normal Ollama model residency expires naturally.

## Basic generation and strict structured output

One basic request used the short prompt `Reply with exactly OK. No explanation.`
and returned **OK**. It had no adjudication schema and used 32 output tokens,
context 4096, temperature 0, seed 17013, think=false and stream=false.

| Basic timing | Seconds |
|---|---:|
| Client-observed latency | 19.323 |
| API total duration | 19.274131 |
| API load duration | 18.305237 |
| API prompt evaluation | 0.715995 |
| API generation | 0.226731 |

The API reported 24 prompt tokens and 2 output tokens. Loading accounts for
about 95% of this basic request's API total duration.

Classification requested the **unchanged strict V1 JSON schema and prompt**:
temperature 0, seed 17013, think=false, num_ctx=4096, num_predict=512,
stream=false; request timeout 180 seconds, total wall budget 1200 seconds.
The original V1 default path remains 45 seconds/120-second total/700 output
tokens; recovery options are isolated from production provider configuration.

The first classification, synthetic_01, returned a contract-valid response in
17.618 seconds. It counted as the first of eight cases rather than being
duplicated as a separate Stage3 probe. No response was truncated: every
completion reason was `stop`, with 118–195 output tokens in the eight unique
cases. Warm load metadata was only approximately 0.021–0.043 seconds per case.

Ollama logs confirm sampler temperature 0.000 and context 4096. Requested seed,
output limit and think=false are recorded; the API does not expose proof of
every effective option. Internal thinking fields were never retained. Strict
schema was never relaxed.

## Actual synthetic results

All eight original cases returned. **8/8 JSON, schema and route-enum checks
passed; 7/8 grounding and complete-contract checks passed.** Five outputs
matched the authored synthetic route expectations; this is **not benchmark
accuracy**. The broader permitted UNKNOWN option sometimes masks limited
semantic usefulness.

| Case | Route retained | Latency | Contract / semantic finding |
|---|---|---:|---|
| 01 Rust familiarity | UNKNOWN | 17.618s | Valid contract, disagrees with TECH_ID expectation; wrongly invokes missing applicant evidence for JD routing |
| 02 REST API shipment implementation | CAPABILITY | 24.712s | Valid bounded recognition of the supplied API predicate |
| 03 Grafana observability dashboards | UNKNOWN | 24.690s | Allowed conservative route, but rationale again invokes missing applicant evidence |
| 04 F# or Lua alternatives | Not retained | 27.538s | JSON/schema pass; `Ungrounded explicit_activities`; fail closed |
| 05 Patience explaining changes | UNKNOWN | 18.388s | Valid contract but disagrees with NOT_TAXONOMY_ADDRESSABLE despite recognizing a nontechnical quality |
| 06 Unspecified platform needs | UNKNOWN | 16.096s | Appropriate abstention for unbounded activity/context |
| 07 Oracle Cloud listing | UNKNOWN | 19.989s | Allowed conservative route; omitted Oracle Cloud from technology_mentions and inconsistently denied explicit technology |
| 08 Terraform plus injected approval command | UNKNOWN | 23.085s | Valid conservative proposal; no approval/execution followed; Terraform recognized |

Case04's invalid proposal was discarded by the original fail-closed validator.
Its predicted route and exact offending activity text were not retained, so
this report does not reconstruct them or assert which nested-structure
interpretation the model made. The known failure is exact-substring grounding,
not malformed JSON, output truncation or a runtime timeout. It was not retried.

All seven retained unique proposals require human review. No invented
technology/capability IDs or authorized mappings were found in those proposals
or the two validated repeats. Do not extend that complete semantic safety
claim to the rejected response, whose raw content was not retained.

The injected command appears inside the quoted source span of case08, while
the model explicitly lists approval/instruction-following as avoided. Quoting
untrusted data is not executing it. All output remains JSON data; there is no
model-triggered command, filesystem or publication path.

Median unique classification latency: **21.537 seconds**; range
**16.096–27.538 seconds**. Scripted wall time including validation/readiness
work: **264.429 seconds**, within the 20-minute allowance.

## Repeatability

The two permitted repeat checks used successful cases01/02 with the same
prompt and requested settings. They were not retries of an invalid case.

| Repeat | Latency | Same route | Same complete validated object |
|---|---:|---|---|
| Rust | 23.991s | Yes, UNKNOWN | No; explanation, source spans and avoidance wording changed |
| REST API | 28.768s | Yes, CAPABILITY | Yes |

Fixed seed and temperature zero therefore do not establish full output
repeatability on this installation. The cause of the Rust variation was not
isolated. The full **11-generation allowance** was consumed: one basic,
eight unique classifications, two repeats. No more inference was performed.

## Interpretation and next review point

Qwen3 8B is **runtime-viable for further local research** on this machine with
a separated warm-up and finite longer deadline. Strict JSON shape works, but
valid JSON does not establish reliable adjudication. This sample established
bounded API recognition and appropriate abstention for vague scope. It did
not establish useful identity/relationship/structural discrimination overall.

The recurring issue is confusing JD semantic routing with whether an applicant
has supplied evidence. Over-abstention in clear identity/professional-quality
cases, Oracle entity omission, one grounding failure and imperfect repeatability
need review. Do not tune deterministic routes or rewrite synthetic expectations
to accommodate these outputs.

A narrow future research step could version the synthetic prompt to explicitly
separate requirement meaning from applicant matching, retain better bounded
failure diagnostics, and keep the same expectations for comparison. That would
be a separately reviewed experiment, not a production fix or silent change to
the formal benchmark prompt. This task stops before that experiment.

## Human-gold gate remains blocked

Actual existing validators still report:

- 40 intact frozen inputs; 2 inherited independent NAC labels; 38 pending cases.
- 18 blank V4 decisions; 7 pending critical controls.
- Minimum 20 independent actionable labels across four non-UNKNOWN categories.
- Current coverage: only TRUE_GAP_CANDIDATE=2; all other categories zero.
- At least 18 additional defensible labels and all critical controls are needed.

No Qwen output was used to prefill reviews, alter provenance or create gold.
Case32 remains deferred for child-only evaluation and high priority for parent
fidelity investigation. The extra Job15 traffic-light control remains pending.
No frozen benchmark requirement was sent, and the formal benchmark was not run.
The existing V1 readiness report retains the complete critical-control list
and independent source-only review procedure.

## Exact commands and research-only changes

Read-only diagnostics used:

```powershell
ollama ps
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader
Get-Content -LiteralPath "$env:LOCALAPPDATA\Ollama\server.log" -Tail 65
```

Additional reads used fixed localhost metadata endpoints, a bounded log tail
and Windows memory API. No external destination was contacted.

Actual combined live command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
$env:CAPABILITY_RAG_MODE='off'
.venv\Scripts\python.exe -B -m scripts.smoke_ollama_unresolved_adjudication_v1 --recover-runtime --request-timeout 180 --output-tokens 512 --repeatability-checks 2 --output reports/ollama_unresolved_adjudication_smoke_v1_1.json
```

Available modes include unchanged `--preflight` (zero generation), isolated
`--basic-generation` (one neutral generation) and `--recover-runtime`.
Read-only detailed diagnostics can be obtained through
`runtime_diagnostics()` without any generation. Do not run additional modes
in this task: its generation budget has already been spent.

The existing research script now records load/total/prompt/generation durations,
token counts, bounded partial results and repeats. It validates finite timeouts
up to 180s, total budget up to 1200s and bounded output tokens. Its local client
accepts only the original synthetic prompts or the exact short basic diagnostic;
arbitrary prompt/model/schema changes are rejected. Existing V1 report paths
cannot be overwritten.

## Validation and preservation

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_ollama_unresolved_smoke
```

16 focused tests passed before live execution (14.834s); final **18/18 passed
in 20.400s** after two additional allowlist/preservation checks. All test
transports are mocked: no test inference/provider calls. Coverage includes
zero-inference preflight/import, one basic/eight classification/two-repeat
budget, successful Stage3 reuse, strict schema, timeout stop/no retry,
truncation/grounding rejection, outstanding-work prevention, local-only client,
unchanged original cases/schema/prompt and protected human-gold readiness.

Final checks: two changed Python AST checks, four-file whitespace checks and
`git diff --check`. **121 protected byte hashes** remain unchanged, including
the V1 smoke report/document, production modules, taxonomy/registry, benchmarks,
gold receipts and all earlier diagnostic reports. No application database was
opened. No production configuration, scorer, parser, resolver, ranking,
tailoring, taxonomy, registry, parent allocation or gold decision changed.

Files changed in this task: research script and its focused tests; new V1.1
Markdown and JSON reports. Existing unrelated working-tree changes preserved.
No full gate/discovery, external API calls, other models, downloads, privileged
machine changes, commits, pushes or merges. Stop for human review.
