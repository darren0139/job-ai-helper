"""Explicitly authored controls, frozen before evaluator implementation. Read-only sources."""
import hashlib,json,sqlite3,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/bullet_choice_benchmark';OUT.mkdir(exist_ok=True)
def sha(v):return hashlib.sha256(v).hexdigest()
# Each role has distinct capability wording; variants are relationship controls, not real experience.
ROLES=[
 ('backend','Build Python REST APIs','Design PostgreSQL schemas','Built Python REST APIs serving authenticated requests.','Designed PostgreSQL schemas for transactional records.'),
 ('frontend','Develop React accessible interfaces','Implement browser performance monitoring','Developed React accessible interfaces with keyboard navigation.','Implemented browser performance monitoring for client routes.'),
 ('fullstack','Implement Node.js authentication services','Build Redis caching','Implemented Node.js authentication services for account access.','Built Redis caching for repeated queries.'),
 ('mobile','Create Kotlin Android applications','Integrate camera image attachments','Created Kotlin Android applications tracking workout sessions.','Integrated camera image attachments into workout entries.'),
 ('qa','Execute unit testing and integration testing','Maintain test reports','Executed unit testing and integration testing for checkout services.','Maintained test reports for release review.'),
 ('devops','Set up GitHub Actions deployment pipelines','Configure Terraform cloud infrastructure','Set up GitHub Actions deployment pipelines for release builds.','Configured Terraform cloud infrastructure for staging environments.'),
 ('data','Build Apache Spark ingestion pipelines','Maintain data quality checks','Built Apache Spark ingestion pipelines for warehouse events.','Maintained data quality checks for warehouse records.'),
 ('security','Perform penetration testing','Implement audit logging','Performed penetration testing on internal applications.','Implemented audit logging for account operations.'),
 ('embedded','Develop C++ control software','Integrate sensor drivers','Developed C++ control software for constrained devices.','Integrated sensor drivers into device firmware.'),
 ('platform','Configure Kubernetes cluster networking','Automate service health checks','Configured Kubernetes cluster networking for isolated services.','Automated service health checks for production workloads.'),
 ('ios','Create Swift iOS applications','Design offline synchronization','Created Swift iOS applications for field operators.','Designed offline synchronization for mobile records.'),
 ('reliability','Implement incident response automation','Analyze distributed tracing','Implemented incident response automation for on-call workflows.','Analyzed distributed tracing for service diagnostics.')]
cases=[]
def add(dataset,cid,jd,reqs,a,b,expected,coverage,kind,split,source=None):
 cases.append(dict(id=cid,dataset=dataset,jd_id=jd['id'],jd_text=jd['text'],jd_sha256=sha(jd['text'].encode()),category=jd['category'],requirements=reqs,base=a,library=b,expected=expected,expected_coverage=coverage,rationale=kind,negative_control='Negation/name-dropping/repetition never establishes completed work.',split=split,source=source or {'kind':'synthetic authored control; not applicant experience'}))
for i,(role,core,pref,a,b) in enumerate(ROLES):
 req=[{'id':f's{i}_core','text':core,'importance':'core'},{'id':f's{i}_bonus','text':pref,'importance':'preferred'}]
 jd={'id':f'SJD{i+1:02}','category':role,'text':f'{role.title()} Engineer. Responsibilities: {core}. Preferred: {pref}.'}
 split='development' if i<8 else 'held_out'
 # Preserve wording families within a single JD split; no exact pair crosses splits.
 variants=[(a,'Tools: '+core+'.','Base stronger',[req[0]['id']], 'Performed work versus unsupported terminology'),
 ('Did not '+core[0].lower()+core[1:]+'.',a,'Library stronger',[req[0]['id']],'Negation must not earn experience coverage'),
 (a,a,'Equivalent',[req[0]['id']],'Identical wording is one contribution with shared provenance'),
 (a,b,'Base stronger',[req[0]['id']],'Core evidence takes priority over unrelated preferred capability'),
 (a,a+' '+b,'Library stronger',[q['id'] for q in req],'Longer wording adds an independent relevant capability')]
 # Complementary and redundancy controls use two Core capabilities, not a Core/bonus override.
 if i in (1,4,8,10):
  req[1]['importance']='core';jd['text']=jd['text'].replace('Preferred:','Responsibilities:')
  variants[3]=(a,b,'Complementary',[q['id'] for q in req],'Distinct Core contributions are complementary')
 if i in (2,6,9,11):variants[4]=(a,a+' '+a,'Equivalent',[req[0]['id']],'Repeating identical work adds no new requirement coverage')
 for j,(x,y,label,cov,why) in enumerate(variants):add('synthetic',f'S{i+1:02}-{j+1}',jd,req,x,y,label,cov,why,split)
