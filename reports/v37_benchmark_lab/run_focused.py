"""Named focused tests; process-local existing Windows sandbox TEMP adapter."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root),str(root/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
import unittest
names=['tests.test_bullet_choice_lab','tests.test_bullet_relevance_diagnostic','tests.test_v37_b4_pair_comparison','tests.test_v37_bullet_inspector','tests.test_normal_bestof_integration'] if '--ui' in sys.argv else ['tests.test_phase9f_certified_selection_v36','tests.test_v37_guarded_integration']
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
