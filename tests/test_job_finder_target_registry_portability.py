from __future__ import annotations

from copy import deepcopy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from database import job_discovery_manager as manager
from job_discovery import pipeline


def target(name="Example", provider="lever", identifier="example", enabled=True, url=""):
    return {
        "company_name": name, "ats_provider": provider, "ats_identifier": identifier,
        "careers_url": url, "enabled": enabled,
    }


def payload(*targets):
    return {"schema_version": manager.TARGET_REGISTRY_SCHEMA_VERSION, "targets": list(targets)}


class TargetRegistryPortabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / "applications.db"
        db_patch = patch.object(manager, "DB_PATH", self.db_path)
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def rows(self):
        return manager.list_target_companies(include_disabled=True)

    def test_export_includes_disabled_rows_in_deterministic_order_without_metadata(self):
        records = [
            target("Zulu", "lever", "zulu", False),
            target("Beta", "ashby", "b"),
            target("Alpha", "ashby", "z"),
            target("Alpha", "ashby", "a"),
        ]
        for record in records:
            manager.upsert_target_company(**record)
        exported = manager.export_target_company_registry()
        self.assertEqual(exported, {
            "schema_version": "job-finder-target-registry-v1",
            "targets": [records[3], records[2], records[1], records[0]],
        })
        self.assertEqual(set(exported), {"schema_version", "targets"})
        for record in exported["targets"]:
            self.assertEqual(set(record), set(manager.TARGET_REGISTRY_FIELDS))
        self.assertEqual(exported, manager.export_target_company_registry())

    def test_merge_receipt_updates_and_preserves_unrelated_targets(self):
        manager.upsert_target_company(**target("Old", identifier="existing"))
        manager.upsert_target_company(**target("Unrelated", identifier="keep"))
        imported = payload(
            target("Changed", identifier="existing", enabled=False, url="https://jobs.lever.co/existing"),
            target("New", identifier="new"),
        )
        receipt = manager.import_target_company_registry(imported)
        self.assertEqual(receipt, {
            "schema_version": manager.TARGET_REGISTRY_SCHEMA_VERSION,
            "input_count": 2, "new_count": 1, "updated_count": 1,
            "unchanged_count": 0, "total_after": 3,
        })
        actual = {row["ats_identifier"]: row for row in self.rows()}
        self.assertEqual(actual["keep"]["company_name"], "Unrelated")
        self.assertEqual(actual["existing"]["company_name"], "Changed")
        self.assertFalse(actual["existing"]["enabled"])
        self.assertEqual(actual["existing"]["careers_url"], "https://jobs.lever.co/existing")

    def test_repeat_import_is_idempotent_including_timestamps(self):
        imported = payload(target(enabled=False))
        manager.import_target_company_registry(imported)
        before = self.rows()
        receipt = manager.import_target_company_registry(imported)
        self.assertEqual(receipt["new_count"], 0)
        self.assertEqual(receipt["updated_count"], 0)
        self.assertEqual(receipt["unchanged_count"], 1)
        self.assertEqual(self.rows(), before)

    def test_disabled_state_round_trips_into_another_database(self):
        manager.upsert_target_company(**target(enabled=False))
        exported = manager.export_target_company_registry()
        with patch.object(manager, "DB_PATH", self.db_path.with_name("restored.db")):
            manager.import_target_company_registry(exported)
            self.assertEqual(manager.export_target_company_registry(), exported)
            self.assertEqual(manager.list_target_companies(), [])

    def test_url_uses_existing_normalizer_and_identity(self):
        manager.upsert_target_company(**target("Old", "smartrecruiters", "NCS3"))
        imported = payload({
            "ats_provider": "smartrecruiters",
            "ats_identifier": "https://careers.smartrecruiters.com/NCS3",
            "enabled": True,
        })
        with patch.object(manager, "normalize_target_identifier", wraps=manager.normalize_target_identifier) as normalize:
            receipt = manager.import_target_company_registry(imported)
        normalize.assert_called_once_with("smartrecruiters", "https://careers.smartrecruiters.com/NCS3")
        self.assertEqual(receipt["updated_count"], 1)
        row = self.rows()[0]
        self.assertEqual(row["ats_identifier"], "NCS3")
        self.assertEqual(row["company_name"], "NCS3")
        self.assertEqual(row["careers_url"], "https://careers.smartrecruiters.com/NCS3")

    def test_all_validation_errors_reject_entire_payload_before_creating_database(self):
        invalid = [
            None, [], "bad", {}, {"schema_version": "future", "targets": []},
            {"schema_version": manager.TARGET_REGISTRY_SCHEMA_VERSION, "targets": {}},
            payload("not an object"),
            payload(target(provider="unsupported")),
            payload(target(identifier=" ")), payload(target(identifier="/")),
            payload(target(identifier=4)), payload(target(name=None)), payload(target(url=[])),
            payload(target(enabled="false")), payload(target(enabled=1)),
            payload({"ats_provider": "lever", "ats_identifier": "example"}),
        ]
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    manager.import_target_company_registry(candidate)
                with self.assertRaises(ValueError):
                    manager.preview_target_company_registry_import(candidate)
                self.assertFalse(self.db_path.exists())

    def test_valid_first_row_is_not_imported_when_later_row_is_invalid(self):
        manager.upsert_target_company(**target("Keep", identifier="keep"))
        before = self.db_path.read_bytes()
        with self.assertRaises(ValueError):
            manager.import_target_company_registry(payload(target(), target(provider="bad")))
        self.assertEqual(self.db_path.read_bytes(), before)

    def test_duplicate_normalized_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            manager.import_target_company_registry(payload(
                target(), target(identifier="https://jobs.lever.co/example"),
            ))
        self.assertFalse(self.db_path.exists())

    def test_preview_classifies_without_any_database_writes(self):
        manager.upsert_target_company(**target("Old", identifier="change"))
        manager.upsert_target_company(**target("Current", identifier="same", enabled=False))
        before = self.db_path.read_bytes()
        incoming = payload(target("New", identifier="new"),
                           target("Updated", identifier="change"),
                           target("Current", identifier="same", enabled=False))
        original = deepcopy(incoming)
        preview = manager.preview_target_company_registry_import(incoming)
        self.assertEqual(
            {change["target"]["ats_identifier"]: change["action"] for change in preview["changes"]},
            {"new": "new", "change": "update", "same": "unchanged"},
        )
        self.assertEqual(
            (preview["new_count"], preview["updated_count"], preview["unchanged_count"], preview["total_after"]),
            (1, 1, 1, 3),
        )
        self.assertEqual(self.db_path.read_bytes(), before)
        self.assertEqual(incoming, original)

    def test_preview_of_missing_database_does_not_create_it(self):
        preview = manager.preview_target_company_registry_import(payload(target()))
        self.assertEqual(preview["new_count"], 1)
        self.assertFalse(self.db_path.exists())

    def test_preview_of_existing_database_without_table_is_read_only(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute("CREATE TABLE unrelated (id INTEGER)")
            db.commit()
        before = self.db_path.read_bytes()
        self.assertEqual(manager.preview_target_company_registry_import(payload(target()))["new_count"], 1)
        self.assertEqual(self.db_path.read_bytes(), before)

    def test_mid_import_database_failure_rolls_back_all_rows(self):
        manager.upsert_target_company(**target("Keep", identifier="keep"))
        before = self.rows()
        original = manager._upsert_target_company_row
        calls = []

        def fail_second(connection, record):
            calls.append(record)
            if len(calls) == 2:
                raise sqlite3.IntegrityError("simulated write failure")
            return original(connection, record)

        with patch.object(manager, "_upsert_target_company_row", side_effect=fail_second):
            with self.assertRaises(sqlite3.IntegrityError):
                manager.import_target_company_registry(payload(target(identifier="a"), target(identifier="b")))
        self.assertEqual(self.rows(), before)

    def test_effective_defaults_are_active_without_database_writes(self):
        effective = manager.list_effective_target_companies(include_disabled=True)
        self.assertEqual(len(effective), 18)
        counts = {
            provider: sum(1 for row in effective if row["ats_provider"] == provider)
            for provider in ("ashby", "greenhouse", "lever", "smartrecruiters")
        }
        self.assertEqual(
            counts,
            {"ashby": 5, "greenhouse": 8, "lever": 3, "smartrecruiters": 2},
        )
        ncs = next(row for row in effective if row["company_name"] == "NCS")
        self.assertEqual((ncs["ats_provider"], ncs["ats_identifier"]), ("smartrecruiters", "NCS3"))
        self.assertEqual(ncs["origin"], "starter")
        self.assertFalse(self.db_path.exists())
        exported = manager.export_effective_target_company_registry()
        self.assertEqual(len(exported["targets"]), 18)
        self.assertFalse(self.db_path.exists())

    def test_live_disable_override_wins_over_starter_default(self):
        manager.upsert_target_company(
            company_name="NCS", ats_provider="smartrecruiters",
            ats_identifier="NCS3", enabled=False,
        )
        enabled = manager.list_effective_target_companies(provider="smartrecruiters")
        self.assertEqual({row["ats_identifier"] for row in enabled}, {"DeliveryHero"})
        all_targets = manager.list_effective_target_companies(
            include_disabled=True, provider="smartrecruiters"
        )
        ncs = next(row for row in all_targets if row["ats_identifier"] == "NCS3")
        self.assertFalse(ncs["enabled"])
        self.assertEqual(ncs["origin"], "live")

    def test_custom_live_target_is_added_alongside_starter_defaults(self):
        manager.upsert_target_company(
            company_name="Future Co", ats_provider="lever",
            ats_identifier="futureco", enabled=True,
        )
        effective = manager.list_effective_target_companies(include_disabled=True)
        self.assertEqual(len(effective), 19)
        future = next(row for row in effective if row["ats_identifier"] == "futureco")
        self.assertEqual(future["company_name"], "Future Co")
        self.assertEqual(future["origin"], "live")
        self.assertEqual(len(manager.list_target_companies(include_disabled=True)), 1)

    def test_importing_starter_registry_does_not_duplicate_effective_targets(self):
        starter = manager.load_singapore_target_company_registry()
        self.assertEqual(manager.import_target_company_registry(starter)["new_count"], 18)
        effective = manager.list_effective_target_companies(include_disabled=True)
        self.assertEqual(len(effective), 18)
        self.assertEqual(len(manager.list_target_companies(include_disabled=True)), 18)

    def test_pipeline_uses_effective_starter_targets_without_import(self):
        expected = {
            "ashby": {"airwallex", "mobbin.com", "bjakcareer", "exa", "fireworks"},
            "greenhouse": {
                "temus", "simplifynext", "okx", "encora10",
                "metabittechnologyllc", "grasshopperasia", "reolink", "drweng",
            },
            "lever": {"csit", "palantir", "funxyz"},
            "smartrecruiters": {"NCS3", "DeliveryHero"},
        }
        for provider, identifiers in expected.items():
            with self.subTest(provider=provider):
                resolved = pipeline._targets({}, provider, None)
                self.assertEqual({row["identifier"] for row in resolved}, identifiers)
        self.assertFalse(self.db_path.exists())

    def test_seed_has_exact_requested_targets_and_validates_without_writing(self):
        raw = json.loads(manager.SINGAPORE_TARGET_REGISTRY_PATH.read_text(encoding="utf-8"))
        starter = manager.load_singapore_target_company_registry()
        self.assertEqual(starter, raw)
        self.assertEqual(len(starter["targets"]), 18)
        expected = {
            "smartrecruiters": {"NCS3", "DeliveryHero"},
            "lever": {"csit", "palantir", "funxyz"},
            "greenhouse": {"temus", "simplifynext", "okx", "encora10", "metabittechnologyllc", "grasshopperasia", "reolink", "drweng"},
            "ashby": {"airwallex", "mobbin.com", "bjakcareer", "exa", "fireworks"},
        }
        for provider, identifiers in expected.items():
            self.assertEqual({r["ats_identifier"] for r in starter["targets"] if r["ats_provider"] == provider}, identifiers)
        ncs = next(row for row in starter["targets"] if row["company_name"] == "NCS")
        self.assertEqual(ncs["ats_identifier"], "NCS3")
        self.assertTrue(all(row["enabled"] for row in starter["targets"]))
        self.assertEqual(manager.preview_target_company_registry_import(starter)["new_count"], 18)
        self.assertFalse(self.db_path.exists())

    def test_seed_import_is_explicit_idempotent_and_does_not_auto_readd_deletions(self):
        manager.init_job_discovery_schema()
        self.assertEqual(self.rows(), [])
        starter = manager.load_singapore_target_company_registry()
        self.assertEqual(self.rows(), [])
        self.assertEqual(manager.import_target_company_registry(starter)["new_count"], 18)
        self.assertEqual(manager.import_target_company_registry(starter)["unchanged_count"], 18)
        row = next(row for row in self.rows() if row["ats_identifier"] == "NCS3")
        manager.set_target_company_enabled(row["id"], False)
        manager.init_job_discovery_schema()
        self.assertFalse(next(r for r in self.rows() if r["id"] == row["id"])["enabled"])
        manager.delete_target_company(row["id"])
        manager.init_job_discovery_schema()
        manager.load_singapore_target_company_registry()
        self.assertEqual(len(self.rows()), 17)

    def test_empty_import_preserves_all_targets(self):
        manager.upsert_target_company(**target())
        before = self.rows()
        self.assertEqual(manager.import_target_company_registry(payload())["total_after"], 1)
        self.assertEqual(self.rows(), before)


if __name__ == "__main__":
    unittest.main()
