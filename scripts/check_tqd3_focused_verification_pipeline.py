"""Zero-cost v1.6 integration smoke using a fake Search transport and temporary DB."""
from __future__ import annotations

import tempfile
from pathlib import Path

from database.taxonomy_discovery_review_manager import list_focused_verification_results
from taxonomy_discovery.focused_verification_targets import build_focused_verification_target
from taxonomy_discovery.focused_verification import execute_focused_verification, interpret_focused_verification, build_focused_draft
from taxonomy_discovery.focused_verification_preview import build_focused_impact_preview


def main():
    target = build_focused_verification_target({"bucket": "confirmed", "candidate_id": "smoke",
        "canonical_name": "ZeroMQ", "taxonomy_capabilities": []})
    calls = []
    def fake(endpoint, payload, headers, timeout):
        calls.append(payload)
        return {"request_id": "v16-smoke", "results": [{"title": "ZeroMQ", "url": "https://zeromq.org/",
                "content": "ZeroMQ is a messaging library."}]}
    with tempfile.TemporaryDirectory() as tmp:
        options = dict(selected_target_ids=[target["target_id"]], explicit_execution=True,
                       db_path=Path(tmp) / "review.sqlite3", api_key="fake", transport=fake)
        row = execute_focused_verification([target], **options)[0]
        assert execute_focused_verification([target], **options)[0] == row
        assert len(calls) == 1
        assert len(list_focused_verification_results(db_path=options["db_path"])) == 1
        interpreted = interpret_focused_verification(row["result"])
        assert interpreted["outcome"] == "verified_identity"
        draft = build_focused_draft(row["result"], interpreted)
        assert draft["status"] == "draft" and draft["requires_human_approval"]
        assert not build_focused_impact_preview(draft, [])["available"]
        assert not draft["scoring_influence"]

        cpp_target = build_focused_verification_target({
            "bucket": "confirmed",
            "candidate_id": "cpp-smoke",
            "canonical_name": "C++",
            "taxonomy_capabilities": ["language.modern_cpp"],
        })
        cpp_result = {
            "provider_request_id": "persisted-cpp-smoke",
            "target_id": cpp_target["target_id"],
            "candidate_id": cpp_target["candidate_id"],
            "target": cpp_target,
            "raw_provider_response": {
                "results": [{
                    "title": "ISO C++",
                    "url": "https://www.iso.org/standard/68564.html",
                    "content": "C++ is a general purpose programming language.",
                }]
            },
        }
        cpp_interpretation = interpret_focused_verification(cpp_result)
        assert cpp_interpretation["outcome"] == "verified_registry_relationship"
        assert cpp_interpretation["relationship_evidence"]["basis"] == "exact_internal_taxonomy"
        cpp_draft = build_focused_draft(cpp_result, cpp_interpretation)
        assert cpp_draft["action"] == "add_technology_capability_relationship"
        assert cpp_draft["proposal_bundle"]["proposals"][0]["entry_kind"] == "language"
    print("TQ-D3 v1.6.1 pipeline smoke PASS: explicit=true fake_transport=true reload_network=0 cpp_saved_reinterpret=true exact_internal_relationship=true model=0 mutation=0 draft_only=true missing_snapshot=closed scoring_influence=false")


if __name__ == "__main__":
    main()
