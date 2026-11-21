"""Read-only, provenance-bounded lexical comparison of two saved Phase 9F bullets.

Lexical overlap is never interpreted as JD coverage, selection cause or qualification.
No model, network, database, filesystem or scorer writes.
"""
from __future__ import annotations
import html
import re
from typing import Any

VERSION = 'phase9f-v27-saved-bullet-jd-terms-v1'
_WORD = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z][A-Za-z0-9]*(?:[.+#/-][A-Za-z0-9+#]+)*|[0-9]+)(?![A-Za-z0-9])")
_STOP = frozenset('a an and as at be by for from in into is it of on or our that the their these this to using use used via was were will with within work working would you your we i they one more such including experience good strong must should able ability skills years role related candidate'.split())


def _terms(text: str) -> set[str]:
    return {m.group().casefold() for m in _WORD.finditer(text or '') if m.group().casefold() not in _STOP and len(m.group()) > 1}


def _marked(text: str, matched: set[str]) -> str:
    """Produce safe Markdown: escape literal source text, bold only exact JD terms."""
    def esc(value: str) -> str:
        value = html.escape(value, quote=False)
        return re.sub(r'([\\`*_{}\[\]()#+!|>~-])', r'\\\1', value)
    out, pos = [], 0
    for match in _WORD.finditer(text):
        out.append(esc(text[pos:match.start()]))
        fragment = esc(match.group())
        out.append('**' + fragment + '**' if match.group().casefold() in matched else fragment)
        pos = match.end()
    out.append(esc(text[pos:]))
    return ''.join(out)


def compare_saved_source_bullets(decision: dict[str, Any], requirement_labels: dict[str, Any]) -> dict[str, Any]:
    """Return exact JD-term sets only with a verified decision-time peer receipt.

    No arbitrary B1/L1 pairing; a peer is the frozen same-project opposite-
    source candidate available at this particular selection step.
    """
    def withheld(message: str) -> dict[str, Any]:
        return {'status': 'withheld', 'message': message}
    if not isinstance(decision, dict) or not decision.get('selected') or not isinstance(requirement_labels, dict):
        return withheld('Selected bullet and saved JD requirement labels are necessary.')
    ctx = decision.get('decision_context') or {}
    if not isinstance(ctx, dict) or ctx.get('version') != 'phase9f-v27-bullet-selection-explanation-v1':
        return withheld('This generation has no verified decision-time peer snapshot.')
    left, right = ctx.get('selected'), ctx.get('best_opposite_source_peer_at_step')
    if not isinstance(left, dict) or not isinstance(right, dict):
        return withheld('No eligible opposite-source bullet was recorded at this step.')
    if (left.get('bullet_id') != decision.get('bullet_id') or
            left.get('bullet') != decision.get('bullet') or
            not isinstance(left.get('sources'), list) or not isinstance(right.get('sources'), list) or
            set(left['sources']) not in ({'base'}, {'library'}) or
            set(right['sources']) != ({'library'} if set(left['sources']) == {'base'} else {'base'})):
        return withheld('Saved source ownership or bullet identity did not verify.')
    if not isinstance(left.get('strong_requirement_ids'), list) or not isinstance(right.get('strong_requirement_ids'), list):
        return withheld('Saved bullet support IDs are unavailable.')
    all_ids = sorted(set(left['strong_requirement_ids']) | set(right['strong_requirement_ids']))
    if not all(isinstance(x, str) and x in requirement_labels and isinstance(requirement_labels[x], dict)
               and isinstance(requirement_labels[x].get('text'), str) and requirement_labels[x]['text'] for x in all_ids):
        return withheld('Saved JD requirement IDs could not be resolved to exact source text.')
    joined = ' '.join(requirement_labels[x]['text'] for x in all_ids)
    jd_terms = _terms(joined)
    left_terms = _terms(left['bullet']) & jd_terms
    right_terms = _terms(right['bullet']) & jd_terms
    required = [{'id': x, 'text': requirement_labels[x]['text'],
                 'project_match': str(requirement_labels[x].get('match') or ''),
                 'selected_support_recorded': x in left['strong_requirement_ids'],
                 'alternative_support_recorded': x in right['strong_requirement_ids'],
                 'lexical_selected': sorted(_terms(requirement_labels[x]['text']) & _terms(left['bullet'])),
                 'lexical_alternative': sorted(_terms(requirement_labels[x]['text']) & _terms(right['bullet']))}
                for x in all_ids]
    is_admit = ctx.get('mode') == 'all_canonical_before_fitting'
    return {
        'status': 'ok', 'comparison_kind': 'read_only_lexical_diagnostic',
        'allocation_has_quality_winner': not is_admit,
        'selection_reason': ('Both sources admitted before fitting; no ranked winner.' if is_admit
                              else 'See frozen lexicographic rank factor; text overlap is NOT the selection cause.'),
        'chosen': {'bullet': left['bullet'], 'sources': left['sources'],
                   'words': left.get('word_count'), 'jd_terms': sorted(left_terms),
                   'marked': _marked(left['bullet'], left_terms),
                   'recorded_strong_ids': list(left['strong_requirement_ids'])},
        'peer': {'bullet': right['bullet'], 'sources': right['sources'],
                 'words': right.get('word_count'), 'jd_terms': sorted(right_terms),
                 'marked': _marked(right['bullet'], right_terms),
                 'recorded_strong_ids': list(right['strong_requirement_ids'])},
        'common_terms': sorted(left_terms & right_terms),
        'chosen_only_terms': sorted(left_terms - right_terms),
        'peer_only_terms': sorted(right_terms - left_terms),
        'requirements': required,
        'caveat': ('Only identical terminology grounded in saved JD rows is highlighted; '
                   'synonyms and transferable matches require separately proven evidence. '
                   'Project-level match labels are NOT per-bullet match labels.'),
    }
