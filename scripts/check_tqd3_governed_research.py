"""Zero-cost H.1 smoke: fake provider, frozen fixture, temporary stores only."""
from unittest.mock import Mock
from tailoring.capability_taxonomy import TAXONOMY_PATH
from taxonomy_discovery import governed_research as h1
from taxonomy_discovery.regression_corpus import build_regression_corpus
from database.taxonomy_discovery_review_manager import save_governed_research_draft, save_governed_research_review
from tests.test_tqd3_regression_corpus import frozen_snapshot
from tests.test_tqd3_governed_research import rules, fake_raw
from tests.tqd3_publication_fixture_support import PublicationFixture


def main():
    with PublicationFixture() as f:
        taxonomy_before = TAXONOMY_PATH.read_bytes()
        registry_before = f.registry_path.read_bytes()
        corpus = build_regression_corpus([frozen_snapshot("Node.js")])
        prepared = h1.prepare_gap_review(corpus=corpus)
        candidate = next(c for c in prepared["candidates"] if c["candidate_route"] == "technology_relationship")
        plan = h1.research_plan(prepared["candidates"], selected_candidate_ids=[candidate["candidate_id"]])
        subject = plan["targets"][0]["subject"]
        fake = Mock(return_value=fake_raw(subject,subject+" is a runtime for backend API development."))
        options = dict(explicit_execution=True,transport=fake,db_path=f.tmp/"h1.sqlite",
                       authority_registry_path=rules(f,[subject]))
        first = h1.execute_plan(plan,prepared["candidates"],**options)
        assert not first["failures"]
        assert h1.execute_plan(plan,prepared["candidates"],**options) == first
        fake.assert_called_once()
        result = first["results"][0]
        assert not result["approval"]
        draft = h1.create_draft(result,explicit_creation=True)
        save_governed_research_draft(result,draft,db_path=options["db_path"],proposal_db_path=f.proposal_db)
        report = h1.temporary_impact(corpus,draft)
        assert report["affected_jobs"] and not report["score_increase_is_correctness"]
        review = save_governed_research_review(result["research_result_id"],result_fingerprint=result["result_fingerprint"],
            decision="approve_for_publication",reviewer="TEST ONLY",regression=report,db_path=options["db_path"])
        assert not review["publication"]
        assert f.registry_path.read_bytes() == registry_before
        assert f.real_registry.read_bytes() == f.real_registry_bytes
        assert TAXONOMY_PATH.read_bytes() == taxonomy_before
        f.network_guard.assert_not_called()
        f.embedding_guard.assert_not_called()
        f.model_guard.assert_not_called()
    print("TQ-D3 H.1 smoke PASS: fake_provider_requests=1 cache_reused=true native_temporary_impact=true human_decision_separate=true production_mutations=0 network=0 model=0")


if __name__ == "__main__":
    main()
