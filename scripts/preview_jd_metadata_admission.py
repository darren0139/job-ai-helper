"""Offline diagnostics, not an oracle. Run through the contained focused runner.

Writes only to that runner's disposable directory; never reads candidate inputs.
"""
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from analysis_stability import stable_evidence_scoring as n
from analysis_stability.coordinated_integration import build_coordinated_analysis
from analysis_stability.jd_metadata_policy import build_metadata_preview
from job_discovery.coordinated_sources import build_library_projection

ROOT = Path(__file__).resolve().parents[1]


def rows(analysis):
    return [{'id': r['requirement_id'], 'text': r['text'], 'importance': r['importance'],
        'allocation': r['group_weight_fraction'], 'label': r['match_label'],
        'match_value': r['match_value'], 'parent_credit': None if r['match_value'] is None else r['match_value']*r['group_weight_fraction'],
        'coverage_denominator_weight': n.IMPORTANCE_WEIGHTS.get(r['importance'],0)*r['group_weight_fraction'],
        'source_provenance': r['source_provenance']} for r in analysis['canonical_requirements']]


def summary(analysis):
    return {'scoring_version': analysis['scoring_version'], 'fingerprint': analysis['input_fingerprint'],
        'alignment': analysis['deterministic_alignment_score'],
        'required_core_coverage': analysis['required_core_coverage_score'],
        'allocation': sum(r['group_weight_fraction'] for r in analysis['canonical_requirements']),
        'labels': dict(Counter(r['match_label'] or 'REVIEW_REQUIRED' for r in analysis['canonical_requirements'])),
        'rows': rows(analysis)}


def native_inputs(raw, profile, resume_profile=None, raw_resume_text=''):
    canonical=n.canonicalise_requirements(profile,raw)
    keyword=n.build_deterministic_keyword_match(requirements=canonical['requirements'],acronym_map=canonical['acronym_map'],
        resume_profile=resume_profile or {},raw_resume_text=raw_resume_text)
    return dict(raw_jd_text=raw,jd_profile=profile,keyword_match=keyword,
        resume_profile=resume_profile or {},raw_resume_text=raw_resume_text,retrieval_mode_override='off')


class MetadataDiagnostics(unittest.TestCase):
    def test_export_synthetic_and_historical_geometry(self):
        fixture=json.loads((ROOT/'tests/fixtures/jd_metadata_admission_v1.json').read_text(encoding='utf-8'))
        projection=build_library_projection([{'id':1,'category':'Project','title':'Synthetic backend project',
            'bullets':['I developed REST APIs using Python.'],'skills':['Python']}])
        profile={'required_skills':['Period','Permanent','Location','Jurong East','Mon\u2013Fri 8am\u20135:30pm']}
        synthetic=[]
        for case in fixture['cases']:
            raw=(fixture['metadata']+fixture['core'] if case.get('layout')=='metadata_then_core'
                 else fixture['core']+fixture['metadata'] if case.get('layout')=='core_then_metadata' else case['raw'])
            inputs=native_inputs(raw,profile,**{k:projection['context'][k] for k in ('resume_profile','raw_resume_text')})
            before=n.build_stable_analysis(**inputs)
            old_gate=build_coordinated_analysis(source_projection=projection,**inputs)
            after=build_metadata_preview(developer_enabled=True,source_projection=projection,**inputs)
            synthetic.append({'case':case['id'],'published':summary(before),'v21':summary(old_gate),
                'v22':summary(after),'classification':after['jd_metadata_classification']})
        corpus=json.loads((ROOT/'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
        historical=[]
        for job in corpus['snapshot']['audit']['corpus']['jobs']:
            inputs=native_inputs(job['frozen_inputs']['raw_jd_text'],{})
            before=build_coordinated_analysis(**inputs)
            after=build_metadata_preview(developer_enabled=True,**inputs)
            old={r['requirement_id']:r for r in before['canonical_requirements']}
            new={r['requirement_id']:r for r in after['canonical_requirements']}
            changed=[{'text':new[k]['text'],'old_allocation':old[k]['group_weight_fraction'],
                      'new_allocation':new[k]['group_weight_fraction'],
                      'old_importance':old[k]['importance'],'new_importance':new[k]['importance']}
                     for k in old.keys() & new.keys()
                     if (old[k]['group_weight_fraction'],old[k]['importance']) != (new[k]['group_weight_fraction'],new[k]['importance'])]
            historical.append({'job_id':job['job_id'],'old_version':before['scoring_version'],'new_version':after['scoring_version'],
                'removed':[old[k]['text'] for k in old.keys()-new.keys()],
                'added':[new[k]['text'] for k in new.keys()-old.keys()], 'changed':changed,
                'old_count':len(old),'new_count':len(new),
                'old_allocation':sum(r['group_weight_fraction'] for r in old.values()),
                'new_allocation':sum(r['group_weight_fraction'] for r in new.values()),
                'old_empty_evidence_alignment':before['deterministic_alignment_score'],
                'new_empty_evidence_alignment':after['deterministic_alignment_score'],
                'ambiguous':[r['raw_text'] for r in after['jd_metadata_classification']['ambiguous_content']]})
        self.assertEqual(len(historical),30)
        # Stable ordering makes exports diffable; these are observations, never expectations.
        for record in historical:
            for key in ('added','removed'):record[key].sort()
            record['changed'].sort(key=lambda r:r['text'])
        target=Path(tempfile.gettempdir())/'jd_metadata_diagnostics.json'
        target.write_text(json.dumps({'synthetic':synthetic,'historical_empty_evidence':historical},
            sort_keys=True,ensure_ascii=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print('JD metadata diagnostic export: '+str(target),flush=True)
