"""Observed H.0.1 failure shapes; deterministic local fixtures only."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import sys
import unittest
from unittest.mock import patch

from taxonomy_discovery.candidate_refinement import concept_key, candidate_report, technology_entities
from taxonomy_discovery.taxonomy_evolution import gap_candidates, overlap_check
from taxonomy_discovery.taxonomy_gaps import GAP_VERSION
from tests.test_tqd3_taxonomy_evolution import gap
from tests.tqd3_publication_fixture_support import PublicationFixture


def candidate(text,terms=None,route="capability_gap"):
    row=gap(text,route)
    row["technology_terms"]=terms or []
    return gap_candidates({"gap_version":GAP_VERSION,"observations":[row]})[0]


class RefinementTests(unittest.TestCase):
    def test_wrapper_keys_only_strip_declared_prefixes(self):
        for prefix in ("knowledge of ","experience with ","experience in ","proficiency in ","familiarity with ","understanding of "):
            self.assertEqual(concept_key(prefix+"network access control"),"network access control")
        self.assertNotEqual(concept_key("database access control"),concept_key("network access control"))
        self.assertEqual(concept_key("working knowledge of network access control"),"working knowledge of network access control")

    def test_administrative_real_shapes(self):
        with PublicationFixture():
            for text in ("160 Robinson Road #13-07 Singapore 068914","Submit your application for software design projects",
                "By applying you consent to personal data processing","Only shortlisted applicants will be notified",
                "Citizenship and application eligibility","Willing to work shifts","Our company is a leading provider of software systems",
                "A part of HPB strives to reduce the burden of diseases"):
                self.assertEqual(candidate(text)["candidate_route"],"administrative_or_non_capability",text)

    def test_duration_credential_no_new_capability(self):
        with PublicationFixture():
            for text in ("5 years of software design","2-5 years experience in network access control",
                         "Bachelor's degree in software engineering","Academic qualifications in computing","Professional certification"):
                result=candidate(text)
                self.assertIn(result["candidate_route"],{"administrative_or_non_capability","existing_capability_resolver_issue"},text)
            self.assertEqual(candidate("5 years of experience")["candidate_route"],"existing_capability_resolver_issue")

    def test_real_data_governance_requirement_is_technical_review(self):
        text=("implement data governance practices in line with singapore government "
              "data classification requirements including access controls data masking "
              "anonymisation and audit logging for sensitive transport and personal data")
        with PublicationFixture():
            c=candidate(text)
            self.assertIn(c["candidate_route"],{"possible_new_capability","existing_capability_resolver_issue",
                "insufficient_signal","technology_identity","technology_relationship"})
            self.assertEqual(c["normalized_cluster"],text)
            self.assertEqual(c["examples"],[text])

    def test_personal_data_privacy_words_alone_are_not_administrative(self):
        with PublicationFixture():
            for text in (
                "Implement access control and audit logging for sensitive personal data",
                "Apply data classification and anonymization to personal data with masking controls",
                "Design privacy policy enforcement and data consent management for sensitive data",
                "Record consent to data processing securely using access control and audit logging",
                "Build data governance controls for personal data anonymisation"):
                self.assertIn(candidate(text)["candidate_route"],{"possible_new_capability","existing_capability_resolver_issue",
                    "insufficient_signal","technology_identity","technology_relationship"},text)

    def test_application_privacy_notices_and_other_admin_boundaries_preserved(self):
        with PublicationFixture():
            for text in (
                "only shortlisted candidates will be notified",
                "by submitting your application for this position you consent to the collection use and disclosure of your personal data ...",
                "You hereby consent to the collection of your personal data for recruitment",
                "Applicants consent to processing of personal data for this position",
                "Submit your resume using the application portal",
                "160 Robinson Road #13-07 Singapore 068914",
                "Citizenship and application eligibility requirements",
                "Shift availability and working hours must be confirmed"):
                self.assertEqual(candidate(text)["candidate_route"],"administrative_or_non_capability",text)

    def test_fragments_softskills_and_generic_technical_words_failclosed(self):
        with PublicationFixture():
            for text in ("software development","including relevant systems","various IT domains","etc","a good team player",
                         "Excellent interpersonal communication skills"):
                self.assertIn(candidate(text)["candidate_route"],{"insufficient_signal","ambiguous_or_noise"},text)

    def test_weak_overlap_not_semantic_equivalence(self):
        with PublicationFixture():
            cases=(("data analysis and insights","algorithms.data_structures_algorithms"),
                   ("knowledge of cloud security","credential.certification"),
                   ("knowledge of network access control","database.access_control"))
            for text,wrong in cases:
                c=candidate(text)
                self.assertNotEqual(c["candidate_route"],"existing_capability_resolver_issue",text)
                self.assertNotIn(wrong,[r["capability_id"] for r in c["overlap"]["high_overlap_candidates"]])
                self.assertTrue(c["overlap"]["lexical_retrieval"])
                self.assertTrue(c["overlap"]["token_overlap_is_lexical_only"])

    def test_native_phrase_overlap_preserved_and_boundary_visible(self):
        with PublicationFixture():
            for text,cid in (("knowledge of web services api rest and grpc","backend.api_development"),
                             ("experience with software system-level integration","integration.client_software")):
                c=candidate(text)
                self.assertEqual(c["candidate_route"],"existing_capability_resolver_issue")
                strong=c["overlap"]["high_overlap_candidates"]
                self.assertIn(cid,[r["capability_id"] for r in strong])
                self.assertTrue(all(r["investigation_only"] for r in strong))
            overlap=overlap_check("software system-level integration")
            self.assertTrue(next(r for r in overlap["high_overlap_candidates"] if r["capability_id"]=="integration.client_software")["unmet_requirement_groups"])

    def test_product_name_subphrase_not_capability_semantics(self):
        with PublicationFixture():
            c=candidate("hands-on experience with Amazon Web Services EC2 Cognito S3 DynamoDB etc")
            self.assertEqual(c["candidate_route"],"technology_identity")
            self.assertTrue(c["overlap"]["requirement_phrase_product_context_conflict"])
            self.assertFalse(c["overlap"]["semantic_resolver_evidence"])
            c=candidate("Amazon Web Services and REST API development")
            self.assertEqual(c["candidate_route"],"existing_capability_resolver_issue")

    def test_generic_tokens_not_concrete_entities(self):
        with PublicationFixture():
            for term in ("e.g","etc","IT","OS","MS","BI","GUI","API","AI","ML","GenAI","CRUD"):
                c=candidate(term,[term],"technology_identity")
                self.assertFalse(c["technology_entity_diagnostics"]["concrete_entities"],term)
                self.assertNotIn(c["candidate_route"],{"technology_identity","technology_relationship"},term)
            self.assertEqual(candidate("API cloud security",["API"])["candidate_route"],"possible_new_capability")
            self.assertEqual(candidate("GenAI solutions with AI orchestration tools",["GenAI"])["candidate_route"],"possible_new_capability")
            self.assertFalse(candidate("cloud security",["Python"])["technology_entity_diagnostics"]["concrete_entities"])

    def test_concrete_entities_eligible_and_architecture_not_entity(self):
        with PublicationFixture():
            names="Keycloak MongoDB Node.js C# PostgreSQL AWS GCP Redis Elasticsearch DynamoDB EC2 S3 BigFix SCCM PyTorch TensorFlow FastAPI Express.js ROS PowerShell Java Python TypeScript".split()
            for name in names:
                c=candidate("experience with "+name,[name])
                self.assertIn(c["candidate_route"],{"technology_identity","technology_relationship","existing_capability_resolver_issue"},name)
                self.assertTrue(c["technology_entity_diagnostics"]["concrete_entities"],name)
            c=candidate("Microservices",["Microservices"],"technology_relationship")
            self.assertEqual(c["candidate_route"],"possible_new_capability")
            self.assertFalse(c["technology_entity_diagnostics"]["concrete_entities"])
            self.assertTrue(c["technology_entity_diagnostics"]["capability_concepts"])

    def test_aggregation_preserves_every_source_and_conflicts(self):
        with PublicationFixture():
            first=gap("knowledge of network access control")
            second=gap("network access control"); second["gap_id"]="second"
            second["provenance"][0].update(job_id=8,snapshot_id=2,requirement_id="another")
            cs=gap_candidates({"gap_version":GAP_VERSION,"observations":[first,second]})
            source=deepcopy(cs)
            report=candidate_report(cs)
            self.assertEqual(report["concept_count"],1)
            cluster=report["concepts"][0]
            self.assertEqual(cluster["distinct_job_count"],2)
            self.assertEqual(cluster["recurrence_priority"],"repeated_cross_job")
            self.assertEqual(cluster["source_gap_ids"],["second","synthetic-gap"])
            self.assertEqual(cluster["provenance"],first["provenance"]+second["provenance"])
            self.assertEqual(report["candidates"],source)
            cs[1]["candidate_route"]="insufficient_signal"
            self.assertTrue(candidate_report(cs)["concepts"][0]["route_conflict"])

    def test_single_job_priority_not_approval_or_exclusion(self):
        with PublicationFixture() as f:
            c=candidate("distributed storage replication")
            self.assertEqual(c["candidate_route"],"possible_new_capability")
            self.assertEqual(c["recurrence_priority"],"single_job")
            report=candidate_report([c])
            self.assertFalse(report["automatic_proposals"])
            self.assertFalse(report["automatic_approval"])
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()
            self.assertEqual(f.real_registry.read_bytes(),f.real_registry_bytes)

    def test_cli_readonly_json_csv_route_and_recurrence_counts(self):
        from scripts.tqd3_regression_corpus import main
        with PublicationFixture() as f:
            input_path=f.tmp/"gaps.json"; output=f.tmp/"candidates.json"; csv=f.tmp/"candidates.csv"
            input_path.write_text(json.dumps({"gap_version":GAP_VERSION,"observations":[gap("network access control")]}))
            before=input_path.read_bytes()
            with patch("sqlite3.connect",side_effect=AssertionError("Candidate CLI must not open any DB")), \
                    patch("database.job_match_manager.save_job_match_snapshot",side_effect=AssertionError("DB write")), \
                    patch("database.taxonomy_discovery_review_manager.save_taxonomy_evolution_proposal",side_effect=AssertionError("draft write")), redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(main(["taxonomy-candidates","--gaps",str(input_path),"--output",str(output),"--csv",str(csv)]),0)
            report=json.loads(output.read_text())
            self.assertEqual(report["source_observations"],1)
            self.assertIn("candidate_route_counts",printed.getvalue())
            self.assertIn("recurrence_counts",printed.getvalue())
            self.assertIn("concept_key",csv.read_text())
            self.assertEqual(input_path.read_bytes(),before)

    def test_ui_filters_render_no_execution(self):
        from tests.test_tqd3_publication_ui import FakeStreamlit
        from taxonomy_discovery.taxonomy_evolution_ui import render_taxonomy_evolution
        fake=FakeStreamlit()
        class Upload:
            def getvalue(self):
                return json.dumps({"gap_version":GAP_VERSION,"observations":[gap("network access control")]})
        fake.file_uploader=lambda label,**k:Upload() if label=="Governed gap inputs JSON" else None
        fake.multiselect=lambda *a,**k:["possible_new_capability"]
        with PublicationFixture(), patch.dict(sys.modules,{"streamlit":fake}), \
            patch("database.taxonomy_discovery_review_manager.list_taxonomy_evolution_proposals",return_value=[]), \
            patch("taxonomy_discovery.taxonomy_evolution.research_with_transport",side_effect=AssertionError("research")):
            render_taxonomy_evolution()
        self.assertTrue(any(name=="dataframe" for name,_ in fake.messages))


if __name__ == "__main__":
    unittest.main()
