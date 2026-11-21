# Independent gold review workflow

Start with `docs/unresolved_gold_review_v2.md`. It audits all 40 original cases,
including exact stored text, original proof and provenance, native resolver
diagnostics, bounded existing knowledge and explicitly proposed discussion routes.
`reports/unresolved_gold_review_v2.json` provides the corresponding machine-readable
packet, including the original source manifest and frozen input versions.

The v1 manifest remains unchanged. The v2 manifest initially carries **only the two
previously confirmed NAC labels**. It does not claim a new reviewer or review date
for those inherited decisions. Its other 38 cases are pending, not UNKNOWN gold.
The native scope diagnostics for NAC conflict with historical semantic adjudication;
the worksheet exposes this rather than silently changing either contract.

The text-ready flag is an editorial prioritization for a human decision, including
deferral. It is not a gold label, proof of actionability or production routing rule.
Original parent JD context is missing. Identity recognition, historical blocker
names and token overlap do not independently justify capability mappings.

Review the cases without viewing model predictions. In a separate JSON file, copy
only completed entries from `reports/unresolved_gold_review_receipts_v2.json`:

- Keep the exact job/requirement IDs, input and source fingerprints.
- Supply the real reviewer, timezone-aware ISO timestamp, exact requirement
  substrings, rationale and source reference. Record any additional human-reviewed
  source context/reference in the rationale; do not substitute a changed input.
- Set the independence attestation only after independent human review.
- Enter one primary route first; include alternatives only if explicitly reviewed.
- Use an empty route list with a completed rationale/receipt for explicit deferral.
  Do not enter UNKNOWN as an actionable label. Do not import the blank template.
- For CAPABILITY/RELATIONSHIP decisions, identify and check the relevant existing
  predicate and negative boundary in the rationale. Mere technology identity is
  never grounds for a capability relationship.

Import completed receipts into **new output paths**, preserving all old files:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
$env:CAPABILITY_RAG_MODE='off'
.venv\Scripts\python.exe -B -m scripts.prepare_unresolved_gold_review --receipts reports/completed_human_receipts.json --manifest-output reports/human_reviewed_benchmark_v2.json --worksheet-output reports/human_review_source_worksheet.md --packet-output reports/human_review_packet.json --template-output reports/human_review_blank_template.json
```

The imported decisions and receipts reside in the new manifest; the worksheet
deliberately retains the original expectations and proposed questions for audit.
Pass the reviewed manifest explicitly with the existing benchmark CLI's
`--benchmark` option. This preparation task authorizes no model execution.

Provenance validation rejects missing human fields, non-independent/model origins,
stale fingerprints, duplicate/unknown IDs, changed controls, malformed timestamps,
fabricated spans, UNKNOWN actionable labels and modified manifest seals. It checks
receipt structure, not a human identity authentication system. A human must actually
review and truthfully attest; a program cannot establish independence by itself.

The labeling prerequisite requires at least 20 actionable cases across four primary
non-UNKNOWN categories, with critical controls resolved. The current 2-label version
does **not** meet it. Even a sufficiently labeled manifest does not establish model
quality: the existing gate still requires a complete validated local benchmark.

Nothing here changes scoring, native resolution, taxonomy, registry, database,
approval/publication or research execution. Test-only reviewer receipts exercise
the validator; none are written as real corpus gold labels.
