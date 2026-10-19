"""Stage 2H diagnostics only: immutable independent profiles through v1.19.

No policy simulation feeds back into scoring. Exceptions, contract expectations
and independent semantic judgments remain separate. Run under the existing
offline check launcher, not an unguarded production app.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from analysis_stability import stable_evidence_scoring as native
from analysis_stability.coordinated_integration import IDENTITIES
from scripts.coordinated_acceptance import parents

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/fixtures/coordinated_realistic_profiles_v1.json'


def original_occurrences(profile, raw):
    """Enumerate supplied bullet/raw origins without native deduplication."""
    rows = []
    for section in ('projects', 'experience'):
        for i, item in enumerate(profile.get(section, [])):
            for j, text in enumerate(item.get('bullets', [])):
                rows.append({'source': f'resume_profile.{section}[{i}].bullets[{j}]', 'text': text})
    rows.extend({'source': f'raw_resume_text[{i}]', 'text': text} for i, text in enumerate(raw.splitlines()))
    return rows


def review_card(row):
    """Diagnostic view model, not Streamlit or a new scoring disposition.

    Do not pool missing actions or convert unknown credit to zero. Display only
    per-original observations. No user résumé changes or evidence invention.
    """
    rec = row['coordinated_action_receipt']
    pending = rec['disposition'] == 'REVIEW_REQUIRED'
    return {'requirement': row['text'], 'status': rec['disposition'],
        'credit_display': 'Unavailable — review required' if pending else str(row['match_value']),
        'message': ('The supplied originals do not establish an admitted disposition. This is not a finding of no experience.'
                    if pending else 'Governed synthetic development result; publication remains blocked.'),
        'r1_blocker': (rec.get('r1_exclusion') or {}).get('reason'),
        'originals': [{'evidence_id': key, 'source': item['record']['source'], 'text': item['record']['text'],
                       'supported_actions': item['proof'].get('supported_actions', []),
                       'unproven_actions': item['proof'].get('missing_actions', []),
                       'denied_actions': item['proof'].get('denied_actions', []),
                       'technical_scope': item['proof'].get('technical_scope'),
                       'admission': item['admission']}
                      for key, item in rec['proofs'].items()]}


@lru_cache(maxsize=1)
def run_study():
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    parent_by_family = {p['obligation']['object_family']: p for p in parents()}
    rows, details, errors = [], {}, []
    for case in fixture['cases']:
        parent = parent_by_family[case['family']]
        # Source text is independently copied into the fixture, not built from
        # detector output. Check its grounding rather than silently substituting.
        assert fixture['source_objects'][case['family']] in parent['original_raw_parent']
        supplied = deepcopy(case['profile'])
        before = deepcopy(supplied)
        raw = case['raw_resume_text']
        try:
            analysis = native.build_stable_analysis(jd_profile={}, keyword_match={},
                resume_profile=supplied, raw_resume_text=raw, raw_jd_text=parent['raw_jd'],
                retrieval_mode_override='off', coordinated_actions_enabled=True)
            assert supplied == before, 'Pipeline modified a supplied profile'
            selected = next(r for r in analysis['canonical_requirements'] if
                            r.get('scoring_parent_occurrence_id') == parent['parent_occurrence_id'])
            rec = selected['coordinated_action_receipt']
            originals = native.build_resume_evidence_index(before, raw)
            occurrences = original_occurrences(before, raw)
            not_retained = [r for r in occurrences if not any(
                p['source'] == r['source'] and p['text'] == r['text'] for p in originals)]
            for r in not_retained:
                r['same_text_retained_elsewhere'] = any(p['text'] == r['text'] for p in originals)
            unknown_fields = sorted(set(before)-{'projects', 'experience', 'education', 'skills', 'certifications'})
            coordinated = [r for r in analysis['canonical_requirements'] if r.get('coordinated_action_receipt')]
            pending = [r for r in coordinated if r['coordinated_action_receipt']['disposition'] == 'REVIEW_REQUIRED']
            label = (selected['match_label'] or 'REVIEW_REQUIRED').upper()
            row = {k: deepcopy(case[k]) for k in ('id', 'family', 'theme', 'expected_current_label',
                'independent_evidence_class', 'independent_semantic_label', 'independent_reason', 'generalization_candidate')}
            row.update(job_id=parent['job_id'], actual_label=label, native_label=rec['native_label'],
                disposition=rec['disposition'], parent_credit=rec['synthetic_parent_contribution'],
                whole_jd_score=analysis['deterministic_alignment_score'],
                whole_jd_withheld=analysis['deterministic_alignment_score'] is None,
                pending_parent_ids=[r['requirement_id'] for r in pending],
                r1_reason=(rec.get('r1_exclusion') or {}).get('reason'),
                contract_agreement=label == case['expected_current_label'],
                semantic_agreement=label == case['independent_semantic_label'],
                missing_core_sections=sorted({'projects', 'experience', 'education', 'skills'}-before.keys()),
                unknown_profile_fields=unknown_fields, supplied_bullet_raw_origins=len(occurrences),
                unretained_origins=not_retained,
                selected_sources=[{'source': r['source'], 'evidence_id': r['evidence_id'], 'text': r['text']}
                                  for r in selected.get('evidence', [])],
                stages=deepcopy(rec['stages']))
            rows.append(row)
            details[case['id']] = {'profile': before, 'raw_resume_text': raw, 'analysis': analysis,
                                   'target': selected, 'original_index': originals,
                                   'review_cards': [review_card(r) for r in coordinated]}
            print('Stage 2H '+case['id']+': '+label+' / '+rec['disposition'], flush=True)
        except Exception as error:
            errors.append({'id': case['id'], 'exception': type(error).__name__+': '+str(error)})
    assert FIXTURE.read_bytes() == fixture_bytes, 'Independent fixture changed during execution'
    return {'kind': 'STAGE_2H_ACTUAL_SYNTHETIC_AUDIT_NOT_NEW_POLICY',
            'identities': deepcopy(IDENTITIES), 'fixture_sha256': hashlib.sha256(fixture_bytes).hexdigest(),
            'rows': rows, 'details': details, 'errors': errors,
            'counts': dict(Counter(r['actual_label'] for r in rows)),
            'withheld': sum(r['whole_jd_withheld'] for r in rows),
            'contract_discrepancies': [r['id'] for r in rows if not r['contract_agreement']],
            'semantic_discrepancies': [r['id'] for r in rows if not r['semantic_agreement']]}


def write_diagnostics(directory):
    """Write only task-owned ignored diagnostics; never a fixture dependency."""
    directory = Path(directory).resolve()
    if not directory.is_relative_to(ROOT/'reports'):
        raise ValueError('Diagnostic exports must remain under ignored reports/')
    directory.mkdir(parents=True, exist_ok=True)
    result = run_study()
    target = directory/'actual_profiles.json'
    if target.exists():
        raise FileExistsError('Preserve existing diagnostic exports')
    target.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    return target
