# Governed Review UI V1.2

The shared unresolved-requirement review panel presents Inspect → Preview →
Validate → Approve → Publish with completed, pending, blocked and failed states.
Validation outcomes and action errors appear beside their action. Successful
approval records its returned receipt and immediately invokes the existing
read-only approval-readiness preflight. No second click is needed to see
“Approved — Ready for publication”, the target version and zero blockers.
The readiness button remains an explicit read-only retry.

Publication still requires its own confirmation and button. Successful approval
and publication disable duplicate submissions. Publication displays the actual
receipt and refreshed native versions, retaining them across the rerun caused
by that publication. Historical analyses are not refreshed.

Session results are bound to the requirement input, native versions, knowledge
fingerprint, preview version and draft/regression contents. Switching or changing
these invalidates stale results and confirmation widgets. A new preview or
validation explicitly clears downstream state. Rerenders perform no validation,
approval or publication. Failed preflight clears old readiness, preserves a
successful approval and offers a read-only retry.

Advanced diagnostics contains raw JSON, fingerprints and complete control rows.
The privacy-sanitized debug bundle remains available. Governance contracts,
production resolution, scoring, taxonomy, registry and database schemas are
unchanged. Focused AppTest coverage mocks all live governance mutations;
existing end-to-end governance tests operate solely on disposable artifacts.
