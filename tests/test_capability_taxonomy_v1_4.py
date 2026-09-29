from __future__ import annotations
from copy import deepcopy
import unittest
from unittest.mock import patch
from tailoring.capability_taxonomy import classify_requirement, evaluate_evidence, get_default_taxonomy
from tailoring.phase6d_stable_scoring_adapter import cap_requirement_with_taxonomy

# Cases are deliberately independent of identities, employers and project names.
SEMANTICS = [
    ("C programming", "Built a C++ service", "none"),
    ("C++ programming", "Implemented firmware in C", "none"),
    ("C/C++ programming", "Built a C++ service", "direct"),
    ("C and C++ programming", "Built a C++ service", "none"),
    ("C++ programming", "Built a service in C#", "none"),
    ("Experience with C", "Built a C service", "direct"),
    ("Modern C++ proficiency", "Built a C++ service", "transferable"),
    ("Modern C++ proficiency", "Built a C++20 service", "direct"),
    ("Modern C programming", "Built firmware using C11", "direct"),
    ("Android application development using Kotlin", "Built an Android application using Kotlin", "direct"),
    ("Android application development using Kotlin", "Implemented an Android feature in Java", "none"),
    ("Android application development", "Published Android software", "direct"),
    ("Android application development", "Kotlin", "none"),
    ("Android application development", "Java", "none"),
    ("Android application development", "Installed Android Studio for app tutorials", "none"),
    ("Android application development", "Built a web app; installed Android Studio", "none"),
    ("Android application development using Kotlin", "Built an Android app in Java\nDeveloped Kotlin desktop software", "none"),
    ("Android application development", "Completed an Android application course in Kotlin", "none"),
    ("Android application development", "Android SDK and Kotlin", "transferable"),
    ("Vulkan", "Implemented OpenGL rendering", "none"),
    ("OpenGL", "Implemented Vulkan rendering", "none"),
    ("OpenGL or Vulkan", "OpenGL", "direct"),
    ("OpenGL and/or Vulkan", "Vulkan", "direct"),
    ("OpenGL and Vulkan", "OpenGL", "none"),
    ("OpenGL and Vulkan", "Implemented OpenGL and Vulkan renderers", "direct"),
    ("OpenGL or Vulkan", "Built graphics features in Unity and Unreal", "none"),
    ("Understand memory allocation", "Knowledge of memory allocation", "direct"),
    ("Optimize cache locality", "Knowledge of cache locality", "transferable"),
    ("Optimize cache locality", "Profiled cache locality", "direct"),
    ("Implement memory allocation", "Knowledge of memory allocation", "transferable"),
    ("Memory allocation and cache performance", "Optimized memory allocation", "none"),
    ("Memory allocation", "Improved application performance", "none"),
    ("Data-oriented programming", "Knowledge of data-oriented design", "direct"),
    ("Implement data-oriented programming", "Data-oriented design", "transferable"),
    ("Data-oriented programming", "Built a database analytics data pipeline", "none"),
    ("Strong foundation in Data Structures/Algorithms", "Implemented A* pathfinding", "transferable"),
    ("Algorithmic complexity", "Implemented Dijkstra", "transferable"),
    ("Runtime analysis", "Knowledge of algorithmic complexity and time complexity", "direct"),
    ("Data structures and algorithms", "Knowledge of data structures and algorithms", "direct"),
    ("Data structures and algorithms", "Built PostgREST data pipelines", "none"),
    ("Implement Dijkstra", "Implemented Dijkstra", "direct"),
    ("Software integration for clients", "Integrated client software systems", "direct"),
    ("Software integration for clients", "Integrated software systems", "transferable"),
    ("Software integration for clients", "Collaborated with clients", "none"),
    ("Software integration for clients", "Integrated with a customer team", "none"),
    ("Real-time telemetry", "Implemented real-time telemetry over UDP", "direct"),
    ("Real-time messaging", "Implemented WebSocket messaging", "direct"),
    ("Event-driven streaming", "Built an event-driven streaming pipeline using Kafka", "direct"),
    ("Real-time messaging", "Kafka and streaming", "transferable"),
    ("Real-time messaging using MQTT", "Implemented WebSocket messaging", "none"),
    ("Streaming systems", "Implemented WebSocket messaging", "none"),
    ("Real-time messaging", "Implemented REST APIs", "none"),
    ("Kubernetes certification", "Deployed Kubernetes workloads", "none"),
    ("Security in CI/CD", "Built Docker images with GitHub Actions", "none"),
    ("Kubernetes orchestration", "Built Docker images", "none"),
]

# Explicit expected first winner, including deliberately mixed surviving rows.
OVERLAPS = [
    ("REST API development using modern C++", "backend.api_development"),
    ("Android application frontend development", "mobile.android_development"),
    ("Client software integration and stakeholder collaboration", "integration.client_software"),
    ("Kubernetes security in CI/CD", "security.ci_cd"),
    ("Real-time messaging backend API development", "realtime.messaging_streaming"),
    ("OpenGL graphics for a custom game engine", "graphics.opengl_vulkan"),
    ("Kubernetes certification", "credential.certification"),
    ("Client collaboration", "collaboration.stakeholder"),
    ("Data-oriented programming and data processing", "systems.data_oriented_programming"),
]


class CapabilityTaxonomyV14Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(get_default_taxonomy().version, "phase6d-capability-taxonomy-v1.4")

    def test_unrecognised_context_stays_unrecognised(self):
        for text in ("Graphics programming", "External clients", "Client requirements", "C# programming"):
            with self.subTest(text=text):
                self.assertIsNone(classify_requirement({"text": text}))

    def test_devops_ids_are_not_duplicated(self):
        tax = get_default_taxonomy()
        ids = [c["capability_id"] for c in tax.capabilities]
        self.assertEqual(len(ids), len(set(ids)))
        for cid in ("devops.containerisation", "devops.kubernetes", "devops.ci_cd", "security.ci_cd"):
            self.assertEqual(ids.count(cid), 1)

    def test_preliminary_ceiling_strength_and_input_immutability(self):
        for label, strength, value in (("none", 0, 0), ("weak", 2, .2), ("transferable", 3, .55)):
            row = {"text": "Android application development", "match_label": label,
                   "match_value": value, "evidence_strength": strength,
                   "evidence": [{"text": "Built an Android application"}]}
            before = deepcopy(row)
            result = cap_requirement_with_taxonomy(row, retrieval_mode_override="off")
            self.assertEqual(result["match_label"], label)
            self.assertEqual(result["evidence_strength"], strength)
            self.assertEqual(row, before)

    def test_caps_lower_strength(self):
        row = {"text": "Modern C++ proficiency", "match_label": "direct", "match_value": 1,
               "evidence_strength": 5, "evidence": [{"text": "Built C++ software"}]}
        result = cap_requirement_with_taxonomy(row, retrieval_mode_override="off")
        self.assertEqual(result["match_label"], "transferable")
        self.assertEqual(result["evidence_strength"], 3)


def _case(requirement, evidence, expected):
    def test(self):
        result = evaluate_evidence({"text": requirement, "atomic_focus": requirement}, evidence)
        self.assertEqual(result["label"], expected, result)
    return test


def _overlap(requirement, expected):
    def test(self):
        self.assertEqual(classify_requirement({"text": requirement}), expected)
    return test


for index, values in enumerate(SEMANTICS):
    setattr(CapabilityTaxonomyV14Tests, f"test_semantics_{index:02d}", _case(*values))
for index, values in enumerate(OVERLAPS):
    setattr(CapabilityTaxonomyV14Tests, f"test_overlap_{index:02d}", _overlap(*values))
