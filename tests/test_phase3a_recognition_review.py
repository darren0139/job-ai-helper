"""Read-only recognition hypotheses, not approved definitions or candidate gold.

Reuse the maintenance engine's native temporary taxonomy scope. No governor
result/review receipt is manufactured and no scoring replay is attempted.
"""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from analysis_stability import stable_evidence_scoring as parser
from analysis_stability.coordinated_runtime import approved_alias_surface_preview
from scripts import preview_bulk_unresolved_v1 as corpus
from tailoring.capability_taxonomy import (
    CapabilityTaxonomy, get_default_taxonomy, temporary_taxonomy_scope,
    _validate_capability,
)
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve

STAKEHOLDER = 'collaboration.stakeholder'
API = 'backend.api_development'


def hypothetical_overlay(kind):
    """Unapproved minimal inflections only; preserve every existing guard/rule."""
    entries = deepcopy(list(get_default_taxonomy().capabilities))
    for entry in entries:
        if entry['capability_id'] == STAKEHOLDER and kind in ('stakeholder_plural', 'combined'):
            entry['requirement']['any_terms'].append('stakeholders')
        if entry['capability_id'] == API and kind in ('api_plural', 'combined'):
            template = next(v for v in entry['requirement']['contextual_phrase_variants']
                            if v['phrase'] == 'web services')
            variant = deepcopy(template)
            variant['phrase'] = 'restful apis'
            entry['requirement']['contextual_phrase_variants'].append(variant)
    seen = set()
    for entry in entries:
        _validate_capability(entry, seen)
    return CapabilityTaxonomy('unapproved-review-only-' + kind, tuple(entries))


def recognition(row):
    result = resolve(row)
    diagnostics = result['taxonomy_diagnostics']
    return dict(knowledge_status=result['knowledge_status'],
                capability_id=result['decision']['capability_id'],
                resolution_source=result['resolution_source'],
                reason=diagnostics['reason'], matched_phrase=diagnostics.get('matched_phrase'),
                recognition_rule=result.get('recognition_rule'),
                rejected_candidate_rules=diagnostics.get('rejected_candidate_rules', []))


def compare(rows, overlay):
    baseline = [recognition(r['input']) for r in rows]
    frozen = corpus.fingerprint(rows)
    with temporary_taxonomy_scope(overlay):
        after = [recognition(r['input']) for r in rows]
    if frozen != corpus.fingerprint(rows):
        raise AssertionError('Original requirement geometry mutated')
    changes = []
    for row, old, new in zip(rows, baseline, after):
        if (old['knowledge_status'], old['capability_id']) != (new['knowledge_status'], new['capability_id']):
            changes.append(dict(job_id=row['job_id'], requirement_id=row['requirement_id'],
                input_fingerprint=corpus.fingerprint(row['input']), input=deepcopy(row['input']),
                before=old, after=new))
    return dict(before=dict(Counter(r['knowledge_status'] for r in baseline)),
                after=dict(Counter(r['knowledge_status'] for r in after)), changes=changes,
                evidence_credit_evaluated=False, requirement_geometry_changed=False)


