"""The Phase 9F smoke must give the verifier a genuine frozen DOCX."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import is_zipfile

from parse import read_resume_docx
from scripts.check_phase9f_tailoring_execution import main


class Phase9FFrozenSourceSmokeTests(unittest.TestCase):
    def test_frozen_selected_base_is_readable_until_verification_finishes(self):
        frozen_paths = []

        def observe_parser(path, **kwargs):
            path = Path(path)
            if path.name == "frozen_selected_base.docx":
                self.assertTrue(path.is_file())
                self.assertTrue(is_zipfile(path), "Expected a real DOCX package")
                frozen_paths.append(path)
            return read_resume_docx(str(path), **kwargs)

        output = StringIO()
        with patch("parse.read_resume_docx", side_effect=observe_parser), redirect_stdout(output):
            main()

        self.assertEqual(len(frozen_paths), 1)
        self.assertFalse(frozen_paths[0].parent.exists())
        self.assertIn("phase8=preapproval_then_approved", output.getvalue())
