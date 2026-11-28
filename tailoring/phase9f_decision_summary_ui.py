"""Visual summaries for saved project selection receipts."""
from html import escape
from math import isclose, isfinite

from tailoring.phase9f_optimizer_diagnostics_v312b214b4 import obj, rows, strings, wording
from tailoring.stable_tailoring_ranking import _IMPORTANCE_POINTS


_CSS = """
<style>
.decision-summary { border:1px solid color-mix(in srgb,currentColor 18%,transparent);
  border-radius:.9rem; padding:1rem 1.1rem; overflow-wrap:anywhere; }
.decision-summary h4 { margin:0 0 .65rem; padding:0; font-size:1.02rem; }
.decision-summary p { margin:.35rem 0; }
.decision-summary .ds-muted { opacity:.78; font-size:.86rem; }
.decision-summary .ds-line { display:flex; gap:.35rem 1rem; flex-wrap:wrap;
  justify-content:space-between; align-items:baseline; }
.decision-summary .ds-line strong:has(.ds-icon) { display:inline-flex; gap:.45rem; align-items:center; }
.decision-summary .ds-numbers { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(9rem,100%),1fr));
  gap:.55rem 1rem; margin:.3rem 0 .55rem; }
.decision-summary .ds-numbers strong { display:block; font-size:1.3rem; line-height:1.4; }
.decision-summary .ds-number { font-variant-numeric:tabular-nums; }
.decision-summary .ds-row { padding:.55rem 0; }
.decision-summary .ds-row + .ds-row { border-top:1px solid color-mix(in srgb,currentColor 12%,transparent); }
.decision-summary .ds-bar { height:.46rem; margin:.33rem 0 0; border-radius:.5rem; position:relative;
  background:color-mix(in srgb,currentColor 11%,transparent); overflow:hidden; }
.decision-summary .ds-bar span { position:absolute; height:100%; border-radius:inherit; background:#5687bf; }
.decision-summary .ds-timeline { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(15rem,100%),1fr));
  list-style:none; margin:.55rem 0 .1rem; padding:0; gap:.4rem .9rem; }
.decision-summary .ds-timeline li { margin:0; display:flex; gap:.45rem; font-size:.9rem; }
.decision-summary .ds-icon { width:1.07rem; height:1.07rem; flex:none; display:inline-grid; place-items:center;
  border:1px solid; border-radius:50%; font-size:.73rem; line-height:1; margin-top:.13rem; }
.decision-summary .ds-kept { color:#278367; }
.decision-summary .ds-removed { color:#cf665e; }
.decision-summary .ds-unknown, .decision-summary .ds-na { opacity:.74; }
.decision-summary .ds-na { border-style:dashed; }
.decision-summary .ds-pair { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(18rem,100%),1fr)); gap:.65rem; }
.decision-summary .ds-pair section { border:1px solid color-mix(in srgb,currentColor 16%,transparent);
  border-radius:.65rem; padding:.65rem .8rem; }
</style>
"""


def _num(value):
    return type(value) in (int, float) and isfinite(value)


def _points(value):
    if not _num(value):
        return 'Unavailable'
    return str(int(value)) if value == int(value) else str(value)


def _card(st, heading, body):
    st.html(f'{_CSS}<section class="decision-summary"><h4>{escape(heading)}</h4>{body}</section>')


def _line(left, right):
    return f'<div class="ds-line"><strong>{escape(left)}</strong><span class="ds-number">{escape(right)}</span></div>'


def _muted(text):
    return f'<p class="ds-muted">{escape(text)}</p>'


def _metrics(items):
    return '<div class="ds-numbers">' + ''.join(
        f'<div><span class="ds-muted">{escape(label)}</span><strong class="ds-number">{escape(value)}</strong></div>'
        for label, value in items
    ) + '</div>'


def _bar(value, ceiling, floor=0):
    if not _num(value) or not floor <= value <= ceiling or ceiling == floor:
        return ''
    scale = ceiling - floor
    start = (min(0, value) - floor) / scale
    return ('<div class="ds-bar" aria-hidden="true">'
            f'<span style="left:{start:.3%};width:{abs(value) / scale:.3%}"></span></div>')


def _project_status(row):
    portfolio = row['Portfolio decision']
    final = row.get('Final DOCX')
    if _num(final) and final > 0:
        return 'In fitted DOCX'
    if final == 0 and portfolio == 'Excluded by portfolio before fitting':
        return portfolio
    if final == 0 and row['Decision'] != 'Rejected':
        return f"{row['Decision']} · absent from fitted DOCX" if row['Decision'] == 'Removed / deprioritized' else row['Decision']
    return portfolio or row['Decision']


