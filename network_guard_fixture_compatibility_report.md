# Network guard fixture compatibility

## Repository and result

Repository: `C:\Users\Admin\Documents\GitHub\Job-AI-Helper-Codex-Resolver`.
Branch: `fix/network-guard-fixture-compatibility`.
Entry HEAD: `e005807d486427a906bc80c1bbd50111a2d3973c`.
Entry status: only the unrelated untracked `coordinated_batch_dashboard_review.md`.

The six original errors still reproduced after the AppTest checkpoint. The bounded repair fixes all six without changing production networking, browser permissions or scoring. Required focused validation completed with **54 passed, one existing Windows platform skip and no failures/errors**. Full CI was not rerun.

## Independent before-fix reproduction

Interpreter: `venv/evidence-completeness-runtime/environment/Scripts/python.exe`, CPython 3.13.12, Windows. Exact command:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/network_guard_compat_runtime tests.test_network_guard_support
```

Before: **19 tests; 12 passed, 6 errors, 1 `AF_UNIX unavailable` skip; 19.272 seconds**. Complete per-test tracebacks are retained in `reports/network_guard_compat_runtime/before.log`.

| Remaining failing test (`NetworkGuardTests`) | Intended real behavior | Failed socket operation / cause |
| --- | --- | --- |
| `test_asyncio_native_event_loop_runs_and_closes` | Native Windows ProactorEventLoop runs a coroutine and closes | AF_INET internal socketpair connect through the test wrapper; outer guard loses its immediate stdlib caller. |
| `test_fallback_socketpair_connect_is_allowed` | Real stdlib fallback pair exchanges bytes and closes | Same wrapped AF_INET connect. |
| `test_real_ipv4_connect_is_allowed_without_external_attempt` | Real local TCP listener/client, no external-attempt recording | Unscoped AF_INET bind at `127.0.0.1:0`. |
| `test_real_ipv6_connect_if_supported` | Real IPv6 loopback TCP transport | Unscoped AF_INET6 bind at `[::1]:0`. |
| `test_streamlit_from_file_under_guard` | Actual AppTest executes its file and renders expected Markdown | Native event-loop construction reaches the wrapped internal socketpair connect. |
| `test_streamlit_from_string_under_guard` | Actual AppTest executes its string and renders expected Markdown | Same native event-loop construction failure. |

Representative connect traceback:

```text
test_network_guard_support.py -> asyncio.new_event_loop()
asyncio.windows_events / proactor_events -> socket.socketpair()
socket.py:_fallback_socketpair -> csock.connect((addr, port))
tests/network_guard_support.py:37 -> original_connect(sock, address)
scripts/offline_release_guard.py:55
RuntimeError: Offline checks prohibit network access
```

The two listener tests instead fail directly at `server.bind` with the same guard RuntimeError. Their `except OSError` does not suppress a policy denial. Failed event-loop construction also caused secondary `_ssock` cleanup diagnostics; those are consequences of initialization failure, not a separate production defect.

The AppTest checkpoint corrected public session-state access. It cannot repair event-loop construction failing before the test script runs. These six errors are test-fixture/audit integration incompatibilities, not production bridge, approval or standard-library defects.

## Selected bounded design

### Transparent stdlib IPC ownership verification

Both audit hooks previously checked the immediate frame's module/function name. `block_external_network_allow_loopback` legitimately delegates to the active original connect, adding a frame. Its loopback filter and restoration contract remain unchanged.

New `scripts/offline_socketpair.py:stdlib_socketpair_allowed` captures the real CPython `socket._fallback_socketpair.__code__` before test wrappers are installed. For each bind/connect event, it finds that exact code object on the current thread's active stack and additionally requires:

- Bind: the audited socket is that constructor frame's own `lsock`, TCP stream, AF_INET/AF_INET6, and the address is exactly `127.0.0.1:0` / `[::1]:0`.
- Connect: the audited socket is that frame's own `csock`, with matching family and stream type, and the destination equals its live listener's actual literal loopback address and allocated port.

A trusted frame alone cannot authorize another socket, peer, wildcard, fixed port or DNS operation. Function names, module names and filenames confer no permission. Transparent wrappers can remain active, preserving their external-attempt accounting. Frame references are released in `finally`; there is no stored grant, environment flag or thread/process-inherited permission.

This replaces the existing stdlib IPC exception rather than adding a general network lane. The prior exception already admitted internal IPv4/IPv6 socketpair operations; the new check adds socket ownership and code-identity verification while supporting delegation. It is not a blanket call-stack filename allowance. Arbitrary Python/native-code sandboxing is outside the existing audit-hook trust model.

### Real listener fixtures

- IPv4: the existing explicit `loopback_http_scope()` contains the original ephemeral listener/client. Connections still pass through the real fixture wrapper. Closed server/client descriptors are asserted afterward.
- IPv6: the fixture uses the actual stdlib AF_INET6 fallback socketpair, whose implementation creates, connects, accepts and closes an ephemeral TCP listener. Both real IPv6 sockets and byte exchange are asserted, then both descriptors are closed. This preserves the real IPv6 transport/delegation contract through constructor-owned IPC. It does not grant general IPv6 listener permission or extend the browser capability.
- Native asyncio, fallback IPC and both AppTest tests retain their original real execution and assertions. No event-loop policy, coroutine, AppTest runner or HTTP server is mocked away.

The platform-only IPv6 `OSError` handling and Windows `AF_UNIX` skip were not converted into policy-denial skips. IPv6 transport passed on this host. No failing coverage was removed or permanently skipped.

## Exact changed files

| File | Change |
| --- | --- |
| `scripts/offline_socketpair.py` (new) | Shared stateless code/socket-ownership predicate for the preexisting stdlib IPC exception. |
| `scripts/offline_release_guard.py` | Replace the immediate caller-name IPC check with the shared ownership check. |
| `scripts/run_coordinated_preview_checks.py` | Use the same predicate in its second connect audit hook. |
| `tests/test_network_guard_support.py` | Scope the real IPv4 listener; use constructor-owned real IPv6 TCP IPC; assert descriptor cleanup. |
| `tests/test_offline_socketpair_security.py` (new) | Three independent guarded-child security tests, reusing the existing safe probe launcher. |
| `network_guard_fixture_compatibility_report.md` (new) | This report. |

`tests/network_guard_support.py`, `scripts/offline_loopback.py`, the outer launcher, production files, prior AppTest fixes and historical expected-result fixtures are unchanged. No extra dependency or ignored diagnostic file is required by the committed tests.

## Security boundary and independent evidence

Default denial remains effective for external IPv4/IPv6, arbitrary loopback use, wildcard binds, DNS, UDP, unauthorized filesystem writes and non-disposable SQLite. The browser scope remains exactly its original one IPv4 TCP listener and exact client endpoint; its code is byte-for-byte unchanged.

New controls verify:

1. A forged `_fallback_socketpair` function with module name `socket` and even the real stdlib filename is rejected: its code identity is different.
2. During a genuine constructor call, another socket cannot bind or connect to the constructor's peer. Even its real listener cannot audit-authorize wildcard/external binds or a fixed port. Its real client cannot authorize another IPv4/IPv6 destination, alternate port or a listener bind. DNS remains denied. Legitimate IPC still exchanges bytes through patched bind/connect delegates afterward.
3. While that constructor is active, an unrelated thread and a fresh Python child still cannot bind. Three repeated exception-path runs restore the fixture's connect wrapper and close both sockets; subsequent unscoped operations remain denied.

External-address and wildcard negative probes invoke actual installed audit hooks using `sys.audit`, without transport syscalls; they cannot contact external services even on assertion failure. Real negative loopback attempts are denied before OS binding. Positive tests use only synthetic local TCP/IPC.

The existing four loopback security tests additionally exercise default denial, copied thread contexts, Python child isolation, filesystem/SQLite restrictions and uncontained child rejection. Real browser HTTP health/authentication still returns the expected 200/401/403 outcomes and closes its listener/thread. Recovery tests retain SQL read-only authorization, fingerprint/source validation, stale/legacy rejection and unchanged store/taxonomy bytes.

## Validation results and commands

All behavioral tests used the original contained launcher with disposable scratch. Sources were stable within each run. Common command prefix:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/network_guard_compat_runtime
```

