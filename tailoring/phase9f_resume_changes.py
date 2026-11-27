"""Read-only changes between the exact Selected Base and fitted DOCX."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json

from tailoring.phase9f_final_evidence_comparison_v2_4 import _read_exact_docx_bullets
from tailoring.phase9f_v39_final_bullet_review import scored_wording
from tailoring.project_title_resolution_v1 import mutually_resolve_project


def read_selected_base_artifact(application_id, generation_id, execution, decision):
    """Resolve the immutable bytes through the existing Phase 9F execution binding."""
    from database.phase9f_tailoring_execution_manager import (
        _resolve_prepared_source_artifact, get_phase9f_application_confirmation,
        get_phase9f_tailoring_execution,
    )

    owner = get_phase9f_tailoring_execution(application_id, generation_id=generation_id)
    if (not owner or not owner.get('execution_fingerprint')
            or owner['execution_fingerprint'] != execution.get('execution_fingerprint')):
        raise ValueError('The fitted generation does not belong to this frozen execution.')
    expected = owner.get('source_artifact')
    if not expected or not expected.get('sha256'):
        raise ValueError('The generation has no frozen Base DOCX identity.')
    confirmation = get_phase9f_application_confirmation(application_id, confirmation_id=owner['confirmation_id'])
    if not confirmation:
        raise ValueError('The frozen Base confirmation is unavailable.')
    return _resolve_prepared_source_artifact(
        decision=decision, confirmation=confirmation, expected_identity=expected,
    )


def read_base_projects(artifact, decision):
    from tailoring.project_section_tailor import _find_resume_project_lists, _resume_project_to_candidate

    snapshot = decision['starting_snapshot']['resume_profile_snapshot']
    records = {}
    for raw in _find_resume_project_lists(snapshot):
        candidate = _resume_project_to_candidate(raw)
        if candidate:
            title = candidate['display_title']
            identity = raw.get('project_id')
            if title in records and identity != records[title]:
                raise ValueError('The frozen Base has competing project identities.')
            records[title] = identity
    bullets, error = _read_exact_docx_bullets(BytesIO(artifact['artifact_bytes']), list(records),
                                            strict_layout=True)
    if error:
        raise ValueError(error)
    return [{'project': title, 'project_id': records[title], 'bullets': texts}
            for title, texts in bullets.items()]


def build_resume_changes(base, audit, projects, independent_scores):
    """Join exact counts, source membership and saved fit events."""
    if not audit.get('verified') or not audit.get('docx_sha256'):
        raise ValueError('Verified fitted DOCX readback is unavailable.')
    final = [row for row in audit['projects'] if row['present_in_docx']]
    ranks = [row for row in projects.get('candidate_project_ranking', []) if isinstance(row, dict)]
    score_context = {'v38_bullet_score_receipt': independent_scores}
    changes = []
    paired = set()
    for previous in base:
        current, method = mutually_resolve_project(previous, base, final)
        if current is None and method != 'no_title_match':
            raise ValueError('A Base project cannot be matched unambiguously to the fitted DOCX.')
        if current is not None:
            paired.add(current['project'])
        changes.append((previous, current))
    changes.extend((None, current) for current in final if current['project'] not in paired)

    result = []
    for original, fitted in changes:
        name = (fitted or original)['project']
        audited = fitted or next((row for row in audit['projects'] if row['project'] == name), {})
        rank, _ = mutually_resolve_project(fitted or original, final if fitted else base, ranks)
        rank = rank or {}
        before = Counter(original['bullets'] if original else [])
        after = Counter(row['text'] for row in fitted['final']) if fitted else Counter()
        library = {row['text'] for row in audited.get('library', [])}
        wording_changes = []
        for label, counts in (('Retained wording', before & after),
                              ('Original wording absent', before - after),
                              ('Added wording', after - before)):
            for text, count in counts.items():
                status = label
                source = []
                if text in before:
                    source.append('Selected Base')
                if text in library:
                    source.append('Evidence Library')
                    if label == 'Added wording':
                        status = 'Added Library wording'
                lineage = [event for event in audited.get('changes', [])
                           if event.get('text') == text and event.get('source_bullets')]
                if label == 'Added wording' and len(lineage) == 1:
                    status = 'Fused wording'
                score = scored_wording(score_context, name, text)
                wording_changes.append({
                    'wording': text, 'count': count, 'status': status,
                    'sources': source, 'lineage': lineage[0] if len(lineage) == 1 else None,
                    'saved_link_points': score['standalone_weighted_points'] if score else None,
                    'saved_jd_ids': score['saved_jd_ids'] if score else None,
                })
        result.append({
            'project': name, 'base_project': original['project'] if original else None,
            'status': 'Retained' if original and fitted else 'Added' if fitted else 'Removed',
            'base_count': before.total(), 'final_count': after.total(),
            'sources': [source for source, present in (
                ('Selected Base', bool(original)), ('Evidence Library', bool(library)),
                ('Fitted DOCX', bool(fitted)),
            ) if present],
            'rank': rank.get('selection_rank', audited.get('rank')),
            'recommendation': rank.get('recommendation'), 'reason': rank.get('reason'),
            'bullets': wording_changes,
        })
    return result


def render_resume_changes(st, *, application_id, generation_id, projects, fit, audit, candidates,
                          execution, decision, baseline_report, raw_jd_text, native_score, optimizer_context=None):
    from tailoring.phase9f_independent_bullet_scores_v312b214b import build_independent_bullet_scores
    from tailoring.phase9f_v365_jd_evidence import requirement_catalog

    if not execution or not decision or fit.get('generation_id') != generation_id:
        st.info('The frozen Base and fitted generation could not be joined.')
        return
    try:
        artifact = read_selected_base_artifact(application_id, generation_id, execution, decision)
        fitted_base = (fit.get('fitting_input_snapshot') or {}).get('source_artifact') or {}
        if fitted_base and fitted_base.get('sha256') != artifact['sha256']:
            raise ValueError('The fitted input and frozen Base DOCX hashes differ.')
        base = read_base_projects(artifact, decision)
        scores = build_independent_bullet_scores(audit, projects, baseline_report, raw_jd_text)
        changes = build_resume_changes(base, audit, projects, scores)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        st.info('Résumé change counts are unavailable. ' + str(exc))
        return

    current = native_score or {}
    comparable = (current.get('application_id') == application_id and current.get('generation_id') == generation_id
            and current.get('decision_fingerprint') == decision.get('decision_fingerprint')
            and current.get('jd_sha256') == sha256(raw_jd_text.encode()).hexdigest()
            and current.get('base_docx_sha256') == artifact['sha256']
            and current.get('final_docx_sha256') == audit['docx_sha256'])
    if comparable:
        key = 'deterministic_alignment_score'
        st.caption(f"Job Match · Base {current['base'][key]} → Fitted {current['final'][key]}")
    else:
        st.caption('A comparable Base and fitted Job Match receipt is unavailable.')
    before = sum(row['status'] != 'Added' for row in changes)
    after = sum(row['status'] != 'Removed' for row in changes)
    before_bullets = sum(row['base_count'] for row in changes)
    after_bullets = sum(row['final_count'] for row in changes)
    st.write(f'Projects {before} → {after} · Project bullets {before_bullets} → {after_bullets}')
    bullets = Counter()
    for row in changes:
        for bullet in row['bullets']:
            bullets[bullet['status']] += bullet['count']
    st.caption(' · '.join(f'{label} {count}' for label, count in sorted(bullets.items())))

    prefix = f"phase9f_resume_changes_{application_id}_{generation_id}_{audit['docx_sha256'][:16]}"
    project = st.selectbox('Filter projects', [row['project'] for row in changes],
                           index=None, placeholder='All projects', key=prefix+'_project')
    types = sorted(set(bullets) | {row['status'] for row in changes})
    change_types = st.multiselect('Filter changes', types, key=prefix+'_type')
    catalog = requirement_catalog(baseline_report, projects)
    for row in changes:
        if project and row['project'] != project:
            continue
        visible = [item for item in row['bullets']
                   if not change_types or row['status'] in change_types or item['status'] in change_types]
        if change_types and row['status'] not in change_types and not visible:
            continue
        with st.expander(f"{row['project']} · {row['status']} · {row['base_count']} → {row['final_count']} bullets"):
            metadata = [', '.join(row['sources'])]
            if row['rank'] is not None:
                metadata.append('Saved rank '+str(row['rank']))
            if row['recommendation']:
                metadata.append(str(row['recommendation']))
            st.caption(' · '.join(metadata))
            if row['reason']:
                st.write(row['reason'])
            for item in visible:
                count = f" ×{item['count']}" if item['count'] > 1 else ''
                st.markdown(f"**{item['status']}{count}**")
                st.write(item['wording'])
                points = item['saved_link_points']
                details = list(item['sources'])
                details.append(f'{points:.3f} saved-link points' if points is not None else 'Saved-link points unavailable')
                if item['saved_jd_ids']:
                    details.extend(catalog.get(rid, {}).get('text') or rid for rid in item['saved_jd_ids'])
                st.caption(' · '.join(details))
                if item['lineage']:
                    st.caption('Recorded source wordings')
                    for original in item['lineage']['source_bullets']:
                        st.write(original)


    from tailoring.phase9f_optimizer_diagnostics_v312b214b4 import build_report

    context = optimizer_context or {}
    report = build_report(application_id=application_id, generation_id=generation_id,
                          projects=projects, fit=fit, audit=audit, baseline_report=baseline_report,
                          raw_jd_text=raw_jd_text, candidate_pool=candidates, independent_scores=scores,
                          result=context.get('result'), optimizer_scope=context.get('scope'))
    report['resume_changes'] = changes
    trace = report['decision_trace']
    trace['whole_document'].append({
        'stage': 'Fitted generation approval',
        'certainty': 'Recorded' if comparable else 'Unavailable',
        'details': ('Approved' if current.get('generation_status') == 'approved' else 'Draft') if comparable
                   else 'No matching current approval receipt is available in this view.',
    })
    with st.expander('Detailed selection and fitting trace'):
        for stage in trace['whole_document']:
            st.caption(stage['stage'] + ' · ' + stage['certainty'])
            st.write(stage['details'])
        wordings = [item for item in trace['wordings'] if project is None or item['project'] == project]
        if wordings:
            index = st.selectbox('Inspect a wording', range(len(wordings)), key=prefix + '_trace_wording',
                                 format_func=lambda i: wordings[i]['project'] + ' · ' + wordings[i]['wording'])
            for stage in wordings[index]['stages']:
                st.caption(stage['stage'] + ' · ' + stage['certainty'])
                st.write(stage['details'])
        else:
            st.caption('No saved wordings in the selected project trace.')
        st.download_button('Download résumé decision trace (JSON)',
                           data=json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8'),
                           file_name=f'phase9f_app_{application_id}_{generation_id[:8]}_resume_changes.json',
                           mime='application/json', key=prefix+'_download', on_click='ignore')
