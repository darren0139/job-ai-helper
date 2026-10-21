# Historical Ollama / adjudication CI isolation

Date: 2026-10-21 (Asia/Singapore). Repository:
`C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`.
Branch: `fix/ollama-historical-ci-isolation`.
HEAD unchanged: `41b024d790013ec7120045744f1fb2b662ff1b81`.

## Decision and separate outcomes

Current behavioral tests now exercise real validators on disposable current-source fixtures. Original historical assertions remain byte-pinned, registered and independently inspectable. No historical experiment was reproduced. The ordinary full command was attempted without reducing its test set, then interrupted as resource-prohibitive; it is not green.

| Verdict | Result |
|---|---|
| Current-source behavioral tests | PASS — 169 registered controls verified; final focused command recorded below |
| Historical frozen integrity | PRESERVED — original source/expectation artifacts and maps unchanged |
| Historical reproduction | BLOCKED — 143 registered assertions, 0 executed; no approved runtime/dependency recipe |
| Historical lane discoverability | PASS — explicit namespaced inventory and exit-coded prerequisite command |
| Fresh-clone portability of current lane | PASS — tracked inputs only, ignored/private artifact denial control and portable byte attributes |
| No-model/no-external-network enforcement | PASS — existing strict guards retained; injected transports only |
| Production behavior unchanged | PASS — production scorer/parser/taxonomy/registry/evidence/cache/persistence source untouched |
| Full CI | FAIL to complete verification: resource-limited interruption; **no observed assertion failure**, no full-suite PASS |
| Ready for isolated checkpoint | YES for this bounded infrastructure/test change; not a release/full-CI approval |

“Full CI” above describes completion of validation, not a demonstrated application defect. The full-project result is **INCOMPLETE**, not an inferred test failure or success. Hosted Ubuntu/Windows CI and the separate Streamlit startup-health job were not run here. No staging, commit, push, merge, reset, cleanup or branch switch occurred. The unrelated dashboard report is unchanged.

## Root cause and initial reproduction

The v1.2/v1.3 classes eagerly called historical `freeze_plan` in `setUp`. Their pure validator, request-bound, digest and metadata assertions never ran after an older preservation map rejected current source bytes. Smoke `run` and `recover_runtime` likewise consumed old explainability/smoke maps before metadata transport. Actual smoke `readiness` and native adjudication `prepare` rebuilt old frozen inputs through current resolver/version identity and correctly rejected different input fingerprints.

These are different validation boundaries. A stale frozen experiment must not be accepted merely because a current behavior test needs a plan. The earlier reports establish 11 EOL-only source differences, eight content evolutions, and 40 changed native input fingerprints. No hash normalization, old benchmark restamping, new independent labels or production compatibility waiver was introduced.

The contained baseline ran 109 methods: **68 passed, 41 errored methods, plus one class-setup error blocking 13 methods**. The 41 are 35 Ollama method errors and six native-adjudication errors, not 41 independent root causes. Two adjacent modules independently reproduced two more setup errors blocking 12 and 17 methods. Across this scope, 151 pre-existing methods were defined: 68 passed, 41 errored, 42 were prevented from executing by three setup blockers. Thus 44 error records do not mean 44 or 83 independent defects.

Complete original tracebacks are retained in local `reports/ollama_ci_isolation/before.log` and `before_adjacent.log`. Main signatures:

- v1.2: `freeze_plan` -> `Prior protected artifacts changed` (10 setup errors).
- v1.3: `freeze_plan` -> old `validate_plan` -> `Protected artifact/runner changed after freeze` (15 setup errors).
- Smoke execution: `run.verify` -> `Protected artifact changed` (4).
- Smoke original readiness: `readiness` -> CLI `prepare` -> `Frozen input/current knowledge changed; benchmark needs review` (1).
- Smoke recovery: `recover_runtime.verify` -> `Protected artifact changed` (5).
- Native CLI/authorization tests: `prepare` -> same frozen-input/current-knowledge error (6).
- Gold review and V4 review class setup: old native `prepare` mismatch (13 and 12 methods blocked).
- V5 review class setup: missing `docs/ollama_unresolved_prompt_comparison_v1_3.md` while validating protected prerequisites (17 methods blocked).

