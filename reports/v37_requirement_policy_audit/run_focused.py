import sys,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path[:0]=[str(root),str(root/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
names=['tests.test_reviewed_jd_knowledge_release','tests.test_requirement_importance_supporting','tests.test_requirement_importance_context_supporting','tests.test_phase9f_ncs_419_compatibility_v2.NCSFormattingAnd419CandidateTests.test_419_manifest_integrity_and_exact_source_membership','tests.test_v37_guarded_integration']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names));raise SystemExit(not r.wasSuccessful())
