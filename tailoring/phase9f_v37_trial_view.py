"""Trusted offline receipts for an explicitly enabled read-only Decision Explorer view."""
from hashlib import sha256
import json
import re

from tailoring.phase9f_v37_document_trial import compare_native_trials


def controlled_trial_rows(data: bytes, *, receipt_sha256: str, jd_sha256: str, scoring_version: str,
                          baseline_sha256: str, trial_sha256: str, catalog: dict, audit: dict) -> list[dict]:
    """Bind the receipt to caller-verified document and scorer identities."""
    if (not all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v)
                for v in (receipt_sha256, jd_sha256, baseline_sha256, trial_sha256))
            or not scoring_version or baseline_sha256 == trial_sha256 or sha256(data).hexdigest() != receipt_sha256):
        return []
    try:
        receipt = json.loads(data)
        before, after = receipt['baseline'], receipt['trial']
        for document, expected in ((before, baseline_sha256), (after, trial_sha256)):
            if (document['jd_sha256'] != jd_sha256 or document['scoring_version'] != scoring_version
                    or document['docx_sha256'] != expected or document['pages'] != 1
                    or document['layout_reference_sha256'] != audit['docx_sha256']
                    or not audit['verified'] or not document['docx_leads_verified']):
                return []
        verdict = compare_native_trials(before, after)
        if verdict['comparison_status'] != 'verified':
            return []
        old = {row['project']: row['after'] for row in before['docx_project_order']}
        new = {row['project']: row['after'] for row in after['docx_project_order']}
        if old.keys() != new.keys():
            return []
        matching = []
        for item in receipt['decisions']:
            project, wording, rid = item['project'], item['wording'], item['requirement_id']
            requirement = catalog.get(rid) or {}
            classification = (item['requirement'], item['importance'])
            reqs = [[r for r in doc['requirements'] if r['id'] == rid] for doc in (before, after)]
            if ((requirement.get('text'), requirement.get('importance')) != classification
                    or any(len(rows) != 1 or (rows[0]['text'], rows[0]['importance']) != classification for rows in reqs)):
                continue
            sources = [tag for group in audit['projects'] if group['project'] == project
                       for key, tag in (('library', 'Evidence Library'), ('base', 'Selected Base'))
                       if any(r['text'] == wording for r in group[key])]
            if not sources or set(sources) != set(item['provenance']).intersection({'Evidence Library', 'Selected Base'}):
                continue
            after_requirement = reqs[1][0]
            controlled = (item['included'] and project in old and wording not in old[project]
                          and new[project].count(wording) == 1 and wording in after_requirement['evidence']
                          and all(old[name] == ([w for w in rows if w != wording] if name == project else rows)
                                  for name, rows in new.items()))
            matching.append({**item, 'sources': sources, 'native_delta': verdict['native_delta'] if controlled else None,
                             'before_label': reqs[0][0]['match_label'], 'after_label': after_requirement['match_label'],
                             'native_strength': after_requirement['evidence_strength'],
                             'word_delta': len(wording.split()) if controlled else None})
        return matching
    except (AttributeError, KeyError, TypeError, ValueError):
        return []


def render_controlled_trials(st, trials, rows, project):
    shown = [item for item in trials if project == 'All projects' or item['project'] == project]
    with st.expander('Offline controlled bullet trials', expanded=False):
        st.caption('Research documents are shown separately from current application generations.')
        if not shown:
            st.caption('Native bullet impact unmeasured.')
        for item in shown:
            st.write(item['wording'])
            st.caption(' · '.join([item['project'], *item['sources']]))
            st.write(f"{item['requirement']} ({item['importance'].title()})")
            st.caption(f"Weak evidence · {'shared' if item['shared'] else 'unique in the selected slate'}")
            row = next((row for row in rows if (row['project'], row['bullet']) == (item['project'], item['wording'])), {})
            tech = ', '.join(row.get('jd_wide_technology_cues', ())) or 'none recorded'
            skills = ', '.join(row.get('matched_action_families', ())) or 'testing'
            st.caption(f'Matched activity · {skills} | JD technology cues · {tech}')
            st.caption(item['reason'])
            if item['native_delta'] is None:
                st.caption('Native bullet impact unmeasured.')
            else:
                st.caption(f"Native Job Match {item['native_delta']:+g} · "
                           f"{item['before_label']} → {item['after_label']} · "
                           f"Validated strength {item['native_strength']}/5 · "
                           f"{item['word_delta']:+d} words · Both documents fit one page.")