The V5 missing document is additional to the eleven previously recovered local documents. It was not fabricated or force-added. All baseline errors precede actual model inference. No original historical test was conditionally skipped before this change.

## Before/after inventory

| Current module | Defined before | Before | Current controls after | Historical assertion archive |
|---|---:|---|---:|---:|
| `tests.test_ollama_prompt_comparison` | 10 | 10 errors in setup | 10 pass | 10 retained |
| `tests.test_ollama_prompt_comparison_v1_3` | 15 | 15 errors in setup | 15 pass | 15 retained |
| `tests.test_ollama_unresolved_smoke` | 18 | 8 pass / 10 errors | 18 pass (one explicitly new unit boundary) | 18 retained |
| `tests.test_unresolved_adjudication` | 58 | 52 pass / 6 errors | 58 pass | 58 retained |
| `tests.test_unresolved_gold_review` | 13 | setup blocked all 13 | 13 pass on controlled current inputs | 13 retained |
| `tests.test_unresolved_review_packet` | 12 | setup blocked all 12 | 12 pass on controlled current inputs | 12 retained |
| `tests.test_unresolved_independent_review_v5` | 17 | setup blocked all 17 | 17 pass (one explicitly new unit source guard) | 17 retained |
| `tests.test_ollama_diagnostic_prerequisites` | 8 | 8 pass | 8 pass, unchanged | not a historical experiment |
| `tests.test_ollama_test_lanes` | new | n/a | 18 new lane/validator controls | n/a |

Current total: **169**. Historical archive total: **143** (overlapping behavioral objectives, separate execution identity). Two original claims are exclusively historical, with no assertion that a current unit result proves them:

1. Actual original 40-case smoke/human-gold readiness, including 18 blank V4 decisions.
2. V5's exact original 139 protected artifacts and 34 verified / 4 partial source-recovery observations.

The current replacements explicitly test “not historical readiness” and six test-owned protected files with zero original-source recoveries. Their names/expectations differ intentionally; the old assertions remain intact in the archive. The committed-pending-manifest test is renamed in the current lane to say **test-owned** pending manifest. Every archived method maps to a current counterpart or a documented historical-only reason in `tests/fixtures/ollama_test_lanes_v1.json`. No original assertion source was deleted.

## Test architecture and invocation

### Existing execution paths

GitHub Actions still invokes `python scripts/run_project_checks.py --mode full --ci` on Python 3.13, Ubuntu and Windows. That runner compiles project files, runs configured zero-cost smoke modules and invokes **unmodified full unittest discovery** (`python -m unittest discover -s tests -v`). It has not been replaced by a focused subset. The new registration smoke is mandatory: if its file disappears, CI errors instead of silently skipping it.

The offline launcher injects the existing filesystem/database/network guard and uses the normal focused module loader or the same full project runner. Direct `python -m unittest tests.<module>` remains supported; an actual guarded Python child invocation of the v1.2 module passed all ten methods. No environment variable selects or suppresses test lanes.

### Current source

Focused checks use the existing launcher and the nine modules in the manifest:

```powershell
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_ci_isolation tests.test_ollama_prompt_comparison tests.test_ollama_prompt_comparison_v1_3 tests.test_ollama_unresolved_smoke tests.test_unresolved_adjudication tests.test_unresolved_gold_review tests.test_unresolved_review_packet tests.test_unresolved_independent_review_v5 tests.test_ollama_diagnostic_prerequisites tests.test_ollama_test_lanes
```

This validates current library behavior, not old source identity. Helpers inject artifact paths, a deterministic observation clock and a single captured current production-metadata identity. The real `freeze_plan`, both `validate_plan` functions, `prepare`, source joins, schema/grounding, human-review and packet validators execute. No validator is mocked to return success. V5's previous blanket `validate_packet=True` and repeated `prepare` result mocks were removed; receipt tests now reach those real validators too.

