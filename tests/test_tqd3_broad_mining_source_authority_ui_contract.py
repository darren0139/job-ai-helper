from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "taxonomy_discovery" / "review_ui.py"
).read_text(encoding="utf-8")


class BroadMiningSourceAuthorityUIContractTests(unittest.TestCase):
    def test_candidate_table_shows_source_authority(self) -> None:
        for token in (
            '"primary_official_sources"',
            '"other_first_party_sources"',
            '"secondary_sources"',
            '"unclassified_sources"',
            '"has_primary_official"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_ui_does_not_trust_provider_authority_label(self) -> None:
        self.assertIn(
            "Provider source labels are not trusted as authority judgments",
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
