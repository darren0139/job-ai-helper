# Browser bridge loopback CI isolation

## Repository and reproduced boundary

Repository: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `fix/browser-bridge-loopback-ci`.
Entry HEAD: `d20c444b47fe75295482e37ff21fb5ad954df10f`.
Entry status: only the unrelated untracked `coordinated_batch_dashboard_review.md`.

The original runtime test reproduced under the existing containment launcher: **one test, one error, 0.083 seconds** (`reports/browser_bridge_ci_runtime/before.log`). Call chain:

```text
tests/test_browser_bridge_runtime.py:24 -> start_browser_bridge_runtime(port=0)
browser_integration/bridge_runtime.py:57 -> JobAIBridgeServer(...)
browser_integration/bridge_server.py:37 -> ThreadingHTTPServer.__init__
socketserver / http.server -> socket.bind
scripts/offline_release_guard.py -> RuntimeError: Offline checks prohibit network access
```

This is an integration-test/validation-policy conflict, not evidence of a production bridge defect. The test needs a real IPv4 TCP server at `127.0.0.1`, an OS-selected port, token-authenticated `/health` HTTP, and deterministic shutdown. Its database is already disposable.

## Architecture decision

**Option B: an explicit scoped test-only socket capability.** A separate controlled process lane (Option A) would require discovery partitioning, aggregate result accounting and new orchestration. The existing guard already runs in each Python process via `sitecustomize`; a scope around the one fixture preserves ordinary discovery and focused test commands without exclusions or permanent skips.

`scripts/offline_loopback.py` has no permission on import. Its context manager stores a short-lived capability in a `ContextVar`, bound to the PID and thread ID. It admits exactly one `AF_INET` / `SOCK_STREAM` bind to the literal tuple `("127.0.0.1", 0)`. The audit hook remembers that socket by weak reference. It subsequently permits TCP clients only to that live socket's actual assigned address/port, plus `getaddrinfo` for that exact numeric IPv4 endpoint with TCP parameters. A second listener and any fixed-port bind remain denied.

Exit revokes the shared state, resets the context and closes the listener as a final safeguard. Copied contexts in other threads fail the owner check. Python children start with empty capability state despite inheriting guard environment variables; PID checking also prevents a copied process state from granting access. No environment flag or test-name matching can grant permission. The actual fixture stops the server and joins its thread before scope exit.

The ordinary release guard remains default-deny. Its preexisting narrow Windows stdlib internal socketpair exception is unchanged. Additional audited DNS APIs (`gethostbyname`, `gethostbyaddr`, `getnameinfo`) are now explicitly denied as well. `socket.create_connection` and HTTP clients must pass through audited resolution/connect calls; socket-server helpers must pass bind. UDP send APIs remain denied. IPv6 is deliberately unsupported by this fixture, including `::1`; wildcard `0.0.0.0` / `::` and external destinations are denied.

The focused launcher installs a second hook restricting connect and resolution. It consults the same capability, so both hooks must agree. Filesystem, SQLite, secrets, subprocess inheritance and all other restrictions are retained. No production module imports this capability, and no application feature flag or scoring identity changed.

This is scoped validation infrastructure for trusted Python tests, not an OS sandbox against malicious Python code or native extensions. It does not claim to mediate raw native networking outside Python audit events.

## Exact changes

| File | Change |
| --- | --- |
| `scripts/offline_loopback.py` (new) | `loopback_http_scope` and `loopback_socket_allowed`: per-scope socket identity, process/thread checks, exact numeric endpoint validation, revocation/closure. |
| `scripts/offline_release_guard.py` | Consult that capability for socket events; explicitly deny additional DNS APIs. Existing filesystem, SQLite and child-process restrictions retained. |
| `scripts/run_coordinated_preview_checks.py` | Consult the same capability in its additional connect/resolution audit hook. |
| `tests/test_browser_bridge_runtime.py` | Scoped real-server fixture, cleanup via context managers/unittest cleanups, proxy-free real HTTP requests, authentication/origin and exception/sequential shutdown tests. |
| `tests/test_offline_loopback_security.py` (new) | Independent guarded child-interpreter controls for denied operations, scope revocation, copied threads, subprocesses, filesystem and database boundaries. Runs under ordinary unittest too by bootstrapping the actual guard in probe children. |
| `browser_bridge_loopback_ci_report.md` (new) | This report. |

No production runtime, HTTP handler, token generator, database manager, capture/mapping code, Streamlit route, CI workflow, full discovery runner or historical oracle was modified.

