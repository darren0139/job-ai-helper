"""V1.2 investigation fixtures and explicitly counterfactual receipts.

No production policy is implemented here. Labels are analyst hypotheses for
individual fixtures, not inferred knowledge or independently verified gold.
The real evaluator/protocol guard, source selector and scorer execute every
preview. The optional recovery change is compiled in memory from the existing
function and scoped to the experimental receipt; no source file is rewritten.
"""
import ast
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import inspect
import json
from pathlib import Path
import re
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as scoring
from tailoring import capability_taxonomy as taxonomy
from tests.test_api_evidence_completeness import native_inputs

ROOT = Path(__file__).resolve().parents[1]
PREVIEW_POLICY = 'DRY_RUN_ONLY-api-knowledge-review-v1.2'
PREVIEW_REASON = 'preview_api_knowledge_partial_support'
POSTGREST = ('Implemented backend data access through PostgREST and applied '
            'Row-Level Security policies to secure database operations.')
CRUD = ('Integrated REST APIs through Supabase/PostgREST for database CRUD operations, '
        'authentication, and Realtime updates.')
CONTRACT_USE = ('Integrated a REST API for CRUD operations, handling HTTP request methods, '
                'JSON responses, API authentication contracts, and error status codes.')
ENDPOINTS = 'Implemented REST API endpoints in an existing Java backend.'
KNOWLEDGE_SCOPE = re.compile(r'Knowledge of (?:API development|API integration|REST APIs?)', re.I)


def case(name, requirement, evidence, hypothesis, basis, *, skills=False):
    return dict(case=name, requirement=requirement, evidence=evidence,
                hypothesis_labels=hypothesis, hypothesis_basis=basis, skills=skills)


