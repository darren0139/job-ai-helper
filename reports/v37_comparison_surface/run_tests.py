import sys,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path[:0]=[str(root),str(root/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
names=['tests.test_decision_explorer_pair_placement','tests.test_v37_b4_pair_comparison','tests.test_v37_bullet_inspector','tests.test_phase9f_v37_decision_explorer','tests.test_normal_bestof_integration']
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(not result.wasSuccessful())