def render_ranking_overview(st, projects):
    if not projects:
        return
    scores = [row[field] for row in projects for field in ('Base ranking score', 'Selection score') if _num(row[field])]
    floor, ceiling = min([0, *scores]), max([100, *scores])
    items = []
    for row in projects:
        rank, base, adjusted = (row[field] for field in ('Rank', 'Base ranking score', 'Selection score'))
        status = _project_status(row)
        score = adjusted if _num(adjusted) else base
        name = f'#{rank} · {row["Project"]}' if _num(rank) else row['Project']
        labels = f'Base {_points(base)} · Adjusted {_points(adjusted)}'
        items.append(f'<div class="ds-row">{_line(name, labels)}{_muted(status)}{_bar(score, ceiling, floor)}</div>')
    _card(st, 'Evaluated projects', _muted(
        'Bars share a point scale and use the adjusted score when it is available. Scores can exceed 100 points.'
    ) + ''.join(items))


def coverage_maximum(rank, requirement):
    # The saved v4 receipt records the effective fraction used by the ranking formula.
    if not _known_ranking(rank):
        return None
    importance = requirement.get('importance')
    weight = _IMPORTANCE_POINTS.get(importance) if isinstance(importance, str) else None
    fraction = requirement.get('group_weight_fraction')
    if weight and _num(fraction) and fraction > 0:
        return round(weight * fraction, 4)
    return None


def _known_ranking(rank):
    return (rank.get('ranking_version') in ('phase6b1-project-ranking-v4', 'phase6b1-project-ranking-v5', 'phase6b1-project-ranking-v6')
            and rank.get('ranking_owner') == 'python_deterministic_evidence_mapping')


def project_calculations(rank):
    if not _known_ranking(rank):
        return []
    coverage, support, score, bonus, penalty, adjusted = (rank.get(field) for field in (
        'deterministic_coverage_score', 'support_score', 'final_score', 'unique_coverage_bonus',
        'overlap_penalty', 'selection_score'))
    result = []
    if _num(coverage) and _num(score):
        if coverage <= 0 and score == 0:
            result.append('Base ranking score = 0 (no positive JD coverage).')
        elif coverage > 0 and _num(support):
            expression = f'Base = min(100, round(2 × {_points(coverage)} + {_points(support)}))'
            saved = f' = {_points(score)}' if min(100, round(2 * coverage + support)) == score else (
                f' · saved score {_points(score)} (displayed inputs are rounded)')
            result.append(expression + saved)
    if all(_num(value) for value in (score, bonus, penalty, adjusted)):
        expression = f'Adjusted = {_points(score)} + {_points(bonus)} − {_points(penalty)}'
        saved = f' = {_points(adjusted)}' if isclose(score + bonus - penalty, adjusted, abs_tol=1e-8) else (
            f' · saved score {_points(adjusted)} (displayed inputs are rounded)')
        result.append(expression + saved)
    return result


def project_requirements(rank):
    relevance = obj(rank.get('project_relevance'))
    relationships = rows(relevance.get('requirement_relationships'))
    matches = rows(rank.get('requirement_matches'))
    matched_ids = {row.get('requirement_id') for row in matches}
    return matches + [row for row in relationships if row.get('requirement_id') not in matched_ids]


def render_project_summary(st, row, requirements):
    rank = row['rank_receipt']
    base, adjusted = row['Base ranking score'], row['Selection score']
    position = row['Rank']
    metrics = _metrics([('Rank', f'#{position}' if _num(position) else 'Unavailable'),
                        ('Base ranking score', _points(base)), ('Adjusted selection score', _points(adjusted))])
    contributions = []
    for item in requirements:
        if item.get('match_label') in (None, 'none'):
            continue
        points = item.get('coverage_points')
        maximum = coverage_maximum(rank, item)
        comparable = maximum and _num(points) and 0 <= points <= maximum
        award = f'{_points(points)} / {_points(maximum)} points' if comparable else (
            f'{_points(points)} points' if _num(points) else 'Points unavailable')
        importance = str(item.get('importance') or 'Importance unavailable').replace('_', ' ').capitalize()
        label = str(item['match_label']).capitalize()
        name = item.get('requirement_text') or item.get('requirement_id') or 'Requirement'
        contributions.append(f'<div class="ds-row">{_line(name, award)}{_muted(f"{importance} · {label}")}'
                             f'{_bar(points, maximum) if comparable else ""}</div>')
    math = ''.join(f'<p class="ds-number">{escape(line)}</p>' for line in project_calculations(rank))
    inputs = (('JD coverage', 'deterministic_coverage_score'), ('Evidence support', 'support_score'),
              ('Unique coverage bonus', 'unique_coverage_bonus'), ('Overlap penalty', 'overlap_penalty'))
    breakdown = _metrics([(label, _points(rank.get(field))) for label, field in inputs])
    if not math:
        math = _muted('Calculation unavailable for this receipt.')
    _card(st, row['Project'], metrics + _muted(_project_status(row))
          + '<div class="ds-row"><strong>JD coverage contributions</strong></div>'
          + (''.join(contributions) or _muted('No awarded JD contributions are recorded.'))
          + '<div class="ds-row">' + breakdown + math
          + _muted('Saved project-ranking points. Native Job Match applies to the résumé.') + '</div>')


def render_portfolio_visual(st, slates):
    values = [item.get('proxy_utility') for _, item in slates if _num(item.get('proxy_utility'))]
    floor, ceiling = min([0, *values]), max([0, *values])
    _card(st, 'Portfolio comparison', _muted('Saved proxy utility on a shared point scale. Native Job Match is separate.')
          + ''.join(f'<div class="ds-row">{_line(label, _points(item.get("proxy_utility")))}'
                    f'{_bar(item.get("proxy_utility"), ceiling, floor)}</div>' for label, item in slates))