CASES = [
    case('saved_job81_statement', 'Knowledge of API development', [POSTGREST], ['none'],
         'Exact saved statement: API development concepts are not established; project title unavailable.'),
    case('development_knowledge_crud_only', 'Knowledge of API development', [CRUD], ['none'],
         'Client CRUD/integration is explicit; development concepts must not be assumed.'),
    case('development_knowledge_contract_practices', 'Knowledge of API development', [CONTRACT_USE], ['weak'],
         'Concrete request/response/authentication contract practices support partial knowledge, without handler authorship.'),
    case('development_knowledge_custom_endpoints', 'Knowledge of API development', [ENDPOINTS], ['direct'],
         'Actual endpoint implementation remains positive development-knowledge evidence.'),
    case('rest_knowledge_plural_supabase', 'Knowledge of REST APIs', [CRUD], ['weak'],
         'Practical REST consumption supports limited understanding; exact plural recognition is a separate constraint.'),
    case('rest_knowledge_singular_supabase', 'Knowledge of REST API', [CRUD], ['weak'],
         'Limited practical REST knowledge; do not infer comprehensive development or REST design expertise.'),
    case('rest_knowledge_contract_practices', 'Knowledge of REST API', [CONTRACT_USE], ['direct'],
         'Simple REST knowledge has explicit request/response concepts and practical use; does not prove API authorship.'),
    case('rest_knowledge_sdk_only', 'Knowledge of REST APIs',
         ['Integrated Supabase authentication and Realtime using its JavaScript SDK.'], ['none'],
         'SDK/Realtime activity alone cannot establish the named REST protocol.'),
    case('integration_knowledge_supabase', 'Knowledge of API integration', [CRUD], ['direct'],
         'API integration is explicit, but the exact native requirement may remain unresolved.'),
    case('integration_obligation', 'Integrate REST APIs', [CRUD], ['direct'],
         'Preserve V1.1 integration credit; this is not an authoring obligation.'),
    case('authoring_postgrest', 'Design and develop REST APIs', [POSTGREST], ['none'],
         'Preserve the V1.1 authoring correction.'),
    case('endpoint_authoring', 'Develop REST API endpoints', [ENDPOINTS], ['direct'],
         'Genuine endpoint implementation remains DIRECT eligible.'),
    case('endpoint_authoring_exact_noncanonical_phrase', 'Develop REST endpoints', [ENDPOINTS], ['direct'],
         'Evaluator proof and native requirement recognition must be reported separately.'),
    case('skills_only', 'Knowledge of API development', ['REST API development, Supabase, PostgREST'], ['none'],
         'A skills list does not establish understanding of development concepts.', skills=True),
    case('documentation_only', 'Knowledge of API development',
         ['Created REST API documentation for an existing service.'], ['none'],
         'Document creation alone does not establish which development concepts are understood.'),
    case('development_experience_denied', 'Knowledge of API development',
         ['No API-development experience; only used Supabase Realtime.'], ['none'],
         'No independent development-knowledge evidence; do not turn consumption into authorship.'),
    case('development_knowledge_denied', 'Knowledge of API development',
         ['I have no knowledge of API development; used PostgREST for database CRUD operations.'], ['none'],
         'An explicit knowledge denial cannot earn positive development-knowledge credit.'),
    case('non_authoring_but_contract_practices', 'Knowledge of API development',
         [CONTRACT_USE + ' I did not implement the separate Python/Flask /message endpoint.'], ['weak'],
         'Explicit concepts can support partial knowledge despite absence of endpoint authorship; no Flask credit.'),
    case('supabase_generated_endpoints', 'Develop REST API endpoints',
         ['Used automatically generated REST API endpoints through Supabase/PostgREST for CRUD operations.'], ['none'],
         'Generated endpoints are not personally implemented handlers.'),
    case('separate_rows_do_not_complete_knowledge', 'Knowledge of API development',
         [CRUD, 'Read about HTTP request validation and JSON error responses.'], ['none', 'none'],
         'Do not combine a consumption row with a separate reading row into a development-knowledge receipt.'),
    case('wrong_protocol', 'Knowledge of REST API', ['Integrated a gRPC API for data exchange.'], ['none'],
         'Preserve protocol completeness.'),
    case('compound_protocols', 'Knowledge of REST and gRPC APIs', [CRUD], ['none'],
         'A narrow knowledge preview must not complete a mixed protocol requirement.'),
    case('internship_development', 'Develop RESTful APIs',
         ['Extended an existing Java backend by developing REST API endpoints to support data exchange with '
          'the Unity-based Maritime Digital Twin, collaborating on MinIO storage integration.'], ['direct'],
         'Preserve the exact V1.1 positive development fixture.'),
    case('internship_combined', 'Design and develop RESTful APIs',
         ['Extended an existing Java backend by developing REST API endpoints to support data exchange with '
          'the Unity-based Maritime Digital Twin, collaborating on MinIO storage integration.'], ['weak'],
         'Preserve approved implementation-without-design partial credit.'),
    case('cpp_knowledge_control', 'Knowledge of C++', ['C++'], ['none'],
         'The API evaluator is irrelevant here; native C++ knowledge policy remains authoritative.', skills=True),
    case('frontend_control', 'Frontend development', ['Built React frontend UI components and dashboard views.'], ['none'],
         'No non-API behavior changes.'),
    case('database_policy_control', 'Implement Row-Level Security policies', [POSTGREST], ['none'],
         'The saved statement retains its existing database-access-control credit; API NONE does not discard its security evidence.'),
]


def inputs_for(item):
    inputs = native_inputs(item['requirement'], item['evidence'])
    if item['skills']:
        inputs.update(resume_profile={'projects': [], 'experience': [], 'education': [],
                                      'skills': {'Listed technologies': item['evidence']}}, raw_resume_text='')
    return inputs


def job81_source():
    data = json.loads((ROOT / 'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
    job = next(j for j in data['snapshot']['audit']['corpus']['jobs'] if j['job_id'] == 81)
    row = next(r for r in job['baseline_stable_analysis']['canonical_requirements']
               if r['requirement_id'] == 'req_8902c2c2d5c0')
    assert row['text'] == 'Knowledge of API development'
    assert row['evidence'][0]['text'] == POSTGREST
    evidence = list(dict.fromkeys(e['text'] for r in job['baseline_stable_analysis']['canonical_requirements']
                                 for e in r.get('evidence', []) if e.get('text')))
    inputs = native_inputs('', evidence)
    inputs.update(jd_profile={}, raw_jd_text=job['frozen_inputs']['raw_jd_text'],
                  keyword_match={'present': [], 'missing': [{'keyword': r['text']} for r in
                                  job['baseline_stable_analysis']['canonical_requirements']]})
    return row, inputs


def preview_recovery():
    """Reuse the selector verbatim except one experimental weak-recovery guard."""
    tree = ast.parse(inspect.getsource(scoring._apply_capability_none_recovery))
    assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'api_partial_implementation' for t in n.targets)]
    assert len(assignments) == 1, 'The existing recovery guard changed; review the simulation'
    extra = ast.parse(
        "capability_id == 'backend.api_development' and "
        "best_decision.get('reason') == 'preview_api_knowledge_partial_support' and "
        "best_decision.get('evidence_policy_version') == 'DRY_RUN_ONLY-api-knowledge-review-v1.2' and "
        "bool(re.fullmatch(r'Knowledge of (?:API development|API integration|REST APIs?)', focus, re.I))",
        mode='eval',
    ).body
    assignments[0].value = ast.BoolOp(op=ast.Or(), values=[assignments[0].value, extra])
    namespace = dict(scoring.__dict__)
    exec(compile(ast.fix_missing_locations(tree), '<V1.2-recovery-counterfactual>', 'exec'), namespace)
    return namespace['_apply_capability_none_recovery']