`HTTPServer.server_bind` normally calls `socket.getfqdn` to populate its display-only `server_name`. The test fixture substitutes the numeric host for that metadata lookup to avoid reverse DNS. It does not replace server creation, bind/listen/accept, HTTP transport, request handlers, authentication or shutdown. HTTP requests explicitly disable inherited machine proxies. Existing synthetic SQLite setup is now registered with `addCleanup`/scoped patching so setup failures restore configuration too.

## Positive and negative evidence

- Real browser HTTP: original health request returns 200 and its existing service-body assertion passes. Missing/wrong tokens return 401; a non-extension origin returns 403; an authenticated extension-origin request returns 200.
- Sequential and exception-path runs exercise actual servers and health requests, then verify the listening socket descriptor is closed and the server thread has terminated. This verifies release of the listening resource; no broad fixed-port rebind permission is introduced for the test.
- Default scope: real loopback bind and `create_connection` attempts are rejected, even with an unrelated environment flag claiming to allow loopback.
- Active scope: external/documentation IPv4 and IPv6 addresses, wildcard interfaces, alternate loopback addresses/ports, DNS hostnames, reverse lookup, UDP and a second listener are rejected.
- Thread/subprocess isolation: a copied ContextVar in another thread and a Python child inheriting the environment cannot bind. After an injected exception, a later ordinary operation is denied and a new explicit scope works independently.
- Filesystem/SQLite/subprocess restrictions remain active inside the network scope: an unauthorized checkout write, outside-root SQLite and `python -S` are rejected.
- Negative external-destination controls invoke the actual installed audit hooks with `sys.audit`, without executing a transport syscall. They cannot contact external services even if an assertion fails. Positive HTTP tests use actual sockets; no external HTTP request is made.

The first new security-probe run found probe defects (nested Windows `-c` quoting and an incorrect expected prefix for the preexisting child-inheritance error). Probe programs now use disposable source files; the subprocess guard was not relaxed. Corrected probes: **4/4 passed, 22.532 seconds**, no skips (`security_after.log`).

## Commands and focused results

Interpreter: `venv/evidence-completeness-runtime/environment/Scripts/python.exe`, CPython 3.13.12, Windows x64. Commands below run from this worktree with `-B` and the unchanged disposable-output launcher. Full logs remain ignored under `reports/browser_bridge_ci_runtime/`.

Original test before and after:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/browser_bridge_ci_runtime tests.test_browser_bridge_runtime.BrowserBridgeRuntimeTests.test_runtime_starts_on_loopback_and_answers_health
```

After: **1 passed, 0 failures/errors/skips, 0.743 seconds** (`original_after.log`). Runtime module: **3 passed, 2.778 seconds** (`runtime_after.log`).

Related run:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/browser_bridge_ci_runtime tests.test_browser_bridge_runtime tests.test_browser_bridge_settings tests.test_browser_bridge_contract tests.test_browser_capture_manager tests.test_browser_capture_url_canonicalization tests.test_browser_capture_queue_ui_contract tests.test_browser_extension_poc_contract tests.test_browser_extraction_quality_contract tests.test_browser_linkedin_adapter_contract tests.test_browser_phase9f_source_contract tests.test_browser_tailor_resume_handoff tests.test_offline_loopback_security tests.test_all_canonical_sequence_regressions_v1
```

**74 passed, 0 failures/errors/skips, 38.346 seconds** (`related.log`). Includes actual health/authentication, token settings, capture persistence on disposable databases, extraction/URL canonicalization, extension mapping whitelist, handoff contracts and the original résumé overflow/containment tests.

## Full offline CI

The workflow's actual full entry point is `python scripts/run_project_checks.py --mode full --ci` on Python 3.13, Ubuntu and Windows. The existing offline launcher runs that same full runner with `--mode full`; `--ci` changes the printed environment label only. No discovery filtering or isolated lane was added: the browser fixture opts in explicitly when its tests execute, and every other test remains under the default guard. The separate hosted Streamlit startup job was not launched against local application state.

