"""An opt-in read-only view over trusted research coverage receipts."""
from hashlib import sha256
import json

from tailoring.phase9f_v37_hard_floor import HARD, verified_research_trial


def load_bonus_view(binding, raw_jd, catalog, audit):
    try:
        data = binding['data']
        if sha256(data).hexdigest() != binding['receipt_sha256'] or not audit['verified']:
            return None
        receipt = json.loads(data)
        before = receipt['baseline']
        variant = receipt['variants'][binding['variant']]
        after = variant['native']
        for name, doc in (('baseline', before), ('trial', after)):
            if (doc['docx_sha256'] != binding[f'{name}_sha256'] or not doc['docx_sha256']
                    or doc['scoring_version'] != binding['scoring_version']
                    or doc['jd_sha256'] != sha256(raw_jd.encode()).hexdigest()
                    or doc['layout_reference_sha256'] != audit['docx_sha256'] or not doc['docx_leads_verified']):
                return None
        verification = verified_research_trial(before, after, receipt['floors'])
        if verification['status'] != 'verified':
            return None
        old = {row['project']: row['after'] for row in before['docx_project_order']}
        new = {row['project']: row['after'] for row in after['docx_project_order']}
        if old.keys() != new.keys():
            return None
        sources = {}
        for group in audit['projects']:
            for key,label in (('base', 'Base'),('library', 'Evidence Library')):
                for bullet in group[key]:
                    sources.setdefault((group['project'], bullet['text']), set()).add(label)
        decisions = {(project, text) for listing in (old, new) for project, texts in listing.items() for text in texts}
        reviews = receipt['source_reviews']
        decisions.update((row['project'], row['wording']) for row in reviews)
        if decisions - sources.keys():
            return None
        for coverage in (receipt['baseline_bonus'], variant['bonus']):
            for row in coverage['requirements']:
                req = catalog.get(row['id'], {})
                if (row['text'], row['importance']) != (req.get('text'), req.get('importance')):
                    return None
        added = [(p,t) for p,texts in new.items() for t in texts if t not in old[p]]
        isolated = added[0] if len(added) == 1 and all(
            old[p] == [t for t in texts if (p,t) != added[0]] for p,texts in new.items()) else None
        return {'baseline': before, 'trial': after, 'previous_bonus': receipt['baseline_bonus'],
                'bonus': variant['bonus'], 'reviews': reviews, 'old': old, 'new': new, 'sources': sources,
                'decisions': sorted(decisions), 'isolated': isolated, 'comparison': verification['comparison'],
                'exact_ats': variant['exact_ats_technologies']}
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _coverage(units):
    if units['status'] == 'not_applicable':
        return 'Not applicable'
    return f"{units['earned']:g} of {units['available']:g} weighted units"


def _reviewed_change(previous, current):
    before, after = previous.get('earned'), current.get('earned')
    if before is None or after is None:
        return 'Reviewed requirement change unavailable'
    if before == 0 < after:
        return 'Newly covered in the research review'
    if 0 < before < after:
        return 'Stronger reviewed evidence for an already-covered requirement'
    if after < before:
        return 'Reviewed coverage decreased'
    return 'Reviewed coverage unchanged'


