# Ollama diagnostic prerequisites investigation

Date: 2026-10-21 (Asia/Singapore). Branch: `fix/ollama-diagnostic-prerequisites`.
HEAD remains `cd66eb553b2e96209d8632c58a3d42bc83609680`.

## Decision

Historical missing Markdown prerequisites were recovered exactly from local Git objects. This does **not** make the historical experiments valid against current production knowledge. All 35 original errors remain, now expressing preservation or frozen-input rejection rather than missing files. No original test was skipped, weakened or edited.

| Verdict | Result |
|---|---|
| Missing prerequisites | PARTIAL — all eleven Markdown files recovered; historical execution/source isolation still unresolved |
| Frozen artifact integrity | PRESERVED — no historical hash map, seal, label, report or source bytes restamped |
| Ollama diagnostic tests | BLOCKED — 8 passed, 35 errors across the original 43 tests |
| Production behavior unchanged | PASS — all 988 entry tracked files byte-identical |
| Ready for isolated checkpoint | YES for the new unit tests and this investigation report only; NO as a complete CI/prerequisite repair |
| Full CI | NOT RERUN |

The unrelated `coordinated_batch_dashboard_review.md` is byte-identical. No index, branch, HEAD, stash or other worktree was changed. No production, scoring, parser, taxonomy, registry, prompt, original oracle, security guard or stale per-JD accounting fixture was edited. Published v1.17 and experimental v1.20–v1.23 source identities remain untouched.

## Failure groups and actual contract boundaries

| Group | Before count | First failing function / signature | After restoration | Historical/current dependency |
|---|---:|---|---|---|
| A | 10 | v1.2 `freeze_plan`, hashing `docs/ollama_unresolved_adjudication_smoke_v1_1.md`: FileNotFoundError | 10 errors: `Prior protected artifacts changed` at the historical-map comparison in the same function | Ignored v1.1 result/map plus current runner/holdout bytes; history must be unchanged before a new plan is issued |
| B | 15 | v1.3 `freeze_plan` -> v1.2 `validate_plan`: `Protected artifact/runner changed after freeze` | Same 15 errors | Ignored v1.2 sealed plan, then exact current checkout bytes, before generating v1.3 jobs |
| C | 4 | smoke `run` -> local `verify`: `Protected artifact changed` | Same 4 errors | Ignored explainability preservation map, rechecked against current source before preflight |
| D | 1 | smoke `readiness` -> adjudication `prepare`: `Frozen input/current knowledge changed; benchmark needs review` | Same error | Tracked benchmark v2/source fixture, but `build_input` reruns current resolver/candidate lookup and embeds current production identity |
| E | 5 | smoke `recover_runtime`, reading `docs/ollama_unresolved_adjudication_smoke_v1.md`: FileNotFoundError | 5 errors: `Protected artifact changed` in recovery `verify` | Ignored original smoke result/map, exact historical Markdown, then byte preservation before preflight |

All 35 failures happen before even injected metadata transport. They do not reach Ollama inference or an actual HTTP transport. Some tests contain earlier successful bounds checks before reaching their blocking call; that does not validate their later objectives.

The three original modules intentionally test full experiment preparation as well as pure validators. Both comparison classes eagerly call `freeze_plan` in `setUp`; consequently pure source-validation tests also fail before their objective. Metadata-only `run` still validates the full preservation envelope and, at its end, historical gold readiness. It is not equivalent to the lower-level `preflight` function.

This is a test/prerequisite coupling and portability defect, not evidence that frozen hashes are wrong. A current-source change may be authorized and desirable while still violating an immutable historical experiment contract. The code deliberately refuses that execution. Changing the meaning of those contracts merely to make these tests green would be a different change requiring review.

## Per-failing-test inventory

Names below are the original unittest methods. The objective is summarized from the method name and assertions. Group definitions above specify each test's exact prerequisite, failing function, frozen/current mode and artifact classification. A/B fail in setup; C/D/E fail in the test body. None reaches inference or metadata transport at its blocking call.

