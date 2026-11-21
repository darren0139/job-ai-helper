# Unresolved requirement adjudication V1

This is a report-only semantic review layer. `UNRESOLVED != TAXONOMY GAP`.
It never supplies production resolver answers, applicant evidence, scoring,
approval, publication, database writes or automatic research.

## Existing ownership and reuse

| Pipeline responsibility | Existing file/function | Reuse |
|---|---|---|
| Canonical requirements | analysis_stability/stable_evidence_scoring.py::canonicalise_requirements | Preserve the frozen native IDs; do not recanonicalize a second corpus |
| Scope/decomposition | tailoring/requirement_scope.py::technology_identity_scope; tailoring/phase6d6_structured_matching.py::technology_requirement_structure | Native diagnostics; original scope/provenance retained for resolution |
| Production resolution | tailoring/production_requirement_resolver.py::resolve_requirement_with_production_knowledge | Always called first, with no applicant evidence; resolved rows skip models |
| Taxonomy | tailoring/capability_taxonomy.py::get_default_taxonomy / classify_requirement_diagnostics | Existing matcher and bounded candidate IDs/requirement terms |
| Registry | taxonomy_discovery/technology_registry.py::get_default_registry / resolve_requirement_text | Existing identity and governed mapping contract; tiny alias-matched candidate set |
| Contextual relationships | taxonomy_discovery/contextual_relationship_validation.py::context / validate | Existing governed destination for proposals; never activate temporary/global mappings here |
| Addressability | taxonomy_discovery/taxonomy_addressability.py::project / classify | Existing reviewed occurrence IDs, buckets, blocker provenance; buckets are not exact gold routes |
| Gap reports | taxonomy_discovery/corpus_gap_resolution.py::audit_corpus_resolution | Existing source receipts and accounting; no alternate unresolved corpus |
| Maintenance | taxonomy_discovery/maintenance_service.py::production_identity / build_research_tranche | Existing versions/fingerprints; human-selected handoff only |
| Readiness / research | taxonomy_discovery/research_readiness.py::audit_candidate; taxonomy_discovery/governed_research.py | Existing future governed workflow; no Tavily call from adjudication |

Authoritative source: `tests/fixtures/confirmed_taxonomy_coverage.json`.
The committed benchmark is only a selection/expectation manifest pointing to
that source: stable job/requirement IDs, source/input fingerprints, review
provenance and acceptable routes. It contains no copied résumé/evidence corpus.

Current source has 276 unresolved occurrences: 2 proven capability gaps, 11
identity/registry dependencies, 9 relationships, 53 structural dependencies,
6 non-addressable and 195 deferred. The two proven occurrences are the Job163
NAC IDs `req_2f6aedb603aa` and `req_6677d37f660c`; model outputs remain candidate
proposals, never new proven gaps. Job31 `req_2410dfcbbf45` is the MongoDB
relationship/non-gap control.

## Frozen representative selection and honest gold labels

40 source occurrences are selected, including NAC, MongoDB, non-addressable,
structural, identity/relationship and ambiguous/unsafe-mapping review cases.
Only the two explicit user-reviewed NAC controls currently have exact
acceptable-route labels (`TRUE_GAP_CANDIDATE`). The source's broad buckets and
lazy addressability outputs do not establish independent exact routes/scopes.
The remaining 38 expectations are deferred with reasons. Do not fill those
labels from model outputs or convert buckets into convenient gold answers.

The local quality gate therefore remains **BENCHMARK INCONCLUSIVE** until human
review supplies at least 20 actionable exact labels spanning four non-UNKNOWN
route categories, resolves the critical controls, and a complete local run is
available. Human review should freeze a new versioned manifest *before* a new
model run. Never overwrite old results or change labels/thresholds post hoc.

This limitation is not a request for cloud spending. Review the local data first.
Synthetic gate fixtures in unit tests prove arithmetic/safety behavior; they
are not gold labels or measurements of Qwen quality on the real corpus.

## Schema and bounded inputs

Schema: `unresolved-adjudication-v1`; prompt: `unresolved-routing-prompt-v1`.
Strict fields, route/scope/reason enums, finite confidence, exact spans, bounded
arrays and candidate-set IDs are enforced. Duplicate keys, malformed JSON,
fabricated spans, invented IDs and invalid schemas normalize to UNKNOWN.
Raw unsafe route claims remain visible to safety metrics even when invalid.

Input is an allowlist: requirement text/ID/importance, native diagnostics and
up to six taxonomy / registry candidates. Frozen receipts do not provide
authoritative nearby JD text, so nearby context is explicitly unavailable.
Full JDs, raw native evidence, profiles, résumé text, secrets and provider
exception bodies are excluded. Sensitive requirement text requires review.
Model notes and proposals are untrusted review material, not production truth.

Gate: JSON >=98%, schema >=98%, actionable agreement >=90% with all independently
gold-labeled expected rows in the denominator, zero false-positive true-gap and
unsafe identity-to-capability claims, and complete/safe critical controls.
Deferred UNKNOWN is separately measured; it never inflates actionable success.
All-UNKNOWN cannot pass. NAC UNKNOWN is inconclusive rather than forced into a gap.