class RecognitionReviewTests(unittest.TestCase):
    def test_inflection_hypotheses_preserve_existing_rules_and_restore_context(self):
        base = get_default_taxonomy()
        frozen = deepcopy(base.capabilities)
        for kind in ('stakeholder_plural', 'api_plural', 'combined'):
            overlay = hypothetical_overlay(kind)
            for cid in (STAKEHOLDER, API):
                old = base.by_id()[cid]
                new = overlay.by_id()[cid]
                self.assertEqual({k:v for k,v in old.items() if k!='requirement'},
                                 {k:v for k,v in new.items() if k!='requirement'})
                for key, value in old['requirement'].items():
                    if isinstance(value, list):
                        self.assertTrue(all(v in new['requirement'][key] for v in value))
                    else:
                        self.assertEqual(value, new['requirement'][key])
            with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                with temporary_taxonomy_scope(overlay):
                    raise RuntimeError('synthetic')
            self.assertIs(get_default_taxonomy(), base)
        self.assertEqual(base.capabilities, frozen)

    def test_positive_and_counterexample_controls_are_not_human_approval(self):
        controls = [
            ('Collaborate with stakeholders', 'stakeholder_plural', None, STAKEHOLDER, 'positive interaction candidate'),
            ('Generate dashboards for stakeholders', 'stakeholder_plural', None, STAKEHOLDER, 'unsafe beneficiary-only counterexample'),
            ('Do not collaborate with stakeholders', 'stakeholder_plural', None, STAKEHOLDER, 'unsafe negation counterexample'),
            ('General teamwork', 'stakeholder_plural', None, None, 'negative unnamed teamwork'),
            ('Customer collaboration', 'stakeholder_plural', STAKEHOLDER, STAKEHOLDER, 'existing approved phrase'),
            ('Experience building RESTful APIs', 'api_plural', API, API, 'existing complete bounded fallback'),
            ('Develop efficient secure RESTful APIs', 'api_plural', None, API, 'qualified recognition candidate'),
            ('Consume RESTful APIs', 'api_plural', None, API, 'recognition is not authorship'),
            ('Read RESTful APIs documentation', 'api_plural', None, API, 'unsafe reading-only counterexample'),
            ('Do not develop RESTful APIs', 'api_plural', None, API, 'unsafe negation counterexample'),
            ('Develop RESTful APIs and maintain MongoDB', 'api_plural', None, API, 'unsafe whole-parent credit counterexample'),
            ('Experience with Amazon Web Services', 'api_plural', None, None, 'protected AWS exclusion'),
            ('Implement web services', 'api_plural', API, API, 'existing product-guarded variant preserved'),
            ('Develop REST APIs', 'api_plural', API, API, 'existing approved fallback'),
            ('Experience with RESTfulness', 'api_plural', None, None, 'whole phrase boundary'),
        ]
        receipts = []
        for text, kind, before, after, purpose in controls:
            row = {'text':text, 'importance':'core'}
            self.assertEqual(recognition(row)['capability_id'], before, text)
            with temporary_taxonomy_scope(hypothetical_overlay(kind)):
                observed = recognition(row)
                self.assertEqual(observed['capability_id'], after, text)
            receipts.append(dict(original_requirement=text, hypothesis=kind, before=before,
                                 after=observed, purpose=purpose, human_approval=False))
        scratch = os.environ.get('JOB_MATCH_TEST_SCRATCH')
        if scratch:
            (Path(scratch)/'recognition_controls.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')

    def test_same_corpus_views_native_temporary_recognition_impact(self):
        base = get_default_taxonomy()
        protected = {name:corpus.sha(corpus.ROOT/name) for name in (
            'taxonomy/capability_taxonomy_v1.json', 'analysis_stability/stable_evidence_scoring.py',
            'analysis_stability/coordinated_runtime.py', 'tailoring/production_requirement_resolver.py',
            'taxonomy_discovery/maintenance_service.py', 'taxonomy_discovery/resolver_improvement.py')}
        jobs, sources = corpus.load_jobs()
        inventory = corpus.build_inventory(jobs)
        self.assertEqual(len(jobs), 30)
        views = {'saved':inventory['saved_rows'], 'raw_native':inventory['raw_jd_only_rows']}
        impacts = {name:{kind:compare(rows,hypothetical_overlay(kind))
                        for kind in ('stakeholder_plural','api_plural','combined')}
                   for name,rows in views.items()}
        with approved_alias_surface_preview():
            raw = []
            for view in jobs:
                job = view['job']
                canonical = parser.canonicalise_requirements({},raw_jd_text=job['frozen_inputs']['raw_jd_text'])
                raw.extend(dict(job_id=job['job_id'],requirement_id=r['requirement_id'],input=r)
                           for r in canonical['requirements'])
            views['raw_v126'] = raw
            impacts['raw_v126'] = {kind:compare(raw,hypothetical_overlay(kind))
                                  for kind in ('stakeholder_plural','api_plural','combined')}
        selected = [r for r in inventory['raw_jd_only_rows'] if r['current']['knowledge_status']=='UNRESOLVED'
                    and any(p['capability_id'] in (STAKEHOLDER,API) for p in r['predicate_observations'])]
        counts = Counter(p['capability_id'] for r in selected for p in r['predicate_observations']
                         if p['capability_id'] in (STAKEHOLDER,API))
        self.assertEqual(counts, {STAKEHOLDER:9,API:4})
        raw_sources = {v['job']['job_id']:v['job']['frozen_inputs']['raw_jd_text'] for v in jobs}
        for row in selected:
            self.assertTrue(row['input']['source_provenance'])
            for parent in row['input']['source_provenance']:
                self.assertIn(parent['raw_parent_text'],raw_sources[row['job_id']])
        self.assertEqual(len(views['saved']),727)
        self.assertEqual(len(views['raw_native']),716)
        self.assertEqual(len(views['raw_v126']),716)
        self.assertIs(get_default_taxonomy(),base)
        self.assertTrue(all(corpus.sha(corpus.ROOT/name)==digest for name,digest in protected.items()))
        body = dict(source_files=sources,current_taxonomy_sha256=corpus.sha(corpus.ROOT/'taxonomy/capability_taxonomy_v1.json'),
                    protected_sha256=protected,
                    selected_source_cases=[dict(job_id=r['job_id'],requirement_id=r['requirement_id'],
                        input=deepcopy(r['input']),input_fingerprint=r['input_fingerprint'],
                        current=recognition(r['input']),observations=r['predicate_observations']) for r in selected],
                    impacts=impacts, approvals_created=0, database_accesses=0, candidate_scores_replayed=0)
        body['fingerprint']=corpus.fingerprint(body)
        scratch = os.environ.get('JOB_MATCH_TEST_SCRATCH')
        if scratch:
            (Path(scratch)/'recognition_review.json').write_text(
                json.dumps(corpus.safe(body),sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('RECOGNITION_REVIEW',json.dumps({name:{k:dict(before=v['before'],after=v['after'],
            changed=len(v['changes']),jobs=sorted({r['job_id'] for r in v['changes']}))
            for k,v in kinds.items()} for name,kinds in impacts.items()},sort_keys=True))
