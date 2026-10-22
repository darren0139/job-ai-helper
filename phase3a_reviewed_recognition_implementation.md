# Phase 3A — Reviewed recognition implementation and verification

## Verdict

**A1 is implemented and verified as a developer recognition-only review function.
S1 has a minimal review contract, with no runtime activation. Neither is ready
for formal publication approval.** No published scorer/taxonomy/registry change,
new scorer version, production gate activation, database migration or application
update was made. Previous Phase 2F/3A/v1.24–v1.26 work is preserved.

## Exact changes

| File | Change |
|---|---|
| `taxonomy_discovery/resolver_improvement.py` | Added `additive_phrase_overlay`; `resolver_overlay` now uses it for plural artifacts. Existing terms, variants, static product exclusions, fallbacks, evidence policies and tiers remain intact. Duplicate phrases preserve their existing guarded rule. New variants freeze the current product-context names. Resolver **draft contract** is v2; old v1 sealed drafts must be regenerated and revalidated. No scorer version changed. |
| `taxonomy_discovery/governed_requirement_resolution.py` | Added explicitly invoked `api_plural_review` and finite source-admission validation, reusing the native resolver and temporary taxonomy scope. No UI, production scoring path or publication writer calls this function automatically. |
| `tests/test_reviewed_api_plural.py` | Seven focused tests for merge preservation/idempotency, admissions/counterexamples, original-source rejection, corpus views, actual workflow isolation, persistence rejection, S1 schema limits and the governed-route blocker. |
| This report | Implementation, measured candidate impact, S1 contract, test results and remaining approvals. |

The change to resolver artifact version is necessary: silently replaying an old
sealed replacement artifact with new additive semantics would misrepresent its
reviewed identity. Existing review/publication validators remain in force and
reject stale drafts. No old report, fixture or draft bytes were rewritten.

## A1 execution and safeguards

`api_plural_review(row, raw_jd_text, explicit_execution=True)` first runs the
existing production-knowledge resolver. Any already-resolved taxonomy, registry
or complete-technology identity is retained; the new phrase cannot steal it.

For an unresolved input, admission requires:

- Exactly one original raw-JD requirement/responsibility parent, with source ID,
  positive source allocation, explicit native grounding and matching sentence.
- The complete normalized raw parent, requirement text, focus, parent text and
  grounded sentence must agree. The original raw parent must occur verbatim in
  the supplied JD. Shortened positive excerpts from negated/compound parents,
  multiple/conflicting occurrences and missing source ownership fail closed.
- A core, score-eligible duty, without negation, optional language or a main-duty
  OR alternative. The framework `such as` example tail is retained in the input;
  its OR list is not reinterpreted as an alternative to developing APIs.
- A finite development verb bound to the actual `RESTful APIs` object: build,
  develop, implement or create, including tested gerunds; optionally coordinated
  integrate/consume, and the observed efficient/secure modifiers. Unrelated
  object verbs, knowledge-only, reading-only and consumption-only duties do not
  authorize this development candidate.

The helper creates the additive native temporary taxonomy, asks the **existing
native resolver** about that exact input and restores context immediately. It
does not install another resolver or leave a taxonomy context active while an
application scorer runs. Source/canonical IDs, importance, parent allocation,
qualifiers, actions and original evidence authority remain unchanged.

A new candidate always returns `REVIEW_REQUIRED` with **null evidence credit,
parent contribution and whole-JD score**, `development_preview_only=True`,
`activation_ready=False` and `requires_human_approval=True`. It is a diagnostic
receipt, not a stable-analysis result or governed approval. Central persistence
guards reject it before a connection executes a write. Native empty-evidence
recognition checks are not treated as candidate evidence assessments.

Compound AND obligations can expose an API-development concept, but remain
complete review inputs: integration, consumption, database work or gRPC does not
disappear. Main-duty OR ambiguity is rejected. Framework examples, efficiency and
security remain unproved; recognized API terminology supplies none of them.

## Measured A1 impact on the same 30 JDs

