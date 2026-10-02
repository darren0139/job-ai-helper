import unittest
import sys
from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import patch
from database.technology_registry_proposal_manager import (
    import_proposal_bundle, list_proposals, list_proposal_publications, save_proposal_review,
    prepare_approved_tranche, publish_approved_tranche,
)
from taxonomy_discovery.technology_registry import resolve_requirement_text
from tests.tqd3_publication_fixture_support import PublicationFixture


class AtomicTrancheTests(unittest.TestCase):
    def test_ui_selection_never_publishes_until_explicit_button(self):
        from taxonomy_discovery import proposal_publication_ui as ui
        from tests.test_tqd3_publication_ui import FakeStreamlit
        proposal = {"proposal_id": "selected", "proposal_bundle_version": "v1", "source_fingerprint": "fp", "label": "Tool"}
        for click in (False, True):
            st = FakeStreamlit(click)
            st.multiselect = lambda *args, **kwargs: ["selected"]
            with patch.dict(sys.modules, {"streamlit": st}), patch.object(ui, "prepare_approved_tranche", return_value={"ready":True,"blockers":[]}), \
                    patch.object(ui, "publish_approved_tranche", return_value={"status":"published"}) as publish:
                ui.render_tranche_publication([proposal], [{"proposal_id":"selected","decision":"approve_mapping"}])
                self.assertEqual(publish.call_count, int(click))
                if click:
                    self.assertTrue(publish.call_args.kwargs["explicit_publish"])

    def test_taxonomy_and_registry_staleness_zero_writes(self):
        with PublicationFixture() as f:
            options = self.setup_tranche(f)
            from tailoring.capability_taxonomy import get_default_taxonomy
            taxonomy = get_default_taxonomy()
            frozen = f.registry_path.read_bytes(), f.proposal_db.read_bytes()
            with patch("taxonomy_discovery.technology_registry.get_default_taxonomy", return_value=SimpleNamespace(version="changed", by_id=taxonomy.by_id)):
                result = publish_approved_tranche(explicit_publish=True, **options)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(len({b["proposal_id"] for b in result["blockers"]}), 2)
            options["expected_registry_version"] = "stale"
            self.assertEqual(publish_approved_tranche(explicit_publish=True, **options)["status"], "blocked")
            self.assertEqual(frozen, (f.registry_path.read_bytes(), f.proposal_db.read_bytes()))

    def setup_tranche(self, f):
        bundle = deepcopy(f.draft["proposal_bundle"])
        p = bundle["proposals"][0]
        p.update(proposal_id="second-proposal", technology_id="focused.secondcpp", label="SecondCPPTool", aliases=["SecondCPPTool"])
        import_proposal_bundle(bundle, db_path=f.proposal_db)
        proposals = list_proposals(db_path=f.proposal_db)
        for p in proposals:
            save_proposal_review(proposal_id=p["proposal_id"], proposal_bundle_version=p["proposal_bundle_version"],
                                decision="approve_mapping", db_path=f.proposal_db)
        return dict(selected_proposals=[{k: p[k] for k in ("proposal_id", "source_fingerprint", "proposal_bundle_version")} for p in proposals],
                    expected_registry_version=f.baseline_version, db_path=f.proposal_db, registry_path=f.registry_path)

    def test_all_valid_one_atomic_replace_and_receipt(self):
        with PublicationFixture() as f:
            options = self.setup_tranche(f)
            before_db = f.proposal_db.read_bytes()
            self.assertTrue(prepare_approved_tranche(**options)["ready"])
            self.assertEqual(before_db, f.proposal_db.read_bytes())
            import os
            with patch("database.technology_registry_proposal_manager.os.replace", wraps=os.replace) as replace:
                receipt = publish_approved_tranche(explicit_publish=True, **options)
                self.assertEqual(replace.call_count, 1)
            self.assertEqual(receipt["proposal_count"], 2)
            self.assertEqual(receipt["blocked_count"], 0)
            self.assertTrue(receipt["production_active"])
            self.assertEqual(len(receipt["capability_relationships_added"]), 2)
            self.assertEqual(len(receipt["aliases_added"]), 2)
            self.assertNotEqual(receipt["source_registry_sha256"], receipt["published_registry_sha256"])
            self.assertEqual(resolve_requirement_text("SecondCPPTool")["capability_id"], f.capability)
            self.assertEqual(len(list_proposal_publications(db_path=f.proposal_db)), 2)
            self.assertEqual(f.real_registry.read_bytes(), f.real_registry_bytes)

    def test_one_bad_item_zero_registry_and_database_writes_all_blockers(self):
        with PublicationFixture() as f:
            options = self.setup_tranche(f)
            options["selected_proposals"][0]["source_fingerprint"] = "stale"
            pid = options["selected_proposals"][1]["proposal_id"]
            save_proposal_review(proposal_id=pid, proposal_bundle_version=options["selected_proposals"][1]["proposal_bundle_version"],
                                decision="reject_proposal", db_path=f.proposal_db)
            before = f.registry_path.read_bytes(), f.proposal_db.read_bytes()
            receipt = publish_approved_tranche(explicit_publish=True, **options)
            self.assertEqual(receipt["status"], "blocked")
            self.assertEqual({b["proposal_id"] for b in receipt["blockers"]}, {p["proposal_id"] for p in options["selected_proposals"]})
            self.assertEqual(before, (f.registry_path.read_bytes(), f.proposal_db.read_bytes()))
            self.assertEqual(list_proposal_publications(db_path=f.proposal_db), [])

    def test_nonexplicit_obsolete_and_staging_failure_closed(self):
        with PublicationFixture() as f:
            options = self.setup_tranche(f)
            before = f.registry_path.read_bytes()
            with self.assertRaises(ValueError):
                publish_approved_tranche(**options)
            with patch("database.technology_registry_proposal_manager.os.replace", side_effect=OSError("stage failed")):
                with self.assertRaises(OSError):
                    publish_approved_tranche(explicit_publish=True, **options)
            self.assertEqual(before, f.registry_path.read_bytes())
            self.assertTrue(all(r["status"] == "prepared" for r in list_proposal_publications(db_path=f.proposal_db)))
            publish_approved_tranche(explicit_publish=True, **options)
            frozen = f.registry_path.read_bytes()
            options["expected_registry_version"] = __import__("taxonomy_discovery.technology_registry", fromlist=["get_default_registry"]).get_default_registry().version
            blocked = publish_approved_tranche(explicit_publish=True, **options)
            self.assertEqual(blocked["status"], "blocked")
            self.assertTrue(any("already covered" in b["reason"] for b in blocked["blockers"]))
            self.assertEqual(frozen, f.registry_path.read_bytes())

    def test_cross_item_alias_conflict_closed(self):
        with PublicationFixture() as f:
            options = self.setup_tranche(f)
            bundle = deepcopy(f.draft["proposal_bundle"])
            p = bundle["proposals"][0]
            p.update(proposal_id="second-proposal", technology_id="focused.secondcpp", label="SecondCPPTool", aliases=["SecondCPPTool", f.name])
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            options = self.setup_tranche(f)
            # setup imports a clean second item; introduce the collision afterwards.
            import_proposal_bundle(bundle, db_path=f.proposal_db)
            proposals = list_proposals(db_path=f.proposal_db)
            options["selected_proposals"] = [{k:p[k] for k in ("proposal_id","source_fingerprint","proposal_bundle_version")} for p in proposals]
            save_proposal_review(proposal_id="second-proposal", proposal_bundle_version=proposals[0]["proposal_bundle_version"], decision="approve_mapping", db_path=f.proposal_db)
            frozen = f.registry_path.read_bytes()
            self.assertFalse(prepare_approved_tranche(**options)["ready"])
            self.assertEqual(publish_approved_tranche(explicit_publish=True, **options)["status"], "blocked")
            self.assertEqual(frozen, f.registry_path.read_bytes())