Comparison fixtures protect a nonempty independent sentinel and current source-copy bytes in disposable scratch. Valid plans must pass the actual integrity validator; tampered bytes, missing files, resealed expectation changes and overlapping protected inputs still fail. Original 6/8 holdouts remain tracked, sealed, untouched inputs. Deterministic unit-plan creation is not an assertion that old plans were faithfully regenerated.

The small new `ollama_behavior_contract_v1.json` contains only the pre-existing **authored synthetic eight-case dataset, strict schema and prompt fingerprint**, extracted from a report whose raw SHA-256 was independently present in its successor's preservation map. It contains no model responses, runtime observations, reviewer judgments, résumé evidence or new labels. The file records that provenance; current code is compared against the independent pre-existing input/schema contract, not merely against itself.

The 40 adjudication controls have independently authored requirement text and UNIT_ONLY source metadata. Established case keys are interface aliases needed by existing worksheet/deferred-child contracts; their new source/input fingerprints explicitly distinguish them from original JD occurrences. A selected ordinary JavaScript/TypeScript phrase and 1/3 allocation exercise the existing deferred-child guard. Simulated prior-label/receipt actors are explicitly test-only, not actual human adjudication. Two simulated prior controls leave the gate unsatisfied; no production gold is created or imported.

All new source/plan/report files are temporary test artifacts. The familiar filenames inside the disposable tree satisfy existing library interfaces; they do not replace ignored historical files in the checkout. Current test reports cannot establish original readiness or source-recovery facts. A path-denial regression runs current fixture preparation with ignored repository `docs/`, root `reports/` and private-ref access rejected. No local Git snapshot ref or ignored acceptance report is required in a fresh clone. Normal current-source metadata may inspect ordinary HEAD; that is not a private historical source dependency.

### Historical source

```powershell
# Inventory only: exit 0, explicitly not reproduction
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_ci_isolation --historical-ollama --list-historical

# Immutable prerequisite inspection: exit 2, BLOCKED
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_ci_isolation --historical-ollama
```

The underlying `scripts.run_ollama_historical_checks` command can inspect a `--bundle-root`, but **cannot execute or approve a runtime**. It imports only stdlib registration logic, never current scoring/resolver modules or archive tests. Matching source bytes alone are insufficient for reproduction: the reviewed platform/dependency/execution recipe is unavailable, so there is no execution-unlock switch.

Historical IDs use `historical@41b024d790013ec7120045744f1fb2b662ff1b81:<original assertion ID>`, disjoint from current test IDs. That revision identifies the pre-isolation **assertion catalog**, not an assertion that this revision reproduces all older experiment source. Per-plan original source bytes remain protected separately. The archive files are exact tracked Git blobs, retained outside ordinary `tests/` discovery as data-only source. Their local `.gitattributes` disables text conversion: CRLF changes still fail raw SHA checks.

The historical command produced `BLOCKED`, `attempted=false`, `validated=false`, zero tests and zero inference. All 143 historical assertions remain **not executed**. No full historical runtime was assembled, no old source imported under current semantics, and no historical PASS was inferred from listing or hashing. The original eight smoke passes in the baseline are current mocked unit observations, not proof of a historical reproduction.

Missing/incompatible historical prerequisite findings (deduplicated; full per-map records are in `historical.log`):