| Module/class and test | Original objective | Group |
|---|---|---|
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_fixed_loopback_transport_disables_proxy_redirect_and_arbitrary_prompt` | fixed loopback transport disables proxy redirect and arbitrary prompt | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_grounding_diagnostics_preserve_legacy_fail_closed` | grounding diagnostics preserve legacy fail closed | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_holdout_frozen_and_expectations_not_in_prompts` | holdout frozen and expectations not in prompts | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_model_digest_change_stops_before_inference` | model digest change stops before inference | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_preflight_is_metadata_only` | preflight is metadata only | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_separate_version_and_unmodified_legacy_prompt_schema` | separate version and unmodified legacy prompt schema | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_stale_plan_or_changed_expected_routes_rejected` | stale plan or changed expected routes rejected | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_timeout_stops_with_reserved_attempt_no_retry` | timeout stops with reserved attempt no retry | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_twenty_calls_no_original_eight_legacy_reruns` | twenty calls no original eight legacy reruns | A |
| `tests.test_ollama_prompt_comparison.PromptComparisonTests.test_unsafe_or_thinking_values_not_retained` | unsafe or thinking values not retained | A |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_alternative_presence_does_not_prove_structure_error` | alternative presence does not prove structure error | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_digest_change_and_finite_loopback_request` | digest change and finite loopback request | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_exposure_professional_route_review` | exposure professional route review | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_freeze_exact_twenty_and_semantic_contrast` | freeze exact twenty and semantic contrast | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_grounding_rejection_cannot_be_rehabilitated` | grounding rejection cannot be rehabilitated | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_identity_route_plus_preserved_activity_is_flag_not_rejection` | identity route plus preserved activity is flag not rejection | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_injection_influence_is_reviewed_not_claimed_causal` | injection influence is reviewed not claimed causal | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_metadata_only_and_twenty_serial_requests` | metadata only and twenty serial requests | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_missing_activity_and_source_denial_reject_only_new_contract` | missing activity and source denial reject only new contract | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_negative_unqualified_activity_not_positive_obligation` | negative unqualified activity not positive obligation | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_same_schema_versions_and_no_hidden_expectations` | same schema versions and no hidden expectations | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_tampered_plan_and_result_provenance` | tampered plan and result provenance | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_technology_absence_and_omission` | technology absence and omission | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_timeout_no_retry_and_outstanding_work_no_generation` | timeout no retry and outstanding work no generation | B |
| `tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_unsupported_capability_gap_and_ids_fail_closed` | unsupported capability gap and ids fail closed | B |
| `tests.test_ollama_unresolved_smoke.LocalSmokeTests.test_actual_readiness_validator_no_new_labels` | actual readiness validator no new labels | D |
| `tests.test_ollama_unresolved_smoke.LocalSmokeTests.test_bounds_and_no_retry_after_failure` | bounds and no retry after failure | C |
| `tests.test_ollama_unresolved_smoke.LocalSmokeTests.test_explicit_only_selected_synthetic_case_and_strict_payload` | explicit only selected synthetic case and strict payload | C |
| `tests.test_ollama_unresolved_smoke.LocalSmokeTests.test_missing_or_remote_model_no_inference` | missing or remote model no inference | C |
| `tests.test_ollama_unresolved_smoke.LocalSmokeTests.test_preflight_no_inference_and_import_is_passive` | preflight no inference and import is passive | C |
| `tests.test_ollama_unresolved_smoke.RuntimeRecoveryTests.test_basic_failure_stops_without_retry` | basic failure stops without retry | E |
| `tests.test_ollama_unresolved_smoke.RuntimeRecoveryTests.test_basic_mode_only_one_request` | basic mode only one request | E |
| `tests.test_ollama_unresolved_smoke.RuntimeRecoveryTests.test_one_basic_eight_classifications_two_repeats_no_duplicate_stage3` | one basic eight classifications two repeats no duplicate stage3 | E |
| `tests.test_ollama_unresolved_smoke.RuntimeRecoveryTests.test_outstanding_generation_blocks_all_requests` | outstanding generation blocks all requests | E |
| `tests.test_ollama_unresolved_smoke.RuntimeRecoveryTests.test_schema_or_truncation_failure_in_stage3_stops` | schema or truncation failure in stage3 stops | E |

## Frozen map audit and provenance

The v1.2 plan says `frozen_at_utc=2026-10-13T04:37:37.162754+00:00` and `AUTHORED_SYNTHETIC_EXPECTATIONS_NOT_INDEPENDENT_GOLD`. The explainability report records HEAD `befaace942de996bf5d80f2a5651556a026ee0ab`, scorer `stable-evidence-v1.16-phase6d20`, taxonomy v1.5. Current knowledge is scorer `stable-evidence-v1.17-phase6d21`, taxonomy v1.6. Registry v1.3, registry bytes and source authority fingerprint are unchanged. This is diagnostic provenance inspection only; the separate stale v1.16 per-JD accounting fixtures were not investigated or changed.

All four preservation maps were exhaustively read and compared without short-circuiting. The original validators stop on the first mismatch, so later missing paths were initially hidden.

| Map (`reports/`, ignored) | Entries | Before matching / differing / missing | After matching / differing / missing |
|---|---:|---|---|
| `unresolved_evidence_explainability_review_v1_1.json` | 105 | 89 / 15 / 1 | 90 / 15 / 0 |
| `ollama_unresolved_adjudication_smoke_v1.json` | 119 | 95 / 15 / 9 | 104 / 15 / 0 |
| `ollama_unresolved_adjudication_smoke_v1_1.json` | 121 | 96 / 15 / 10 | 106 / 15 / 0 |
| `ollama_unresolved_prompt_comparison_v1_2_plan.json` | 128 | 98 / 19 / 11 | 109 / 19 / 0 |

The 19 differing tracked paths in the v1.2 map are listed below. The first 15 are also the explainability/smoke-map differences. Every frozen expected digest has a matching local Git source representation: either the exact blob or the blob materialized with CRLF. Matching a file to a commit does not prove that the entire historical runtime and its dependencies were reconstructed.

`EOL only` means current and frozen source have identical LF-normalized content, but different protected bytes. `Content evolved` means normalization cannot reconcile them. The validators enforce exact bytes in both cases; no normalization was added. `core.autocrlf=true` explains the checkout sensitivity. None of these files was edited during this task.

| Path | Frozen SHA-256 | Current SHA-256 | Locally matching revision/representation | Interpretation; latest source change |
|---|---|---|---|---|
| `analysis_stability/__init__.py` | `a9a5836c97977886db16374ec62fa7ca1b6e4f6a7df1d6cf0af93a599d384787` | `45ee0178100f98a98fca7b9104da2ca90ee1ad60796ac057485b3d171509a5a2` | `3773169c7c2f7db6b35e4a0228788b55194e236a` (git-blob) | EOL only; 3773169c7c2f7db6b35e4a0228788b55194e236a 2026-07-22T16:18:00+08:00 phase-6a1c-stable-analysis |
| `analysis_stability/evidence_support.py` | `4588f40c16cb53805dd50c8ff6038c144ee2386412a644934af6ba6c648cd30b` | `902a2838cb5037d90fb6f21eec53c342e42f4717920ab9eb2fea570a759657cd` | `313c93a1d4abe5992b42a0ad2704084dc2659d33` (git-blob) | EOL only; 313c93a1d4abe5992b42a0ad2704084dc2659d33 2026-08-04T15:38:49+08:00 Add deterministic Phase 9C cross-JD evaluation |
| `analysis_stability/stable_evidence_scoring.py` | `16cbd0096e228356aade8d495d66e5135332c6e7ebff7e077ac8394e877afb98` | `3781be8520882842f8021e1c8bd392c6ac034919375c8dcf4c58accb79451619` | `edb115d4a8d196fd917566eb1d06f0476d1af757` (blob-as-CRLF) | Content evolved; 299c09dd1084a6fc67724b5244e46dbe77c8d322 2026-10-20T23:07:19+08:00 fix: refine experimental JD metadata boundaries v1.23 |
| `tailoring/capability_taxonomy.py` | `71b9471c3863ed1d857cd80e489cb1ee877c4673c78760f42ad635f27d09fd17` | `373c3cb8d7aedd8122d258c2fc395d49dbb5ca73f93ff02a87b3a254ba7db96f` | `421ad429b0073863c59602aebba89e7231d6a087` (blob-as-CRLF) | Content evolved; d37dbb5231d7211efc7b0c0297a20e34d6f597bf 2026-10-17T01:37:01+08:00 enforce API evidence completeness and preserve scoring identity |
| `tailoring/deterministic_project_rules.py` | `fd62a665e83b8149dac9bac4f0eef293bff8e11916a22532b6cb9d25194251e7` | `1341010c767fcec436ec326e3394acbdd490698de7c792bc36d0dd0925558b6b` | `f67be2d8c6c5ebbe6f4bc089186739d7f8c08ce8` (git-blob) | EOL only; f67be2d8c6c5ebbe6f4bc089186739d7f8c08ce8 2026-07-16T18:45:00+08:00 change deterministic file |
| `tailoring/initial_analysis_explainer_ui.py` | `96ec5835ee2497a5188eb837009ff698d0caad898d3e24ac674e9d7b01f577b6` | `26f48a52cd1dd14aa6e9652117ff2bc726d379c84f9c18693aa69a23bce8dce1` | `0dbb550af58919e0f8d963737c4f73ba53d354da` (blob-as-CRLF) | Content evolved; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `tailoring/jd_user_input_overrides.py` | `aea829497ed3da16173f26709dadd9d0bc16d0e52861db02f2926f6390b80c7c` | `7ce0829f9bb19820772aa22fbe8be6be4977ab65e5ce32038cf014bd353901aa` | `0dbb550af58919e0f8d963737c4f73ba53d354da` (blob-as-CRLF) | Content evolved; a58cc7b7e29d90b841cfa2ae1602c41dbfdcd81e 2026-10-20T19:35:09+08:00 feat: add source-aware coordinated Job Match developer preview |
| `tailoring/job_match_ab_analysis.py` | `c9763504cda2f5723e4550670a7f2cb54bf8e70207b12e941c631a500d3edce0` | `92f637aa1493d7b3edceb864be9784b61ad10022ab2941ba849136986955f0a1` | `6e9293f891c9a08eb2d69d549a1dfdb40b04e25c` (git-blob) | EOL only; 6e9293f891c9a08eb2d69d549a1dfdb40b04e25c 2026-10-07T22:06:16+08:00 Add Job Match session initial-vs-tailored analysis |
| `tailoring/phase6d_ranking_adapter.py` | `bd16b094a168e3c5d78585de1af39c30be16ebf11b778beb43d023deafd31f4c` | `1de84ce11c4b32d74fa21786ef47f87a3a4ac5f18f1f791090f8a9baff9e44f3` | `45647fc7923063d475dbb57d8adb8e0c01b8876c` (git-blob) | EOL only; 45647fc7923063d475dbb57d8adb8e0c01b8876c 2026-07-28T15:59:57+08:00 stable scoring, API cost observability and taxonomy |
| `tailoring/phase6d_stable_scoring_adapter.py` | `499453bf9348383734edd75f310c94bb8f0764fc73b024625718b9d583f1e9e9` | `8749d859c2e4d17c973391588da134509468da35bf946375bd448bc8fb8b5801` | `edb115d4a8d196fd917566eb1d06f0476d1af757` (blob-as-CRLF) | Content evolved; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `tailoring/phase9b_role_family.py` | `24fdfcdb4bfbb507196f561a271534f87cda4e2751f6b6ffe6c43eb48875e8e8` | `f60ebe8b5cd83dea859e77a70ab2a9dcc973b04f2700147c4ff3a8244d1e1f59` | `8f34c1512865a8f42aae216ff3a41e4bf2c641af` (git-blob) | EOL only; 8f34c1512865a8f42aae216ff3a41e4bf2c641af 2026-08-03T16:15:58+08:00 add Phase 9B blueprint candidate registry |
| `tailoring/phase9e_tailoring_base_visual_preview.py` | `b0fd8b3ed9cf2713f0bd4b9371a3d1ab6d2ba06b4babbdfc69df36c2471cd096` | `cfd1b50a7748dd53ecc589991f3905d9514614f7d89f7c19783e0bf498cebde9` | `cb9318f57db496c5ae4a5f24a30e029a073a9514` (git-blob) | EOL only; cb9318f57db496c5ae4a5f24a30e029a073a9514 2026-10-02T18:56:59+08:00 Checkpoint TQ-D3 publication and Phase 9E currentness |
| `tailoring/production_requirement_resolver.py` | `09610d229e054169ceb4146b5a8fce924a242b891e9b902ea8655bf76ccce060` | `d773bdfaebdaad0dfcf4da5cec376c6756cdd5809069dd5834191e08917061bb` | `edb115d4a8d196fd917566eb1d06f0476d1af757` (blob-as-CRLF) | Content evolved; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `tailoring/requirement_scope.py` | `e02afbfe3568ee101895c16d5ec2a1fc59df017ce2f6a01eb2d1d87eb93bae1b` | `053c694ecbc3f9e5233d686ff946863a41cd569bbc9578820b73461cf38d3c7c` | `edb115d4a8d196fd917566eb1d06f0476d1af757` (blob-as-CRLF) | Content evolved; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `taxonomy/capability_taxonomy_v1.json` | `da7b5e6952935a7dda88347c5af41eba65784b45da1c5b68f45a8768f605563e` | `1c68940cbfa1bc459b81bdc8182e2165f370eb628bfe0e3e1940388a15f57513` | `bc0aaef0265f618c826cb08debefd065e24ed758` (git-blob) | Content evolved; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `scripts/smoke_ollama_unresolved_adjudication_v1.py` | `99a4fd3f641df2b64368354a1439ebcc3b2175d12fa5feb2015d43332c1b389b` | `12c80a735123c7d8c933710ac2379fda40f14a5a84bb8af7abd64ff3a2864853` | `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc` (git-blob) | EOL only; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `tests/test_ollama_unresolved_smoke.py` | `113af675a62dfb0c53cbfbf3644387ea886d29606032cbdffafe8110d5d7e081` | `ec561e54a0945d0c3d7d990d5cabe72d5dbf73dd7679aa21279f39f0c97295f3` | `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc` (git-blob) | EOL only; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `scripts/compare_ollama_unresolved_prompts_v1_2.py` | `45cf173b8b48fb6a295a30dca1cb1ed6ee1c05b7ffc7f611318cc1b8188891e5` | `56f248076ece32651c73752df93810b4ac8df0a0e791d938fb4632bfb5583d25` | `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc` (git-blob) | EOL only; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |
| `tests/test_ollama_prompt_comparison.py` | `78121b290773b066dd6889c098fb4e6a5dbbdb34d3ae816d9610798309499537` | `6ea28ec33ee671b6b3e8ccaba01f31e8cf8fee1491ffed57328a4e296b873341` | `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc` (git-blob) | EOL only; 91f8d3dff2c8eda2a518ac9bc082d5df83102cdc 2026-10-16T13:21:41+08:00 governed unresolved resolution and taxonomy accounting |

There are 11 EOL-only differences and eight content changes. Local history ties the latter to subsequent resolver/scope, taxonomy/accounting, API completeness, coordinated scoring/preview and metadata-boundary checkpoints. These are committed source evolution, not changes introduced by the recent network repair. This audit does not certify every prior algorithm change; it establishes why the old byte/source identity cannot be asserted for current code.

For independent pre-security reproduction, all 19 corresponding Git blobs at current HEAD are exactly equal to those at `299c09dd1084a6fc67724b5244e46dbe77c8d322` (before containment/browser/AppTest/network fixes). The diagnostic scripts and original diagnostic tests were introduced at `91f8d3dff2c8eda2a518ac9bc082d5df83102cdc` and have no later committed content changes. The current source-based hash rejection can therefore be demonstrated directly without running old or unguarded code. No checkout/reset or removal of security protections was needed.

### Frozen-input identity

A contained metadata-only probe of the existing 40 frozen JD occurrences found: original source fingerprint matches; zero occurrences now resolve away; **all 40 current input fingerprints differ**. For the first key `(31, req_2410dfcbbf45)`, expected input is `d0225739ef0d530e788b661bfa135784e25860eb9e606ee11f6869eb48796055`, current is `594513a80f8bbca4bd028046570be037e3b3232a0bcb81be0451c5461f84cc86`. `build_input` includes current production versions and current resolver/taxonomy/registry candidates. Version and implementation identity drift alone is sufficient to invalidate the old digest; this audit does not claim all source interpretations changed. Benchmark seals, source data and existing labels were not replaced. The original two inherited independent labels and authored synthetic expectations remain distinct.

## Missing documents: origin, recovery and exact inventory

`git log --all --full-history -- <two smoke paths>` has no commits. That search alone is insufficient: `git rev-list --objects --all -- <paths>` locates standalone **tree** refs. The recoverable source is local tree `0a406ec1799434ed1c66f360191f8bd10c5c3b27`, retained by `refs/codex/turn-diffs/checkpoints/eeb316f9cf0a0cd30c53b231388bc77b/214fc88caf939ea78895abc8333dfaf4/1791999727843/cdafcb1e-3e33-4b8f-bc97-f54b165494d3`. It is not a commit, stash restore or current production activation. Tree provenance establishes locally retained content; it does not independently validate the historical model observations.

Both smoke documents describe historical model requests/results, authored synthetic expectations, bounded diagnostics and the still-blocked independent-human gold gate. They are not independent adjudication receipts. Original CLI entry points produce JSON, not these Markdown reports. No deterministic Markdown generator was found, and regenerating from present code/model runs would change the historical meaning. Their commands contain historical `.venv` launch paths; the current supported interpreter/containment launcher below was used instead.

The same tree supplies all nine other missing preservation-map documents. Three documents match the raw blob bytes; eight match after CRLF materialization. Every restored byte sequence was checked against the **pre-existing frozen expected SHA-256 before writing**, then checked again afterwards. No text, result, judgment or checksum was authored to fill a gap. Existing files were never overwritten. These paths remain ignored under `.gitignore:63 /docs/*`; original JSON dependencies remain ignored under `.gitignore:55 /reports/*`.

| Restored local-only file | Source Git blob | Exact frozen/restored SHA-256 | Representation |
|---|---|---|---|
| `docs/ollama_unresolved_adjudication_smoke_v1.md` | `8c9dd4aa295fcdd76b3d9c2211a8e2de56e0e379` | `d9ece928ea96cc9673ec6c0f6ea5d17766672becb5dcbb64ac8677ca0308ba74` | git-blob |
| `docs/ollama_unresolved_adjudication_smoke_v1_1.md` | `795842319d8bb42d40a6ba7391214f1a24ac5c44` | `31308b9d751d17cfa2a827d4d01cdd37784680559780d48ea0754e397786d8a6` | git-blob |
| `docs/unresolved_semantic_layer1_evidence_relevance_v1.md` | `219f150936a65b7b73ebba5efc6a911bd3f9fb96` | `11048e1766740fbf1f7e809feccd7de2d371bd78e6973ea8d694ca1c54caaabe` | git-blob |
| `docs/unresolved_adjudication_v1.md` | `8fe4a61a237ef4b2994f733fdc69ab2fb74baf36` | `3fec86b0f535b6d9c5d8a2ca4b7af407fa7fdebc09dd29b7b2ad92354bd34a93` | blob-as-CRLF |
| `docs/unresolved_evidence_explainability_review_v1_1.md` | `fabe66ffdd63f7e7c8dd793c9957674ac700d0dd` | `91ee9ab704be6bd810b5d153a969a0814d7b83323218a72756a4f4b86405faf0` | blob-as-CRLF |
| `docs/unresolved_gold_decision_review_v3.md` | `cbb7b1736e3d5d5d9433bbcea653033917ac93ab` | `d3d855cfb6b365d0e2523a103a1c9235e1a2ec70da7e41443c11bba36f7c4525` | blob-as-CRLF |
| `docs/unresolved_gold_review_packet_v4.md` | `088f2b8f8b1e526d3cb23a46513d51be931b7dfa` | `ebf959f254a949644301e72cb4ddb0a019711acffa81405d126f22bce9fdcb80` | blob-as-CRLF |
| `docs/unresolved_gold_review_v2.md` | `0a8c0fdc69b7f483c1f666dd92e67983212a8a6d` | `72516c792895652ff876cfe4dae6739e810295eaf19c1ba73283a37ac4cd70c4` | blob-as-CRLF |
| `docs/unresolved_gold_review_workflow.md` | `020def2cee3ff4565c53b09d094eb4ab2fe67c4f` | `f015b86658011ea707f514590fe69c820476c2d64d8e844e36d051cacc4d7fc9` | blob-as-CRLF |
| `docs/unresolved_multidimensional_route_audit_v1.md` | `c6f35a54effaa12af3a6600fd1044ae653499b3f` | `2d2455bf226d102fa8747a4cc31b90fca611b0280a677a8f470a59191fedcd88` | blob-as-CRLF |
| `docs/unresolved_multidimensional_triage_v1.md` | `d0f7bd855809bedccb806b11231216137ddce602` | `3ac2cec6faf74b13068d052631e58a21c01f982e99d8d95a11f603da2088b6ef` | blob-as-CRLF |

These are legitimate local prerequisite restorations, **not a portable committed fixture solution**. A fresh clone normally lacks both these ignored reports and private tree refs. No report or restored historical review document should be force-added indiscriminately; any future distributable historical bundle needs independent provenance/privacy/dependency review. The complete historical runtime has not been assembled or claimed to pass.

## Smallest implemented correction and regression protection

Added `tests/test_ollama_diagnostic_prerequisites.py` with eight current-source unit tests. It directly exercises the real metadata-only `preflight`, separately from full historical experiment preparation. It requires no ignored files, local Git refs, executable Ollama or running server. No original test, expected route, independent oracle or assertion was changed. Its intentionally invalid miniature plans are explicitly rejection-only fixtures; they can never serve as a successful historical benchmark or compatibility mode.

The tests prove passive reload/import without opener/process creation; injected version/tags requests only and repeatable metadata; unavailable metadata remains blocked; changed bytes reject before transport without restamping; missing critical files reject without creating reports; even EOL changes remain rejected by the byte contract; invalid seals fail; and both tracked sealed synthetic holdouts remain deterministic and byte-identical. Temporary artifacts use contained `tempfile` scratch. Historical restoration provenance is independently checked against the frozen digests and local Git objects, not inferred from these unit fixtures.

No generic compatibility mode or source-hash waiver was introduced. Moving the original whole-run metadata assertions to lower-level preflight would silently lose their preservation/readiness coverage; they remain in place. Adding isolated unit coverage does not claim those blocked full-run contracts passed.

## Commands and test results

All unittest invocations used Python 3.13.12 and:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/ollama_diagnostic_runtime <modules>
```

| Modules / invocation | Before | Final outcome |
|---|---|---|
| `tests.test_ollama_prompt_comparison` (independent invocation) | 10 run, 10 errors | 10 run, 10 errors; missing-document signature becomes preservation rejection |
| `tests.test_ollama_prompt_comparison_v1_3` (independent invocation) | 15 run, 15 errors | 15 run, 15 errors; same rejection |
| `tests.test_ollama_unresolved_smoke` (independent invocation) | 18 run, 8 pass, 10 errors | 18 run, 8 pass, 10 errors; five missing-document errors become preservation rejection |
| `tests.test_ollama_diagnostic_prerequisites` | New | 8 run, 8 pass; also passed in combined rerun |
| Adjacent `tests.test_ollama_prompt_review_v1_3`, `tests.test_unresolved_adjudication`, `tests.test_unresolved_gold_review`, `tests.test_frozen_evidence_contract` | 75 run, 69 pass, 6 test errors + 1 class-setup error | Combined with new 8 tests: 83 run, 77 pass, 6 test errors + 1 class-setup error |
| `tests.test_offline_loopback_security`, `tests.test_offline_socketpair_security`, `tests.test_network_guard_support` | Existing guards unchanged | 26 run, 25 pass, 1 platform skip (AF_UNIX unavailable); 0 failures/errors |
| Diagnostic-only `reports.ollama_diagnostic_runtime.probe_knowledge` | Metadata observation only | 1 run, pass; records drift, does not approve it |

All focused runs have **zero assertion failures**. Errors are explicitly retained, not counted as successes. unittest does not add a class-setup error to its executed-test count: the 13 `HumanReviewTests` were not executed because `setUpClass` failed. In the adjacent group, the other six errors are `NativeInputTests.test_cli_default_no_transport_init_or_network`, `test_cloud_preflight_with_key_zero_calls`, `test_frozen_manifest_labels_not_bucket_conversion`, `test_no_auto_all_corpus_expansion`, `test_paid_execution_requires_prior_qwen_and_confirmation`, and `test_whole_paid_plan_over_budget_never_initializes_transport`. Each reaches the same `prepare` frozen-input/current-knowledge rejection. Supplemental source review (7), frozen evidence/source provenance (10), schema, provider denial, budget and other native-input checks pass. The class error is a shared prerequisite failure, not 13 independently measured results.

Original-module before/final logs, adjacent/security logs, `contract_audit.json` (all map entries/current hashes), restoration receipts and metadata probes are retained only under ignored `reports/ollama_diagnostic_runtime/`. An interrupted parallel launch was rerun to completion. The `after_*` module logs record the initial two-document restoration; complete `final_*` logs record verification after all eleven documents were restored. `final_adjacent.log` records the final combined adjacent rerun.

Syntax was checked with in-memory `compile`, producing no repository bytecode. The tests import all three diagnostic modules under containment. `git diff --check` and `git diff --cached --check` pass; the new untracked test/report were checked separately for trailing whitespace (Git diff does not cover untracked files).

## Security, integrity and inventory

No Ollama, Tavily, model/embedding or external-service call was made. No model was started/downloaded. Original diagnostic errors precede injected transport; passing transport tests mock the opener. New tests inject metadata and deny opener/process creation on import. Containment remains enabled throughout project imports/tests. Security regressions intentionally exercise denied network operations and explicitly scoped disposable loopback listeners; these are not Ollama or external-service connections. No claim of zero socket operations across security self-tests is made.

All 989 entry ledger files (988 tracked plus the unrelated dashboard review) match their original SHA-256 values. No existing tracked file changed, including production/version/security/accounting sources. No live candidate data, résumé, saved application, database, `.env`, other worktree or shared runtime was used. Disposable framework/runtime outputs remain under the launcher scratch roots.

Exact reviewable additions:

- `tests/test_ollama_diagnostic_prerequisites.py` — eight independent current-source tests.
- `ollama_diagnostic_prerequisites_report.md` — this report.

The eleven restored local-only document paths are exhaustively listed above. They remain ignored and must not be treated as staged changes. Other new ignored outputs are under `reports/ollama_diagnostic_runtime/`: `baseline.json`, `contract_audit.json`, `restored_documents.json`, `audit_local.py`, `build_report.py`, `probe_knowledge.py`, before/after/final module logs, adjacent/security/prerequisite/knowledge logs, and launcher-created `offline-release-*` disposable trees. A machine-readable recursive inventory is retained there as `generated_inventory.json`. None is a production dependency. The unrelated pre-existing dashboard report remains untouched. There are no staged files.

## Remaining decision and eventual CI impact

Missing documents are now resolved locally, but the original error count is **35 before / 35 after**. The frozen benchmark is intentionally historical. Do not replace its hashes, currentness identities, independent labels or protected-source snapshot with current values. A full green Ollama suite requires a separately reviewable choice:

1. Build a narrowly scoped, distributable historical fixture/runtime from verified local objects and original artifacts, with privacy/dependency review and explicit historical-mode labeling. Require an independently pinned source envelope; do not silently run current imports under a historical label.
2. Separately retain current-source unit contracts and design a new, explicitly versioned/currently reviewed experiment if a current-source benchmark is wanted. This needs approval of its evidence/currentness boundary; old judgments must not be promoted into new independent gold.

The smallest next action is review of the historical fixture boundary and which safe artifacts may be distributed, not another production algorithm repair. Most needed source representations exist locally, but a complete dependency-pinned, isolated historical execution was not validated here. The restored documents alone do not solve fresh-clone CI. The eight new tests are portable unit coverage, not a replacement for the original diagnostics. Full CI remains unverified and separately blocked by the already-known accounting-fixture issue; that issue was left untouched.

Stop for review. No staging, commit, push, merge, reset, branch switch, cleanup or production activation was performed.