def bullet_lifecycle(row):
    caller, prepared, final = (row.get(field) for field in ('Caller', 'Prepared', 'Final DOCX'))
    steps = {step['stage']: step for step in row['trace']}
    preparation = obj(steps.get('Preparation'))
    fitting = obj(steps.get('Fitting actions'))
    prep_events = rows(preparation.get('details')) if preparation.get('certainty') == 'Recorded' else []
    fit_events = rows(fitting.get('details')) if fitting.get('certainty') == 'Recorded' else []
    removed_in_fit = any(row['Wording'] == wording(event.get('removed_bullet'))
                         or row['Wording'] in [wording(text) for text in strings(event.get('source_bullets'))]
                         for event in fit_events)
    receipt = row['receipt'].get('selected')
    admitted = ('kept', 'Admitted during allocation') if receipt is True else (
        ('removed', 'Not selected during allocation') if receipt is False else ('unknown', 'Allocation unavailable'))
    generated = {'Present': ('kept', 'Present in generation / fitter caller'),
                 'Absent': ('na', 'Absent in generation / fitter caller')}.get(
                     caller, ('unknown', 'Generation / fitter caller unavailable'))
    preparation_status = ('removed', 'Removed during preparation') if prep_events else (
        ('unknown', 'Absent after preparation · cause unavailable') if caller == 'Present' and prepared == 'Absent'
        else {'Present': ('kept', 'Present after preparation'), 'Absent': ('na', 'Absent after preparation')}.get(
            prepared, ('unknown', 'Preparation unavailable')))
    if prepared == 'Absent':
        fitting_status = ('na', 'Not present during fitting')
    elif removed_in_fit and final == 'Absent':
        fitting_status = ('removed', 'Removed or fused during fitting')
    elif prepared == 'Present' and final == 'Present':
        fitting_status = ('kept', 'Survived fitting')
    elif prepared == 'Present' and final == 'Absent':
        fitting_status = ('unknown', 'Absent after fitting · cause unavailable')
    else:
        fitting_status = ('unknown', 'Fitting outcome unavailable')
    final_status = {'Present': ('kept', 'In fitted DOCX'), 'Absent': ('removed', 'Absent from fitted DOCX')}.get(
        final, ('unknown', 'Fitted DOCX membership unavailable'))
    optimizer = {'Included': ('kept', 'Proposed by optimizer'),
                 'Considered, excluded': ('na', 'Considered · not proposed')}.get(
                     row.get('Optimizer proposal'), ('unknown', 'Optimizer consideration unavailable'))
    if final == 'Present':
        headline = final_status
    elif prep_events:
        headline = ('removed', 'Removed before fitting')
    elif removed_in_fit and final == 'Absent':
        headline = fitting_status
    else:
        headline = final_status
    return headline, (admitted, generated, preparation_status, fitting_status, final_status, optimizer)


def _status(tone, label):
    icon = {'kept': '✓', 'removed': '×', 'unknown': '?', 'na': '−'}[tone]
    return f'<span class="ds-icon ds-{tone}" aria-hidden="true">{icon}</span><span>{escape(label)}</span>'


def render_bullet_summary(st, row, reason):
    headline, timeline = bullet_lifecycle(row)
    order = row['Allocation order']
    meta = ' · '.join(filter(None, (row['Source'], f'Allocation order #{order}' if order is not None else None)))
    scores = [('Strong allocation', 'Allocation evidence'), ('Weak allocation', 'Weak allocation evidence'),
              ('Pre-fit deduplication', 'Pre-fit deduplication points'), ('Independent saved links', 'Independent saved-link points')]
    if row['Optimizer marginal proxy'] is not None:
        scores.append(('Optimizer marginal proxy', 'Optimizer marginal proxy'))
    _card(st, 'Bullet decision summary',
          f'<div class="ds-line"><strong>{_status(*headline)}</strong><span>{escape(meta)}</span></div>'
          f'<p>{escape(row["Wording"])}</p>'
          + (f'<p class="ds-row"><strong>Recorded reason</strong><br>{escape(reason)}</p>' if reason else
             _muted('Decision reason unavailable.'))
          + '<div class="ds-row">' + _metrics([(label, _points(row.get(field))) for label, field in scores]) + '</div>'
          + '<ol class="ds-timeline" aria-label="Bullet lifecycle">' + ''.join(
              f'<li>{_status(*step)}</li>' for step in timeline) + '</ol>')


def render_wording_pair(st, heading, pair):
    markup = ''.join(
        f'<section><strong>{escape(label)}</strong>{_muted(source or "Source unavailable")}'
        f'<p>{escape(text)}</p>{_muted(f"Pre-fit points {_points(prefit)} · Independent saved-link points {_points(independent)}")}'
        '</section>'
        for label, text, source, prefit, independent in pair)
    _card(st, heading, f'<div class="ds-pair">{markup}</div>')
