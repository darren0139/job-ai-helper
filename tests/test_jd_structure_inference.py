from __future__ import annotations

import unittest

from analysis_stability.jd_section_inference import infer_semantic_list_heading
from analysis_stability.stable_evidence_scoring import canonicalise_requirements
from job_discovery.text_utils import html_to_text


def _texts(result):
    return [str(row.get("text") or "") for row in result.get("requirements", []) or []]


class GenericJDStructureInferenceTests(unittest.TestCase):
    def test_html_list_markers_are_preserved(self):
        value = html_to_text(
            "<h3>What You Bring</h3>"
            "<ul><li>Knowledge of SQL</li><li>Python experience</li></ul>"
        )
        self.assertIn("- Knowledge of SQL", value)
        self.assertIn("- Python experience", value)

    def test_generic_responsibility_heading(self):
        lines = [
            "How You'll Make an Impact",
            "- Build and maintain backend services.",
            "- Collaborate with engineers on application design.",
            "- Troubleshoot production software issues.",
        ]
        self.assertEqual(
            infer_semantic_list_heading(lines, 0)["section"],
            "responsibilities",
        )

    def test_generic_requirement_heading(self):
        lines = [
            "What You Bring",
            "- Experience with Python and Java.",
            "- Knowledge of SQL databases.",
            "- Ability to work in a collaborative team.",
        ]
        self.assertEqual(
            infer_semantic_list_heading(lines, 0)["section"],
            "requirements",
        )

    def test_generic_offer_heading(self):
        lines = [
            "Why Join Us",
            "- Competitive remuneration and benefits.",
            "- Flexible workplace and work-life balance.",
            "- Health insurance and annual leave.",
        ]
        self.assertEqual(infer_semantic_list_heading(lines, 0)["section"], "stop")

    def test_ambiguous_custom_heading_does_not_guess(self):
        result = infer_semantic_list_heading(
            ["Our Technology", "- Python", "- SQL", "- Docker"],
            0,
        )
        self.assertTrue(result["is_heading_candidate"])
        self.assertEqual(result["section"], "")

    def test_unheaded_prose_is_not_reclassified(self):
        result = infer_semantic_list_heading(
            [
                "We build technology for customers around the world.",
                "Our products serve multiple industries.",
                "The team is based in Singapore.",
            ],
            0,
        )
        self.assertFalse(result["is_heading_candidate"])

    def test_plain_text_list_run_without_bullet_glyphs(self):
        result = infer_semantic_list_heading(
            [
                "Qualities We Value",
                "Experience with Python is preferred.",
                "Knowledge of SQL is an advantage.",
                "Ability to solve problems analytically.",
                "Attention to detail and quality is desired.",
            ],
            0,
        )
        self.assertEqual(result["section"], "requirements")
        self.assertFalse(result["marked_list"])

    def test_stop_section_blocks_you_will_marketing_sentence(self):
        raw = "\n".join(
            [
                "Benefits",
                "- You will work in an environment where you will use cutting-edge technologies.",
                "- Competitive remuneration and benefits.",
                "- Flexible workplace and annual leave.",
            ]
        )
        result = canonicalise_requirements({}, raw)
        joined = "\n".join(_texts(result)).lower()
        self.assertNotIn("cutting-edge technologies", joined)
        exclusions = result.get("decomposition_debug", {}).get(
            "unheaded_raw_exclusions", []
        )
        self.assertTrue(
            any(row.get("reason") == "explicit_non_scoring_section" for row in exclusions)
        )

    def test_st_engineering_style_sections_recover_requirements(self):
        raw = "\n".join(
            [
                "Be Part of Our Success",
                "- Collaborate with other developers and engineers to specify, design, build, and maintain software applications.",
                "- Perform software implementation and testing.",
                "- Analyze and troubleshoot software issues.",
                "- Generate relevant documentations and reports.",
                "- Contribute to continuous improvement of software development best practices.",
                "- Keep up-to-date with industry trends and technology developments.",
                "Qualities We Value",
                "- Basic programming experience with knowledge of C#, Java, Javascript, HTML5 and Python is preferred.",
                "- Knowledge of databases (SQL / NoSQL) is an advantage.",
                "- Familiar with full-stack development and comfortable using AngularJS, NodeJS, ReactJS and other common frameworks is an advantage.",
                "- Familiar with concepts of software engineering and Agile Development is preferred.",
                "- Ability to learn new software and technologies quickly.",
                "- A good team player who contribute and work effectively in a collaborative team environment.",
                "- Candidates with critical thinking, analytical and creative problem-solving skills is highly desired.",
                "- Attention to detail and quality is a desired attribute.",
                "Our Commitment That Goes Beyond the Norm",
                "- An environment where you will be working on cutting-edge technologies and architectures.",
                "- Safe space where diverse perspectives are valued and unique contributions are celebrated.",
                "- Meaningful work and projects that make a difference.",
                "- A fun, passionate and collaborative workplace.",
                "- Competitive remuneration and comprehensive benefits.",
            ]
        )
        result = canonicalise_requirements({}, raw)
        text = "\n".join(_texts(result)).lower()

        for fragment in (
            "software implementation and testing",
            "troubleshoot software issues",
            "python",
            "sql / nosql",
            "full-stack development",
            "agile development",
            "team player",
            "problem-solving",
            "attention to detail",
        ):
            self.assertIn(fragment, text)

        self.assertNotIn("cutting-edge technologies and architectures", text)
        self.assertNotIn("competitive remuneration", text)

        headings = {
            str(row.get("text") or ""): str(row.get("section") or "")
            for row in result.get("filtered_section_headings", []) or []
        }
        self.assertEqual(headings.get("Be Part of Our Success"), "responsibilities")
        self.assertEqual(headings.get("Qualities We Value"), "requirements")
        self.assertEqual(
            headings.get("Our Commitment That Goes Beyond the Norm"),
            "stop",
        )


if __name__ == "__main__":
    unittest.main()
