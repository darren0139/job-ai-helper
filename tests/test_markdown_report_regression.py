from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import unittest
from typing import Any


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _load_report_helpers() -> dict[str, object]:
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    required_names = {
        "_markdown_escape",
        "build_stable_alignment_summary",
        "create_markdown_report",
    }

    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in required_names
    ]

    found_names = {node.name for node in functions}
    missing = required_names - found_names
    if missing:
        raise AssertionError(
            f"Missing report helper functions: {sorted(missing)}"
        )

    module = ast.Module(body=functions, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace: dict[str, object] = {
        "Any": Any,
        "datetime": datetime,
    }
    exec(
        compile(module, str(APP_PATH), "exec"),
        namespace,
    )
    return namespace


class MarkdownReportRegressionTests(unittest.TestCase):
    def test_markdown_escape_is_defined_and_escapes_tables(self) -> None:
        namespace = _load_report_helpers()
        escape = namespace["_markdown_escape"]

        self.assertEqual(
            escape("A | B\nC"),
            r"A \| B C",
        )

    def test_markdown_report_can_be_created(self) -> None:
        namespace = _load_report_helpers()
        create_report = namespace["create_markdown_report"]

        report = {
            "resume_profile": {"name": "Test | Candidate"},
            "jd_profile": {
                "job_title": "Engineer",
                "company": "Example",
            },
            "stable_analysis": {
                "deterministic_alignment_score": 32,
                "alignment_band": "weak alignment",
                "required_core_coverage_score": 24,
                "preferred_coverage_score": 0,
                "credited_requirement_count": 1,
                "requirement_count": 2,
                "evidence_strength_score": 80,
                "canonical_requirements": [
                    {
                        "importance": "required",
                        "text": "Example | requirement",
                        "match_label": "direct",
                        "evidence": [
                            {"text": "Explicit evidence"}
                        ],
                    }
                ],
                "validation_warnings": [],
            },
            "bullets": {"bullet_quality_avg": 70},
            "structure": {"structure_score": 100},
            "jargon": {"jargon_score": 100},
            "degree_alignment": {
                "degree_alignment_score": 70
            },
            "keyword_match": {"keyword_match_score": 50},
            "legacy_overall_score": 69,
        }

        markdown_text, filename = create_report(report)

        self.assertIn(
            "Test \\| Candidate",
            markdown_text,
        )
        self.assertIn(
            "Example \\| requirement",
            markdown_text,
        )
        self.assertTrue(filename.endswith(".md"))


if __name__ == "__main__":
    unittest.main()
