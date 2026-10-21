"""Disposable CURRENT-SOURCE unit artifacts, never historical reproduction.

Real freeze/prepare/hash/gold validators run unchanged. Only artifact locations,
the observation clock and metadata dependencies are injected. No original
historical file, checksum, input fingerprint or human label is rewritten.
"""
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'CURRENT_SOURCE_UNIT_ONLY_NOT_HISTORICAL_OR_INDEPENDENT_GOLD'


def write(root, name, value):
    path = root/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2)+'\n', encoding='utf-8')
    return path


class UnitClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 1, 1, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


@contextmanager
def comparison_artifacts():
    from scripts import smoke_ollama_unresolved_adjudication_v1 as smoke
    from scripts import compare_ollama_unresolved_prompts_v1_2 as old
    from scripts import compare_ollama_unresolved_prompts_v1_3 as new
    contract = json.loads((ROOT/'tests/fixtures/ollama_behavior_contract_v1.json').read_text())
    with tempfile.TemporaryDirectory(prefix='current-ollama-') as directory, ExitStack() as stack:
        root = Path(directory)
        files = ['scripts/smoke_ollama_unresolved_adjudication_v1.py',
                 'scripts/compare_ollama_unresolved_prompts_v1_2.py',
                 'scripts/compare_ollama_unresolved_prompts_v1_3.py',
                 'tests/test_ollama_unresolved_smoke.py', 'tests/test_ollama_prompt_comparison.py',
                 'tests/test_ollama_prompt_comparison_v1_3.py',
                 'tests/fixtures/ollama_unresolved_holdout_v1_2.json',
                 'tests/fixtures/ollama_unresolved_holdout_v1_3.json']
        for name in files:
            path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT/name).read_bytes())
        sentinel = write(root, 'unit_source.json', {'fixture_scope': SCOPE, 'value': 'immutable unit sentinel'})
        hashes = {'unit_source.json': hashlib.sha256(sentinel.read_bytes()).hexdigest()}
        protected = [{'exact_requirement': 'ZEBRA protected unit source must never enter a synthetic prompt.'}]
        write(root, 'reports/unresolved_gold_decision_review_v3.json', {'fixture_scope': SCOPE, 'cases': protected})
        write(root, 'reports/unresolved_gold_review_packet_v4.json', {'fixture_scope': SCOPE,
              'cases': [{'exact_frozen_requirement': protected[0]['exact_requirement']}]})
        write(root, 'reports/unresolved_evidence_explainability_review_v1_1.json',
              {'fixture_scope': SCOPE, 'protected_artifact_hashes': hashes})
        write(root, 'reports/ollama_unresolved_adjudication_smoke_v1.json',
              {'fixture_scope': SCOPE, 'protected_hashes': hashes,
               'synthetic_dataset': contract['synthetic_dataset'], 'schema': contract['schema'],
               'rows': [{'prompt_fingerprint': contract['first_prompt_fingerprint']}]})
        write(root, 'reports/ollama_unresolved_adjudication_smoke_v1_1.json',
              {'fixture_scope': SCOPE, 'protected_hashes': hashes})
        for name in ['ollama_unresolved_adjudication_smoke_v1',
                     'ollama_unresolved_adjudication_smoke_v1_1', 'ollama_unresolved_prompt_comparison_v1_2']:
            path=root/'docs'/(name+'.md');path.parent.mkdir(exist_ok=True)
            path.write_text(SCOPE+'\n', encoding='utf-8')
        for module in (smoke, old, new):
            stack.enter_context(patch.object(module, 'ROOT', root))
        for module, suffix in ((old, 'v1_2'), (new, 'v1_3')):
            stack.enter_context(patch.object(module, 'HOLDOUT', root/f'tests/fixtures/ollama_unresolved_holdout_{suffix}.json'))
            stack.enter_context(patch.object(module, 'datetime', UnitClock))
        stack.enter_context(patch.object(old, '__file__', str(root/'scripts/compare_ollama_unresolved_prompts_v1_2.py')))
        plan = old.freeze_plan()  # real positive integrity/selection validation
        old.validate_plan(plan)
        write(root, 'reports/ollama_unresolved_prompt_comparison_v1_2_plan.json', plan)
        write(root, 'reports/ollama_unresolved_prompt_comparison_v1_2.json', {'fixture_scope': SCOPE})
        yield root