| Path / boundary | Finding |
|---|---|
| `analysis_stability/__init__.py` | BYTE_HASH_MISMATCH |
| `analysis_stability/evidence_support.py` | BYTE_HASH_MISMATCH |
| `analysis_stability/stable_evidence_scoring.py` | BYTE_HASH_MISMATCH |
| `docs/ollama_unresolved_prompt_comparison_v1_2.md` | MISSING |
| `historical_runtime` | REVIEWED_SOURCE_DEPENDENCY_AND_EXECUTION_RECIPE_NOT_AVAILABLE |
| `scripts/compare_ollama_unresolved_prompts_v1_2.py` | BYTE_HASH_MISMATCH |
| `scripts/smoke_ollama_unresolved_adjudication_v1.py` | BYTE_HASH_MISMATCH |
| `tailoring/capability_taxonomy.py` | BYTE_HASH_MISMATCH |
| `tailoring/deterministic_project_rules.py` | BYTE_HASH_MISMATCH |
| `tailoring/initial_analysis_explainer_ui.py` | BYTE_HASH_MISMATCH |
| `tailoring/jd_user_input_overrides.py` | BYTE_HASH_MISMATCH |
| `tailoring/job_match_ab_analysis.py` | BYTE_HASH_MISMATCH |
| `tailoring/phase6d_ranking_adapter.py` | BYTE_HASH_MISMATCH |
| `tailoring/phase6d_stable_scoring_adapter.py` | BYTE_HASH_MISMATCH |
| `tailoring/phase9b_role_family.py` | BYTE_HASH_MISMATCH |
| `tailoring/phase9e_tailoring_base_visual_preview.py` | BYTE_HASH_MISMATCH |
| `tailoring/production_requirement_resolver.py` | BYTE_HASH_MISMATCH |
| `tailoring/requirement_scope.py` | BYTE_HASH_MISMATCH |
| `taxonomy/capability_taxonomy_v1.json` | BYTE_HASH_MISMATCH |
| `tests/test_ollama_prompt_comparison.py` | BYTE_HASH_MISMATCH |
| `tests/test_ollama_prompt_comparison_v1_3.py` | BYTE_HASH_MISMATCH |
| `tests/test_ollama_unresolved_smoke.py` | BYTE_HASH_MISMATCH |

A future historical execution needs independently reviewed original per-plan source envelopes, original artifacts and provenance, dependencies/platform/encoding pins, safe storage/output boundaries and an approved offline execution recipe. Privacy-sensitive or uncertain historical observations were not added to Git. The original independent-human gate and original labels remain unchanged; authored synthetic expectations cannot satisfy them.

## False-green protections

The machine inventory is mandatory in normal smoke registration and independently checked by unittest. It verifies every archive file/hash/method, every original-to-current mapping, each current module's actual unittest-loading IDs, and distinct historical/current namespaces. New historical files/methods cannot disappear from both lanes: unregistered files, changed source bytes, missing mappings and missing current counterparts fail. Historical listing never certifies reproduction.

The 18 lane tests include real positive/negative freeze validation; changed sentinel/source rejection before transport; missing source rejection without regeneration; protected-input overlap; raw CRLF/path-escape checks; immutable archive rejection; missing/blocked historical prerequisites with no implementation imports; original human-gold bytes unchanged; ignored/private prerequisite denial; deterministic unit plans; actual direct unittest child invocation; and mandatory normal-CI registration. These complement existing proxy/redirect denial, arbitrary-prompt rejection, model digest, time/request/retry/budget/consent and strict schema/grounding assertions.

## Verification results and full-run limits

All runs used Python 3.13 and the existing strict offline launcher. Simulated requests intentionally exercise bounded request counts; **zero actual model/provider inference or external-service operations** occurred. Existing security self-tests deliberately exercise denied sockets and approved ephemeral local test listeners; this is not a claim of zero socket syscalls across security tests.

| Selection | Result |
|---|---|
| Original primary baseline | 109 executed, 68 pass, 41 method errors + 1 setup error; 13 blocked methods |
| Adjacent original baseline | 0 executed, 2 setup errors; 29 blocked methods |
| Initial corrected primary six modules | 122/122 pass |
| Corrected native/gold/V4/V5 group | 100/100 pass |
| Combined focused current group before last mandatory-check control | 168/168 pass |
| Final lane-integrity module | 18/18 pass, including direct 10-test unittest child |
| Final nine-module current selection | **169/169 pass**, 0 failures/errors/skips (`current_169_final.log`) |
| Existing loopback/socketpair/network + Per-JD/compatibility checks | 61 run: 60 pass, 1 platform skip (AF_UNIX unavailable), 0 failures/errors |
| Actual full-discovery inventory | 3,202 cases, no import failures; all 169 current IDs are present |
| Historical explicit inventory | Exit 0: INVENTORY_ONLY_NOT_REPRODUCTION, 143 retained assertions |
| Historical explicit prerequisites | Exit 2: BLOCKED, 0 historical tests executed |

