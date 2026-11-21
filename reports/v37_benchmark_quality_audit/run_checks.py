import json,sys,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable()
from tailoring.bullet_choice_lab import SELECTOR_CASES
out=Path(__file__).resolve().parent;results=[]
for name in SELECTOR_CASES:
 proc=subprocess.run([sys.executable,'-B','-m','tailoring.bullet_choice_lab','--selector-case',name],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=12)
 if proc.returncode:results.append({'case_id':name,'pass':None,'error':proc.stderr[-1500:]})
 else:results.append(json.loads(proc.stdout))
(out/'selector_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
names=['tests.test_relevance_corrections','tests.test_bullet_choice_lab.EstimatedControls','tests.test_bullet_choice_lab.LabContracts.test_frozen_cases_and_split_identities','tests.test_bullet_choice_lab.LabContracts.test_regression_and_incompatible_run_detection','tests.test_v37_guarded_integration']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
print('Selector contracts:',[(x['case_id'],x['pass']) for x in results]);raise SystemExit(not (r.wasSuccessful() and all(x['pass'] is True for x in results)))
