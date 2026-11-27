import unittest, copy
from tailoring.technology_database_evidence_v312b219b import requirement, evaluate, apply_policy, VERSION
from tailoring.phase9f_scoring_policy_registry_v312b2190 import B215,B219A,B219B,LEGACY,policy_path
F='Proficiency in one or more frontend framework (HTML5/Angular/React JS)'
B='Proficiency in one or more backend languages (Java/.NET/Python/PHP)'
D='Proficiency in database will be an added advantage'

def row(text,section='projects',n=0):
    return {'text':text,'section':section,'source':f'resume_profile.projects[0].bullets[{n}]' if section=='projects' else 'resume_profile.skills.languages[0]' if section=='skills' else 'raw_resume_text[0]','evidence_id':str(n)}

class TechnologyPolicyTests(unittest.TestCase):
    def label(self,req,text,label,section='projects',raw=None):
        hit=evaluate(requirement(req),row(text,section),text if raw is None else raw)
        self.assertEqual(hit[0] if hit else 'none',label,(req,text,hit))
    def test_frontend(self):
        self.label(F,'Built full-stack help-desk workflows in a 4-person team using React and Supabase/PostgreSQL, connecting frontend ticket-management features with a secure database-backed service.','direct')
    def test_backend(self):
        self.label(B,'Developed Java REST API endpoints to support data exchange between backend services and the Unity-based Maritime Digital Twin, collaborating on MinIO storage integration.','direct')
        self.label(B,'Implemented REST API endpoints using Python.','direct')
    def test_database(self):
        self.label(D,'Implemented SQLite-backed saved application sessions with reports and persistent chat history.','direct')
        self.label(D,'Implemented PostgreSQL schema and queries for a web application.','direct')
        self.label(D,'Connected frontend to the PostgreSQL-backed service.','transferable')
    def test_skill_only(self):
        self.label(F,'React','transferable','skills');self.label(B,'Python','transferable','skills');self.label(D,'SQLite','weak','skills')
        self.label(F,'React','none','skills',raw='No React experience.')
    def test_not_backend(self):
        for t in ('Used Python to clean datasets.','Built a client for Java backend services.','Developed React frontend using Java REST API endpoints.','Consumed Java REST API endpoints.','Developed REST API endpoints for Java service using Python; no Java work.'):
            self.label(B,t,'none')
    def test_not_frontend(self):
        for t in ('Built a Python service for React frontend.','Built backend API using React frontend.','The team built a React frontend.','Planned to build a React frontend.','Built a dashboard without React.','React, JavaScript, HTML5'):
            self.label(F,t,'none')
    def test_not_database(self):
        for t in ('PostgreSQL, SQLite, Supabase','Built a UI without database access using SQLite.','The vendor implemented PostgreSQL queries.','Planned to implement PostgreSQL schema.','Built a game asset manager.'):
            self.label(D,t,'none')
    def test_relational_not_nosql(self):
        self.label('Experience with relational databases','Implemented MongoDB schema and queries.','none')
    def test_unknown_and_conjunction_abstain(self):
        for t in ('Proficiency in Python and Java','Proficiency in one or more backend languages (Python/UnknownLang)','Advanced database administration','Proficiency in databases and Kubernetes','Experience with Python or Java and Docker','Proficiency in one or more frontend frameworks (React and Angular)'):
            self.assertIsNone(requirement(t),t)
    def test_explicit_or(self):
        self.label('Proficiency in Python or Java','Implemented REST API endpoints using Python.','direct')
        self.label('Proficiency in Python or Java','Used Python to clean datasets.','transferable')
    def test_no_hidden_profile(self):
        self.label(B,'Developed Java REST API endpoints.','none',raw='Built a game.')
    def test_no_cross_row(self):
        a={'text':B,'requirement_id':'r','importance':'core','group_weight_fraction':1,'match_label':'none'}
        rows, audit=apply_policy([a],[row('Developed REST API endpoints.'),row('Java','skills',1)],'Developed REST API endpoints.\nJava')
        self.assertEqual(rows[0]['match_label'],'transferable');self.assertEqual(len(rows[0]['evidence']),1);self.assertEqual(rows[0]['evidence'][0]['text'],'Java');self.assertFalse(audit[0]['combined_evidence_rows'])
    def test_scope_and_input_immutable(self):
        a={'text':D,'requirement_id':'r','importance':'preferred','group_weight_fraction':0.5,'atomic_group_id':'g','match_label':'none'};b={'text':'Degree in Computer Science','match_label':'direct'};c={**a,'score_eligible':False};inp=[a,b,c];before=copy.deepcopy(inp)
        rows,audit=apply_policy(inp,[row('Implemented SQLite-backed saved application sessions.')]);self.assertEqual(inp,before);self.assertEqual(rows[0]['group_weight_fraction'],0.5);self.assertEqual(rows[1:],inp[1:]);self.assertEqual(len(audit),1)
    def test_registered_successor(self):
        self.assertEqual(policy_path(B219A,B219B),(B219A,B219B));self.assertEqual(policy_path(B215,B219B),(B215,B219A,B219B));self.assertIsNone(policy_path(B219B,B219A));self.assertIsNone(policy_path(B219A,B219B+'-unknown'))
        for old in LEGACY:self.assertEqual(policy_path(old,B219B),(old,B215,B219A,B219B))
