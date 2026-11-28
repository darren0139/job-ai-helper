import unittest

from tailoring.fullstack_project_evidence_v312b222d4b import Link, evaluate_project, evaluate_wording

DIRECT = "Built a full-stack IT service request tracker with React, TypeScript, FastAPI, and PostgreSQL, spanning application development, database design, and RESTful APIs."
IMPACT = "Built full-stack application features in a team project, connecting frontend workflows with secure database access and real-time backend queries."
FRONT = "Built React frontend ticket editing for the HelpDesk application."
BACK = "Implemented FastAPI backend ticket endpoints for the HelpDesk application."
BRIDGE = "Connected the React ticket editor to the FastAPI backend ticket endpoints in HelpDesk."


def record(evidence_id, text, *, project_id="help", source="evidence_library", kind="bullet"):
    return dict(evidence_id=evidence_id, text=text, project_id=project_id, source=source, kind=kind)


class OwnedFullstackCandidateTests(unittest.TestCase):
    def test_explicit_project_bullet_and_impact(self):
        self.assertEqual(evaluate_wording(DIRECT), "direct")
        self.assertEqual(evaluate_project("help", [record("impact", IMPACT, kind="impact")]),
                         Link("direct", ("impact",)))

    def test_owned_composite_requires_related_distinct_implementation_records(self):
        rows = [record("front", FRONT), record("backend", BACK), record("bridge", BRIDGE)]
        self.assertEqual(evaluate_project("help", rows), Link("direct", ("front", "backend", "bridge")))
        self.assertEqual(evaluate_wording(BRIDGE), "transferable")
        self.assertEqual(evaluate_project("help", rows[:2]), Link("transferable", ("front",)))
        unrelated = record("other", "Implemented FastAPI backend payroll endpoints for the Staff application.")
        self.assertEqual(evaluate_project("help", [rows[0], unrelated, rows[2]]).label, "transferable")

    def test_cross_project_and_cross_source_records_do_not_complete_evidence(self):
        rows = [record("front", FRONT), record("bridge", BRIDGE)]
        for foreign in (record("back", BACK, project_id="other"), record("back", BACK, source="resume"),
                        record("back", BACK, kind="tool")):
            self.assertEqual(evaluate_project("help", [*rows, foreign]).label, "transferable")
        self.assertEqual(evaluate_project("", rows).label, "none")

    def test_negated_hypothetical_vendor_ci_and_keyword_only_controls(self):
        for text in (
            "Would have built a full-stack web application with React frontend and FastAPI backend.",
            "The vendor built a full-stack application with React frontend and API backend.",
            "Built a React frontend but the backend was not implemented.",
            "Created automated backend and frontend tests for a web application.",
            "Built CI tooling for UI workflows.",
            "OpenAI API", "database design",
        ):
            with self.subTest(text=text):
                self.assertEqual(evaluate_wording(text), "none")
        self.assertEqual(evaluate_wording(FRONT), "transferable")