| Separate input view | Rows | Native unresolved baseline | New pending A1 recognition candidates | Published/native result changes |
|---|---:|---:|---:|---:|
| Saved historical projection | 727 | 536 | **0** | 0 |
| Current native raw-only | 716 | 519 | **3** | 0 |
| Explicit v1.26 raw-only | 716 | 520 | **3** | 0 |

Saved projections lack the required original source receipts. Unlike the earlier
unbounded phrase hypothesis, this implementation does not borrow raw provenance
to make their three lexical observations admissible. The two raw views recognize
the same three candidate concepts, each still awaiting complete-scope review:

| Job / requirement | Exact original requirement | Preserved scope |
|---|---|---|
| 31 / `req_d0a20edbb7ae` | Proven experience building efficient, secure RESTful APIs with frameworks such as Express.js, Fastify, FastAPI, Spring Boot, or equivalent enterprise-grade tools | Building, efficiency, security and framework examples/equivalence; not proof of those modifiers. |
| 479 / `req_5eabf1000188` | Develop and integrate RESTful APIs with front-end applications | Both development and integration with the front-end application. |
| 479 / `req_fc4e6757e8e4` | Experience developing and consuming RESTful APIs | Both development and consumption. |

Job 566 `req_b34860727bff`, the original hands-on Amazon Web Services
(EC2/Cognito/S3/DynamoDB) requirement, remains excluded. Existing guarded `web
services`, REST-development fallback and approved REST/API recognition are
preserved. No claim about historical candidate matching, evidence improvement or
whole-JD alignment follows from these candidate counts. Denominators were not pooled.

Ignored receipt: `reports/reviewed_api_implementation/impact.json`, 37,274 bytes,
canonical SHA-256 seal
`1c19531fe705fa773ac7313c87cbe522979f1828761d4eb9b43d6b5ba2c37416`.
It includes separate source packets, all new null-credit receipts, AWS controls
and implementation hashes. It is not a launch/test dependency or approval record.

## S0 and S1

S0 remains rejected. No `stakeholders` requirement alias was added. Existing
cross-functional, communication and all other identities stay intact.

S1 cannot safely be encoded by the current governed artifacts. The schema only
accepts the already defined API complete-scope policy/fallback. Its plural draft
mechanism deliberately cannot express a single-word stakeholder inflection or
action-to-object binding. The schema-rejection test confirms this boundary.
**Actual S1 recognition changes are zero in every view.** No unsupported predicate
was slipped into `any_terms` or a technology alias.

Minimal S1 contract requiring review:

1. Reuse `collaboration.stakeholder`; consider the candidate only after all
   approved recognition, registry and complete-identity resolution fails.
2. Require an affirmative collaboration action grammatically bound to an explicit
   stakeholder object in the same complete, independently grounded duty. Do not
   equate noun presence with collaboration. No adjacent-sentence borrowing.
3. Initial positive family: collaborate/collaborating **with stakeholders**, with
   explicit stakeholder descriptors allowed. Exact grammar and descriptors need
   approval before encoding a new scope rule; no arbitrary verb list is implied.
4. Exclude beneficiaries/audiences, negation, optional claims, incidental mentions,
   generic teamwork, engage/update/relationship-building and vague work-across.
5. Preserve other mandatory actions/artifacts/modifiers and original allocation.
   A collaboration concept never supplies numeric credit for the entire parent.
6. Require the same explicit developer invocation, null-credit review receipt,
   immutable source fingerprint, independent controls and publication rejection
   as A1. A schema/artifact extension must be reviewed before implementation.

Job 158 `req_5e1c1de91a3c` (“Collaborate with various stakeholders to build
mission-ready tools and platforms”) is the clear source-bound regression example;
its build obligation must remain. This is a proposed contract example, not an
implemented S1 success. Job 240 binds *influence* to stakeholders and *collaborate*
to engineering/product/policy teams: do not pretend the collaboration verb binds
to stakeholders. Jobs 16/72 communication duties and Job 48 analytics beneficiaries
remain outside S1. Job 81 work-across, Job 158 relations/workflows and Job 163
engage/update remain separately reviewable, not automatically admitted.