The actual full command was:

```powershell
venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_ci_isolation_full --full-project
```

It compiled **690 Python files**, completed **all 44 configured smoke checks**, and entered unchanged full unittest discovery. After approximately 15 minutes total, only **76 of 3,202** unittest cases had observable completed results, all passing. It was interrupted through its owned session/process group as resource-prohibitive for this bounded repair; the group was verified exited. This is not a passing full command and not evidence of an application assertion failure. **3,126 current-source cases remain unexecuted in this full attempt**, including groups that passed independently in focused checks. No focused result was used to fill in full-suite outcomes.

`reports/ollama_ci_isolation/full_project_progress.json` preserves all 76 observed IDs/statuses and the exact 3,126 unexecuted IDs, with a separate full-discovery inventory. The last observed case was in `test_application_blueprint_manager`; no test failures or skips had yet been observed. The remaining full-suite cases are **not evaluated**, not classified as historical blockers or assumed green. Full logs are preserved as `full_project.log`. Hosted matrix and startup-health validation remain outstanding.

Full CI must be completed using the unchanged configured runner on a suitably provisioned environment. This checkpoint does not redefine full CI as the focused group. The ordinary registration check prints historical NOT_RUN status, so a future normal-CI PASS still cannot mean a historical experiment was reproduced.

## Exact implementation inventory

| Existing file changed | Purpose |
|---|---|
| `scripts/run_project_checks.py` | Adds mandatory registration smoke; preserves full unittest discovery and all ordinary checks |
| `scripts/run_offline_release_checks.py` | Adds explicit historical inventory/precondition mode with existing containment; full-project command unchanged |
| `tests/test_ollama_prompt_comparison.py` | Current test-owned artifact setup; real freeze/validation and all behavioral assertions retained |
| `tests/test_ollama_prompt_comparison_v1_3.py` | Same separation for v1.3, including its real prior-plan validator |
| `tests/test_ollama_unresolved_smoke.py` | Controlled artifact roots; original actual-readiness assertion archived and replaced with explicit unit non-certification control |
| `tests/test_unresolved_adjudication.py` | Seven native tests use current controlled sources/manifests, including real negative fingerprint rejection; all other current assertions unchanged |
| `tests/test_unresolved_gold_review.py` | Real validator setup on UNIT_ONLY current data; pending-manifest method renamed to avoid historical claim |
| `tests/test_unresolved_review_packet.py` | Reach existing receipt/provenance assertions using current source fixture |
| `tests/test_unresolved_independent_review_v5.py` | Real current packet/preparation validators, no blanket success mocks; original 139/34/4 observation archived, independent current guard added |

New reviewable files:

- `tests/ollama_current_fixtures.py` — disposable unit input/metadata boundaries, not historical artifact generators.
- `tests/test_ollama_test_lanes.py` — 18 registration/integrity/security/portability controls.
- `tests/fixtures/ollama_behavior_contract_v1.json` — small independently frozen synthetic input/schema contract only.
- `tests/fixtures/ollama_test_lanes_v1.json` — machine-readable 143-assertion map, byte pins and lane provenance.
- `scripts/ollama_test_lanes.py` — stdlib-only inventory, raw-byte checks, fail-closed prerequisites.
- `scripts/check_ollama_test_lanes.py` — visible mandatory normal-CI registration check.
- `scripts/run_ollama_historical_checks.py` — explicit inventory/BLOCKED prerequisite command.
- `historical_tests/README.md` and `historical_tests/.gitattributes` — maintained lane contract and exact-byte portability.
- Seven original source archives under `historical_tests/ollama/` (listed below).
- `ollama_historical_ci_isolation_report.md` — this assessment.

