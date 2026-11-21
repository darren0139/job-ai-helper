import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path('reports/v37_bestof_release_ui_workspace').resolve()))
from sandbox import enable
enable()
names=['tests.test_relevance_corrections','tests.test_bullet_choice_lab','tests.test_ui_review_capture','tests.test_v37_b4_pair_comparison','tests.test_decision_explorer_pair_placement']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
if '--tests-only' in sys.argv:raise SystemExit(not r.wasSuccessful())
from tailoring.bullet_choice_lab import run_benchmarks,compare_runs
out=Path('reports/v37_relevance_corrections');after=run_benchmarks(selectors=False);before=json.loads((out/'before.json').read_text());(out/'after.json').write_text(json.dumps(after,indent=2));(out/'benchmark_diff.json').write_text(json.dumps(compare_runs(before,after),indent=2));print(before['summary']);print(after['summary']);raise SystemExit(not r.wasSuccessful())
