from pathlib import Path
import sys,os,unittest
r=Path.cwd();sys.path[:0]=[str(r),str(r/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable();os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
names=['tests.test_normal_bestof_integration','tests.test_v37_bestof_release.BestOfRelease.test_factual_review_reuses_displayed_slate_and_still_applies_selected_base_floor','tests.test_phase8_score_explainability','tests.test_score_component_tables_ui','tests.test_score_component_tables_arrow_ui','tests.test_score_component_stacked_v12','tests.test_score_component_point_labels_v122','tests.test_score_component_native_max_v123']
print('Named tests:',names,flush=True)
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names));sys.exit(not r.wasSuccessful())
