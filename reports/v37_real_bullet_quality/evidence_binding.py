from hashlib import sha256
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint
from tailoring.phase9f_v365_jd_evidence import requirement_catalog

def bind(case,receipt):
 d=receipt.get('document_analysis') or {};authority=d.get('final') or {};native=receipt.get('after_stable_analysis') or {}
 if not authority:return {},'No saved actual-document authority'
 checks=[(d.get('final_document_sha256')==case['audit']['docx_sha256'],'DOCX hash mismatch'),
  (authority.get('jd_text_sha256')==sha256(case['raw_jd_text'].encode()).hexdigest(),'JD hash mismatch'),
  (authority.get('stable_analysis_fingerprint')==fingerprint_value(native),'Native analysis fingerprint mismatch'),
  (authority.get('fingerprint')==fingerprint_value({k:v for k,v in authority.items() if k!='fingerprint'}),'Authority fingerprint mismatch'),
  (authority.get('canonical_requirement_fingerprint')==canonical_requirement_scope_fingerprint(native.get('canonical_requirements',[])),'Requirement fingerprint mismatch'),
  ((authority.get('identity') or {}).get('scoring_version')==native.get('scoring_version'),'Scorer identity mismatch')]
 for passed,why in checks:
  if not passed:return {},why
 catalog=requirement_catalog(case['baseline'],case['projects'])
 frozen={k:(v['text'],v['importance']) for k,v in catalog.items()}
 saved={v['requirement_id']:(v['text'],v['importance']) for v in native['canonical_requirements']}
 if frozen!=saved:return {},'Saved native requirement text/importance differs from case catalog'
 return {'status':'verified','a_docx_sha256':case['audit']['docx_sha256'],'native_document_evidence':{'existing':{'docx_sha256':case['audit']['docx_sha256'],'requirements':native['canonical_requirements']}}},'Bound existing-document citations only; no candidate/bullet delta measured'
