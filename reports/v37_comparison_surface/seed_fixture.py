"""Disposable copy of real App156 state; reuse saved immutable artifacts/receipts."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import sqlite3,json,shutil,sys,os
root=Path(__file__).resolve().parents[2];out=Path(__file__).resolve().parent;folder=out/'disposable';(folder/'data').mkdir(parents=True,exist_ok=True);dest=folder/'data/applications.db'
assert not dest.exists(),'Do not overwrite an existing fixture database'
with sqlite3.connect((root/'data/applications.db').resolve().as_uri()+'?mode=ro',uri=True) as source:
 with sqlite3.connect(dest) as target:source.backup(target)
sys.path.insert(0,str(root));os.chdir(folder)
from database.tailoring_generation_control import get_tailoring_generation
from database.tailoring_version_manager import save_application_tailoring_generation
saved=json.loads((root/'reports/v37_real_bullet_quality/native_trial.json').read_text(encoding='utf-8'));gid=saved['result']['generation_id'];generation=get_tailoring_generation(156,gid);fit=deepcopy(generation['fit_result']);records=[]
for key in ('docx_path','pdf_path'):
 source=Path(fit[key]);source=source if source.is_absolute() else root/source
 destination=folder/'outputs/tailored_resumes'/source.name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination);assert source.read_bytes()==destination.read_bytes();fit[key]=str(destination);records.append({'source':str(source),'copy':str(destination),'sha256':sha256(destination.read_bytes()).hexdigest()})
assert records[0]['sha256']==saved['result']['a_docx_sha256']
save_application_tailoring_generation(application_id=156,generation_id=gid,fit_result=fit,docx_path=fit['docx_path'],pdf_path=fit['pdf_path'])
(out/'fixture.json').write_text(json.dumps({'application':156,'generation_id':gid,'artifacts':records,'cached_trial':'reports/v37_real_bullet_quality/native_trial.json','scope':'Actual saved real application copied to disposable DB; only artifact paths relocated through normal persistence API. No frozen identity, membership, scores or approvals edited.'},indent=2),encoding='utf-8')
