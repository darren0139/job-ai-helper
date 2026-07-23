# CI, model benchmarking, and Chroma JD identity helpers

This package is additive. It does not replace Phase 6B.1 runtime files.

## Add

```text
.github/workflows/ci.yml
config/model_benchmark_catalog.json
rag/jd_identity.py
scripts/benchmark_models.py
scripts/run_tailoring_trial.bat
scripts/run_tailoring_trial.ps1
tests/test_model_benchmark.py
tests/test_jd_identity.py
```

Add to `.gitignore`:

```gitignore
benchmark_results/
stability_results/
test_inputs/
```

Keep personal debug bundles and résumés out of Git.

## Short Phase 6B.1 trial command

Command Prompt:

```bat
scripts\run_tailoring_trial.bat "C:\Users\Admin\Downloads\app_72_debug_bundle.json"
```

PowerShell:

```powershell
.\scripts\run_tailoring_trial.ps1 `
  -DebugBundle "C:\Users\Admin\Downloads\app_72_debug_bundle.json"
```

Environment variables can override the batch defaults:

```bat
set RUNS=3
set ANALYSIS_MODEL=openai/gpt-5.6-luna
set REASONING_EFFORT=low
scripts\run_tailoring_trial.bat "C:\path\bundle.json"
```

## Model cost/quality benchmark

The first model is the baseline:

```bat
python -m scripts.benchmark_models ^
  --debug-bundle "C:\path\bundle.json" ^
  --models openai/gpt-5.6-terra openai/gpt-5.6-luna openai/gpt-5.4-mini openai/gpt-5-mini ^
  --runs 2 ^
  --reasoning-effort low
```

Generated files:

```text
benchmark_results/models_<timestamp>/
├── comparison.csv
├── comparison.json
└── one JSON file per model
```

Compare:

- project order and set;
- requirement labels;
- Skills output;
- bullet wording;
- median latency;
- token usage;
- estimated text-token cost.

The estimate captures the final provider response for the Projects call and the
final provider response for the Skills call. Retries and JSON-correction calls
can increase the actual bill.

## CI versus paid benchmarks

The GitHub Actions CI workflow never calls a paid model. It compiles the code,
runs unit/regression tests on Windows and Linux, and performs a Streamlit startup
smoke test.

Keep the paid model benchmark local or run it through a separately protected,
manually triggered workflow using sanitized fixtures and repository secrets.

## CD

For Streamlit Community Cloud, the normal CD path is:

```text
Pull request -> CI passes -> merge to main -> Streamlit redeploys main
```

Configure branch protection so the `Python 3.13` matrix checks and the
`Streamlit startup smoke test` must pass before merging.

## Chroma JD deduplication

Use two IDs:

- `canonical_jd_id`: stable identity for company + title + location;
- `source_version_id`: hash of the normalized full posting.

Suggested Chroma metadata:

```json
{
  "canonical_jd_id": "jd_...",
  "source_version_id": "jdv_...",
  "company_normalized": "garena",
  "title_normalized": "associate configuration qa",
  "location_normalized": "singapore",
  "first_seen_at": "...",
  "last_seen_at": "..."
}
```

Workflow:

1. Build the identity with `build_job_identity`.
2. Query Chroma using `canonical_jd_id`.
3. If the exact `source_version_id` already exists, skip insertion.
4. When the canonical ID matches but the version differs, update the canonical
   record and append the version to a history table/list.
5. For slightly changed titles or locations, retrieve the closest records and
   call `is_probable_near_duplicate`; optionally combine it with embedding
   cosine similarity.
6. Store chunks with IDs such as
   `canonical_jd_id + ":chunk:" + zero-padded chunk index`.
7. Use Chroma `upsert`, not `add`, for canonical records.

Do not merge postings solely because embeddings are similar. Require matching
company/title identity plus high text or embedding similarity.