Exact full command:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/browser_bridge_ci_runtime --full-project
```

- Compilation: **680 Python files passed**.
- Configured smoke checks: **43 passed**, including Phase 8/9 aggregation, current-scorer baseline rebuild, immutable provenance, application execution and mocked fitting.
- Full discovery passed all three real browser runtime tests, the original résumé containment regression and all four new independent loopback security tests.
- Recorded completed outcomes: **1,309 = 1,265 passed, 43 errors, 1 platform skip, 0 assertion failures**. The skip is the existing `AF_UNIX unavailable` condition on Windows, not a browser test exclusion.
- Runtime to the recorded stop request: **2964.192 seconds (49 minutes 24.2 seconds)**. See `full_start.json` / `full_stop.json`. The process was interrupted after identifying unrelated blockers; no normal final unittest summary exists. Counts are parsed completed records, not a claim that the whole suite ran. Any unlogged in-flight work is uncounted.
- Full CI: **BLOCKED / incomplete**, not PASS. `full.log` preserves the execution evidence; `final_integrity_counts.json` lists every error record.

The live status filter initially missed two errors because their completion statuses were on separate lines interleaved with Streamlit warnings. Final parsing accounts for multiline records. The first errors were the recovery tests below, not the later network-support test first noticed during live monitoring. Interim “no reported errors” updates were therefore incomplete; these final counts supersede them.

### Unrelated blockers and independent reproductions

| Group | Full-run errors | Established cause |
| --- | ---: | --- |
| `test_governed_review_recovery_v1_2_1` | 2 | Tests access `AppTest.session_state.filtered_state`; the installed AppTest proxy treats this as a session key and raises `AttributeError`. |
| `test_network_guard_support` | 6 | Its general loopback test wrapper conflicts with the stricter outer audit guard, including wrapped Windows socketpair calls and unscoped IPv4/IPv6 listeners. |
| Ollama diagnostic tests (`test_ollama_prompt_comparison`, `_v1_3`, `test_ollama_unresolved_smoke`) | 35 | Historical raw-hash preservation maps are stale at entry and required diagnostic Markdown files are absent. Errors occur before transport/inference. |

**First error:** `RecoveryTests.test_legacy_session_approval_without_recovery_key_is_not_trusted`:

```text
tests/test_governed_review_recovery_v1_2_1.py:167
    key=next(k for k in app.session_state.filtered_state if k.endswith('_packet'))
streamlit/testing/v1/app_test.py:204
    raise AttributeError(f"{key} not found in session_state.")
AttributeError: filtered_state not found in session_state.
```

The other recovery test fails at line 73 on the same proxy access. Both independently reproduce with the modified guard (**2 errors / 2 tests, 4.177 seconds**) and an isolated copy of the **entry-HEAD guard** (**2 errors / 2 tests, 4.586 seconds**). Their test files and application modules are unchanged. This points to test/API compatibility, not a production browser defect. Full tracebacks: `first_blocker.log` / `baseline_first_blocker.log`.

Network-support reproduction: **19 tests, 12 passed, 6 errors, 1 skip, 4.052 seconds**. The entry-HEAD guard gives the same six errors and skip in 3.479 seconds (`baseline_next_blocker.log`). The first stack is:

```text
test_network_guard_support.py:84 -> asyncio.new_event_loop()
asyncio -> socket._fallback_socketpair -> csock.connect(...)
tests/network_guard_support.py:37 -> original_connect(sock, address)
scripts/offline_release_guard.py:55 -> RuntimeError: Offline checks prohibit network access
```

The preexisting stdlib exception checks the immediate caller. The test wrapper inserts another frame, so the immediate caller is no longer `_fallback_socketpair`. Two additional tests bind real unscoped IPv4/IPv6 listeners, which the outer guard correctly rejects. The other errors are the same event-loop conflict through Streamlit AppTest. Failed loop initialization also emits secondary `_ssock` cleanup diagnostics. Fixing this safely needs a separately bounded IPC/fixture design; this patch does not globally allow loopback or widen the browser capability to IPv6.

The diagnostic reproductions distinguish:

```text
compare_ollama_unresolved_prompts_v1_2.py:freeze_plan -> sha -> read_bytes
FileNotFoundError: .../docs/ollama_unresolved_adjudication_smoke_v1_1.md

compare_ollama_unresolved_prompts_v1_3.py:freeze_plan -> old.validate_plan
ValueError: Protected artifact/runner changed after freeze

smoke_ollama_unresolved_adjudication_v1.py:run -> verify
ValueError: Protected artifact changed

smoke_ollama_unresolved_adjudication_v1.py:recover_runtime -> read_bytes
FileNotFoundError: .../docs/ollama_unresolved_adjudication_smoke_v1.md

