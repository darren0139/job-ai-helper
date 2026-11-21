from pathlib import Path
import sys,os,unittest
root=Path.cwd();sys.path.insert(0,str(root));sys.path.insert(0,str(root/'reports/v37_bestof_release_ui_workspace'))
from sandbox import enable
enable();os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
names=['tests.test_normal_bestof_integration','tests.test_bullet_relevance_diagnostic','tests.test_v37_bullet_inspector','tests.test_v37_b4_pair_comparison','tests.test_v37_b2_ui_repair','tests.test_phase9f_v365_explainability','tests.test_v37_guarded_integration','tests.test_v37_bestof_release.BestOfRelease.test_factual_review_reuses_displayed_slate_and_still_applies_selected_base_floor','tests.test_v37_bestof_release.BestOfRelease.test_existing_fit_panel_waits_for_explicit_comparison','tests.test_application_session_first_analysis_binding','tests.test_full_page_job_finder_and_score_ui']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names));sys.exit(not r.wasSuccessful())