# Corpus anchors: immutable snapshot classifications, preserved exactly; no reparsing or scorer calls.
anchors=[(15,'req_2e581717a7ab','Implemented robust security protocols to protect national infrastructure.'),
 (16,'req_88b6b8db1ad8','Implemented validation checks, monitoring, and alerting to ensure data quality, consistency, and lineage across the data platform.'),
 (31,'req_bc26569100e0','Designed robust MongoDB and Elasticsearch data solutions for high-volume transactions and CRUD operations.'),
 (35,'req_fd62c2abf0b8','Performed penetration testing against internal services.'),
 (44,'req_b019e34d6212','Led software and hardware integration for robotic systems.'),
 (141,'req_5a2fe56ceb02','Implemented secure coding practices in reviewed services.'),
 (144,'req_2e36ef47aacf','Designed, developed, and executed comprehensive test plans and test cases covering functional and non-functional requirements.'),
 (146,'req_0ec16745d552','Designed and created automated tests to ensure functionality of components and applications.')]
packet=Path('C:/Users/Admin/Downloads/job_ai_helper_phase2d3_rebaseline_v14.zip')
with zipfile.ZipFile(packet) as z:raw=z.read('full_raw_42_jds.json');cohort=json.loads(raw)
conn=sqlite3.connect((ROOT/'data/applications.db').resolve().as_uri()+'?mode=ro',uri=True)
used=[];unavailable=[]
for index,(job,rid,strong) in enumerate(anchors):
 original=next(q for q in cohort if q['cohort']=='FROZEN' and q['job_id']==job)
 saved=conn.execute('select s.id,s.stable_analysis_json,j.description from job_match_snapshots s join discovered_jobs j on j.id=s.discovered_job_id and j.content_hash=s.job_content_hash where j.id=? order by s.id desc limit 1',(job,)).fetchone()
 if not saved or ' '.join(saved[2].split())!=' '.join(original['jd'].split()):unavailable.append(job);continue
 native=json.loads(saved[1]);q=next(q for q in native['canonical_requirements'] if q['requirement_id']==rid)
 if q.get('evidence_eligible') is False or q.get('score_eligible') is False:unavailable.append(job);continue
 req=[{**q,'id':rid}];jd={'id':f'FROZEN-{job}','category':'corpus','text':original['jd']}
 source={'kind':'synthetic bullets; real frozen JD requirement','job_id':job,'snapshot_id':saved[0],'snapshot_sha256':sha(saved[1].encode()),'cohort':'FROZEN','packet_sha256':sha(raw),'raw_jd_sha256':original['raw_jd_sha256']}
 assert sha(original['jd'].encode())==original['raw_jd_sha256']
 # Assertions concern direction of demonstrated versus negated/name-only activity, not full compound satisfaction.
 controls=[(strong,'Keywords: '+q['text'],'Base stronger','Performed claim versus a requirement pasted as keywords'),('Planning to '+strong[0].lower()+strong[1:],strong,'Library stronger','A future plan is not performed experience'),(strong,'Did not '+strong[0].lower()+strong[1:],'Base stronger','Negated claim is not performed experience')]
 for j,(a,b,label,why) in enumerate(controls):add('corpus',f'C{job}-{j+1}',jd,req,a,b,label,[rid],why,'development' if index<5 else 'held_out',source)
 used.append(job)
conn.close()
# Real comparisons retained byte-for-byte inside source_case; no expected labels generated.
real_path=ROOT/'reports/v37_real_bullet_quality/cases.json'
for c in json.loads(real_path.read_text(encoding='utf-8')):
 reqs=c['jd_requirements']
 add('real',c['case_id'],{'id':f'APP-{c["application"]}','category':'real saved','text':c['jd_text']},reqs,c['base']['bullet'],c['library']['bullet'],None,[], 'No independently declared real expected label.','observation',{'kind':'saved real application','cases_sha256':sha(real_path.read_bytes())})
 cases[-1]['source_case']=c
payload={'schema_version':1,'dataset_version':'bullet-choice-lab-v1','expectation_authority':'Authored metamorphic/control relationships, frozen before evaluator; NOT independent real-world gold labels.','split_policy':'Whole JD/capability family split. Repeated mutation mechanisms across splits deliberately test invariants; this is not independent semantic generalization. Real wording groups remain correlated.','cohort_inventory':{'frozen':30,'retrospective':12,'used_frozen_jobs':used,'unavailable_anchors':unavailable,'retrospective_used':0,'packet_sha256':sha(raw)},'cases':cases}
b=(json.dumps(payload,indent=2,ensure_ascii=False)+'\n').encode();(OUT/'v1.json').write_bytes(b);(OUT/'v1.sha256').write_text(sha(b)+'\n',encoding='utf-8');print(len(cases),'cases frozen',sha(b))
