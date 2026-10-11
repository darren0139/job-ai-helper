"""Experimental completeness gate, test-only; no production entry point."""
from contextlib import contextmanager
from copy import deepcopy
from collections import defaultdict
import re
from unittest.mock import patch
from analysis_stability import stable_evidence_scoring as scorer
from tailoring.phase6d6_structured_matching import technology_requirement_structure, STRUCTURED_MATCH_VERSION
from tailoring.capability_taxonomy import evaluate_capability_evidence

EXAMPLE = re.compile(r'\b(?:such as|including|for example|e\.g\.)\b', re.I)
ONE_OF = re.compile(r'\b(?:one of|one or more of|either)\b', re.I)
COORDINATED = re.compile(r'\b(?:and|or)\b|,', re.I)
ACTIVITY = re.compile(r'\b(?:build|building|develop|development|implement|maintain|monitor|deploy|work|fix|design|support)\b', re.I)


def _has_support(row):
    return row.get('match_label') in {'direct', 'transferable'} and bool(row.get('evidence'))


def _approved_structured(row):
    # Preserve the native independently verified producer, including its approved
    # multi-language receipt. Never synthesize an evidence list from child rows.
    return (row.get('structured_match_version') == STRUCTURED_MATCH_VERSION
            and row.get('structured_match_kind') == 'programming_language_group'
            and row.get('structured_match_status') in {'applied', 'confirmed_existing_direct', 'confirmed_existing_transferable'}
            and row.get('structured_match_group_mode') in {'all', 'any'}
            and bool(row.get('structured_match_matched_terms')) and _has_support(row))


def _parent_capability_proof(row, parent):
    cap = row.get('capability_id')
    if not cap or not _has_support(row):
        return False
    full = {**row, 'text': parent, 'atomic_focus': parent}
    return any(evaluate_capability_evidence(cap, full, e.get('text', '')).get('label')
               in {'direct', 'transferable'} for e in row.get('evidence', []))


def mode_for(parent, rows):
    structure = technology_requirement_structure({'text': parent, 'importance': rows[0].get('importance')})
    if EXAMPLE.search(parent):
        return 'EXAMPLE_ONLY', structure
    if ONE_OF.search(parent):
        return 'ONE_OF', structure
    if structure['mode'] == 'any':
        return 'ANY', structure
    if structure['mode'] == 'all':
        return 'ALL', structure
    if structure['source'] == 'native_coherent_example_or_alternative_parent':
        return 'COHERENT_PARENT', structure
    # Coordination signals uncertainty, never a guessed AND/OR operator.
    if COORDINATED.search(parent):
        return ('MIXED_ACTIVITY_SCOPE' if ACTIVITY.search(parent) else 'COHERENT_PARENT'), structure
    return 'ATOMIC', structure


def evaluate_group(parent, rows):
    """Complete-parent proof only; knowledge never implies evidence.

    ALL can use one common selected receipt. Independently supported children
    using different evidence rows are not silently combined. Existing native
    structured programming-language receipts remain an approved exception.
    """
    mode, structure = mode_for(parent, rows)
    result = {'mode': mode, 'native_structure': structure, 'complete': False,
              'reason': 'structural_semantics_not_proven', 'children': [
                  {'requirement_id': r.get('requirement_id'), 'label': r.get('match_label'),
                   'capability_id': r.get('capability_id'), 'knowledge_status': r.get('knowledge_status'),
                   'evidence_ids': [e.get('evidence_id') for e in r.get('evidence', [])]}
                  for r in rows]}
    if mode == 'ATOMIC':
        return {**result, 'complete': all(_has_support(r) for r in rows),
                'reason': 'atomic_native_credit_unchanged'}
    if len(rows) == 1 and _approved_structured(rows[0]):
        return {**result, 'complete': True, 'reason': 'approved_native_structured_receipt'}
    if mode in {'EXAMPLE_ONLY', 'COHERENT_PARENT', 'MIXED_ACTIVITY_SCOPE'}:
        if len(rows) == 1 and _parent_capability_proof(rows[0], parent):
            return {**result, 'complete': True, 'reason': 'single_row_independent_parent_capability_proof'}
        return result
    if mode in {'ANY', 'ONE_OF'}:
        if structure.get('mode') != 'any':
            return result
        allowed = {scorer._normalise_basic(c['atomic_focus']) for c in structure['components']}
        for row in rows:
            focus = scorer._normalise_basic(row.get('atomic_focus') or row.get('text'))
            if focus in allowed and _has_support(row):
                return {**result, 'complete': True, 'reason': 'native_allowed_alternative_supported'}
        return {**result, 'reason': 'no_supported_native_alternative'}
    components = {scorer._normalise_basic(c['atomic_focus']) for c in structure['components']}
    actual = {scorer._normalise_basic(r.get('atomic_focus') or r.get('text')) for r in rows}
    if not components or actual != components:
        return {**result, 'reason': 'mandatory_component_set_unavailable_or_incomplete'}
    if not all(_has_support(r) for r in rows):
        return {**result, 'reason': 'mandatory_component_support_missing'}
    receipts = [{(e.get('evidence_id'), e.get('source'), e.get('text'))
                 for e in r.get('evidence', []) if e.get('evidence_id') and e.get('source')}
                for r in rows]
    if not set.intersection(*receipts):
        return {**result, 'reason': 'MULTI_EVIDENCE_COMPLETENESS_NOT_SUPPORTED'}
    return {**result, 'complete': True, 'reason': 'all_components_supported_by_common_native_receipt'}


def apply_guard(rows):
    output = deepcopy(rows)
    groups = defaultdict(list)
    for row in output:
        groups[row.get('atomic_group_id') or row.get('requirement_id')].append(row)
    for group in groups.values():
        parents = {r.get('parent_text') or r.get('text') for r in group}
        if len(parents) != 1:
            decision = {'mode': 'COHERENT_PARENT', 'complete': False,
                        'reason': 'conflicting_parent_provenance'}
        else:
            decision = evaluate_group(next(iter(parents)), group)
        if decision['mode'] == 'ATOMIC':
            continue
        for row in group:
            row['experimental_compound_completeness'] = {**deepcopy(decision),
                'original_label': row.get('match_label'), 'original_value': row.get('match_value'),
                'original_evidence': deepcopy(row.get('evidence', []))}
            if not decision['complete']:
                row.update(match_label='none', match_value=0.0, evidence_strength=0, evidence=[])
    return output


@contextmanager
def completeness_simulation():
    """Patch only the final native aggregation input; restore on exit."""
    native = scorer.compute_deterministic_alignment
    def guarded(rows, **kwargs):
        rows[:] = apply_guard(rows)
        return native(rows, **kwargs)
    with patch.object(scorer, 'compute_deterministic_alignment', guarded):
        yield