@contextmanager
def receipt_hypothesis(requirement, evidence, labels, *, allow_weak_recovery=False):
    """Inject fixture hypotheses AFTER the real evaluator, retaining its guard.

    This exact-text mapping is a counterfactual experiment, not a proposed
    general language matcher. Non-knowledge requirements cannot be changed.
    """
    original = taxonomy._evaluate_capability_record
    mapping = dict(zip(evidence, labels))

    def evaluate(**kwargs):
        decision = original(**kwargs)
        focus = kwargs['requirement'].get('atomic_focus') or kwargs['requirement'].get('text')
        if (kwargs['capability'].get('capability_id') != 'backend.api_development'
                or focus != requirement or not KNOWLEDGE_SCOPE.fullmatch(str(focus))
                or kwargs['evidence_text'] not in mapping
                or decision.get('reason') == 'requested_api_protocol_evidence_missing'):
            return decision
        label = mapping[kwargs['evidence_text']]
        if label == decision['label']:
            return decision
        return {**decision, 'label': label, 'reason': PREVIEW_REASON if label == 'weak' else
                'preview_knowledge_complete_coverage_hypothesis', 'evidence_policy_version': PREVIEW_POLICY}

    with ExitStack() as stack:
        stack.enter_context(patch.object(taxonomy, '_evaluate_capability_record', evaluate))
        if allow_weak_recovery:
            stack.enter_context(patch.object(scoring, '_apply_capability_none_recovery', preview_recovery()))
        yield


def evaluate_inputs(inputs):
    frozen = deepcopy(inputs)
    result = scoring.build_stable_analysis(**inputs)
    assert inputs == frozen, 'Native inputs mutated'
    return result


def matrix():
    results = []
    for item in CASES:
        inputs = inputs_for(item)
        direct = lambda: [taxonomy.evaluate_capability_evidence(
            'backend.api_development', {'text': item['requirement']}, e) for e in item['evidence']]
        base_decisions, base = direct(), evaluate_inputs(inputs)
        with receipt_hypothesis(item['requirement'], item['evidence'], item['hypothesis_labels']):
            hypothetical, unchanged_recovery = direct(), evaluate_inputs(inputs)
        with receipt_hypothesis(item['requirement'], item['evidence'], item['hypothesis_labels'],
                                allow_weak_recovery=True):
            scoped_recovery = evaluate_inputs(inputs)
        assert base == evaluate_inputs(inputs), 'Preview context leaked into production evaluation'
        results.append({**deepcopy(item), 'baseline_evaluator': base_decisions, 'baseline_native': base,
                        'hypothesis_evaluator': hypothetical, 'hypothesis_current_recovery_native': unchanged_recovery,
                        'hypothesis_scoped_recovery_native': scoped_recovery})
    return results


def job81_alternatives():
    row, inputs = job81_source()
    baseline = evaluate_inputs(inputs)
    alternatives = []
    for label, recovery in (('none', False), ('weak', False), ('weak', True), ('direct', False)):
        with receipt_hypothesis(row['text'], [POSTGREST], [label], allow_weak_recovery=recovery):
            decision = taxonomy.evaluate_capability_evidence('backend.api_development', row, POSTGREST)
            native = evaluate_inputs(inputs)
        alternatives.append({'label_hypothesis': label, 'experimental_recovery_exception': recovery,
                             'evaluator': decision, 'native': native})
    assert baseline == evaluate_inputs(inputs)
    return {'original_saved_row': row, 'source_project_title': None,
            'project_title_limitation': 'Saved source is projects[1].bullets[1]; no project-title mapping in this projection. QueryAI identity is unverified.',
            'native_projection_limitation': 'All six saved selected statements are projected into one disposable project; native source paths are projection paths, not the original profile.',
            'baseline': baseline, 'alternatives': alternatives}