| Selection following that prefix | Result | Unittest runtime |
| --- | --- | ---: |
| `tests.test_network_guard_support` before fix | 12 passed, 6 errors, 1 platform skip / 19 | 19.272 s |
| Same complete module after initial repair | 18 passed, 1 platform skip / 19 | 12.166 s |
| Module plus `tests.test_offline_socketpair_security` | 21 passed, 1 platform skip / 22 | 35.013 s |
| Required combined regression selection below | **54 passed, 1 platform skip / 55; zero failures/errors** | **94.565 s** |
| Final strengthened `tests.test_offline_socketpair_security` | **3/3 passed**, no skips | **10.520 s** |

The final security-only rerun followed stronger constructor-owned bind and forged-filename probes; guard/fixture implementations were unchanged from the successful required run. Exact required command:

```powershell
& venv/evidence-completeness-runtime/environment/Scripts/python.exe -B scripts/run_offline_release_checks.py --scratch-root reports/network_guard_compat_runtime tests.test_network_guard_support tests.test_offline_socketpair_security tests.test_browser_bridge_runtime tests.test_offline_loopback_security tests.test_governed_review_recovery_v1_2_1 tests.test_unresolved_requirement_review_ui
```

This includes all named required modules. It preserves the previous AppTest compatibility fix and verifies real browser health/authentication, the original loopback security boundary and the complete repaired network module.

