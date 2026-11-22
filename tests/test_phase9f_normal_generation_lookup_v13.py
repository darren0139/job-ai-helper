"""Normal F execution ownership is distinct from Workspace generation ownership."""
import json
import sqlite3
import unittest
from database.phase9f_session_revision import active_execution_row, ensure_tables

NORMAL='phase9f-f-normal-generation-lifecycle-v1'

FIELDS=('execution_id','execution_fingerprint','confirmation_id','confirmation_fingerprint',
        'phase9e_decision_fingerprint','starting_snapshot_fingerprint',
        'exact_jd_identity_fingerprint','evidence_snapshot_fingerprint','section_scope_fingerprint')


def prov(label):
    return {
        'execution_id':'exec-'+label,
        'execution_fingerprint':'exec-fp-'+label,
        'confirmation_id':'confirm-'+label,
        'confirmation_fingerprint':'confirm-fp-'+label,
        'phase9e_decision_fingerprint':'decision-'+label,
        'starting_snapshot_fingerprint':'start-'+label,
        'exact_jd_identity_fingerprint':'jd-'+label,
        'evidence_snapshot_fingerprint':'evidence-'+label,
        'section_scope_fingerprint':'scope-'+label,
    }


def settings(label, *, modification=None):
    p=prov(label)
    payload={'phase9f_f_normal_lifecycle':{'lifecycle_version':NORMAL,'generation_status':'completed','provenance':p},
             'phase9f_f_provenance':dict(p),
             'phase9e_binding':{'decision_fingerprint':p['phase9e_decision_fingerprint']}}
    if modification: modification(payload)
    return json.dumps(payload)


def make_db(c):
    c.executescript('''
        CREATE TABLE phase9f_application_confirmations (
            confirmation_id TEXT PRIMARY KEY, application_id INTEGER NOT NULL UNIQUE,
            confirmation_fingerprint TEXT, phase9e_decision_fingerprint TEXT);
        CREATE TABLE phase9f_tailoring_executions (
            execution_id TEXT PRIMARY KEY, application_id INTEGER NOT NULL UNIQUE,
            execution_fingerprint TEXT, confirmation_id TEXT, confirmation_fingerprint TEXT,
            phase9e_decision_fingerprint TEXT, starting_snapshot_fingerprint TEXT,
            exact_jd_identity_fingerprint TEXT, evidence_snapshot_fingerprint TEXT,
            section_scope_fingerprint TEXT, generation_id TEXT, stage_outputs_json TEXT);
        CREATE TABLE application_tailoring_generation_meta (
            application_id INTEGER, generation_id TEXT, generation_kind TEXT,
            phase9e_decision_fingerprint TEXT);
        CREATE TABLE application_tailoring_versions (
            application_id INTEGER, generation_id TEXT, generation_settings_json TEXT);
    ''')
    ensure_tables(c)
    for label, table, confirmation_table in (
        ('A', 'phase9f_tailoring_executions', 'phase9f_application_confirmations'),
        ('B', 'phase9f_execution_revisions', 'phase9f_confirmation_revisions'),
    ):
        p=prov(label)
        c.execute(f'''INSERT INTO {confirmation_table}
            (confirmation_id, application_id, confirmation_fingerprint, phase9e_decision_fingerprint)
            VALUES (?,?,?,?)''', (p['confirmation_id'],1,p['confirmation_fingerprint'],p['phase9e_decision_fingerprint']))
        c.execute(f'''INSERT INTO {table}
            (execution_id, application_id, execution_fingerprint, confirmation_id, confirmation_fingerprint,
             phase9e_decision_fingerprint, starting_snapshot_fingerprint, exact_jd_identity_fingerprint,
             evidence_snapshot_fingerprint, section_scope_fingerprint, generation_id, stage_outputs_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?)''', (
             p['execution_id'],1,p['execution_fingerprint'],p['confirmation_id'],p['confirmation_fingerprint'],
             p['phase9e_decision_fingerprint'],p['starting_snapshot_fingerprint'],
             p['exact_jd_identity_fingerprint'],p['evidence_snapshot_fingerprint'],
             p['section_scope_fingerprint'],json.dumps({'normal_lifecycle_adapter_version': NORMAL}),
            ))
        add_generation(c, 'gen-'+label,label)
    c.execute('INSERT INTO phase9f_active_revision VALUES (?,?,?,?)',
             (1,'confirm-B','confirm-A','phase9f-session-reconfirmation-v1'))


def add_generation(c, gen, label, *, content=None):
    c.execute('INSERT INTO application_tailoring_generation_meta VALUES (?,?,?,?)',
              (1,gen,'phase9f_f_normal_projects_skills','decision-'+label))
    c.execute('INSERT INTO application_tailoring_versions VALUES (?,?,?)',
              (1,gen,content or settings(label)))


