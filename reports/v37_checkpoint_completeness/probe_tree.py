"""Named focused checks against exact committed tree, with isolated temp data."""
import os, sys, json, importlib, unittest, tempfile, socket
import types
from pathlib import Path
from unittest.mock import patch
OUT=Path(__file__).resolve().parent; TREE=OUT/'committed_tree'; ROOT=OUT.parents[1]
sys.path=[str(TREE)]+[p for p in sys.path if p and Path(p).resolve()!=ROOT and 'Job-AI-Helper/reports' not in p.replace('\\','/')]
os.chdir(OUT)
os.environ.update(DOTENV_DONT_LOAD='1',LITELLM_LOCAL_MODEL_COST_MAP='True',PYTHONDONTWRITEBYTECODE='1')
# Process-local environment adapter used in earlier focused checks; no source edits.
class TempOS:
    def __getattr__(self,k):return getattr(os,k)
    def mkdir(self,path,mode=0o777,**kwargs):os.mkdir(path,0o777,**kwargs)
tempfile._os=TempOS()
def no_network(*a,**k): raise OSError('Network disabled in checkpoint audit')
socket.socket.connect=no_network;socket.socket.connect_ex=no_network
import pandas

if '--remaining-source-tests' in sys.argv:
    suite=unittest.TestSuite()
    for name in ['test_phase9f_joint_resume_optimizer_v2_6','test_phase9f_v364_baseline_and_decisions','test_phase9f_frozen_source_smoke']:
        mod=types.ModuleType('tests.'+name);mod.__file__=str(TREE/'tests'/f'{name}.py')
        sys.modules[mod.__name__]=mod
        try:exec(compile((ROOT/'tests'/f'{name}.py').read_bytes(),mod.__file__,'exec'),mod.__dict__)
        except Exception as e:print('IMPORT ERROR',name,type(e).__name__,str(e))
        else:suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(mod))
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    (OUT/'remaining_test_probes.json').write_text(json.dumps({'run':r.testsRun,'failures':[(str(t),s) for t,s in r.failures],'errors':[(str(t),s) for t,s in r.errors],'skips':[(str(t),s) for t,s in r.skipped]},indent=2),encoding='utf-8')
    raise SystemExit(not r.wasSuccessful())

if '--additional-probes' in sys.argv:
    results={}
    # Actual committed DB approval entry point; intercept all possible writes.
    db=importlib.import_module('database.tailoring_generation_control')
    state={'generation_settings':{'phase9f_f_normal_lifecycle':{'lifecycle_version':'phase9f-f-normal-generation-lifecycle-v1','generation_status':'completed','fit':{'status':'completed'}}},'fit_result':{'fit_one_page':True}}
    with patch.object(db,'get_tailoring_generation',return_value=state),patch.object(db,'record_generation_metadata',side_effect=AssertionError('Reached metadata-write boundary before Selected Base floor')) as writer,patch('tailoring.phase9f_v361_approval_floor.verify_current_phase9f_floor',return_value={'ready':False,'reason':'Selected Base is worse'}) as floor:
        try: db.approve_tailoring_generation(156,'audit-generation')
        except Exception as e:results['direct_db_approval']={'exception':type(e).__name__,'message':str(e),'floor_calls':floor.call_count,'write_boundary_reached':writer.called}
    # Untracked test imports loaded from their source without adding source roots.
    for name in ['test_phase9f_combined_selection_v2_7','test_phase9f_v361_approval_floor']:
        source=ROOT/'tests'/f'{name}.py'
        try:exec(compile(source.read_bytes(),str(TREE/'tests'/f'{name}.py'),'exec'),{'__name__':'audit_probe_'+name,'__file__':str(TREE/'tests'/f'{name}.py')})
        except Exception as e:results[name]={'status':'import_failed','exception':type(e).__name__,'message':str(e)}
        else:results[name]={'status':'import_succeeded'}
    (OUT/'additional_probes.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2));raise SystemExit(0)

names=['tests.test_normal_bestof_integration','tests.test_v37_bestof_release','tests.test_v37_b4_pair_comparison','tests.test_decision_explorer_pair_placement','tests.test_v37_bullet_inspector','tests.test_v37_guarded_integration','tests.test_ui_review_capture','tests.test_benchmark_public_fixture']
if '--compatibility-tests' in sys.argv:
    os.chdir(TREE)
    names=['tests.test_application_session_first_analysis_binding.FirstAnalysisBindingTests.test_ui_blank_origins_and_exact_bound_jd_are_passive',
      'tests.test_full_page_job_finder_and_score_ui.FullPageAndSessionControlsTests.test_phase8_calculation_remains_native_and_unchanged',
      'tests.test_job_match_session_ab.JobMatchSessionABTests.test_streamlit_contract_extends_existing_phase8_view',
      'tests.test_phase8_score_explainability.Phase8ScoreExplainabilityTests.test_score_receipt_v5_compact_and_export_contract']
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
r=unittest.TextTestRunner(verbosity=2).run(suite)
origins={k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.startswith(('tailoring.','database.','browser_integration.','tests.')) and getattr(v,'__file__',None)}
leaks={k:v for k,v in origins.items() if not Path(v).is_relative_to(TREE)}
assert not leaks,leaks
(OUT/('compatibility_tests.json' if '--compatibility-tests' in sys.argv else 'committed_tests.json')).write_text(json.dumps({'modules':names,'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':[(str(t),s) for t,s in r.skipped],'module_origins':origins,'source_leaks':leaks},indent=2),encoding='utf-8')
raise SystemExit(not r.wasSuccessful())
