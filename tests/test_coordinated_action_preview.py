"""Analyst preview invariants, not authorization to change production parsing."""
from copy import deepcopy
import json
import unittest

from scripts import preview_coordinated_actions_v1 as preview


class CoordinatedActionPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        jobs=json.loads((preview.inventory.ROOT/preview.inventory.FIXTURES[0]).read_text(encoding='utf-8'))['snapshot']['audit']['corpus']['jobs']
        cls.jobs={j['job_id']:j for j in jobs}
        cls.comparisons={jid:preview.compare_job(cls.jobs[jid],jobs.index(cls.jobs[jid])) for jid in (16,359,479,566)}

    def text_run(self,text,proposed):
        return preview.canonical('Responsibilities:\n'+text,proposed=proposed,
                                 profile={'responsibilities':[text]})

    def test_actual_jobs_remove_object_free_fragments(self):
        for jid in (359,479):
            changes=self.comparisons[jid]['changed_parents']
            self.assertTrue(changes)
            selected=next(c for c in changes if any(r['text']=='Design, develop' for r in c['baseline']))
            self.assertEqual(selected['child_count_delta'],-1)
            self.assertEqual(len(selected['proposed']),1)
            self.assertIn('maintain',selected['proposed'][0]['text'])
            self.assertTrue(selected['canonical_identities_change'])

    def test_related_jobs_reproduce_build_and_bullet_variants(self):
        for jid in (16,566):
            self.assertTrue(self.comparisons[jid]['changed_parents'])
            self.assertTrue(any('build' in c['original_raw_parent'].lower()
                                for c in self.comparisons[jid]['changed_parents']))
            self.assertTrue(all(len(c['proposed'])==1 and c['child_count_delta']==-1
                                for c in self.comparisons[jid]['changed_parents']))
        bullet=[c['original_raw_parent'] for c in self.comparisons[566]['changed_parents']]
        self.assertTrue(any(t.startswith('\u00b7') for t in bullet))
        self.assertFalse(any('\u00c2\u00b7' in t for t in bullet))

    def test_exact_parent_spans_fractions_and_determinism(self):
        for job in self.comparisons.values():
            self.assertTrue(job['deterministic_repeat'])
            self.assertTrue(job['native_repeat_unchanged'])
            for c in job['changed_parents']:
                self.assertTrue(c['allocation_conserved'])
                self.assertEqual(c['baseline_allocation_sum'],1)
                self.assertEqual(c['proposed_allocation_sum'],1)
                self.assertTrue(c['source_spans_preserved'])
                self.assertFalse(c['importance_values_change'])
                self.assertFalse(c['evidence_eligibility_values_change'])
            for key in ('baseline_atomic_group_sums','proposed_atomic_group_sums'):
                self.assertTrue(all(abs(total-1)<.00001 for total in job[key].values()))

    def test_independent_clauses_are_not_disabled(self):
        text='Design REST endpoints and develop database migrations.'
        baseline=self.text_run(text,False);after=self.text_run(text,True)
        self.assertEqual(baseline,after)
        self.assertEqual(len(after['requirements']),2)
        # Native grammar does not admit "implement" as second-clause prefix.
        # This separate coverage limit is exposed, not silently fixed here.
        text='Design REST endpoints and implement database migrations.'
        self.assertEqual(self.text_run(text,False),self.text_run(text,True))

    def test_three_or_more_verbs_retain_the_complete_shared_object(self):
        for text in ['Design, develop and maintain scalable applications.',
                     'Design, develop, test and maintain embedded software modules.']:
            after=self.text_run(text,True)
            self.assertEqual(len(after['requirements']),1)
            self.assertIn('maintain',after['requirements'][0]['text'])
            self.assertIn('applications' if 'applications' in text else 'modules',after['requirements'][0]['text'])

    def test_optional_frameworks_and_and_or_scopes_are_not_inferred(self):
        for text in ['Design, develop and maintain applications using frameworks such as React or Angular.',
                     'Design REST endpoints or develop gRPC services.',
                     'Develop and consume REST APIs.',
                     'Design, develop and maintain applications, preferably using Python.']:
            baseline=self.text_run(text,False);after=self.text_run(text,True)
            self.assertEqual({r['importance'] for r in baseline['requirements']},
                             {r['importance'] for r in after['requirements']})
            if ' or ' in text:
                self.assertEqual(baseline,after)

    def test_negations_incomplete_fragments_and_unknown_objects_fail_closed(self):
        for text in ['Do not design, develop and maintain applications.',
                     'Design, develop and never maintain applications.',
                     'Design, develop','Design, develop and maintain',
                     'Design, develop and maintain unusual things.',
                     'Design, develop and maintain applications and deploy cloud systems.']:
            self.assertEqual(self.text_run(text,False),self.text_run(text,True))

    def test_duplicates_and_overlapping_parents_preserve_allocation_boundaries(self):
        rows=['Design, develop and maintain scalable applications.',
              'Design, develop and maintain scalable applications.',
              'Design, develop and maintain scalable applications using Python.']
        profile={'responsibilities':rows};frozen=deepcopy(profile)
        after=preview.canonical('Responsibilities:\n'+'\n'.join(rows),proposed=True,profile=profile)
        self.assertEqual(profile,frozen)
        self.assertEqual(len({r['requirement_id'] for r in after['requirements']}),len(after['requirements']))
        self.assertTrue(all(abs(v-1)<.00001 for v in preview.group_sums(after).values()))
        records=[{'requirement':r} for r in after['requirements']]
        for a in preview.inventory.allocations(records):
            self.assertIn(a['status'],('CONSERVED','NON_CONTRIBUTING_PROVENANCE_ONLY'))

    def test_whitespace_and_line_wrap_keep_canonical_identity(self):
        variants=['Design, develop and maintain scalable applications.',
                  'Design,  develop and maintain  scalable applications.',
                  'Design, develop and\nmaintain scalable applications.']
        results=[self.text_run(t,True) for t in variants]
        identity=lambda c:[(r['requirement_id'],r['text'],r['group_weight_fraction']) for r in c['requirements']]
        self.assertTrue(all(identity(r)==identity(results[0]) for r in results))

    def test_production_namespace_and_versions_remain_untouched(self):
        function=preview.native._split_safe_independent_and_pair
        frozen=preview.inventory.knowledge_identity()
        self.text_run('Design, develop and maintain scalable applications.',True)
        self.assertIs(preview.native._split_safe_independent_and_pair,function)
        self.assertEqual(preview.inventory.knowledge_identity(),frozen)
        self.assertEqual(preview.native.SCORING_VERSION,'stable-evidence-v1.17-phase6d21')

    def test_utf8_corpus_count_agrees_with_stage1_source_manifest(self):
        expected=json.loads((preview.inventory.ROOT/'bulk_unresolved_stage1_summary.json').read_text(encoding='utf-8'))
        total=sum(len(preview.canonical(j['frozen_inputs']['raw_jd_text'])['requirements']) for j in self.jobs.values())
        self.assertEqual(total,expected['cohorts']['raw_jd_only']['rows'])
