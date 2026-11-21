"""Relocate immutable fixture artifacts via normal persistence API; no scoring/identity edits."""
from pathlib import Path
from copy import deepcopy
import os,sys,json,hashlib,shutil
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));os.chdir(root/'reports/v37_benchmark_lab/disposable')
from database.tailoring_generation_control import get_tailoring_generation
from database.tailoring_version_manager import save_application_tailoring_generation
f=json.loads((root/'reports/v37_normal_final_fixture/fixture.json').read_text(encoding='utf-8'))
g=get_tailoring_generation(2,f['generation_id']);fit=deepcopy(g['fit_result']);folder=Path.cwd()/'outputs/tailored_resumes';folder.mkdir(parents=True,exist_ok=True);record=[]
for field in ['docx_path','pdf_path']:
 source=Path(fit[field]);dest=folder/source.name
 if not dest.exists():shutil.copy2(source,dest)
 assert source.read_bytes()==dest.read_bytes()
 record.append({'source':str(source),'copy':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()});fit[field]=str(dest)
save_application_tailoring_generation(application_id=2,generation_id=f['generation_id'],fit_result=fit,docx_path=fit['docx_path'],pdf_path=fit['pdf_path'])
(root/'reports/v37_benchmark_lab/fixture_relocation.json').write_text(json.dumps({'generation_id':f['generation_id'],'artifacts':record,'identity_edits':False,'api':'save_application_tailoring_generation; only paths relocated to owned fixture output directory'},indent=2),encoding='utf-8')
print('Fixture artifacts byte-identical; owned paths persisted through normal API.')
