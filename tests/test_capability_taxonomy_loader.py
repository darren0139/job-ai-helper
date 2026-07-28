from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tailoring.capability_taxonomy import (
    get_default_taxonomy,
    load_taxonomy,
)


class CapabilityTaxonomyLoaderTests(unittest.TestCase):
    def test_default_taxonomy_loads_and_is_versioned(self):
        taxonomy = get_default_taxonomy()
        self.assertEqual(
            taxonomy.version,
            "phase6d-capability-taxonomy-v1",
        )
        self.assertGreaterEqual(len(taxonomy.capabilities), 20)

    def test_duplicate_capability_ids_are_rejected(self):
        payload = {
            "taxonomy_version": "test",
            "capabilities": [
                {
                    "capability_id": "duplicate",
                    "label": "One",
                    "domain": "test",
                    "priority": 1,
                    "requirement": {"any_terms": ["one"], "all_terms": []},
                    "evidence_tiers": [{"label": "direct", "any_terms": ["one"]}],
                    "does_not_prove": [],
                },
                {
                    "capability_id": "duplicate",
                    "label": "Two",
                    "domain": "test",
                    "priority": 2,
                    "requirement": {"any_terms": ["two"], "all_terms": []},
                    "evidence_tiers": [{"label": "direct", "any_terms": ["two"]}],
                    "does_not_prove": [],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "taxonomy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate capability_id"):
                load_taxonomy(path)


if __name__ == "__main__":
    unittest.main()