Outputs include exact case/expectation/proposed-route/span rows, missing/UNKNOWN
IDs, confusion, scope/entity metrics where gold exists, latency, token usage
where reported, input/version fingerprints and JSON/Markdown summaries.

## Windows CMD: zero-call preview

```cmd
set PYTHONDONTWRITEBYTECODE=1
set LITELLM_LOCAL_MODEL_COST_MAP=True
.\.venv\Scripts\python.exe -B -m scripts.adjudicate_unresolved_requirements --dry-run --limit 40 --output reports\unresolved_preview.json
```

Dry-run is also the default without `--execute`; an API key does not enable
any provider. Filters: `--job-id`, `--requirement-id`, `--limit`.

## Windows CMD: human-local Qwen benchmark

```cmd
ollama list
ollama ps
.\.venv\Scripts\python.exe -B -m scripts.adjudicate_unresolved_requirements --provider ollama --model qwen3:8b --execute --limit 40 --output reports\unresolved_qwen.json
```

If absent, the separate install command is `ollama pull qwen3:8b`. Nothing
installs a model automatically. The transport uses fixed localhost, ignores
proxies, rejects redirects, disables thinking, and never falls back to cloud.
CI uses fake transports and needs neither Ollama nor provider credentials.
No live local/cloud inference was performed during implementation.

If a complete, adequately reviewed local run passes, stop with LOCAL SUFFICIENT
and no cloud comparison. A failed adequate run offers optional review; an
inconclusive run prioritizes local labels/context. Neither launches cloud.
An all-corpus run requires a separate invocation, explicit all-reviewed
confirmation and a human-reviewed sufficient representative report.

## Optional cloud: separate user request only

Paid execution is never part of implementation or CI. Only necessary bounded
requirement semantics leave the computer, after privacy review. A completed
local Qwen report with the same frozen inputs/expectations must precede it.

The adapter supports the exact requested `gpt-5.6-luna` and optional separately
selected `gpt-5.4-mini`, never the generic `gpt-5.6` alias. Official references:
[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[output/reasoning tokens](https://developers.openai.com/api/docs/guides/token-counting).

Example price configuration, **not execution-ready**:

```json
{
  "model": "gpt-5.6-luna",
  "input_per_million": "0.20",
  "output_per_million": "1.20",
  "tier": "standard",
  "source": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
  "verified": false,
  "verified_at": null
}
```

Independently verify current standard rates, set `verified` and a timezone-aware
ISO `verified_at`, then save `reports\verified_luna_prices.json`. Verification
expires after 24 hours. Supported conservative rates may be increased, never
silently lowered below reference assumptions. No discounts are assumed.

Human-only zero-call cost preflight:

```cmd
.\.venv\Scripts\python.exe -B -m scripts.adjudicate_unresolved_requirements --provider openai --model gpt-5.6-luna --pricing reports\verified_luna_prices.json --max-cases 40 --max-cost-usd 0.50 --max-output-tokens 1200 --dry-run --output reports\unresolved_cloud_preflight.json
```

Inspect every selected case, exact inputs, price assumptions, token bounds and
worst-case sum. Configure OPENAI_API_KEY through the environment without printing
it. Only after a separate explicit user request and privacy/cost confirmation:

```cmd
.\.venv\Scripts\python.exe -B -m scripts.adjudicate_unresolved_requirements --provider openai --model gpt-5.6-luna --pricing reports\verified_luna_prices.json --local-report reports\unresolved_qwen.json --max-cases 40 --max-cost-usd 0.50 --max-output-tokens 1200 --experiment-id unresolved-v1 --ledger reports\unresolved-v1-ledger.json --confirm-preflight COPY_EXACT_PREFLIGHT_ID --privacy-reviewed --authorize-paid --execute --output reports\unresolved_cloud.json
```

Do not run this command merely because it is documented. Reuse the same ledger,
experiment and cases for all models/resumptions/retries. Do not delete or replace
the ledger to reset the allowance. A fresh model has its own exact preflight
confirmation but shares the same US$0.50 ceiling.

Ledger files contain no credentials. Atomic reservations precede serial sends;
locking prevents concurrent budget use. Unknown usage, timeouts, inconsistent
reasoning/output totals or uncertain failures retain the full reservation and
stop pending human reconciliation. There are no hidden retries. Conservative
reservations remain charged locally even after a lower observed bill; this
deliberately refuses to expand the budget via speculative refunds.

Output is bounded including reasoning tokens. Text input is bounded to 16,000
estimated tokens using UTF-8 bytes plus framing headroom and additional input
cost headroom. Actual budget-blocked requests are distinguished from initiated
requests. Partial reports preserve failures and untested cases.

This is a local ceiling for benchmark-initiated requests, not a provider/account
billing guarantee. It cannot control unrelated account usage or changes outside
verified assumptions. No provider tools, research, Tavily, embeddings, high-priced
tiers, parallel fan-out or automatic provider switching are enabled.
