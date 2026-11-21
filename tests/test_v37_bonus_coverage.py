import unittest

from tailoring.phase9f_v37_bonus_coverage import bonus_catalog, bonus_summary, reviewed_bonus_links, uploaded_bonus_excerpts


def requirement(rid, text, category, parent=None, fraction=1.0):
    parent = parent or text
    return {'requirement_id': rid, 'text': text, 'importance': category, 'parent_text': parent,
            'scoring_parent_occurrence_id': parent, 'group_weight_fraction': fraction,
            'score_eligible': True, 'evidence_eligible': True, 'source_provenance': [
                {'source': 'raw_jd.requirements', 'grounding': {'span_id': rid, 'sentence_text': parent}}]}


class BonusCoverageTests(unittest.TestCase):
    def test_factual_document_prose_earns_weighted_units_once(self):
        supporting = requirement('s', 'Familiarity with Docker', 'supporting')
        preferred = requirement('p', 'Knowledge of SQL is preferred', 'preferred')
        jd = '\n'.join(x['text'] for x in (supporting, preferred))
        catalog = bonus_catalog([supporting, preferred], jd, expected_jd=jd)
        wording = 'Configured Docker builds and used SQL to validate migration results.'
        alt = 'Used SQL to reconcile migration results.'
        excerpts = uploaded_bonus_excerpts(f'Experience\n{wording}\n{alt}')
        reviews = [{'requirement_id': rid, 'excerpt': f'raw_resume_text[{i}]', 'wording': text, 'basis': 'Concrete documented action.',
                    'label': label, 'strength': 3} for rid,i,text,label in (
                        ('s',1,wording,'direct'), ('p',1,wording,'transferable'), ('p',2,alt,'direct'))]
        links, withheld = reviewed_bonus_links(catalog, excerpts, reviews)
        self.assertEqual(withheld, [])
        score = bonus_summary(catalog, links, ['raw_resume_text[1]', 'raw_resume_text[2]', 'raw_resume_text[2]'])
        self.assertEqual(score['categories']['supporting']['earned'], 2)
        self.assertEqual(score['categories']['preferred']['earned'], 1)
        self.assertEqual(score['requirements'][1]['witness_count'], 2)
        self.assertFalse(score['requirements'][0]['best']['evidence']['independently_attested'])

    def test_keyword_only_planned_and_negated_receive_no_bonus(self):
        req = requirement('s', 'Familiarity with Docker', 'supporting')
        catalog = bonus_catalog([req], req['text'], expected_jd=req['text'])
        raw = 'Docker Docker Docker\nPlanned to use Docker\nImplemented an API and never used Docker'
        excerpts = uploaded_bonus_excerpts(raw)
        reviews = [{'requirement_id': 's', 'excerpt': key, 'wording': value['text'], 'basis': 'fixture',
                    'label': 'direct', 'strength': 4} for key,value in excerpts.items()]
        links, withheld = reviewed_bonus_links(catalog, excerpts, reviews)
        self.assertEqual(len(withheld), 3)
        score = bonus_summary(catalog, links, list(excerpts))
        self.assertEqual(score['categories']['supporting']['earned'], 0)
        self.assertEqual(score['categories']['preferred']['status'], 'not_applicable')

    def test_clipped_fragment_does_not_redistribute_its_weight(self):
        parent = 'Design, build and maintain scalable backend services and API'
        clipped = requirement('a', 'Design, build', 'supporting', parent, .5)
        sibling = requirement('b', 'maintain scalable backend services and API', 'supporting', parent, .5)
        catalog = bonus_catalog([clipped, sibling], parent, expected_jd=parent)
        self.assertFalse(catalog['a']['eligible'])
        self.assertEqual(catalog['a']['weight'], 1)
        self.assertEqual(bonus_summary(catalog, {}, [])['categories']['supporting']['available'], 1)
        self.assertFalse(bonus_catalog([sibling], parent, expected_jd='Changed JD')['b']['eligible'])

    def test_explicit_skills_claim_requires_independent_attestation(self):
        req = requirement('p', 'Knowledge of SQL is preferred', 'preferred')
        catalog = bonus_catalog([req], req['text'], expected_jd=req['text'])
        review = {'requirement_id': 'p', 'excerpt': 'fixed', 'wording': 'SQL', 'basis': 'Verified named qualification.',
                  'label': 'direct', 'strength': 3, 'skill_qualification': True}
        excerpt = {'section': 'skills', 'text': 'SQL', 'verified': True}
        self.assertFalse(reviewed_bonus_links(catalog, {'fixed': excerpt}, [review])[0])
        self.assertTrue(reviewed_bonus_links(catalog, {'fixed': {**excerpt, 'independently_attested': True}}, [review])[0])