def render_bonus_view(st, view, project, ranked):
    st.markdown('#### Offline research coverage')
    if view is None:
        st.caption('Compatible offline receipt unavailable. Native impact unmeasured.')
        return
    old, new = view['old'], view['new']
    baseline, trial = view['baseline'], view['trial']
    comparison = view['comparison']
    st.write(f"**Main native Job Match** · {baseline['score']:g}/100 → {trial['score']:g}/100")
    for category in ('supporting', 'preferred'):
        previous = view['previous_bonus']['categories'][category]
        current = view['bonus']['categories'][category]
        st.write(f"**{category.title()} coverage** · {_coverage(previous)} → {_coverage(current)}")
    delta = comparison['native_delta']
    outcome = 'tie' if delta == 0 else f'{delta:+g} points'
    st.caption(f"Native outcome · {outcome} | Both documents fit one page | "
               f"{len(comparison['hard_regressions'])} Required/Core regressions.")
    st.caption('Supporting and Preferred are research weighted units. Native Job Match is reported separately.')
    st.caption('Exact JD technologies across the document · ' + (', '.join(view['exact_ats']) or 'none recorded'))
    requirements = {r['id']: r for r in view['bonus']['requirements']}
    previous_requirements = {r['id']: r for r in view['previous_bonus']['requirements']}
    native_before = {r['id']: r['match_label'] for r in baseline['requirements']}
    native_after = {r['id']: r['match_label'] for r in trial['requirements']}
    by_wording = {(row['project'], row['bullet']): row for row in ranked}
    for group, wording in view['decisions']:
        if project != 'All projects' and group != project:
            continue
        key = (group, wording)
        kept = wording in new[group]
        canonical = wording == new[group][0]
        role = 'Project introduction' if canonical else 'Included' if kept else 'Excluded'
        with st.expander(f"{group} · {role} · {len(wording.split())} words · {wording[:65]}"):
            st.write(wording)
            st.caption('Source · ' + ', '.join(sorted(view['sources'][key])))
            evidence = by_wording.get(key, {})
            signals = [*evidence.get('jd_wide_technology_cues', ()), *evidence.get('matched_action_families', ())]
            if signals:
                st.caption('JD technology and activity cues · ' + ', '.join(signals))
            for row in trial['requirements']:
                if row['importance'] in HARD and wording in row['evidence']:
                    st.write(f"{row['text']} · {row['importance'].title()} · {row['match_label']} · "
                             f"Native strength {row['evidence_strength']}/5")
            reviews = [row for row in view['reviews'] if (row['project'], row['wording']) == key]
            for review in reviews:
                rid = review['requirement_id']
                req = requirements[rid]
                st.write(f"{req['text']} · {req['importance'].title()} · Reviewed {review['label']} · "
                         f"Reviewed strength {review['strength']}/5")
                st.caption(review['basis'])
                if kept:
                    change = _reviewed_change(previous_requirements.get(rid, {}), req)
                    st.caption(f"Requirement-level review · {change} · {req['coverage']} evidence")
                    before_label = native_before.get(rid, 'not recorded')
                    after_label = native_after.get(rid, 'not recorded')
                    st.caption(f'Native requirement match · {before_label} → {after_label}')
                else:
                    st.caption('Coverage · outside the selected slate')
                if not kept:
                    best = req['best'] or {}
                    best_text = (best.get('evidence') or {}).get('text', '')
                    if best.get('label') == review['label'] and len(best_text.split()) < len(wording.split()):
                        difference = len(wording.split()) - len(best_text.split())
                        st.caption(f'The selected wording provides the same reviewed label and uses {difference} fewer words.')
                        st.write(best_text)
            if canonical:
                st.caption('Retained as the reviewed opening for this project.')
            elif key == view['isolated']:
                st.caption(f'Isolated addition · {len(wording.split())} words · Native Job Match {delta:+g}.')
            elif not kept and not reviews:
                st.caption('Outside the selected combination.')


def render_native_bonus(st, receipt, before_label, after_label, *, key):
    """Display the current native receipt alongside the independent research view."""
    with st.expander('Preferred and Supporting coverage', expanded=False):
        if receipt['status'] != 'verified':
            st.caption('Coverage unavailable. ' + receipt['reason'])
            return
        table = []
        for lane in ('preferred', 'supporting'):
            result = receipt['lanes'][lane]
            status = result['status']
            if status == 'applicable':
                available = result['available_units']
                before = f"{result['before_units']:g}/{available:g}"
                after = f"{result['after_units']:g}/{available:g}"
                delta = f"{result['delta_units']:+g} units"
            else:
                before = after = status.replace('_', ' ').capitalize()
                delta = '—'
            table.append({'Lane': lane.capitalize(), before_label: before, after_label: after, 'Change': delta})
        st.table(table)
        for row in receipt['requirements']:
            st.write(f"**{row['importance'].capitalize()}** · {row['text']}")
            if row['status'] != 'verified':
                st.caption(row['status'].capitalize() + ' · ' + row['exclusion'].replace('_', ' '))
                continue
            for label, side in ((before_label, 'before'), (after_label, 'after')):
                observed = row[side]
                st.caption(f"{label} · {observed['match_label'].capitalize()} · strength {observed['evidence_strength']}/5")
                if not observed['evidence']:
                    st.caption('Uncovered opportunity')
                for item in observed['evidence']:
                    st.text(item['text'])
        st.download_button('Download native coverage (JSON)', json.dumps(receipt, ensure_ascii=False, indent=2),
                           file_name='native_bonus_coverage.json', mime='application/json', key=key, on_click='ignore')
