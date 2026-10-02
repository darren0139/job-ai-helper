"""Zero-cost v1.7 publication proof. Only temporary production knowledge is written."""
from __future__ import annotations

from tests.tqd3_publication_fixture_support import PublicationFixture
from taxonomy_discovery.focused_verification_preview import build_focused_impact_preview
from taxonomy_discovery.technology_registry import resolve_requirement_text, get_default_registry
from tailoring.phase6d_stable_scoring_adapter import cap_requirement_with_taxonomy
from job_discovery.matching import current_match_versions


def main():
    with PublicationFixture() as f:
        baseline = f.registry_path.read_bytes()
        assert resolve_requirement_text(f.requirement["text"])["status"] == "unresolved"
        assert f.interpretation["outcome"] == "verified_registry_relationship"
        assert build_focused_impact_preview(f.draft, f.snapshots())["would_resolve_after"] == 1
        f.approve()
        assert f.registry_path.read_bytes() == baseline
        assert resolve_requirement_text(f.requirement["text"])["status"] == "unresolved"
        f.publish()
        resolved = cap_requirement_with_taxonomy(f.requirement)
        assert resolved["capability_id"] == f.capability
        assert resolved["match_label"] == "none"
        assert current_match_versions()["technology_registry_version"] == get_default_registry().version
        assert f.real_registry.read_bytes() == f.real_registry_bytes
        f.network_guard.assert_not_called()
        f.embedding_guard.assert_not_called()
        f.model_guard.assert_not_called()
    print("TQ-D3 v1.7 publication smoke PASS: approval_is_publication=false explicit_publish=true temporary_registry_only=true runtime_resolution=active network=0 model=0 evidence_not_upgraded=true")


if __name__ == "__main__":
    main()
