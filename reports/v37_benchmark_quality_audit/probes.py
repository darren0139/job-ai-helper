import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tailoring.bullet_choice_estimated import estimate_pair,terms
cases=[
('generic','Proficiency in database will be an added advantage','Added automated unit tests.','Implemented database queries.','Generic added/advantage must not imply database experience.'),
('explicit_alternative','Proficiency in one or more frontend framework (HTML5/Angular/React JS)','Built React JS frontend interfaces.','Skills: React JS','React is an applicable alternative; keyword-list lacks performed activity.'),
('plain_or','Use either React or Angular','Developed React interfaces.','Developed Angular interfaces.','Either/or alternatives should not be conjunctive deficiencies; proficiency still unverified.'),
('and','Execute unit and integration testing','Added unit tests.','Added unit and integration tests.','Unit only supports a subactivity; it does not establish integration.'),
('passive','Perform unit testing','Unit tests were authored for the API.','Authored unit tests for the API.','Positive performed-action paraphrases; authoring is outside current whitelist.'),
('future','Perform unit testing','Will implement unit tests.','Implemented unit tests.','Future work not performed work.'),
('negated','Perform unit testing','Never implemented unit tests.','Implemented unit tests.','Negated work not performed work.'),
('nominal','Perform unit testing','Responsibility: implementation of unit testing for API releases.','Implemented unit tests for API releases.','Unstructured factual-style responsibility; nominal descriptions may be conservatively withheld.'),
('mixed_negation','Perform unit and integration testing','Implemented unit tests, but not integration tests.','Implemented unit tests.','Whole-sentence negation can erase a genuinely positive subclaim.'),
('test_plans','Create test plans','Created test plans for API releases.','Plan to create test plans for API releases.','Legitimate plans noun must remain distinct from future intent.'),
('repetition','Perform unit testing','Keywords: unit testing unit testing unit testing.','Implemented unit tests.','Repeated terminology not activity.'),
('identity','Implement Java services','Implemented JavaScript services.','Implemented Java services.','JavaScript is not Java.'),
('namespace_false_support','Good foundation in modern C/C++ programming','Built focused programming tutorials.','Built a C++ asset manager.','No C++ identity is present in Base; focused must not become technical evidence.'),
('postgresql_capability','Proficiency in database will be an added advantage','Connected frontend services to PostgreSQL.','Connected frontend services to a database.','Named PostgreSQL is relevant database terminology, not less relevant simply for omitting database.'),
('performing_after_taxonomy','Develop React interfaces','Built React interfaces.','Built React interfaces.','Equivalent explicit wording is not verified proficiency.'),
('partial_long_compound','Write automated tests and work with our QA team to ensure the operation and correctness of new product features','Added automated unit tests in CI.','Added cover letter generation.','Explicit automated-test subactivity should be explained without full compound credit.')]
cases.append(('postgresql_with_action','Proficiency in database will be an added advantage','Built frontend services connected to PostgreSQL.','Built frontend services connected to a database.','Both actions are admitted; isolate missing PostgreSQL-to-database relationship.'))
cases.append(('positive_not_only','Perform unit testing','Implemented not only unit tests but also integration tests.','Implemented unit tests.','Whole-sentence negation can suppress positive not-only constructions.'))
rows=[]
for name,req,a,b,question in cases:
 result=estimate_pair(a,b,[{'id':name,'text':req,'importance':'preferred' if name=='postgresql_capability' else 'core'}]);rows.append({'id':name,'requirement':req,'base':a,'library':b,'audit_question':question,'result':result,'scope':'New analyst-designed diagnostic probe, not an independent labelled benchmark or frozen case'})
# Parent deduplication and surrounding-text redundancy use existing evaluator contracts.
q={'id':'same','text':'Perform unit testing','importance':'core'}
rows.append({'id':'duplicate_parent','result':estimate_pair('Implemented unit tests.','Implemented unit tests.',[q,q]),'audit_question':'Same parent ID appears once; no weight addition.'})
rows.append({'id':'conflicting_parent','result':estimate_pair('Implemented unit tests.','Implemented unit tests.',[q,{**q,'importance':'preferred'}]),'audit_question':'Conflicting identity withheld.'})
rows.append({'id':'surrounding_duplicate','result':estimate_pair('Implemented unit tests.','Implemented unit tests and API integration.',[q],selected=['Implemented unit tests.']),'audit_question':'Surrounding duplicate does not add unique requirement coverage.'})
q2={'id':'other','text':'Implement PostgreSQL transactions','importance':'core'}
rows.append({'id':'complementary','result':estimate_pair('Implemented unit tests.','Implemented PostgreSQL transactions.',[q,q2]),'audit_question':'Different supported requirements may be complementary, not a forced winner.'})
Path(__file__).with_name('probes.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print([(r['id'],r['result']['outcome']) for r in rows])