@contextmanager
def adjudication_artifacts():
    """Authored 40-case validator controls. Simulated prior labels are NOT gold.

    Existing frozen keys are interface aliases for worksheet/deferred-child
    controls only. New source fingerprints and UNIT_ONLY provenance prevent
    confusing these invented texts/metadata with original JD occurrences.
    Fingerprints bind new unit inputs, never replace the historical benchmark.
    """
    from taxonomy_discovery import unresolved_adjudication as a
    from taxonomy_discovery import unresolved_gold_review as review
    from scripts import adjudicate_unresolved_requirements as cli
    from tests.governed_review_fixtures import isolated_taxonomy
    with tempfile.TemporaryDirectory(prefix='current-adjudication-') as directory, ExitStack() as stack:
        root=Path(directory)
        stack.enter_context(isolated_taxonomy(published=True))
        identity = a.production_identity()
        stack.enter_context(patch.object(a, 'production_identity', side_effect=lambda: deepcopy(identity)))
        rows=[];jobs=[]
        terms=['MongoDB, Redis, Elasticsearch', 'SQL', 'AWS', 'Node.js', 'C#', 'JavaScript', 'MongoDB']
        keys=json.loads((ROOT/'tests/fixtures/unresolved_adjudication_benchmark_v1.json').read_text())['expectations']
        for i in range(40):
            jid, rid = keys[i]['key']
            text = ('MongoDB, Redis, Elasticsearch' if i == 0 else
                    f'Quuxscope obligation {i} involving {terms[i % len(terms)]}')
            requirement={'requirement_id':rid, 'text':text, 'importance':'required'}
            if (jid,rid)==(31,'req_8d47527c8f34'):
                requirement.update(text='Proficiency in the modern JavaScript/TypeScript ecosystem',
                                   group_weight_fraction=0.333333)
            jobs.append({'job_id':jid, 'baseline_stable_analysis':{'canonical_requirements':[requirement]}})
            rows.append({'job_id':jid, 'requirement_id':rid, 'review_reason':SCOPE})
        source=write(root, 'unit_source.json', {'fixture_scope':SCOPE,
            'snapshot':{'manifest':{'fixture_scope':SCOPE}, 'audit':{'corpus':{'jobs':jobs}}},
            'plan':{'taxonomy_addressability':{'rows':rows}}})
        occurrences=a.load_occurrences(source)
        cases=[a.build_input(o) for o in occurrences]
        if any(c is None for c in cases):
            raise AssertionError('Authored unresolved unit controls unexpectedly resolved')
        parent={'schema_version':'unresolved-adjudication-benchmark-v1', 'prompt_version':a.PROMPT_VERSION,
                'fixture_scope':SCOPE, 'source_path':source.name,
                'source_fingerprint':occurrences[0]['source_fingerprint'],
                'review_state':'UNIT_ONLY_SIMULATED_PRIOR_LABELS_NOT_HUMAN_GOLD', 'expectations':[]}
        for i, case in enumerate(cases):
            parent['expectations'].append({'key':[case['job_id'],case['requirement_id']],
                'input_fingerprint':a.fingerprint(case), 'review_bucket':'UNIT_ONLY',
                'primary_blocker':'UNIT_ONLY', 'acceptable_routes':['TRUE_GAP_CANDIDATE'] if i in (1,2) else [],
                'critical':i in (0,3,4,5,6,7,8), 'non_gap_control':i not in (1,2),
                'identity_only_control':False, 'review_reason':SCOPE})
        review.seal(parent)
        original=write(root, 'tests/fixtures/unresolved_adjudication_benchmark_v1.json', parent)
        stack.enter_context(patch.object(review, 'ORIGINAL', original))
        stack.enter_context(patch.object(review, 'ROOT', root))
        stack.enter_context(patch.object(a, 'SOURCE', source))
        # Location injection for default-bound Python arguments; the actual
        # load_occurrences/prepare functions and all their validators run.
        stack.enter_context(patch.object(a.load_occurrences, '__defaults__', (source,)))
        stack.enter_context(patch.object(cli.prepare, '__defaults__', (source,)))
        stack.enter_context(patch.object(cli, 'BENCHMARK', original))
        pending=review.versioned_manifest(parent, [], cases)
        write(root, 'tests/fixtures/unresolved_adjudication_benchmark_v2.json', pending)
        # Source-only V5 packet controls. No original recovery result, private
        # review or model observation is copied. All recovery is UNAVAILABLE.
        recovered={'fixture_scope':SCOPE, 'parent_manifest_fingerprint':parent['fingerprint'],
                   'source_fingerprint':parent['source_fingerprint'], 'sources':{}, 'cases':[]}
        for case in cases:
            recovered['cases'].append({'key':[case['job_id'],case['requirement_id']],
                'exact_requirement':case['requirement_text'],
                'source_context':{'source_references':[SCOPE], 'raw_jd_sha256':None,
                                  'status':'UNIT_ONLY_ORIGINAL_SOURCE_RECOVERY_UNAVAILABLE'}})
        write(root, 'reports/unresolved_gold_decision_review_v3.json', recovered)
        from taxonomy_discovery import unresolved_independent_review as v5, unresolved_review_packet as v4
        write(root, 'reports/unresolved_gold_review_packet_v4.json', {'fixture_scope':SCOPE,
              'cases':[{'key':[j,r]} for _,j,r in v4.SELECTION]})
        write(root, 'reports/ollama_unresolved_prompt_comparison_v1_3_plan.json',
              {'fixture_scope':SCOPE, 'protected_hashes':{'unit_source.json':hashlib.sha256(source.read_bytes()).hexdigest()}})
        write(root, 'reports/ollama_unresolved_prompt_comparison_v1_3.json', {'fixture_scope':SCOPE})
        path=root/'docs/ollama_unresolved_prompt_comparison_v1_3.md';path.parent.mkdir(exist_ok=True)
        path.write_text(SCOPE+'\n',encoding='utf-8')
        for name in ['scripts/review_ollama_unresolved_comparison_v1_3.py','tests/test_ollama_prompt_review_v1_3.py']:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
        stack.enter_context(patch.object(v5,'ROOT',root))
        cli.prepare(parent, source)
        yield root
