"""Independent conflict/occurrence controls; no new selection or union policy."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from analysis_stability import coordinated_conflicts as conflicts
from analysis_stability import coordinated_policy as policy
from analysis_stability import stable_evidence_scoring as native
from scripts.coordinated_acceptance import parents

FIXTURE = Path(__file__).with_name('fixtures')/'coordinated_conflict_policy_v1.json'


def packet(family='embedded', negative=None, relation='same', experience=False):
    parent = next(p for p in parents() if p['obligation']['object_family'] == family)
    obj = parent['obligation']['object']
    positive = 'I designed, developed, maintained '+obj+'.'
    if family == 'backend':
        positive += ' Designed REST API interfaces and implemented REST API endpoints in Java.'
    section = 'experience' if experience else 'projects'
    profile = {'projects': [], 'experience': [], 'education': [], 'skills': {}}
    profile[section] = [{'title': 'Independent project', 'bullets': [positive]}]
    raw = ''
    if negative:
        negative = negative.format(object=obj)
        if relation == 'same': profile[section][0]['bullets'].append(negative)
        elif relation == 'different': profile[section].append({'title':'Independent project','bullets':[negative]})
        elif relation == 'raw': raw = negative
        elif relation == 'summary': profile['summary'] = negative
    # The original ledger must exist before the deduplicated index.
    ledger = conflicts.build_ledger(profile, raw)
    index = native.build_resume_evidence_index(profile, raw)
    ledger = conflicts.attach_index_coverage(ledger, index)
    selected = next(r for r in index if r['source'] == f'resume_profile.{section}[0].bullets[0]')
    obligation = policy.prior.ground_to_raw_jd(parent['obligation'], parent['raw_jd'])
    return profile, obligation, selected, ledger, index


class ConflictContractTests(unittest.TestCase):
    def test_independent_scope_and_protocol_controls(self):
        for case in json.loads(FIXTURE.read_text())['controls']:
            with self.subTest(control=case['id']):
                _, o, selected, ledger, index = packet(case['family'], case['negative'], case['relation'])
                result = conflicts.inspect_selected(o, selected, ledger, index)
                self.assertEqual(result['status'], case['status'])
                self.assertEqual(result['quarantine'], case['status'] != 'NO_APPLICABLE_CONFLICT')

    def test_same_experience_occurrence_not_other_experience(self):
        for relation, status in (('same','PROVEN_CONFLICT'),('different','NO_APPLICABLE_CONFLICT')):
            _, o, selected, ledger, index = packet(negative='Never maintained {object}.', relation=relation, experience=True)
            self.assertEqual(conflicts.inspect_selected(o, selected, ledger, index)['status'], status)

    def test_duplicate_occurrences_retained_without_selectable_fallback(self):
        profile, o, selected, _, _ = packet(negative='Never maintained {object}.')
        profile['projects'].append({'title':'Other project', 'bullets':[selected['text']]})
        ledger = conflicts.build_ledger(profile)
        index = native.build_resume_evidence_index(profile, '')
        ledger = conflicts.attach_index_coverage(ledger, index)
        duplicates = [r for r in ledger['occurrences'] if r['text'] == selected['text']]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(len({r['occurrence_id'] for r in duplicates}), 2)
        self.assertEqual({r['index_status'] for r in duplicates}, {'INDEXED_ORIGINAL','DUPLICATE_OTHER_ORIGIN'})
        self.assertEqual(conflicts.inspect_selected(o, selected, ledger, index)['status'], 'PROVEN_CONFLICT')
        fallback = {k: duplicates[1][k] for k in ('source','section','text','evidence_id')}
        self.assertEqual(conflicts.inspect_selected(o, fallback, ledger, index)['status'], 'UNCERTAIN_SOURCE')

    def test_forged_source_never_declared_clean(self):
        _, o, selected, ledger, index = packet()
        for key in ('evidence_id','source','text','section'):
            self.assertTrue(conflicts.inspect_selected(o, {**selected, key:'FORGED'}, ledger, index)['quarantine'])

    def test_normalized_duplicate_and_unavailable_original_coverage(self):
        profile, o, selected, _, _ = packet()
        profile['projects'].append({'title': 'Other project', 'bullets': [selected['text'].upper()]})
        ledger = conflicts.attach_index_coverage(conflicts.build_ledger(profile),
                                                  native.build_resume_evidence_index(profile, ''))
        duplicate = next(r for r in ledger['occurrences'] if r['source'] == 'resume_profile.projects[1].bullets[0]')
        self.assertEqual(duplicate['index_status'], 'DUPLICATE_OTHER_ORIGIN')
        profile['projects'][0]['bullets'].append(None)
        ledger = conflicts.build_ledger(profile)
        result = conflicts.inspect_selected(o, selected, ledger, native.build_resume_evidence_index(profile, ''))
        self.assertEqual(result['status'], 'UNCERTAIN_SCOPE')
        self.assertEqual(result['findings'][0]['kind'], 'SOURCE_COVERAGE')

    def test_ledger_and_inspection_are_read_only_and_deterministic(self):
        profile, o, selected, ledger, index = packet(negative='Never maintained {object}.')
        frozen = deepcopy((profile, ledger, index))
        first = conflicts.inspect_selected(o, selected, ledger, index)
        self.assertEqual(first, conflicts.inspect_selected(o, selected, ledger, index))
        self.assertEqual((profile, ledger, index), frozen)
        self.assertTrue(first['findings'][0]['negative_original']['original_text'])
        self.assertEqual(first['findings'][0]['relationship'], 'SAME_ORIGINAL_CONTAINER')

    def test_endpoint_routes_are_not_globally_equated(self):
        for route, expected in (('/orders','NO_APPLICABLE_CONFLICT'),('/users','PROVEN_CONFLICT')):
            profile, o, _, _, _ = packet('backend')
            profile['projects'][0]['bullets'][0] = ('I designed, developed, maintained '+o['object']+'. '
                'Designed REST API interfaces and implemented REST API endpoints for /users.')
            profile['projects'][0]['bullets'].append('Never implemented REST API endpoints for '+route+'.')
            ledger = conflicts.build_ledger(profile)
            index = native.build_resume_evidence_index(profile, '')
            selected = next(r for r in index if r['source'].endswith('.bullets[0]'))
            self.assertEqual(conflicts.inspect_selected(o, selected, ledger, index)['status'], expected)