class NormalHistoricalLookup(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.row_factory=sqlite3.Row
        self.addCleanup(self.c.close)
        make_db(self.c)

    def check_owner(self, gen, expected):
        row=active_execution_row(self.c,1,generation_id=gen)
        self.assertEqual(row['execution_id'], 'exec-'+expected)
        self.assertIsNone(row['generation_id'])

    def test_original_and_revision_normal_generations_resolve(self):
        self.check_owner('gen-A','A')
        self.check_owner('gen-B','B')
        self.assertEqual(active_execution_row(self.c,1)['execution_id'],'exec-B')

    def test_multiple_workspace_generations_share_one_frozen_execution(self):
        add_generation(self.c,'gen-A2','A')
        self.check_owner('gen-A','A')
        self.check_owner('gen-A2','A')
        self.check_owner('gen-B','B')

    def test_f_owned_rephrase_uses_same_immutable_context(self):
        add_generation(self.c,'gen-A-r','A')
        self.c.execute('UPDATE application_tailoring_generation_meta SET generation_kind=? WHERE generation_id=?',
                       ('phase9f_f_normal_jd_rephrase','gen-A-r'))
        self.check_owner('gen-A-r','A')

    def test_missing_generation_never_substitutes_active(self):
        self.assertIsNone(active_execution_row(self.c,1,generation_id='gen-unknown'))

    def test_corrupt_provenance_rejected(self):
        data=json.loads(settings('A'))
        data['phase9f_f_normal_lifecycle']['provenance']['execution_id']='exec-B'
        self.c.execute('UPDATE application_tailoring_versions SET generation_settings_json=? WHERE generation_id=?',
                       (json.dumps(data),'gen-A'))
        with self.assertRaisesRegex(ValueError,'provenance'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_decision_mismatch_rejected(self):
        self.c.execute('UPDATE application_tailoring_generation_meta SET phase9e_decision_fingerprint=? WHERE generation_id=?',
                       ('decision-B','gen-A'))
        with self.assertRaisesRegex(ValueError,'provenance'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_wrong_confirmation_identity_rejected(self):
        data=json.loads(settings('A'))
        data['phase9f_f_normal_lifecycle']['provenance']['confirmation_id']='confirm-B'
        data['phase9f_f_provenance']['confirmation_id']='confirm-B'
        self.c.execute('UPDATE application_tailoring_versions SET generation_settings_json=? WHERE generation_id=?',
                       (json.dumps(data),'gen-A'))
        with self.assertRaisesRegex(ValueError,'confirmation'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_execution_identity_mismatch_rejected(self):
        self.c.execute('UPDATE phase9f_tailoring_executions SET execution_fingerprint=? WHERE application_id=1',('evil',))
        with self.assertRaisesRegex(ValueError,'execution conflicts'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_legacy_private_stage_never_adopted_as_normal(self):
        self.c.execute('UPDATE phase9f_tailoring_executions SET stage_outputs_json=?',
                       (json.dumps({'projects':{'status':'completed'}}),))
        with self.assertRaisesRegex(ValueError,'legacy/private'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_explicit_misbound_generation_fails(self):
        self.c.execute('UPDATE phase9f_tailoring_executions SET generation_id=?',('gen-fake',))
        with self.assertRaisesRegex(ValueError,'explicit generation binding'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_missing_lifecycle_cannot_reuse_unbound_execution(self):
        self.c.execute('UPDATE application_tailoring_versions SET generation_settings_json=? WHERE generation_id=?',
                       (json.dumps({'phase9e_binding':{'decision_fingerprint':'decision-A'}}),'gen-A'))
        with self.assertRaisesRegex(ValueError,'generation binding conflicts'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_no_source_from_other_application(self):
        self.c.execute('UPDATE phase9f_tailoring_executions SET application_id=2')
        with self.assertRaisesRegex(ValueError,'missing or duplicate'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_invalid_generation_kind_rejected(self):
        self.c.execute('UPDATE application_tailoring_generation_meta SET generation_kind=? WHERE generation_id=?',
                       ('manual','gen-A'))
        with self.assertRaisesRegex(ValueError,'generation kind'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def _approval_probe(self, state, is_approvable):
        """Run the real approval function before its write boundary on a temp DB."""
        import tempfile
        from pathlib import Path
        from tests.test_phase9f_reconfirmation_integrity_seam import approval_function
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination=Path(temporary.name)/'phase9f.sqlite'
        self.c.commit()
        cloned=sqlite3.connect(destination)
        try:
            self.c.backup(cloned)
        finally:
            cloned.close()
        approve, namespace=approval_function()
        def connect():
            db=sqlite3.connect(destination)
            db.row_factory=sqlite3.Row
            return db
        namespace.update({
            'PHASE9F_F_NORMAL_LIFECYCLE_VERSION': NORMAL,
            'get_tailoring_generation':lambda app,gen:state,
            'get_phase9f_normal_generation_lifecycle':lambda gen: gen.get('generation_settings',{}).get('phase9f_f_normal_lifecycle',{}),
            'is_phase9f_normal_generation_approvable':lambda gen:is_approvable,
            '_connect':connect,
            'record_generation_metadata':lambda **kw:self.fail('Approval write boundary reached'),
        })
        return approve

    def test_missing_lifecycle_rejected_before_execution_lookup(self):
        state={'generation_kind':'phase9f_f_normal_projects_skills',
               'phase9e_decision_fingerprint':'decision-A','generation_settings':{}}
        approve=self._approval_probe(state,True)
        with self.assertRaisesRegex(ValueError,'legacy approval is forbidden'):
            approve(1,'gen-A')

    def test_valid_frozen_owner_reaches_incomplete_guard(self):
        state={'generation_kind':'phase9f_f_normal_projects_skills',
               'phase9e_decision_fingerprint':'decision-A',
               'generation_settings':{'phase9f_f_normal_lifecycle':{'lifecycle_version':NORMAL}}}
        approve=self._approval_probe(state,False)
        with self.assertRaisesRegex(ValueError,'incomplete or has not produced'):
            approve(1,'gen-A')


if __name__=='__main__': unittest.main()
