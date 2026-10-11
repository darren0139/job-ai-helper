"""Frozen producer provenance, without changing evidence or score semantics."""
from copy import deepcopy
import unittest

from analysis_stability.stable_evidence_scoring import build_resume_evidence_index, SCORING_VERSION
from tailoring.phase6d6_structured_matching import apply_structured_requirement_matches
from taxonomy_discovery.regression_corpus import duplicate_credit_violations

REQUIREMENT = "Work closely with DSP, FPGA, RF, and System Engineering teams to support end to end software integration"
BULLET = "Collaborated with a custom-engine team to integrate systems across asset loading, audio, and gameplay workflows."


def receipt(bullet=BULLET):
    profile = {"projects":[{}, {}, {"bullets":["Other work", "Other work", "Other work", bullet]}]}
    context = {"resume_profile":profile,"raw_resume_text":""}
    rows, _ = apply_structured_requirement_matches([
        {"requirement_id":"fixture-integration","text":REQUIREMENT,"importance":"core",
         "score_eligible":True,"match_label":"none","match_value":0,"evidence":[]}],
        resume_profile=profile)
    return {"canonical_requirements":rows,"credited_requirement_count":1,"scoring_version":SCORING_VERSION}, context


class FrozenEvidenceContractTests(unittest.TestCase):
    def test_exact_observed_source_has_two_native_ids_and_passes_without_replacement(self):
        stable, context = receipt()
        frozen = deepcopy((stable,context))
        selected = stable['canonical_requirements'][0]['evidence'][0]
        general = next(e for e in build_resume_evidence_index(context['resume_profile']) if e['source']==selected['source'])
        self.assertEqual(selected['evidence_id'],'ev_7e28db11d2c7')
        self.assertEqual(general['evidence_id'],'ev_6b4a9be6e246')
        self.assertEqual(selected['text'],general['text'])
        self.assertEqual(selected['source'],'resume_profile.projects[2].bullets[3]')
        self.assertEqual(duplicate_credit_violations(stable,context),[])
        self.assertEqual((stable,context),frozen)
        self.assertEqual(stable['canonical_requirements'][0]['match_label'],'transferable')
        self.assertEqual(stable['canonical_requirements'][0]['match_value'],0.55)

    def test_generic_punctuation_and_alias_normalizations_use_native_producer(self):
        for bullet in (BULLET.rstrip('.'), BULLET.replace('custom-engine','AWS & Azure software'),
                       BULLET.replace('custom-engine','custom—engine')):
            with self.subTest(bullet=bullet):
                stable, context=receipt(bullet)
                self.assertEqual(duplicate_credit_violations(stable,context),[])
                self.assertEqual(receipt(bullet), (stable,context))

    def test_live_profile_cannot_supply_missing_frozen_source(self):
        stable, context=receipt()
        frozen=deepcopy(context)
        context['resume_profile']['projects'][2]['bullets'][3]='Unrelated live profile edit'
        self.assertEqual(duplicate_credit_violations(stable,frozen),[])
        self.assertIn('evidence_not_in_frozen_resume:fixture-integration',duplicate_credit_violations(stable,context))

    def test_unknown_normalization_version_fails_closed(self):
        stable, context=receipt()
        stable['canonical_requirements'][0]['structured_match_version']='unknown-normalizer'
        result=duplicate_credit_violations(stable,context)
        self.assertIn('frozen_structured_evidence_version_mismatch:fixture-integration',result)
        self.assertIn('evidence_not_in_frozen_resume:fixture-integration',result)

    def test_missing_source_and_forged_id_remain_violations(self):
        stable, context=receipt()
        missing=deepcopy(context); missing['resume_profile']['projects']=[]
        self.assertIn('evidence_not_in_frozen_resume:fixture-integration',duplicate_credit_violations(stable,missing))
        stable['canonical_requirements'][0]['evidence'][0]['evidence_id']='ev_forged'
        self.assertIn('evidence_not_in_frozen_resume:fixture-integration',duplicate_credit_violations(stable,context))

    def test_wrong_text_source_or_producer_cannot_borrow_valid_id(self):
        stable, context=receipt()
        for field in ('text','source','section'):
            changed=deepcopy(stable)
            changed['canonical_requirements'][0]['evidence'][0][field]='forged'
            self.assertIn('frozen_evidence_source_mismatch:fixture-integration',duplicate_credit_violations(changed,context))
        changed=deepcopy(stable); changed['canonical_requirements'][0]['structured_match_kind']='unrelated_producer'
        self.assertIn('evidence_not_in_frozen_resume:fixture-integration',duplicate_credit_violations(changed,context))
        changed=deepcopy(stable); changed['canonical_requirements'][0].pop('structured_match_status')
        self.assertIn('evidence_not_in_frozen_resume:fixture-integration',duplicate_credit_violations(changed,context))

    def test_general_evidence_also_requires_exact_frozen_source(self):
        stable, context=receipt()
        row=stable['canonical_requirements'][0]
        row['evidence']=[next(e for e in build_resume_evidence_index(context['resume_profile']) if e['source'].endswith('bullets[3]'))]
        row.pop('structured_match_status')
        self.assertEqual(duplicate_credit_violations(stable,context),[])
        row['evidence'][0]['text']='Invented evidence with copied ID'
        self.assertIn('frozen_evidence_source_mismatch:fixture-integration',duplicate_credit_violations(stable,context))

    def test_duplicate_and_credit_without_evidence_guards_remain_active(self):
        stable, context=receipt()
        stable['canonical_requirements'][0]['evidence'] *= 2
        self.assertIn('duplicate_selected_evidence:fixture-integration',duplicate_credit_violations(stable,context))
        stable['canonical_requirements'][0]['evidence']=[]
        self.assertIn('credit_without_evidence:fixture-integration',duplicate_credit_violations(stable,context))

    def test_replay_identity_uses_copied_frozen_inputs_after_source_changes(self):
        from tests.test_tqd3_regression_corpus import frozen_snapshot
        from tests.tqd3_publication_fixture_support import PublicationFixture
        from taxonomy_discovery.regression_corpus import build_regression_corpus, replay_current_corpus
        with PublicationFixture() as f:
            source = frozen_snapshot()
            corpus = build_regression_corpus([source])
            frozen = deepcopy(corpus)
            source['evidence_snapshot'][0]['description'] = 'Completely different live evidence'
            source['stable_analysis']['canonical_requirements'][0]['evidence'] = []
            replay = replay_current_corpus(corpus)
            before = frozen['jobs'][0]['baseline_stable_analysis']
            after = replay['jobs'][0]['baseline_stable_analysis']
            self.assertEqual(before['input_fingerprint'],after['input_fingerprint'])
            self.assertEqual(before['canonical_requirements'],after['canonical_requirements'])
            self.assertEqual(frozen['jobs'][0]['metrics'],replay['jobs'][0]['metrics'])
            self.assertEqual(duplicate_credit_violations(after,replay['jobs'][0]['frozen_inputs']['context']),[])
            self.assertEqual(corpus,frozen)
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_frozen_snapshot_context_currentness_mismatch_blocks_replay(self):
        from tests.test_tqd3_regression_corpus import frozen_snapshot
        from tests.tqd3_publication_fixture_support import PublicationFixture
        from taxonomy_discovery.regression_corpus import build_regression_corpus, replay_current_corpus
        with PublicationFixture() as f:
            corpus = build_regression_corpus([frozen_snapshot()])
            corpus['jobs'][0]['frozen_inputs']['context']['raw_resume_text'] += ' invented live data'
            result = replay_current_corpus(corpus)
            self.assertEqual(result['current_replay']['jobs_blocked'],1)
            self.assertIn('Frozen context disagrees with frozen evidence',result['jobs'][0]['current_replay']['blockers'])
            self.assertEqual(corpus['jobs'][0]['baseline_stable_analysis'],result['jobs'][0]['baseline_stable_analysis'])
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()


if __name__=='__main__':
    unittest.main()
