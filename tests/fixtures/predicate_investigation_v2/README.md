# Original existing-predicate V2 research artifacts

`report.json` and `manifest.json` are exact original Git blob bytes recovered
from pre-existing Codex checkpoint **tree**
`0a406ec1799434ed1c66f360191f8bd10c5c3b27`. This is not a commit and was not
created during recovery. Its existing ref encodes 2026-10-15 01:42:07.843 +08:00;
that ref timestamp is metadata, not an independently signed timestamp.
Full ref, paths, Git blob IDs, byte counts and SHA-256 are in `provenance.json`.
The same tree preserves the companion investigation document and original script.

The archived report and manifest predate the current recovery. Their complete
contents, all 13 input rows/source versions, 150 protected hashes, allocations,
analyst conclusions and internal seals are unchanged. No resolver, model or
historical database reconstruction was run to create these copies. The original
tests still perform their original assertions using these authenticated inputs.
This does not certify the underlying original database or reproduce the research.

Archived bytes use LF. Current ignored local reports use CRLF; they have identical
parsed data and identical bytes after CRLF-to-LF normalization. These fixtures
were extracted directly from Git, not normalized/regenerated from local reports.
Their hashes deliberately describe the original Git bytes, not the different
raw CRLF files. Neither original local file nor its expected identity was changed.

Privacy review: requirement/JD text, capability observations, source/job/snapshot
IDs, software identities, aggregate database metadata and protected-file hashes
are present. No applicant résumé/evidence payload, credentials, email address,
absolute local path or model output was found. Existing `safe_history` filtering
is preserved. Do not add the real database or other research bundles here.

`tests/predicate_historical_fixtures.py` checks complete SHA-256, Git blob identity,
internal seals and the pair's expected manifest identity. The byte pins are
independent of the runtime resolver and of the artifact self-seals. Missing or
modified fixtures fail; there is no fallback to ignored reports/current output.
Normal CI needs only this tracked set, not the local checkpoint ref or any Git
history. `.gitattributes` preserves the archived bytes on Windows and Unix.