## Formal maintenance approval readiness

**Ready for developer review; BLOCKED for formal approval/publication.**

The merge defect is corrected, but a lexical plural artifact by itself does not
encode A1's unresolved-only precedence, source admission, development-object
binding or mandatory null-credit disposition. The review packet is deliberately
not marked as a governed resolver draft. The current candidate planner rejects
a bare “RESTful APIs” synthetic research candidate as ineligible; no route was
forced and no research/result/reviewer receipt was fabricated.

Also, existing `governed_publication` preflight rejects a plural publication when
the target already has contextual variants. This protection remains unchanged.
It prevents the corrected temporary merge from silently authorizing live
publication into the current API definition. Publication compatibility is outside
this experimental implementation.

Remaining explicit approvals/work:

- Approve the exact S1 grammar/schema contract or leave it pending.
- Review the full A1 source-admission and unresolved-only/null-credit contract;
  represent that complete contract in an authentic current governed artifact.
- Recreate any affected v1 draft as v2, obtain source-bound native validation and
  attach an explicit human review to its exact artifact/regression fingerprints.
- Separately decide numeric parent-completeness/modifier policies. This task adds
  none. Preserve native NONE and P3 ceilings, API V1.1 and original-record ownership.
- Separately approve any future publication/version/cache compatibility change.
  No production activation, saved-result persistence or migration is authorized.

The seven application #152 policy questions remain pending as recorded in the
previous decision matrix; no application-specific score or policy was changed.

## Verification

All runs used Python 3.13 and `scripts/run_offline_release_checks.py` with `-B`,
disposable scratch stores and strict offline guards. No original or copied real
application database was opened. Existing lifecycle tests simulate approvals and
publication only inside their labelled disposable fixtures; these are not real
human approvals or production publication.

Final main command:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/reviewed_api_final tests.test_reviewed_api_plural tests.test_api_evidence_completeness tests.test_governed_requirement_resolution tests.test_governed_requirement_activation_v1_1 tests.test_tqd3_governed_research.GovernanceImpactTests tests.test_taxonomy_maintenance_service tests.test_evidence_relevance_preview.RelevancePreviewTests.test_geometry_published_parity_and_determinism tests.test_phase3a_eligible_evidence.EligibleEvidenceTests.test_native_source_guards_none_ceiling_and_known_capabilities_unchanged tests.test_phase3a_alias_surface
```

**73 PASS, 111.595s.** This run covered the six implemented A1/S1 tests, API V1.1,
governed validation/publication lifecycle controls, maintenance safeguards,
v1.24/v1.25 isolation and all eight v1.26 regressions. Actual Job Finder,
document-grounded Initial Analysis and Phase 8 builders produce identical results
before/after a review invocation; their authoritative evidence sources remain
separate. No A1 context is active during these numeric calls.

An additional planner test initially expected a bare plural candidate to create
a governed draft and errored at the eligibility validator. Inspection established
that this was an incorrect new test assumption, not a broken validator. The final
test asserts the actual fail-closed boundary and verifies no review store was
created. No existing assertion or independent oracle was weakened.

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/reviewed_api_route_final tests.test_reviewed_api_plural.ReviewedPluralTests.test_governance_rejects_unreviewed_plural_route_without_fake_receipts
```

**1 PASS, 0.387s**; total final coverage **74 passing tests**. Initial five focused
controls also passed before broader validation. No full CI was run. The known
historical protected-source-hash failure remains separate and untouched, not
claimed fixed or rerun here. New maintenance implementation bytes are explicitly
pinned in the new receipt; old diagnostic hash ledgers are not rewritten.

AST, whitespace, protected-file and receipt integrity checks accompany the final
workspace audit. Published taxonomy remains SHA-256
`1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513`;
historical fixtures, original dashboard report, published scoring and gate defaults
are preserved. No staging, commits, pushes, merges or publication.
