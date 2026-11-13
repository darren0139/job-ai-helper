"""Bounded, read-only shadow comparison of Base vs Library bullet candidates.

Uses the application's *existing* per-bullet requirement-support rules on both
sources with the *same saved pooled project requirement matches*. Computes
transparent coverage signals under the final DOCX's bullet-count/word budget.
NOT a factual accuracy judge, verified page-fit optimizer, or production selector.
"""
from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Any, Callable

POLICY_VERSION = 'phase9f-bullet-quality-shadow-v2.5'
MAX_POOL = 15
MAX_BULLETS = 8
MAX_SUBSETS = 15000


def _text(s: Any) -> str:
    return ' '.join(str(s or '').split())


def _key(s: Any) -> str:
    return _text(s).casefold()


def _words(s: str) -> int:
    return len(_text(s).split())


def _withheld(reason: str) -> dict[str, Any]:
    return {'status': 'withheld', 'reason': reason, 'policy_version': POLICY_VERSION,
            'candidates': [], 'shadow_slate': [], 'final_slate': []}


def _rank_for_project(projects: dict[str, Any], name: str) -> dict[str, Any] | None:
    rows = projects.get('candidate_project_ranking')
    if not isinstance(rows, list):
        return None
    matched = [r for r in rows if isinstance(r, dict) and
               _key(r.get('display_title') or r.get('title')) == _key(name)]
    return matched[0] if len(matched) == 1 else None


