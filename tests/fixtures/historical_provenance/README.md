# Portable authenticated historical source inputs

These three source-only files were extracted with `git --no-replace-objects
show <full-revision>:<original-path>` from reachable local commit trees. No
source was reconstructed from current code. They contain repository Python
implementation text, not candidate data, database records or model output.

| Fixture | Revision | Original path | Git blob |
|---|---|---|---|
| stage2d_stable_evidence_scoring.py.txt | 3e6ff34501b4d68cbe3e66b55ec8af5b0e288026 | analysis_stability/stable_evidence_scoring.py | db453efe860f0a561ce132064859f2c194a54738 |
| v122_stable_evidence_scoring.py.txt | 07912485d4803f355a760f2623a4a08f5b729fa2 | analysis_stability/stable_evidence_scoring.py | ae44831634cb3467800b72ea1e2950b0a3cc2fd5 |
| v122_jd_metadata_policy.py.txt | 07912485d4803f355a760f2623a4a08f5b729fa2 | analysis_stability/jd_metadata_policy.py | f59d01e7f77cc0b3f9f744a959c04e8c61065b74 |

Sizes and SHA-256 pins are in `scripts/historical_source_fixtures.py`.
Stage 2D's SHA-256 is independently present in the pre-existing unchanged
`coordinated_action_ownership_oracle_v1.json` production source map. The v1.22
pins preserve the exact source pair previously selected by the checkpoint test;
the policy equality and historical/current analysis assertions are unchanged.
The loader checks full revision/path registration, byte count, SHA-256 and Git
blob identity. A missing or corrupt fixture is an error; there is no Git lookup
or current-source fallback at runtime. `.gitattributes` preserves original LF
bytes on both CI platforms. `.py.txt` prevents accidental test discovery/import.

Tests execute these sources in an explicitly historical module namespace using
the current test dependency environment, as they did before the portability
repair. This validates the stated current/historical compatibility assertions;
it is **not historical Ollama experiment reproduction** and supplies no missing
runtime recipe or ignored predicate-research report. Those claims remain separate.
