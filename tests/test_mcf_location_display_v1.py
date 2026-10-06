from __future__ import annotations

import unittest

from job_discovery.location_display import (
    display_job_location,
    format_singapore_postal_location,
    is_singapore_postal_code,
)


class MyCareersFutureLocationDisplayTests(unittest.TestCase):
    def test_detects_singapore_postal_code(self) -> None:
        self.assertTrue(is_singapore_postal_code("609966"))
        self.assertTrue(is_singapore_postal_code("049483"))
        self.assertFalse(is_singapore_postal_code("Singapore"))
        self.assertFalse(is_singapore_postal_code("12345"))
        self.assertFalse(is_singapore_postal_code("1234567"))

    def test_formats_bare_postal_code(self) -> None:
        self.assertEqual(
            format_singapore_postal_location("609966"),
            "Singapore 609966",
        )

    def test_preserves_human_readable_location(self) -> None:
        self.assertEqual(
            format_singapore_postal_location("Singapore"),
            "Singapore",
        )
        self.assertEqual(
            format_singapore_postal_location("Jurong East, Singapore"),
            "Jurong East, Singapore",
        )

    def test_only_mcf_rows_receive_legacy_repair(self) -> None:
        self.assertEqual(
            display_job_location(
                {"source": "mycareersfuture", "location": "609966"}
            ),
            "Singapore 609966",
        )
        self.assertEqual(
            display_job_location(
                {"source": "smartrecruiters", "location": "609966"}
            ),
            "609966",
        )

    def test_blank_location_stays_blank(self) -> None:
        self.assertEqual(
            display_job_location(
                {"source": "mycareersfuture", "location": ""}
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
