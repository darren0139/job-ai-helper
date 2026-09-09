from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from database import tailoring_version_manager as base_manager
from database.global_blueprint_tag_manager import list_blueprint_tags
from tests.phase9d_test_support import seed_phase9d_database


HARNESS = Path(__file__).with_name("blueprint_tag_library_streamlit_harness.py")


def _by_key(elements, key):
    return next(element for element in elements if element.key == key)


class BlueprintTagLibraryStreamlitAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.old_environment = os.environ.get("PHASE9D_TEST_DATABASE")
        self.database_path = Path(self.temporary.name) / "tag-library-ui.sqlite"
        seed_phase9d_database(self.database_path)
        os.environ["PHASE9D_TEST_DATABASE"] = str(self.database_path)

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        if self.old_environment is None:
            os.environ.pop("PHASE9D_TEST_DATABASE", None)
        else:
            os.environ["PHASE9D_TEST_DATABASE"] = self.old_environment
        self.temporary.cleanup()

    def test_system_library_renders_and_custom_tag_can_be_created(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        tag_table = app.dataframe[0].value
        self.assertIn("Backend", set(tag_table["Tag"].tolist()))
        self.assertIn("AI", set(tag_table["Tag"].tolist()))

        _by_key(app.text_input, "blueprint_tag_create_label").set_value(
            "Security"
        ).run()
        _by_key(app.text_input, "blueprint_tag_create_category").set_value(
            "Technical domain"
        ).run()
        _by_key(app.button, "blueprint_tag_create").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                "created custom blueprint tag" in message.value.lower()
                for message in app.success
            )
        )
        self.assertIn(
            "Security",
            {row["label"] for row in list_blueprint_tags()},
        )

    def test_app_registers_top_level_tag_library_route(self):
        source = (HARNESS.parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('"Tag Library"', source)
        self.assertIn('elif page == "Tag Library":', source)
        self.assertIn("render_blueprint_tag_library()", source)


if __name__ == "__main__":
    unittest.main()
