"""Controlled project-bullet experiments on isolated, hash-bound DOCX copies."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256

from tailoring.phase9f_certified_selection_v36 import _candidate, _solve
from tailoring.phase9f_jd_relevance_optimizer_v35 import VERSION as FITTED_WRITER_VERSION
from tailoring.phase9f_v365_jd_evidence import explain_bullet, requirement_catalog, requirement_fragment
from tailoring.phase9f_v37_corpus_benchmark import build_case_model, slate_metrics
from tailoring.phase9f_v37_document_trial import compare_native_trials, evaluate_document_trial
from taxonomy_discovery.offline_execution import offline_execution

VERSION = 'phase9f-v37-native-bullet-trial-v1'
OPERATIONS = ('remove', 'force_in', 'base_to_library', 'library_to_base', 'use_freed_words')


def _locate(model: dict, project: str, wording: str, *, selected: bool) -> int:
    hits = [i for i, bullet in enumerate(model['bullets'])
            if bullet['project'] == project and bullet['text'] == wording]
    if len(hits) != 1:
        raise ValueError('Choose exact unique saved project and bullet wording.')
    index = hits[0]
    if (index in model['baseline_indices']) != selected:
        raise ValueError('Expected a selected bullet.' if selected else 'Expected an excluded bullet.')
    if not selected and not {'Selected Base', 'Evidence Library'}.intersection(model['bullets'][index]['source_labels']):
        raise ValueError('The excluded wording has no eligible Base or Library provenance.')
    return index


def _slate(model: dict, *, edits: dict[int, int | None], extra: int | None = None) -> dict:
    """Keep exact order, ownership, and slots for every unaffected bullet."""
    rows = []
    indices = []
    for group, _, owned, original in model['groups']:
        after = [edits.get(index, index) for index in original]
        after = [index for index in after if index is not None]
        if extra is not None and extra in owned:
            after.append(extra)
        if not 1 <= len(after) <= 8 or len(set(after)) != len(after):
            raise ValueError('A trial must retain one to eight distinct bullets per project.')
        indices.extend(after)
        selected = [model['bullets'][index] for index in after]
        rows.append({
            'project': group['project'],
            'before': [model['bullets'][index]['text'] for index in original],
            'after': [bullet['text'] for bullet in selected],
            'sources': [bullet['source_labels'] for bullet in selected],
            'supported_jd_ids': [sorted(bullet['ids']) for bullet in selected],
            'after_count': len(after), 'before_count': len(original),
        })
    return {
        'proposal': {'version': FITTED_WRITER_VERSION, 'status': 'candidate', 'changed': True,
                     'variable_bullet_counts': True, 'project_set_unchanged': True, 'projects': rows},
        'indices': tuple(indices),
    }


def plan_trials(model: dict, source: dict, *, operation: str, project: str,
                remove: str = '', insert: str = '', extra: str = '', extra_project: str = '') -> dict:
    if operation not in OPERATIONS:
        raise ValueError('Choose an available counterfactual operation.')
    if operation == 'remove':
        if not remove or insert or extra or extra_project:
            raise ValueError('A removal needs one exact selected bullet.')
        old = _locate(model, project, remove, selected=True)
        return {'remove': _slate(model, edits={old: None})}
    if operation == 'force_in':
        if not insert or remove or extra or extra_project:
            raise ValueError('Forced inclusion needs one exact excluded bullet.')
        index = _locate(model, project, insert, selected=False)
        solution = _solve(model, [], time_limit=1.0, forced={index: 1})
        if solution.get('status') != 'optimal_proxy':
            return {'forced_in': {'status': 'unavailable', 'reason': solution.get('reason')}}
        return {'forced_in': {'proposal': _candidate(model, source, solution, 1),
                               'indices': solution['selected_indices'], 'proxy_receipt': solution['phase_receipts']}}

    if not remove or not insert or (operation != 'use_freed_words' and (extra or extra_project)):
        raise ValueError('A source swap needs exact selected and excluded wordings.')
    old = _locate(model, project, remove, selected=True)
    new = _locate(model, project, insert, selected=False)
    old_tags = set(model['bullets'][old]['source_labels'])
    new_tags = set(model['bullets'][new]['source_labels'])
    base_to_library = 'Selected Base' in old_tags and 'Evidence Library' in new_tags
    library_to_base = 'Evidence Library' in old_tags and 'Selected Base' in new_tags
    if ((operation == 'base_to_library' and not base_to_library)
            or (operation == 'library_to_base' and not library_to_base)
            or (operation == 'use_freed_words' and not (base_to_library or library_to_base))):
        raise ValueError('The saved source provenances do not support that swap direction.')
    swapped = _slate(model, edits={old: new})
    if operation != 'use_freed_words':
        return {'swap': swapped}
    saved = model['bullets'][old]['words'] - model['bullets'][new]['words']
    if saved <= 0 or not extra:
        raise ValueError('The space trial requires a shorter replacement and a distinct additional bullet.')
    added = _locate(model, extra_project or project, extra, selected=False)
    if added == new:
        raise ValueError('Select a separate additional bullet.')
    combined = _slate(model, edits={old: new}, extra=added)
    try:
        extra_only = _slate(model, edits={}, extra=added)
    except ValueError as error:
        extra_only = {'status': 'unavailable', 'reason': str(error)}
    return {'swap': swapped, 'swap_plus_extra': combined, 'extra_without_swap': extra_only}


def _wording_effects(model: dict, baseline: tuple[int, ...], alternative: tuple[int, ...],
                     catalog: dict, raw_jd: str) -> list[dict]:
    old, new = set(baseline), set(alternative)
    fragments = {rid: requirement_fragment(req, raw_jd) for rid, req in catalog.items()}
    verification_scope = {}
    for name, indices in (('baseline', old), ('trial', new)):
        verification_scope[name] = Counter(rid for index in indices
                                           for rid in model['bullets'][index]['ids'])
    changed = []
    for action, indices, role in (('removed', sorted(old - new), 'baseline'),
                                  ('added', sorted(new - old), 'trial')):
        for index in indices:
            bullet = model['bullets'][index]
            match = explain_bullet({'bullet': bullet['text'], 'saved_jd_ids': sorted(bullet['ids'])}, catalog,
                                   raw_jd_text=raw_jd, fragments=fragments)
            changed.append({
                'action': action, 'project': bullet['project'], 'wording': bullet['text'],
                'sources': bullet['source_labels'], 'words': bullet['words'],
                'matched_technologies': match['jd_wide_technology_cues'],
                'matched_activities': match['matched_action_families'],
                'saved_links': [{'text': req['text'], 'importance': req['importance'],
                                 'parent': req['fragment']['parent'],
                                 'source_status': req['fragment']['source_status'],
                                 'grammar_status': req['fragment']['grammar_status'],
                                 'lexical_cues': req['keyword_overlap'],
                                 'saved_support': 'unique' if verification_scope[role][req['id']] == 1 else 'shared'}
                                for req in match['jd_links']],
            })
    return changed


def evaluate_counterfactual(case: dict, *, operation: str, project: str, remove: str = '',
                            insert: str = '', extra: str = '', extra_project: str = '',
                            work_root=None, evaluate=evaluate_document_trial, evaluator=None) -> dict:
    with offline_execution('V3.7 counterfactual evaluation is offline'):
        model, source = build_case_model(case['audit'], case['projects'], evaluator=evaluator)
        plans = plan_trials(model, source, operation=operation, project=project, remove=remove,
                            insert=insert, extra=extra, extra_project=extra_project)
        baseline = tuple(index for _, _, _, indices in model['groups'] for index in indices)
        catalog = requirement_catalog(case['baseline'], case['projects'])
        raw = case['raw_jd_text']
        baseline_metrics = slate_metrics(model, baseline, catalog, raw)
        baseline_native = evaluate(case, work_root=work_root)
        result = {'schema': VERSION, 'application_id': case['application_id'], 'generation_id': case['generation_id'],
                  'jd_sha256': sha256(raw.encode('utf-8')).hexdigest(), 'operation': operation,
                  'baseline': {'proxy': baseline_metrics, 'native': baseline_native}, 'trials': {}}
        for name, plan in plans.items():
            if 'proposal' not in plan:
                result['trials'][name] = plan
                continue
            indices = plan['indices']
            stats = slate_metrics(model, indices, catalog, raw)
            changes = _wording_effects(model, baseline, indices, catalog, raw)
            measured = (evaluate(case, plan['proposal'], work_root=work_root)
                        if baseline_native['status'] == 'verified' else
                        {'status': 'unavailable', 'score': None, 'pages': None,
                         'reason': 'The actual baseline document could not be verified.'})
            comparison = compare_native_trials(baseline_native, measured)
            result['trials'][name] = {
                'status': comparison['comparison_status'],
                'scope': ('constrained_reoptimization' if name == 'forced_in' else 'controlled_bullet_edit'),
                'changed_bullets': changes, 'proxy': stats, 'native': measured, 'comparison': comparison,
                'saved_link_proxy_delta': round(stats['selection_proxy_saved_points']
                                                - baseline_metrics['selection_proxy_saved_points'], 4),
                'words_saved': baseline_metrics['project_bullet_words'] - stats['project_bullet_words'],
                'proxy_solve_receipt': plan.get('proxy_receipt'),
            }
        if operation == 'use_freed_words':
            swap = result['trials']['swap']
            both = result['trials']['swap_plus_extra']
            alone = result['trials']['extra_without_swap']
            marginal = compare_native_trials(swap['native'], both['native'])
            result['space_test'] = {
                'added_bullet_native_effect_after_swap': marginal,
                'swap_saved_words': swap['words_saved'],
                'added_bullet_cost': both['proxy']['project_bullet_words'] - swap['proxy']['project_bullet_words'],
                'fit_enabled_by_swap': (
                    True if both['status'] == 'verified' and alone.get('native', {}).get('status') == 'fit_failed'
                    else False if both['status'] == alone['status'] == 'verified' else None),
            }
        return result