| Original assertion source archive | SHA-256 | Registered methods |
|---|---|---:|
| `historical_tests/ollama/test_ollama_prompt_comparison.py` | `78121b290773b066dd6889c098fb4e6a5dbbdb34d3ae816d9610798309499537` | 10 |
| `historical_tests/ollama/test_ollama_prompt_comparison_v1_3.py` | `a42920d1b93dd04fc593b560437afef84885a8c45b813d17425d0f31795cef48` | 15 |
| `historical_tests/ollama/test_ollama_unresolved_smoke.py` | `113af675a62dfb0c53cbfbf3644387ea886d29606032cbdffafe8110d5d7e081` | 18 |
| `historical_tests/ollama/test_unresolved_adjudication.py` | `25fbe1b2d9ae8ef868c3dc204f985cae4e6e6f771d006ab44cf5f8b7b64a66a3` | 58 |
| `historical_tests/ollama/test_unresolved_gold_review.py` | `4f34a5a4df19763cd2e223cd97fbd0797a7468eb9f4e0e8476b480e19f90bcf9` | 13 |
| `historical_tests/ollama/test_unresolved_review_packet.py` | `681abc6004fb42f4e6682dabaaf9b9a0d829f29d988e066df87041b89ed8f6c2` | 12 |
| `historical_tests/ollama/test_unresolved_independent_review_v5.py` | `9af6f418f49bf34d9a8801dda449fb11c4eac9e102a79f9ff2bc0a7af9cb26e3` | 17 |

No private historical Markdown, model outputs, real résumé data, candidate review records, original large diagnostic report or database was added to the checkpoint. Only safe source archives, synthetic controls and metadata are proposed. All local runtime logs/probes/baselines/discovery/progress JSON are under ignored `reports/ollama_ci_isolation/` or `reports/ollama_ci_isolation_full/`; they are not test prerequisites or staging candidates.

## Integrity, remaining blockers and next action

The starting ledger includes all tracked files, the unrelated dashboard review and existing ignored Ollama/unresolved JSON maps. Only the nine existing runner/test files above changed; production, original fixture/manifests, all existing map/label bytes, cache/persistence, browser bridge and filesystem/network/database guard sources remain identical. Published scorer remains `stable-evidence-v1.17-phase6d21`; experimental v1.20–v1.23 gates/defaults are untouched.

Historical `per_jd_scoring_audit.json` remains byte-identical, SHA-256:
`a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f`.
All eleven previously recovered documents still match their pre-existing frozen hashes. No frozen checksum was regenerated. The exact-byte archive attribute and CRLF negative test prevent silent historical normalization.

Syntax/import checks, Git whitespace checks and separate checks for new untracked-file whitespace pass. The source-registration checker and full discovery import inventory also pass. Branch, HEAD, unrelated untracked dashboard file and production identities are preserved. No outstanding full-run process remains.

Remaining boundaries:

- **Historical prerequisite:** original source/artifact mismatches, missing V1.3 material and no approved dependency-pinned historical runtime/execution recipe. Historical reproduction remains BLOCKED, with every retained claim registered.
- **Current-source regression:** none found in the focused current controls or 76 completed broad cases. This does not establish outcomes for the other 3,126 full-run cases.
- **Infrastructure/resource limit:** full verification did not complete locally. Its exact pending IDs are preserved; complete the unchanged full command before a full-CI/release claim.
- **Application defect:** none demonstrated by this bounded work; no application algorithm was changed.

Review the isolated test/runner checkpoint, then complete the normal hosted/full validation with adequate runtime. Any historical runtime bundle or execution support requires a separate provenance/privacy/dependency review. Do not restore old evidence from current output, alter old labels or turn an inventory PASS into historical reproduction. Stop for review; no Git publication action was taken.