smoke_ollama_unresolved_adjudication_v1.py:readiness -> prepare
ValueError: Frozen input/current knowledge changed; benchmark needs review
```

These are portability/preservation prerequisites, not permission to call Ollama. The inspected v1.2 plan has **19 tracked-file hash mismatches already at entry**, and the explainability preservation map has **15 already at entry**; **neither map has a newly introduced mismatch** from this patch. Some stored paths refer to historical source versions, so a raw-hash mismatch does not itself demonstrate a scoring defect. The actual readiness test also rejects an outdated frozen-input/current-knowledge contract before any transport (independent reproduction: one error, 0.208 seconds). Missing-document inventory and hash comparisons are in `diagnostic_hash_analysis.json`; representative exact tracebacks are in `secondary_blocker.log`, `diagnostic_blockers.log` and `readiness_blocker.log`. The interrupted full run does not supply individual final-summary tracebacks for all 35 diagnostic errors; their per-case names are preserved and the distinct observed prerequisite failures were reproduced. No frozen map, independent expectation, diagnostic report or missing Markdown artifact was rewritten to obtain a pass.

Focused reproduction commands used the same launcher/prefix above, followed by:

```text
tests.test_network_guard_support
tests.test_governed_review_recovery_v1_2_1.RecoveryTests.test_legacy_session_approval_without_recovery_key_is_not_trusted
tests.test_governed_review_recovery_v1_2_1.RecoveryTests.test_reopen_and_code_reload_recovers_exact_real_approval_without_writes
tests.test_ollama_prompt_comparison.PromptComparisonTests.test_preflight_is_metadata_only
tests.test_ollama_prompt_comparison_v1_3.SourceFirstTests.test_metadata_only_and_twenty_serial_requests
tests.test_ollama_unresolved_smoke.LocalSmokeTests.test_preflight_no_inference_and_import_is_passive
tests.test_ollama_unresolved_smoke.RuntimeRecoveryTests.test_basic_mode_only_one_request
tests.test_ollama_unresolved_smoke.LocalSmokeTests.test_actual_readiness_validator_no_new_labels
```

The entry-guard comparisons used `git show HEAD:scripts/offline_release_guard.py` copied into a task-owned disposable module, loaded by its own `sitecustomize` in a child process with the existing guard environment contract. No checkout file was restored or replaced. The same focused runner executed the named tests beneath that guard. These comparisons establish that the network/recovery failures predate this patch. No unrelated implementation fixes or additional full-suite rerun were attempted.

## Integrity and compatibility

The entry SHA-256 ledger covers **981 tracked files plus the preserved dashboard report**. Final comparison: **979 unchanged, exactly three existing files changed**, matching the inventory. The new capability, security tests and requested report are additional. All production files and historical oracles match entry bytes, including published v1.17, coordinated v1.20/v1.21, metadata v1.22/v1.23, résumé rendering/fitting, Job Finder, Phase 8, Application Sessions, browser capture persistence and application routes. No experimental gate, scoring fingerprint or version constant changed.

The 74-test run verifies related browser persistence/mapping contracts and the original résumé overflow sequence. Full discovery additionally exercised scoring/source-selection/currentness/preview safeguards through the reached modules, but this report does not claim that every later test completed. Existing frozen diagnostic hash mismatches were not created or repaired by this patch.

The two existing files under `outputs/` were checked by metadata only (size and nanosecond modification time), without opening résumé contents, and remained identical across full execution. All guarded test writes stayed in disposable scratch; SQLite outside it remained rejected. New tests use generated tokens, disposable synthetic databases and local HTTP, with no live candidate or production-database access. Negative external probes are audit-only and do not send traffic.

Per-fixture cleanup closes listeners/threads, restores module paths and removes temporary probe programs/databases. The full launcher intentionally retains its task-owned scratch and logs for local review; interrupted-run residue is confined there. `reports/browser_bridge_ci_runtime/` is ignored by existing rules and must not be staged. No existing user artifact was deleted or uploaded.

Final checks:

- Syntax parsing: **PASS for all five changed/new Python files**. Imports, focused execution and full-run compilation also passed.
- `git diff --check` / `git diff --cached --check`: **PASS**; staged diff empty.
- Branch and HEAD unchanged from entry.
- The unrelated `coordinated_batch_dashboard_review.md` remains byte-for-byte unchanged.
- Changed existing files: only the two audit-hook infrastructure files and browser runtime test listed above.
- New task files: capability module, independent security tests and this report. No workflow, production, taxonomy/registry, database, historical fixture or version change.

## Verdicts

| Decision | Verdict |
| --- | --- |
| Browser-runtime test | **PASS**, real HTTP, standalone and full discovery |
| Network containment preserved | **PASS**, explicit one-listener scope, negative and inheritance controls |
| Related browser tests | **PASS**, 74/74 including security and résumé controls |
| Full CI | **BLOCKED / incomplete**, 43 unrelated errors recorded |
| Production behavior unchanged | **PASS**, production hashes unchanged |
| Ready for checkpoint | **NO for a full-CI-cleared checkpoint** |

The bounded browser isolation fix is ready for code review. Remaining work is separately scoped test/API compatibility, IPC isolation and diagnostic-fixture portability; no broad permission grant or frozen-expectation refresh is recommended. Nothing was staged, committed, pushed or merged.
