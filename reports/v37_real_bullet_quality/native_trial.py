"""One bounded actual Best-of candidate, disposable outputs; original DB read-only."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import sys,os,json,shutil
r=Path(__file__).resolve().parents[2];sys.path[:0]=[str(r),str(r/'reports/v37_bestof_release_ui_workspace')]
from sandbox import enable
enable();os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
from tailoring.phase9f_v37_corpus_benchmark import load_case,readonly_db
from tailoring.phase9f_joint_resume_optimizer_v2_6 import materialize_verified_candidate
from tailoring.phase9f_certified_selection_v36 import build_certified_optimization,selected_base_floor_gate
from tailoring.phase9f_automatic_bestof_v30 import evaluate_auto,verify_fitted_a_against_baselines
out=Path(__file__).resolve().parent;work=out/'disposable';dest=work/'outputs/tailored_resumes';dest.mkdir(parents=True,exist_ok=True)
try:
 with readonly_db(r/'data/applications.db') as db:c=load_case(db,251,r)
 source=dest/c['source_docx'].name;shutil.copy2(c['source_docx'],source);assert sha256(source.read_bytes()).hexdigest()==c['audit']['docx_sha256']
 fit=deepcopy(c['generation']['fit_result']);fit['docx_path']=str(source)
 generation=deepcopy(c['generation']);generation['fit_result']=fit
 proposal=build_certified_optimization(c['audit'],c['projects'])
 variants=proposal.get('candidate_variants') or [proposal];chosen=deepcopy(variants[0]);chosen.pop('candidate_variants',None)
 result=evaluate_auto(audit=c['audit'],projects=c['projects'],fit=fit,generation=generation,baseline_report=c['baseline'],raw_jd_text=c['raw_jd_text'],source_docx=source,repo_root=work,application_id=156,optimizer=lambda _a,_p:chosen,generator=materialize_verified_candidate)
 starting=verify_fitted_a_against_baselines(audit=c['audit'],fit=fit,generation=generation,baseline_report=c['baseline'],raw_jd_text=c['raw_jd_text'],source_docx=source)
 result['a_vs_starting']=starting;result=selected_base_floor_gate(result,starting)
 record={'application':156,'candidate_limit':1,'proposal':chosen,'result':result,'scope':'Current production-constrained Best-of. Factual review not auto-granted. Not an individual bullet causal comparison.'}
except Exception as e:record={'status':'unavailable','error_type':type(e).__name__,'reason':str(e)}
(out/'native_trial.json').write_text(json.dumps(record,indent=2,ensure_ascii=False,default=str),encoding='utf-8');print(json.dumps({k:record.get('result',record).get(k) for k in ['status','reason','winner','a_score','b_score','hard_regressed_ids']},ensure_ascii=True))

