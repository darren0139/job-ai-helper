import sys,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
# Profiled cold pandas import exceeded AppTest default3s; warm dependency only.
import pandas
out=Path(__file__).resolve().parent
names=['tests.test_benchmark_public_fixture','tests.test_cpp_relevance_identity','tests.test_relevance_corrections','tests.test_v37_bestof_release','tests.test_v37_b4_pair_comparison','tests.test_decision_explorer_pair_placement','tests.test_ui_review_capture','tests.test_bullet_choice_lab','tests.test_normal_bestof_integration','tests.test_v37_guarded_integration']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
if '--tests-only' in sys.argv:raise SystemExit(not r.wasSuccessful())
from tailoring.bullet_choice_lab import run_benchmarks,compare_runs
from tailoring.bullet_choice_lab_ui import exports
from zipfile import ZipFile
from io import BytesIO
before=json.loads((ROOT/'reports/v37_relevance_corrections/after.json').read_text());after=run_benchmarks();(out/'benchmark_after.json').write_text(json.dumps(after,indent=2));(out/'benchmark_diff.json').write_text(json.dumps(compare_runs(before,after),indent=2))
payload,csv,zipped=exports(after)
with ZipFile(BytesIO(zipped)) as z:
 assert z.testzip() is None and z.read('run.json')==payload and z.read('results.csv')==csv
assert after['executed']==116 and after['summary']['real_unlabelled']==20 and after['summary']['real_accuracy'] is None
assert after['summary']['selector_pass']==7 and after['summary']['selector_fail']==0
(out/'export_check.json').write_text(json.dumps({'zip_crc':'pass','json_csv_bytes':'pass','real_labels_remain_unavailable':True}))
print('Benchmark',after['summary']);raise SystemExit(not r.wasSuccessful())
