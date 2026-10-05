from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from taxonomy_discovery import proposal_publication_ui as ui


class FakeStreamlit:
    def __init__(self, click=False):
        self.click = click
        self.messages = []
        self.session_state = {}
        self.buttons = []

    def button(self, label, **kwargs):
        self.buttons.append((label, kwargs))
        return self.click

    def expander(self, *args, **kwargs):
        self.messages.append(("expander", args))
        return self

    def tabs(self, labels):
        self.messages.append(("tabs", (labels,)))
        return [self for _ in labels]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.messages.append((name, args))


class PublicationUITests(unittest.TestCase):
    def proposal(self):
        return {"proposal_id": "focused-cpp", "proposal_bundle_version": "proposal-version", "label": "C++",
                "source_fingerprint": "fingerprint", "proposal_classification": "safe_mapping_candidate",
                "proposed_capability_id": "language.modern_cpp",
                "aliases": ["C++", "C++ programming language"],
                "sources": [{"publisher": "iso.org", "url": "https://www.iso.org/standard/68564.html"}],
                "focused_verification": {"outcome": "verified_registry_relationship", "authoritative_evidence": []}}

    def test_approval_does_not_publish_on_rerender(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}), patch.object(ui, "publish_approved_proposal") as publish, \
                patch.object(ui, "proposal_publication_state", return_value={"state": "human_approved",
                    "display": "Approved — not yet published", "production_active": False, "registry_version": "current"}):
            for _ in range(2):
                ui.render_proposal_publication(self.proposal(), {"decision": "approve_mapping"})
            publish.assert_not_called()
            self.assertEqual(st.buttons[0][0], "Publish approved change")

    def test_only_explicit_publish_click_calls_production_promotion(self):
        with patch.dict(sys.modules, {"streamlit": FakeStreamlit(True)}), \
                patch.object(ui, "publish_approved_proposal") as publish, \
                patch.object(ui, "proposal_publication_state", return_value={"state": "human_approved",
                    "display": "Approved — not yet published", "production_active": False, "registry_version": "current"}):
            ui.render_proposal_publication(self.proposal(), {"decision": "approve_mapping"})
            publish.assert_called_once_with(proposal_id="focused-cpp", explicit_publish=True,
                expected_source_fingerprint="fingerprint", expected_registry_version="current",
                proposal_bundle_version="proposal-version")

    def test_unapproved_or_published_proposals_never_show_publish_button(self):
        for state in ("draft", "production_active"):
            st = FakeStreamlit(True)
            with patch.dict(sys.modules, {"streamlit": st}), patch.object(ui, "publish_approved_proposal") as publish, \
                    patch.object(ui, "proposal_publication_state", return_value={"state": state,
                        "display": state, "production_active": state == "production_active",
                        "registry_version": "current", "taxonomy_version": "taxonomy"}):
                ui.render_proposal_publication(self.proposal(), {})
                publish.assert_not_called()
                self.assertEqual(st.buttons, [])

    def test_navigation_opens_exact_proposal_despite_historical_filters(self):
        state = {ui.PROPOSAL_INSPECTOR_KEY: "historical-unrelated"}
        ui.request_proposal_navigation(state, "focused-cpp")
        self.assertEqual(state[ui.DISCOVERY_TABS_KEY], "Research Proposals")
        ids = ui.prepare_proposal_inspector(state,
            [{"proposal_id": "historical-unrelated"}, {"proposal_id": "focused-cpp"}],
            [{"proposal_id": "historical-unrelated"}])
        self.assertEqual(ids[0], "focused-cpp")
        self.assertEqual(state[ui.PROPOSAL_INSPECTOR_KEY], "focused-cpp")
        # Form edits/rerenders must retain this exact proposal, not return to
        # an unrelated proposal selected by old filters.
        self.assertEqual(ui.prepare_proposal_inspector(state,
            [{"proposal_id": "historical-unrelated"}, {"proposal_id": "focused-cpp"}],
            [{"proposal_id": "historical-unrelated"}])[0], "focused-cpp")

    def test_handoff_button_is_a_navigation_callback_not_publication(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}):
            ui.render_focused_review_handoff({"proposal_bundle": {"proposals": [
                {"proposal_id": "focused-cpp", "proposed_capability_id": "language.modern_cpp"}]}}, "C++")
        label, kwargs = st.buttons[0]
        self.assertEqual(label, "Open C++ proposal")
        kwargs["on_click"](*kwargs["args"])
        self.assertEqual(st.session_state[ui.REQUESTED_PROPOSAL_KEY], "focused-cpp")

    def test_manual_approval_is_available_and_publication_follows_form(self):
        source = Path("taxonomy_discovery/review_ui.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertLess(source.index('"Save proposal decision"'), source.index("render_proposal_publication("))
        self.assertIn('key=DISCOVERY_TABS_KEY, on_change="rerun"', source)
        self.assertIn('"approve_identity"', source)
        self.assertNotIn("publish_approved_proposal(", source)

    def test_friendly_labels_preserve_internal_values(self):
        self.assertEqual(ui.friendly_decision_label("approve_mapping"), "Approve mapping")
        self.assertEqual(ui.friendly_decision_label("unreviewed"), "Not reviewed yet")
        self.assertEqual(ui.friendly_verification_label("verified_registry_relationship"), "Verified relationship")
        self.assertEqual(ui.friendly_classification_label("safe_mapping_candidate"), "Safe mapping candidate")

    def test_verified_state_is_independent_from_automation_suggestion(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}), \
                patch.object(ui, "proposal_publication_state", return_value={"state": "draft",
                    "display": "Unreviewed / not approved", "production_active": False,
                    "registry_version": "current", "taxonomy_version": "taxonomy"}):
            ui.render_proposal_publication(self.proposal(), {}, automation_suggestion="unreviewed")
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("Verified relationship", rendered)
        self.assertIn("Not reviewed yet", rendered)
        self.assertIn("does not invalidate verified evidence", rendered)
        self.assertEqual(st.buttons, [])

    def test_approved_state_has_clear_next_action_and_production_warning(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}), \
                patch.object(ui, "proposal_publication_state", return_value={"state": "human_approved",
                    "display": "Approved — not yet published", "production_active": False,
                    "registry_version": "current", "taxonomy_version": "taxonomy"}):
            ui.render_proposal_publication(self.proposal(), {"decision": "approve_mapping"},
                                           automation_suggestion="unreviewed")
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("Production has not changed yet", rendered)
        self.assertIn("Publishing writes approved registry knowledge to production", rendered)
        self.assertEqual([label for label, _ in st.buttons], ["Publish approved change"])

    def test_published_state_shows_production_active_without_publish_button(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}), \
                patch.object(ui, "proposal_publication_state", return_value={"state": "production_active",
                    "display": "Published", "production_active": True,
                    "registry_version": "technology-registry-v1.2", "taxonomy_version": "taxonomy-v1"}):
            ui.render_proposal_publication(self.proposal(), {"decision": "approve_mapping"},
                                           automation_suggestion="approve_mapping")
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("Production active", rendered)
        self.assertIn("technology-registry-v1.2", rendered)
        self.assertEqual(st.buttons, [])

    def test_review_ui_separates_bulk_automation_from_manual_review(self):
        source = Path("taxonomy_discovery/review_ui.py").read_text(encoding="utf-8")
        self.assertIn("Optional bulk automation · Python recommendations", source)
        self.assertIn("For normal review, use the single-proposal inspector below.", source)
        self.assertIn("Automation suggestion (optional)", source)
        self.assertIn("format_func=friendly_decision_label", source)
        self.assertIn("Download registry vNext preview JSON · Preview only", source)
        self.assertLess(source.index("#### Human decision"), source.index("Research summary / evidence context"))

    def test_mapping_guidance_explains_good_enough_approval_threshold(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}):
            ui.render_human_decision_guidance(self.proposal(), {"decision": "unreviewed"})
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("What is good enough to approve?", rendered)
        self.assertIn("Focused verification supports this technology-to-capability relationship", rendered)
        self.assertIn("language.modern_cpp", rendered)
        self.assertIn("Does language.modern_cpp accurately describe", rendered)
        self.assertIn("Approve mapping", rendered)
        self.assertIn("recognised but unmapped", rendered.lower())

    def test_saved_decision_guidance_keeps_human_judgment_explicit(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}):
            ui.render_human_decision_guidance(self.proposal(), {"decision": "approve_mapping"})
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("Saved human decision: Approve mapping", rendered)
        self.assertIn("final semantic fit remains a human judgment", rendered)
        self.assertIn("Aliases to review", rendered)

    def test_publish_guidance_explains_readiness_and_revalidation(self):
        st = FakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}), \
                patch.object(ui, "proposal_publication_state", return_value={"state": "human_approved",
                    "display": "Approved — not yet published", "production_active": False,
                    "registry_version": "current", "taxonomy_version": "taxonomy"}):
            ui.render_proposal_publication(self.proposal(), {"decision": "approve_mapping"})
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("What is good enough to publish?", rendered)
        self.assertIn("revalidate the proposal fingerprint", rendered)
        self.assertIn("fails closed", rendered)
        self.assertIn("does not create candidate/resume evidence", rendered)
        self.assertEqual([label for label, _ in st.buttons], ["Publish approved change"])

    def test_review_ui_places_decision_guidance_before_form(self):
        source = Path("taxonomy_discovery/review_ui.py").read_text(encoding="utf-8")
        self.assertIn("Research confidence (diagnostic)", source)
        self.assertIn("supporting diagnostics, not approval thresholds", source)
        guidance_pos = source.index("render_human_decision_guidance(proposal, review)")
        form_pos = source.index("with st.form(", guidance_pos)
        self.assertLess(guidance_pos, form_pos)

    def test_existing_checkpoint_handoff_evidence_reloads_without_research(self):
        from copy import deepcopy
        from database.taxonomy_discovery_review_manager import list_focused_verification_results, save_focused_verification_decision
        from tests.tqd3_publication_fixture_support import PublicationFixture
        with PublicationFixture() as f:
            historic = deepcopy(f.draft)
            historic["proposal_bundle"]["proposals"][0].pop("focused_verification")
            row = list_focused_verification_results(db_path=f.review_db)[0]
            save_focused_verification_decision(artifact_id=row["artifact_id"], decision="send_to_review",
                draft=historic, db_path=f.review_db)
            proposal = deepcopy(f.proposal)
            proposal.pop("focused_verification")
            context = ui.focused_proposal_context(proposal, review_db_path=f.review_db)
            self.assertEqual(context["outcome"], "verified_registry_relationship")
            self.assertEqual(context["provider_request_id"], f.result["provider_request_id"])
            f.network_guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