def _unique_candidates(audit: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    rows = []
    index: dict[str, int] = {}
    for source, field in (('Selected Base', 'base'), ('Evidence Library', 'library')):
        bullets = audit.get(field)
        if not isinstance(bullets, list):
            return [], f'{source} bullet records missing.'
        for item in bullets:
            if not isinstance(item, dict) or not isinstance(item.get('text'), str):
                return [], 'Source bullet is not text.'
            line = _text(item['text'])
            if not line:
                return [], 'Source contains an empty bullet.'
            key = _key(line)
            if key in index:
                current = rows[index[key]]
                current['sources'].append(source)
                continue
            index[key] = len(rows)
            rows.append({'text': line, 'sources': [source], 'words': _words(line),
                         'source_label': f'{"B" if source == "Selected Base" else "L"}{item.get("number")}',
                         'support_ids': [], 'signal_points': 0.0})
    if len(rows) > MAX_POOL:
        return [], f'{len(rows)} distinct source bullets exceed bounded limit {MAX_POOL}.'
    return rows, ''


def _support_for_bullets(bullets: list[str], rank: dict[str, Any],
                         builder: Callable[..., list[dict[str, Any]]]) -> tuple[list[set[str]] | None, str]:
    try:
        details = builder(bullets=bullets, ranking_row=rank)
    except Exception as exc:
        return None, 'Shared bullet support evaluator unavailable: ' + type(exc).__name__
    if not isinstance(details, list) or len(details) != len(bullets):
        return None, 'Shared bullet evaluator returned an invalid row count.'
    known = {_text(m.get('requirement_id')) for m in rank.get('requirement_matches') or []
             if isinstance(m, dict) and _text(m.get('requirement_id'))}
    result: list[set[str]] = []
    for i, row in enumerate(details):
        if (not isinstance(row, dict) or row.get('bullet_index') != i or
                _key(row.get('bullet_text')) != _key(bullets[i]) or
                not isinstance(row.get('supported_requirement_ids'), list)):
            return None, 'Shared bullet evaluator returned mismatched bullet identities.'
        identifiers = row['supported_requirement_ids']
        if not all(isinstance(s, str) and _text(s) in known for s in identifiers):
            return None, 'Shared bullet evaluator returned foreign requirement identifiers.'
        result.append(set(identifiers))
    return result, ''


def _points(rank: dict[str, Any]) -> tuple[dict[str, float], str]:
    points = {}
    matches = rank.get('requirement_matches')
    if not isinstance(matches, list):
        return {}, 'Saved requirement-matching receipt absent.'
    for m in matches:
        if not isinstance(m, dict):
            return {}, 'Malformed saved requirement match.'
        rid = _text(m.get('requirement_id'))
        if not rid or rid in points:
            return {}, 'Missing or duplicate saved requirement ID.'
        if m.get('match_label') not in {'direct', 'transferable', 'weak'}:
            continue
        raw = m.get('coverage_points')
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return {}, 'Missing saved requirement coverage value.'
        if not 0 < v < 10000:
            return {}, 'Invalid saved requirement coverage value.'
        points[rid] = v
    return points, ''


def _score(slate: list[dict[str, Any]], points: dict[str, float]) -> tuple[float, list[str]]:
    support = sorted(set().union(*(set(row['support_ids']) for row in slate))) if slate else []
    return round(sum(points.get(s, 0.0) for s in support), 4), support


def build_shadow_bullet_quality_trial(
    audit: dict[str, Any], projects: dict[str, Any], *,
    priority_builder: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Shadow-only proxy: never changes source, report, selection or DOCX.

    Same final project bullet count; strict max word count as a cheap **proxy**
    for layout, not an actual page-fit guarantee. Enumerates all candidate slates
    only under MAX_SUBSETS; otherwise withholds. Canonical Library first on ties.
    A pool-level requirement match is not independent per-bullet ground truth.
    """
    if not isinstance(audit, dict) or not isinstance(projects, dict):
        return _withheld('Exact verified final audit and project-ranking receipts required.')
    name = _text(audit.get('project'))
    rank = _rank_for_project(projects, name)
    if rank is None:
        return _withheld('Project rank identity is missing or ambiguous.')
    points, error = _points(rank)
    if error:
        return _withheld(error)
    if not points:
        return {
            **_withheld('No saved project JD requirement matches; no supported coverage-quality comparison.'),
            'status': 'no_supported_requirements', 'project': name,
        }
    source, error = _unique_candidates(audit)
    if error:
        return _withheld(error)
    final = audit.get('final')
    if not isinstance(final, list) or not all(isinstance(x, dict) and isinstance(x.get('text'), str) and _text(x['text']) for x in final):
        return _withheld('Verified actual final-DOCX bullet records unavailable.')
    limit = len(final)
    if not (1 <= limit <= MAX_BULLETS) or len(source) < limit:
        return _withheld('Final count exceeds bounded comparison or canonical source pool is too small.')
    possible = comb(len(source), limit)
    if possible > MAX_SUBSETS:
        return _withheld(f'{possible} candidate slates exceed bounded evaluation limit {MAX_SUBSETS}.')
    builder = priority_builder
    if builder is None:
        try:
            from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
            builder = build_bullet_evidence_priorities
        except ImportError:
            return _withheld('Shared canonical bullet-priority evaluator unavailable.')
    final_rows = [{'text': _text(x['text']), 'words': _words(x['text'])} for x in final]
    all_bullets = [r['text'] for r in source] + [r['text'] for r in final_rows]
    support, error = _support_for_bullets(all_bullets, rank, builder)
    if support is None:
        return _withheld(error)
    for row, ids in zip(source + final_rows, support):
        row['support_ids'] = sorted(s for s in ids if s in points)
        row['signal_points'] = round(sum(points[x] for x in row['support_ids']), 4)
    final_words = sum(x['words'] for x in final_rows)
    baseline_points, baseline_ids = _score(final_rows, points)
    best = None
    best_metric = None
    feasible = 0
    for selection in combinations(range(len(source)), limit):
        slate = [source[i] for i in selection]
        total_words = sum(x['words'] for x in slate)
        if total_words > final_words:
            continue
        feasible += 1
        coverage, req_ids = _score(slate, points)
        # Tie-breaker: fewer words, prefer canonical Library over Base, then
        # stable source order. Never call this a semantic quality score.
        canonical_count = sum('Evidence Library' in x['sources'] for x in slate)
        metric = (coverage, -total_words, canonical_count, tuple(-i for i in selection))
        if best_metric is None or metric > best_metric:
            best_metric = metric
            best = (slate, coverage, req_ids, total_words)
    if best is None:
        return {'status': 'no_feasible_source_slate', 'reason': 'No same-count source slate fits the final-DOCX word-count proxy.',
                'policy_version': POLICY_VERSION, 'project': name, 'final_slate': final_rows,
                'final_word_budget': final_words, 'final_signal_points': baseline_points,
                'final_signal_ids': baseline_ids, 'candidates': source, 'shadow_slate': [],
                'tested_subsets': possible, 'feasible_subsets': 0}
    slate, value, ids, words = best
    stronger = value > baseline_points + 1e-6
    return {
        'status': 'potential_coverage_gain' if stronger else 'no_coverage_gain_signal',
        'project': name, 'policy_version': POLICY_VERSION,
        'reason': ('A bounded same-count/word-budget source slate has a HIGHER inferred JD coverage signal. '
                   'Human factual review, source approval and real page-fit are REQUIRED.' if stronger else
                   'No higher inferred JD coverage signal under this bounded source slate comparison.'),
        'candidates': source, 'final_slate': final_rows, 'shadow_slate': slate,
        'final_word_budget': final_words, 'shadow_words': words,
        'final_signal_points': baseline_points, 'shadow_signal_points': value,
        'final_signal_ids': baseline_ids, 'shadow_signal_ids': ids,
        'signal_delta': round(value-baseline_points, 4),
        'tested_subsets': possible, 'feasible_subsets': feasible,
        'base_promotions_needed': [r['text'] for r in slate if 'Evidence Library' not in r['sources']],
        'method': 'Existing deterministic bullet-support evaluator + saved pooled per-project requirement matches; '
                  'distinct requirement coverage counted once; exact final bullet count; word count at most actual final. '
                  'No independent factual validation, causality, true page-fit proof or Job Match rescoring.',
    }


def render_shadow_bullet_quality_trial(st: Any, *, audit_project: dict[str, Any], projects: dict[str, Any], application_id: int) -> bool:
    """Invoked ONLY from the already-verified V2.4 audit, never on an unbound source."""
    st.caption('Optional bounded, local shadow evaluation — **no model calls, no résumé edits**. '
               'Compares approved source wording against actual final DOCX under the same bullet count and word budget.')
    if not st.checkbox('Run local Base vs Library quality pilot for this project', value=False,
                       key=f'phase9f_shadow_quality_v25_{int(application_id)}_{_key(audit_project.get("project"))}'):
        return False
    result = build_shadow_bullet_quality_trial(audit_project, projects)
    if result['status'] in {'withheld', 'no_supported_requirements', 'no_feasible_source_slate'}:
        st.info(result['reason'])
        return False
    st.write('**Finding:** ' + result['reason'])
    st.caption(result['method'])
    c1, c2, c3 = st.columns(3)
    c1.metric('Final coverage proxy', result['final_signal_points'])
    c2.metric('Candidate coverage proxy', result['shadow_signal_points'])
    c3.metric('Final vs candidate words', f'{result["final_word_budget"]} / {result["shadow_words"]}')
    st.caption(f'Checked {result["tested_subsets"]} same-count slates; {result["feasible_subsets"]} met the word-count proxy. '
               'These are *not* new Job Match points or a verified one-page layout.')
    if result['base_promotions_needed']:
        st.warning('The shadow candidate includes Base-only bullets. They are NOT approved canonical writer inputs. '
                   'Review and approve factual content in the Evidence Library before any use.')
    tab_final, tab_alternative, tab_pool = st.tabs(['Actual final bullets', 'Shadow candidate — NOT applied', 'All source candidates'])
    with tab_final:
        for i, r in enumerate(result['final_slate'], 1):
            with st.container(border=True):
                st.write(f'**F{i} · {r["words"]} words · inferred support {r["signal_points"]}**')
                st.write(r['text'])
                st.caption('Candidate requirement IDs: ' + (', '.join(r['support_ids']) or 'none detected'))
    with tab_alternative:
        for i, r in enumerate(result['shadow_slate'], 1):
            with st.container(border=True):
                st.write(f'**S{i} · {" + ".join(r["sources"])} · {r["words"]} words · inferred support {r["signal_points"]}**')
                st.write(r['text'])
                st.caption('Candidate requirement IDs: ' + (', '.join(r['support_ids']) or 'none detected'))
    with tab_pool:
        st.dataframe([{'Source': ' + '.join(r['sources']), 'Bullet text': r['text'], 'Words': r['words'],
                       'Inferred support IDs': ', '.join(r['support_ids']), 'Support proxy': r['signal_points']}
                      for r in result['candidates']], use_container_width=True, hide_index=True,
                     column_config={'Bullet text': st.column_config.TextColumn(width='large')})
    st.caption('**Decision:** advisory only. Do not call any slate “best possible” without held-out factual/quality labels and rendered one-page fit verification.')
    return True
