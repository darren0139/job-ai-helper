from __future__ import annotations
import json, sqlite3, tempfile, unittest
from pathlib import Path
from tailoring.portfolio_quality_v311 import optimize_portfolio_projects
from tailoring.portfolio_quality_corpus_v311 import audit_saved_corpus

def p(name, count, matches=None, score=25):
    return {'project_id':name,'title':name,'display_title':name,
            'draft_bullets':['Implemented '+name+' feature '+str(i) for i in range(count)],
            'project_fit_score':score,'requirement_matches':matches if matches is not None else []}

def m(r, importance='preferred', match='direct'):
    return {'requirement_id':r,'importance':importance,'match_label':match}

def wrap(rows): return {'recommended_projects':rows, 'unchanged_marker':{'x':1}}

class PortfolioTests(unittest.TestCase):
    def test_darren_prefers_deeper_two_projects(self):
        rows=[p('job',7,[m('core1','core'),m('db')],100),p('query',3,[m('db')],62),
              p('workout',1,[],0),p('migration',1,[m('core2','core','weak')],38),p('cyber',1,[],0)]
        src=wrap(rows)
        out=optimize_portfolio_projects(src)
        self.assertEqual([r['title'] for r in out['recommended_projects']],['job','query'])
        self.assertEqual(src,wrap(rows))
        self.assertEqual(out['portfolio_quality_selection']['candidate_count'],26)
        self.assertEqual(out['portfolio_quality_selection']['status'],'proxy_selected_not_native_verified')

    def test_required_one_bullet_project_retained(self):
        rows=[p('backend',4,[m('r1','required')],90),p('cloud',1,[m('aws','required')],10),p('game',3,[],0)]
        selected=optimize_portfolio_projects(wrap(rows))['recommended_projects']
        self.assertIn('cloud',[r['title'] for r in selected])

    def test_weak_is_not_credit(self):
        rows=[p('a',3,[m('core','required')],95),p('b',3,[m('not_credit','required','weak')],70),p('c',1,[],0)]
        rec=optimize_portfolio_projects(wrap(rows))['portfolio_quality_selection']
        self.assertEqual(rec['baseline']['hard_required_core_covered'],1)

    def test_no_evidence_holds(self):
        with self.assertRaisesRegex(ValueError,'no independently linked'):
            optimize_portfolio_projects(wrap([p('a',1),p('b',3)]))

    def test_one_project_exception(self):
        out=optimize_portfolio_projects(wrap([p('a',1,[m('core','required')])]))
        self.assertEqual(out['portfolio_quality_selection']['minimum_rule'],'one_project_exception_only_saved_project')

    def test_duplicate_id_refused(self):
        with self.assertRaisesRegex(ValueError,'duplicated'):
            optimize_portfolio_projects(wrap([p('a',2),p('a',1)]))

    def test_invalid_bullets_refused(self):
        x=p('a',2,[m('r')]);x['draft_bullets']=['']
        with self.assertRaisesRegex(ValueError,'bullets'):
            optimize_portfolio_projects(wrap([x,p('b',2)]))

    def test_stable_order_and_no_cross_project_mutation(self):
        src=wrap([p('a',3,[m('r1','required')]),p('b',1,[m('r2','preferred')]),p('c',1,[])])
        first=optimize_portfolio_projects(src)
        second=optimize_portfolio_projects(src)
        self.assertEqual(first,second)
        self.assertEqual(src['recommended_projects'][1]['draft_bullets'], ['Implemented b feature 0'])

    def test_no_unmeasured_full_native_score(self):
        out=optimize_portfolio_projects(wrap([p('a',3,[m('r1','required')]),p('b',2,[m('r2')])]))
        data=out['portfolio_quality_selection']
        self.assertNotIn('native_job_match',data)
        self.assertTrue(data['no_candidate_generations_persisted'])

    def test_corpus_readonly_and_does_not_change_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'test.db'
            c=sqlite3.connect(db)
            c.executescript('CREATE TABLE applications (id INTEGER);'
                'INSERT INTO applications(id) VALUES (1);'
                'CREATE TABLE application_tailoring_versions (application_id INTEGER,generation_id TEXT, projects_json TEXT);'
                'CREATE TABLE application_tailoring_generation_meta (application_id INTEGER,generation_id TEXT,status TEXT);')
            c.execute('INSERT INTO application_tailoring_versions VALUES (?,?,?)',
                 (1,'gen',json.dumps(wrap([p('a',2,[m('core','core')]),p('b',2,[m('pref')])]))))
            c.execute('INSERT INTO application_tailoring_generation_meta VALUES (?,?,?)',(1,'gen','approved'))
            c.commit();c.close()
            before=db.read_bytes();report=audit_saved_corpus(db,run_dedupe=False)
            self.assertEqual(db.read_bytes(),before)
            self.assertEqual(report['generations_checked'],1)
            self.assertEqual(report['generations'][0]['historical_status'],'approved')
            self.assertEqual(report['held'],0)

if __name__=='__main__': unittest.main()
