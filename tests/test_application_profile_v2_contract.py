from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database.application_profile_manager as manager


class ApplicationProfileV2ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_db_path = manager.DB_PATH
        self.tempdir = tempfile.TemporaryDirectory()
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"

    def tearDown(self) -> None:
        manager.DB_PATH = self.old_db_path
        self.tempdir.cleanup()

    def test_profile_v2_has_platform_neutral_contact_and_address_fields(self) -> None:
        profile = manager.get_application_profile()

        self.assertEqual(manager.APPLICATION_PROFILE_VERSION, 2)
        self.assertIn("middle_name", profile["personal"])
        self.assertIn("phone_country_code", profile["personal"])
        self.assertIn("address", profile)
        self.assertEqual(
            set(profile["address"]),
            {
                "address_line_1",
                "address_line_2",
                "city",
                "state_region",
                "postal_code",
                "country",
            },
        )

    def test_old_shape_migrates_without_guessing_new_fields(self) -> None:
        manager.save_application_profile(
            {
                "personal": {
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "email": "ada@example.com",
                },
                "work_eligibility": {"requires_sponsorship": "No"},
            }
        )
        profile = manager.get_application_profile()

        self.assertEqual(profile["personal"]["first_name"], "Ada")
        self.assertEqual(profile["personal"]["middle_name"], "")
        self.assertEqual(profile["personal"]["phone_country_code"], "")
        self.assertTrue(all(value == "" for value in profile["address"].values()))

    def test_structured_address_round_trip(self) -> None:
        manager.save_application_profile(
            {
                "personal": {
                    "first_name": "Ada",
                    "phone_country_code": "+65",
                },
                "address": {
                    "address_line_1": "1 Example Street",
                    "city": "Singapore",
                    "postal_code": "123456",
                    "country": "Singapore",
                },
            }
        )
        profile = manager.get_application_profile()

        self.assertEqual(profile["personal"]["phone_country_code"], "+65")
        self.assertEqual(profile["address"]["address_line_1"], "1 Example Street")
        self.assertEqual(profile["address"]["city"], "Singapore")
        self.assertEqual(profile["address"]["postal_code"], "123456")
        self.assertEqual(profile["address"]["country"], "Singapore")


if __name__ == "__main__":
    unittest.main()