### Additional direct-consumer run: stopped, not green

An additional run used the required selection followed by:

```text
tests.test_per_jd_taxonomy_status
tests.test_post_publication_accounting
tests.test_scoring_eligibility_calibration
tests.test_technology_maintenance_batch
tests.test_tqd3_production_resolver_inspector
tests.test_tqd3_research_readiness
tests.test_unresolved_adjudication
```

It was stopped in the first extra module after accounting failures appeared. Parsed completed records: **56 passed, 6 errors, 2 assertion failures, 1 existing platform skip**, with one unfinished logged test and no final unittest summary. Later extra modules were not reached. `focused.log` and `integrity_and_counts.json` retain all names; this incomplete broader selection is not counted as a pass.

Two representative cases were independently reproduced under the new guard and under a disposable copy of the unchanged entry-HEAD guard:

```text
tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_incomplete_accounting_keeps_positive_proofs_without_requiring_all_rows
tests.test_per_jd_taxonomy_status.PerJDTaxonomyTests.test_live_aggregate_without_review_sums_occurrences_and_additional_items
```

Both runs gave one error and one assertion failure (new guard: 1.061 s; entry guard: 0.845 s). Exact causes:

```text
test_per_jd_taxonomy_status.py:173 -> view -> coverage_presentation.py:198
ValueError: Stale/incompatible analysis: scoring_version

test_per_jd_taxonomy_status.py:108
AssertionError: (0, 0, None) != (23, 23, 100)
```

The frozen job-163 analysis in `tests/fixtures/per_jd_scoring_audit.json` uses `stable-evidence-v1.16-phase6d20`; published current scoring is v1.17. The stale analysis is rejected/excluded instead of satisfying the accounting expectation. The fixture, production accounting, versions and expected totals match entry bytes. These representative failures predate this patch; no socket permission could resolve their version mismatch. Remaining extra accounting cases were not individually repaired or fully triaged. No frozen fixture was restamped and no production policy/assertion was changed.

The baseline comparison copied `git show HEAD:scripts/offline_release_guard.py` into task scratch and loaded it via its own guarded child `sitecustomize`, using the original disposable environment contract. No checkout file was restored or replaced.

## Integrity and remaining CI work

Entry SHA-256 ledger: **985 tracked files plus the unrelated dashboard report**. Final comparison: **983 unchanged and exactly three existing files changed**, as listed above. The two new Python files and this report are additional. All production browser/authentication, résumé, Job Finder, Phase 8, Application Session, database/cache, taxonomy/registry and scorer files remain unchanged, including v1.17, v1.20/v1.21 and v1.22/v1.23 identities and gates. The prior AppTest checkpoint and browser capability match entry hashes. The unrelated dashboard report is preserved byte-for-byte.

All five changed/new Python files pass syntax parsing; guarded imports/execution pass. `git diff --check` and `git diff --cached --check` pass, with an empty staged diff. Branch and HEAD are unchanged. No real database/candidate record, saved analysis, production artifact or external service was used. Test stores, synthetic tokens, temporary scripts and output remain under ignored `reports/network_guard_compat_runtime/`. Fixture contexts clean their sockets/threads/event loops and restore patches; launcher scratch/logs are retained locally for review. No user data was cleaned or uploaded.

Full CI was **NOT RERUN**, as requested. Frozen Ollama diagnostic prerequisites remain unmodified and require their separate investigation. The additional stale per-JD accounting fixture also needs separate review before a comprehensive green-CI claim. This task does not establish a current full-suite error total.

## Verdicts

| Decision | Verdict |
| --- | --- |
| Network fixture tests | **PASS**, all six original errors fixed; 18 passes and one existing platform skip |
| Default network containment | **PASS**, ownership/endpoint and default-denial controls passed |
| Browser integration security | **PASS**, real HTTP and existing loopback controls |
| Production unchanged | **PASS**, protected hashes unchanged |
| Ready for isolated checkpoint | **YES**, bounded infrastructure/test changes and this report |
| Full CI | **NOT RERUN**, broader unrelated blockers remain |

Nothing was staged, committed, pushed, merged or switched. Stop for review.
