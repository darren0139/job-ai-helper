"""Independent provenance contract before the source-aware scoring hook."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from analysis_stability import coordinated_conflicts as conflicts
from analysis_stability import coordinated_policy as policy
from analysis_stability import stable_evidence_scoring as native
from job_discovery.coordinated_sources import build_library_projection, verified_projection_ledger
from scripts.coordinated_acceptance import parents

FIXTURE = Path(__file__).with_name('fixtures')/'coordinated_library_projection_v1.json'


def source_items(denial=None, other_project=False):
    parent = next(p for p in parents() if p['obligation']['object_family'] == 'embedded')
    positive = 'I designed, developed, maintained '+parent['obligation']['object']+'.'
    items = [{'id':101, 'category':'Project', 'title':'Independent project', 'bullets':[positive]}]
    if denial:
        if other_project:
            items.append({'id':202, 'category':'Project', 'title':'Other project', 'bullets':[denial]})
        else:
            items[0]['bullets'].append(denial)
    return items, policy.prior.ground_to_raw_jd(parent['obligation'], parent['raw_jd'])


class LibrarySourceTests(unittest.TestCase):
    def ledger(self, projection):
        context = projection['context']
        return verified_projection_ledger(projection, context['resume_profile'], context['raw_resume_text'])

    def test_aliases_have_original_item_field_container_and_text(self):
        denial = json.loads(FIXTURE.read_text())['same_project_denial']
        items, _ = source_items(denial, other_project=True)
        frozen = deepcopy(items)
        projection = build_library_projection(items)
        ledger = self.ledger(projection)
        raw = next(r for r in ledger['occurrences'] if r['kind']=='RAW_TEXT' and r['text']==denial)
        original = next(r for r in ledger['occurrences'] if r['source']=='resume_profile.projects[1].bullets[0]')
        self.assertEqual(raw['raw_alias_status'], 'VERIFIED_SCOPED_ORIGINALS')
        self.assertEqual(raw['verified_alias_occurrences'], [original['occurrence_id']])
        origin = raw['library_origins'][0]
        self.assertEqual(origin['library_item_id'], 202)
        self.assertEqual(origin['source'], 'evidence_library[id=202].bullets[0].lines[0]')
        self.assertEqual(origin['original_text'], denial)
        self.assertEqual(origin['container'], 'resume_profile.projects[1]')
        self.assertEqual(items, frozen)

    def test_duplicate_projects_and_field_lines_are_not_erased(self):
        items, _ = source_items()
        text = items[0]['bullets'][0]
        items[0]['description'] = text+'\n'+text
        items.append({'id':202,'category':'Project','title':'Other project','bullets':[text]})
        projection = build_library_projection(items)
        originals = [r for r in projection['originals'] if r['projected_text']==text]
        self.assertEqual(len(originals),4)
        self.assertEqual(len({r['occurrence_id'] for r in originals}),4)
        ledger = self.ledger(projection)
        bullets = [r for r in ledger['occurrences'] if r['kind']=='BULLET']
        self.assertEqual(len(bullets),2)
        self.assertEqual({r['library_origins'][0]['library_item_id'] for r in bullets},{101,202})

    def test_explicit_raw_only_duplicate_is_not_a_verified_alias(self):
        items, _ = source_items()
        text = items[0]['bullets'][0]
        ledger = self.ledger(build_library_projection(items, raw_only_text=text))
        raw = [r for r in ledger['occurrences'] if r['kind']=='RAW_TEXT' and r['text']==text]
        self.assertEqual(len(raw),2)
        self.assertEqual(raw[0]['raw_alias_status'],'VERIFIED_SCOPED_ORIGINALS')
        self.assertNotIn('raw_alias_status',raw[1])
        self.assertIsNone(raw[1]['container'])

    def test_unindexed_metadata_and_raw_only_categories_remain_unindexed(self):
        items, _ = source_items()
        items[0]['unindexed_notes'] = 'Never maintained it.'
        items.append({'id':303,'category':'Other','title':'Original notes','description':'Never maintained it.'})
        ledger = self.ledger(build_library_projection(items))
        note = next(r for r in ledger['occurrences'] if r['source'].endswith('.unindexed_notes'))
        self.assertEqual(note['kind'],'UNINDEXED_FIELD')
        self.assertEqual(note['container'],'resume_profile.projects[0]')
        raw = next(r for r in ledger['occurrences'] if r['kind']=='RAW_TEXT' and r['text']=='Never maintained it.')
        self.assertEqual(raw['raw_alias_status'],'UNSCOPED_OR_PARTIAL_COVERAGE')

    def test_forged_alias_or_document_authority_fails_replay(self):
        items, _ = source_items()
        for field in ('authority','raw_aliases','originals','context'):
            projection = build_library_projection(items)
            forged = deepcopy(projection)
            forged[field] = 'ACTUAL_RESUME_DOCUMENT' if field=='authority' else []
            with self.subTest(field=field), self.assertRaises(ValueError):
                verified_projection_ledger(forged, projection['context']['resume_profile'], projection['context']['raw_resume_text'])
        projection = build_library_projection(items)
        with self.assertRaises(ValueError):
            verified_projection_ledger(projection, projection['context']['resume_profile'], 'Forged raw text')
        for ids in ([items[0], items[0]], [{**items[0],'id':0}]):
            with self.assertRaises(ValueError): build_library_projection(ids)
