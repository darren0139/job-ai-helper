# Evidence Completeness V1 — review required

2026-10-16. Investigation and baseline probes completed; production correction
has not been implemented. The requested stop condition applies: a changed
evidence policy needs a reproducibility/currentness version decision, and
partial design/development coverage needs an explicit contract.

## Git and scope

- Worktree: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
- Branch: `feat/llm-unresolved-requirement-adjudication-v1`.
- Baseline: `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc`; initially clean.
- Governed resolver, published taxonomy v1.6 and post-publication accounting
  sources/fixtures are present. The other worktrees were only listed by Git.
- Only this report and its JSON results are added. No production/test source,
  resume evidence, taxonomy, registry, publication or snapshot is edited.

## Root cause and existing contracts

`tailoring/capability_taxonomy.py::_evaluate_capability_record` (line 655)
first checks named REST/gRPC protocols. PostgREST is accepted as REST protocol
support; it does not establish API authorship. Missing protocols return
`requested_api_protocol_evidence_missing`. Alternatives and single-row
completeness are already considered by this guard.

The API tier in `taxonomy/capability_taxonomy_v1.json` (line 1477 onward)
then accepts any of built/implemented/developed/created/**integrated** and any
of api/rest api/restful api/endpoint/web service/fastapi/**postgrest**.
`_matches_groups` (line 48) tests co-occurrence, not who authored what.
Consequently data access, documentation and negated endpoint creation can
receive `explicit_backend_api_implementation`, DIRECT, value 1.0. There is no
API-specific authorship or independent design-obligation check. The API has
only a DIRECT evidence tier; otherwise it returns `recognised_but_unsupported`.

The exact internship wording instead receives NONE: `developing` does not
match `developed`; plural `endpoints` also does not match singular `endpoint`.
The explicit singular `API` token is present, so the missing accepted action
alone is sufficient to explain its failure. This is an additional production
predicate gap, not evidence that extending an existing backend is invalid.

`analysis_stability/stable_evidence_scoring.py` supplies the existing path:

- `build_resume_evidence_index` (3006) retains source rows and provenance.
- `_evidence_source_is_requirement_compatible` (3249) constrains credentials,
  education and structural headings. No source rule proves API authorship.
- `_apply_capability_single_row_reselection` (3317) is taxonomy opt-in,
  bounded by the preliminary label, and keeps the first stronger eligible row.
- `tailoring/phase6d_stable_scoring_adapter.py::cap_requirement_with_taxonomy`
  (39) resolves knowledge and caps preliminary evidence without upgrading it.
- `_apply_capability_none_recovery` (3477) uses
  `evaluate_capability_evidence` for a canonical resolved capability. It ranks
  by label, coverage, then overlap, preserving index order on exact ties.
  DIRECT does not require lexical overlap. WEAK recovery requires positive
  overlap. Changing that global rule is unnecessary for this task.
- `compute_deterministic_alignment` (4238) retains the existing values:
  DIRECT 1.0, TRANSFERABLE .55, WEAK .20, NONE 0.0. Coverage uses existing
  importance/parent-group weighting and the overall score also includes mean
  evidence strength. No formula change is proposed.

The actual canonicalizer leaves `Design and develop RESTful APIs` as one
non-atomic requirement. Existing atomic-child promotion applies to already
split children; it does not allocate separate design and implementation
credit here. `tests/test_compound_completeness_contract.py` uses an explicitly
experimental simulation guard, not an active global production contract.

## Proposed contract — not executed or released

Apply a bounded API-specific completeness policy in the existing evaluator,
shared by normal capping and capability-none recovery. Retain requirement
recognition, taxonomy v1.6, source selection, named-protocol guards and weights.
Do not add a separate matcher or require global lexical overlap.

| Obligation and evidence | Proposed evaluator decision |
|---|---|
| Development; personally implemented REST endpoints, including an existing backend | DIRECT / 1.0 |
| Design and development; explicitly designed interfaces and implemented endpoints/handlers | DIRECT / 1.0 |
| Design and development; endpoint implementation alone | WEAK / .20, subject to approval of partial-coverage semantics |
| Authoring; existing-API consumption/integration only | NONE / 0.0 |
| Authoring; PostgREST data access/RLS only | NONE / 0.0 |
| Authoring; documentation or skills only | NONE / 0.0 |
| Authoring; explicit non-authoring/negated implementation | NONE / 0.0 for that denied obligation |
| REST required; only gRPC or unspecified FastAPI protocol | Preserve current named-protocol guard |
| Integration explicitly required | Evaluate integration scope; preserve valid credit rather than impose authorship |
| Mixed independent obligations | Require complete scoped support; no global decomposition change in this correction |

NONE is recommended for integration/data-access evidence against an authoring
obligation because it establishes a different activity. WEAK is proposed only
for demonstrated implementation that partially covers an independently
required design-and-development obligation. No new score tier is requested.
Negation must be scoped to the actual activity: a denial of architecture
ownership must not erase explicit endpoint implementation. Likewise,
integration elsewhere in a sentence must not erase genuine endpoint authorship.
Action inflections and endpoint plurals need bounded handling.

## Executed disposable baseline

`evidence_completeness_v1_review.json` records 23 scenarios, direct evaluator
decisions, complete native final rows, selected sources/IDs, values, scores and
repeat equality. Every native analysis was run twice and compared in full.
Socket and SQLite connects were blocked for these probes; no database was
needed. Proposed labels in the JSON are review expectations, not outputs of
an implemented evaluator or independently verified gold labels.

| Case | Baseline evaluator | Baseline native value | Proposed evaluator |
|---|---|---:|---|
| Exact EDB PostgREST statement, combined obligation | DIRECT | 1.0 | NONE |
| Exact internship wording, development obligation | NONE | 0.0 | DIRECT |
| Exact internship wording, combined obligation | NONE | 0.0 | WEAK, review required |
| Explicit REST interface design and handler implementation | DIRECT | 1.0 | DIRECT |
| Explicit REST endpoints using FastAPI | DIRECT | 1.0 | DIRECT |
| FastAPI endpoints without explicit REST | NONE | 0.0 | NONE |
| Existing REST API integration, authoring obligation | DIRECT | 1.0 | NONE |
| Created API documentation | DIRECT | 1.0 | NONE |
| Integration plus explicit denial of endpoint creation | DIRECT | 1.0 | NONE |
| Skills/knowledge list only | NONE | 0.0 | NONE |
| Explicit REST implementation plus unrelated integration | DIRECT | 1.0 | DIRECT |
| Existing valid generic API endpoint implementation | DIRECT | 1.0 | DIRECT |
| Java backend queries without API work | NONE | 0.0 | NONE |
| C++ and frontend positive controls | Their own capabilities DIRECT | 1.0 | Unchanged |

With PostgREST and internship rows available together, the baseline selects
PostgREST as DIRECT and rejects the internship row. The proposed selection
should favor the internship row for development; this has not been executed
under a corrected policy. Exact baseline provenance is in the JSON.

Native final labels can differ from direct API evaluator labels. For example,
generic gRPC, dual-protocol and integration-only requirement phrasings produce
WEAK native rows despite DIRECT API evaluator probes; separate REST and gRPC
rows produce native WEAK despite individually failing the complete-protocol
API guard. Those synthetic phrasings do not establish a canonical API
resolution in this path. Do not claim that changing the API predicate alone
fixes all unrecognized-requirement lexical matches. The recognized Job 566
compound NONE control passes in the recovery suite.

Cross-job scope is these synthetic requirement variants and the supplied EDB
fixture. No live corpus impact or unexpected-regression absence is claimed.
Unrelated controls are baseline protections, not proof about an unimplemented
correction. The future regression suite must compare both evaluator decisions
and final native outcomes and preserve deterministic tie behavior.

The earlier accounting audit attributes approximately 3.536296 overall points
to the current EDB row. Removing unsupported credit would remove its attributed
coverage/evidence contribution, but total-score change must be recomputed with
the complete evidence-strength population. The supplied snapshot projection
removed other resume evidence and cannot reproduce the saved score of 20:
native recomputation gives 14, and manually changing only this row gives 12
for WEAK or 11 for NONE. These JSON sensitivity results are explicitly NOT
predictions of production after scores. Single-positive synthetic jobs score
100 for DIRECT, 22 for WEAK and 0 for NONE under unchanged formulas.

## Why implementation stops here

`job_discovery/matching.py::current_match_versions` (196) and snapshot lookup
use scoring/taxonomy/registry identity; they do not hash evaluator code.
`build_stable_analysis` input identity (4433) includes text and existing
versions, not the evidence predicate source. The current scoring version is
`stable-evidence-v1.16-phase6d20`. A production policy change with all identities
unchanged can produce different results under the same identity and leave
saved matches apparently current. Approve a scoring-version increment, or an
explicitly designed evidence-policy version propagated through currentness
and reproducibility identity, before implementation. A scoring-version bump
is the smaller existing-contract option; no new version has been chosen.

Also approve whether implementation-only support for a combined design and
development obligation receives existing WEAK or NONE. The recommendation is
WEAK; calling it DIRECT would overstate the independent design obligation.
These are the stop conditions in section 6 of the supplied request.

## Validation and protection

- `python -B -m unittest discover -s tests -p test_capability_none_recovery.py -v`:
  9 passed on available Python 3.14.4; Python 3.13 was not installed.
- Guarded unittest discovery for `test_capability_taxonomy_v1_4_boundaries.py`,
  `test_governed_requirement_resolution.py`,
  `test_compound_completeness_contract.py`, and
  `test_post_publication_accounting.py`: 54 run, 33 passed, 21 temporary-directory
  permission errors. No assertion failures; zero external network attempts.
- Retried those patterns with workspace-owned temporary storage: 46 run,
  33 passed, 13 errors (12 setup errors and one accounting-module import error)
  from temporary-directory permissions. Zero external network attempts.
  SQLite access was restricted to disposable temporary paths in both runs.
  The workspace scratch directory was removed with an exact-path elevated
  cleanup after ordinary cleanup was denied. No test assertions were changed.
- `run_tests_quick` and `run_tests`: both exited 1 before running checks because
  `.venv/Scripts/python.exe` is absent. Full supported-version validation is
  outstanding. No environment installation or virtual-environment edit made.
- JSON records before/after SHA-256 hashes for 20 protected local artifacts,
  including taxonomy/registry JSON, evaluator, scorer, adapter, resolver,
  publication-related sources and the saved snapshot fixture. All match.
- Live databases, user-level databases and database-backed publication receipts
  were not accessed, so no live database/receipt/snapshot hash comparison is
  claimed. Snapshots 40/56 were not rewritten. The separate master worktree
  was not accessed. Candidate evidence/fingerprints and all production versions
  remain unchanged.

## Manual acceptance after contract approval

1. Establish the approved scoring/evidence identity and implement only the
   bounded policy in the existing evaluator, with focused regression fixtures.
2. On Python 3.13, run the smallest new regression, the existing recovery,
   protocol, selection, compound and accounting tests, then `run_tests_quick`
   and `run_tests` with disposable state and external model/network calls blocked.
3. Inspect evaluator and native selected-evidence receipts for exact PostgREST,
   exact internship wording, explicit design/implementation, scoped negatives,
   REST/gRPC and mixed integration cases. Confirm source/eligibility/weights
   and unrelated capabilities remain stable.
4. Review cross-job disposable comparisons and protected hashes before release.
   Review saved historical snapshots as stored; authorize any production refresh
   separately. Do not save the hypothetical internship wording automatically.

Stop for user review. No commit, push, merge, branch switch, live Job Match
refresh, publication or Bulk Unresolved Resolution work has been performed.
