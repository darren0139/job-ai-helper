"""Read-only ATS diagnostics over exact document excerpts and governed links."""
from __future__ import annotations

from collections import defaultdict
import re

from tailoring.phase6d_ranking_adapter import match_requirement_to_candidate
from tailoring.phase9f_v365_jd_evidence import meaningful_terms, requirement_fragment
from taxonomy_discovery.technology_registry import get_default_registry, normalise

SUPPORTED = {'direct', 'transferable'}


def _present(surface: str, text: str) -> bool:
    surface = normalise(surface)
    return bool(surface and re.search(r'(?<![a-z0-9+#])' + re.escape(surface) + r'(?![a-z0-9+#])', text))


def ats_evidence(requirements: list[dict], excerpts: list[dict], raw_jd: str, *,
                 scorer_rows: list[dict] = ()) -> dict:
    """Separate literal identity, candidate support, provenance, and coverage."""
    registry = get_default_registry()
    native = {r.get('id') or r.get('requirement_id'): r for r in scorer_rows}
    normalized = [normalise(excerpt['text']) for excerpt in excerpts]
    evaluations = []
    parent_allocations = defaultdict(dict)
    for req in requirements:
        rid = req['requirement_id']
        raw = req['text']
        jd = normalise(raw)
        terms = meaningful_terms(raw)
        parent = req.get('scoring_parent_occurrence_id') or rid
        fraction = req.get('group_weight_fraction')
        fragment = requirement_fragment({'text': raw, 'parent': req.get('parent_text'),
                                         'source_provenance': req.get('source_provenance')}, raw_jd)
        governed = fragment['eligible_for_bonus_explanation'] and req.get('evidence_eligible', True)
        jd_technologies = [(entry, [alias for alias in entry['aliases'] if _present(alias, jd)])
                           for entry in registry.entries]
        jd_technologies = [(entry, aliases) for entry, aliases in jd_technologies if aliases]
        matches = []
        scored = native.get(rid) or {}
        scorer_evidence = {
            normalise(item.get('text') if isinstance(item, dict) else item)
            for item in scored.get('evidence') or []
        }
        for excerpt, text in zip(excerpts, normalized, strict=True):
            exact, aliases = [], []
            for entry, surfaces in jd_technologies:
                if any(_present(term, text) for term in surfaces):
                    exact.append(entry['technology_id'])
                elif any(_present(term, text) for term in entry['aliases']):
                    aliases.append(entry['technology_id'])
            identical_skill = excerpt['section'] == 'skills' and _present(excerpt['text'], jd)
            cues = sorted(terms & meaningful_terms(excerpt['text']))
            decision = match_requirement_to_candidate(requirement=req, candidate_evidence_text=excerpt['text'])
            native_label = scored.get('match_label') if text in scorer_evidence else None
            label = decision.get('label')
            grounded = (excerpt.get('attested') is True and governed
                        and (label in SUPPORTED or native_label in SUPPORTED))
            if not (exact or aliases or identical_skill or cues or grounded):
                continue
            matches.append({
                'section': excerpt['section'], 'project': excerpt.get('project'), 'text': excerpt['text'],
                'attested': excerpt.get('attested') is True, 'exact_technologies': exact,
                'technology_aliases': aliases, 'exact_skill': identical_skill,
                'lexical_cues': cues, 'capability_label': label, 'native_excerpt_label': native_label,
                'capability_reason': decision.get('reason'), 'grounded_support': grounded,
                'unsupported_keyword_only': (bool(exact or aliases or identical_skill)
                                             and excerpt.get('attested') is not True),
            })
        for i, match in enumerate(matches):
            others = {row['section'] for j, row in enumerate(matches) if i != j and row['grounded_support']}
            match['supported_elsewhere'] = sorted(others)
            match['generic_or_repeated_cue_only'] = bool(match['lexical_cues'] and not match['grounded_support']
                                                        and not match['exact_technologies'] and not match['exact_skill'])
        if any(match['grounded_support'] for match in matches) and isinstance(fraction, (int, float)):
            parent_allocations[parent][rid] = min(1.0, max(0.0, fraction))
        evaluations.append({'id': rid, 'text': raw, 'importance': req['importance'], 'parent': parent,
                            'parent_fraction': fraction, 'fragment_status': fragment['source_status'],
                            'evidence_scope_eligible': governed,
                            'jd_technologies': [entry['technology_id'] for entry, _ in jd_technologies],
                            'matches': matches})
    return {'registry_version': registry.version, 'requirements': evaluations,
            'supported_parent_allocations': {parent: min(1.0, sum(parts.values()))
                                             for parent, parts in parent_allocations.items()},
            'grounded_requirement_ids': sorted(row['id'] for row in evaluations
                                               if any(m['grounded_support'] for m in row['matches'])),
            'distinct_exact_technologies': sorted({technology for row in evaluations for m in row['matches']
                                                   if m['attested'] for technology in m['exact_technologies']}),
            'unsupported_keyword_occurrences': sum(m['unsupported_keyword_only'] for row in evaluations
                                                   for m in row['matches'])}


def resume_excerpts(projects: list[dict], skill_lines: list[dict]) -> list[dict]:
    return [
        {'section': 'projects', 'project': row['project'], 'text': text, 'attested': True}
        for row in projects for text in row['after']
    ] + [
        {'section': 'skills', 'text': text, 'attested': True}
        for row in skill_lines for text in row['items']
    ]
