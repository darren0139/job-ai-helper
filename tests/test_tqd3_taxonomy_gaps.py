import json
import sys
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from taxonomy_discovery.regression_corpus import CORPUS_VERSION
from taxonomy_discovery.taxonomy_gaps import aggregate_corpus_gaps
from tests.tqd3_publication_fixture_support import PublicationFixture


def gap_corpus():
    rows = [{"requirement_id":str(i),"requirement_text":text,"importance":"required","score_eligible":True,
             "resolution_status":"unresolved","retrieval_suggestions":[{"capability_id":"language.modern_cpp","score":0.4}]}
            for i,text in enumerate(["Experience with ZetaNovelTool","Experience with MongoDB","C++","design resilient payment workflows","other"])]
    jobs = [{"job_id":jid,"snapshot_id":jid+10,"job_content_hash":"fixture","versions":{"taxonomy_version":"old"},
             "requirements":deepcopy(rows)} for jid in (1,2)]
    return {"corpus_version":CORPUS_VERSION,"jobs":jobs}


class TaxonomyGapTests(unittest.TestCase):
    def test_routes_exact_aggregation_provenance_and_zero_mutation(self):
        with PublicationFixture() as f:
            corpus = gap_corpus()
            frozen = deepcopy(corpus)
            report = aggregate_corpus_gaps(corpus)
            self.assertEqual(report["job_count"],2)
            self.assertEqual(corpus,frozen)
            by_example = {r["examples"][0]:r for r in report["observations"]}
            self.assertEqual(by_example["Experience with ZetaNovelTool"]["recommended_research_route"],"technology_identity")
            self.assertEqual(by_example["Experience with MongoDB"]["recommended_research_route"],"technology_relationship")
            self.assertEqual(by_example["C++"]["recommended_research_route"],"resolver_issue/already_covered")
            self.assertEqual(by_example["design resilient payment workflows"]["recommended_research_route"],"capability_gap")
            self.assertEqual(by_example["other"]["recommended_research_route"],"ambiguous/noise")
            for gap in report["observations"]:
                self.assertEqual(gap["occurrence_count"],2)
                self.assertEqual(gap["job_count"],2)
                self.assertEqual(len(gap["provenance"]),2)
                self.assertEqual(gap["importance_distribution"],{"required":2})
                self.assertTrue(gap["retrieval_suggestions"])
            self.assertFalse(report["governance"]["proposal_creation"])
            self.assertFalse(report["governance"]["scoring_influence"])
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)
            f.network_guard.assert_not_called()
            f.embedding_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_resolved_ineligible_duplicate_and_missing_provenance(self):
        with PublicationFixture():
            corpus = gap_corpus()
            row = corpus["jobs"][0]["requirements"][0]
            corpus["jobs"][0]["requirements"].append(deepcopy(row))
            corpus["jobs"][0]["requirements"][1]["score_eligible"] = False
            corpus["jobs"][1]["requirements"][1]["resolution_status"] = "resolved"
            report = aggregate_corpus_gaps(corpus)
            self.assertEqual(len(report["observations"]),4)
            zeta = next(r for r in report["observations"] if "ZetaNovelTool" in r["examples"][0])
            self.assertEqual(zeta["occurrence_count"],2)
            corpus["jobs"][0]["job_content_hash"] = ""
            self.assertTrue(aggregate_corpus_gaps(corpus)["excluded"])

    def test_ui_upload_and_cli_are_diagnostics_only(self):
        from taxonomy_discovery.corpus_review_ui import render_corpus_research_inputs
        from tests.test_tqd3_publication_ui import FakeStreamlit
        with PublicationFixture() as f:
            corpus = gap_corpus()
            st = FakeStreamlit()
            st.file_uploader = lambda *args,**kwargs: SimpleNamespace(getvalue=lambda: json.dumps(corpus).encode())
            with patch.dict(sys.modules,{"streamlit":st}):
                render_corpus_research_inputs()
            self.assertTrue(any(message[0]=="dataframe" for message in st.messages))
            from scripts.tqd3_regression_corpus import main
            input_path, output_path = f.tmp/"corpus.json", f.tmp/"gaps.json"
            input_path.write_text(json.dumps(corpus))
            self.assertEqual(main(["gaps","--corpus",str(input_path),"--output",str(output_path)]),0)
            output = json.loads(output_path.read_text())
            self.assertTrue(output["governance"]["research_input_only"])
            self.assertEqual(output["job_count"],2)
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)
