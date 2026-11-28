"""V3.9 read-only actual-DOCX bullet browser and scored source explanation.

Never converts a proposed B into the selected final or claims an independent
per-bullet native score. Source comparisons use frozen, read-only evidence.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

VERSION = 'phase9f-v39-final-bullet-browser-v1'


def _norm(value: Any) -> str:
    return ' '.join(str(value or '').split()).casefold()


def _rows(audit: dict) -> tuple[list[dict], str]:
    if not isinstance(audit, dict) or audit.get('verified') is not True or not audit.get('docx_sha256'):
        return [], 'A verified fitted-DOCX audit is unavailable.'
    projects = audit.get('projects')
    if not isinstance(projects, list) or not projects:
        return [], 'The fitted-DOCX audit contains no projects.'
    output = []
    names = set()
    for group in projects:
        if not isinstance(group, dict) or not isinstance(group.get('final'), list):
            return [], 'Malformed fitted-DOCX project audit.'
        title = str(group.get('project') or '')
        if not title or _norm(title) in names:
            return [], 'Ambiguous fitted-DOCX project identity.'
        names.add(_norm(title))
        seen = set()
        for bullet in group['final']:
            value = str(bullet.get('text') or '') if isinstance(bullet, dict) else ''
            key = _norm(value)
            if not key or key in seen:
                return [], 'Ambiguous fitted-DOCX bullet identity.'
            seen.add(key)
            output.append({'project': title, 'bullet': value})
    if not output:
        return [], 'The fitted-DOCX audit contains no project bullets.'
    return output, ''


def chosen_document(audit: dict, result: dict, *, repo_root: Path | None = None) -> dict:
    """Identify exact chosen bytes, failing closed on stale/mismatched challenger.

    If B is the recorded winner, independent DOCX readback MUST exactly match
    the proposed project slate. A candidate cannot be silently substituted.
    """
    initial, error = _rows(audit)
    if error:
        return {'status': 'unavailable', 'reason': error, 'bullets': []}
    if not isinstance(result, dict) or result.get('winner') != 'optimized_candidate':
        return {'status': 'verified_fitted', 'role': 'fitted', 'bullets': initial,
                'removed': [], 'docx_sha256': audit['docx_sha256'],
                'deduplication_status': 'not_applied',
                'reason': 'The existing fitted DOCX remains selected; proposed removals are not final removals.'}
    if (result.get('status') != 'verified' or
            str(result.get('generation_id') or '') != str(audit.get('generation_id') or '') or
            result.get('a_docx_sha256') != audit['docx_sha256']):
        return {'status': 'unavailable', 'reason': 'Selected challenger and fitted-DOCX receipt are incompatible.', 'bullets': []}
    candidate = Path(str(result.get('candidate_file') or ''))
    if not candidate.is_file() or candidate.suffix.lower() != '.docx':
        return {'status': 'unavailable', 'reason': 'Chosen challenger DOCX unavailable.', 'bullets': []}
    try:
        candidate = candidate.resolve(strict=True)
        if repo_root is not None:
            candidate.relative_to(Path(repo_root).resolve() / 'outputs' / 'tailored_resumes' / 'optimizations')
        digest = sha256(candidate.read_bytes()).hexdigest()
    except (OSError, ValueError):
        return {'status': 'unavailable', 'reason': 'Challenger path is not a verified owned document.', 'bullets': []}
    if digest != result.get('b_docx_sha256'):
        return {'status': 'unavailable', 'reason': 'Challenger DOCX bytes have changed.', 'bullets': []}
    proposal = result.get('proposal') or {}
    groups = proposal.get('projects')
    if not isinstance(groups, list) or len(groups) != len(audit['projects']):
        return {'status': 'unavailable', 'reason': 'Proposed project identities are missing.', 'bullets': []}
    from tailoring.phase9f_final_evidence_comparison_v2_4 import _read_exact_docx_bullets
    names = [str(group['project']) for group in audit['projects']]
    actual, problem = _read_exact_docx_bullets(candidate, names)
    if problem:
        return {'status': 'unavailable', 'reason': 'Chosen challenger project readback failed: '+problem, 'bullets': []}
    chosen = []
    for group in groups:
        title = str(group.get('project') or '')
        expected = group.get('after')
        if title not in actual or not isinstance(expected, list):
            return {'status': 'unavailable', 'reason': 'Challenger project identity mismatch.', 'bullets': []}
        if Counter(map(_norm, actual[title])) != Counter(map(_norm, expected)) or len(actual[title]) != len(expected):
            return {'status': 'unavailable', 'reason': 'Chosen DOCX bullets differ from the scored proposal.', 'bullets': []}
        chosen.extend({'project': title, 'bullet': x} for x in actual[title])
    if len(chosen) == 0:
        return {'status': 'unavailable', 'reason': 'Chosen challenger has no project bullets.', 'bullets': []}
    selected = {(_norm(x['project']), _norm(x['bullet'])) for x in chosen}
    removed = [x for x in initial if (_norm(x['project']), _norm(x['bullet'])) not in selected]
    return {'status': 'verified_challenger', 'role': 'challenger', 'bullets': chosen,
            'removed': removed, 'docx_sha256': digest,
            'deduplication_status': 'removed_in_verified_challenger' if removed else 'no_bullets_removed',
            'reason': 'The chosen challenger was independently read from its current DOCX bytes; approval and application activation remain separate.'}


def scored_wording(proposal: dict, project: str, wording: str) -> dict | None:
    receipt = proposal.get('v38_bullet_score_receipt') if isinstance(proposal, dict) else None
    if not isinstance(receipt, dict) or receipt.get('status') != 'available':
        return None
    matches = [row for row in receipt.get('bullets') or [] if isinstance(row, dict) and
               _norm(row.get('project')) == _norm(project) and _norm(row.get('wording')) == _norm(wording)]
    return matches[0] if len(matches) == 1 else None


SAME_WORK = 'Same work'
RELATED_EVIDENCE = 'Related evidence'
MANUAL_COMPARISON = 'Manual comparison'


def _pair_links(proposal: dict, project: str, wording: str) -> set[str]:
    receipt = scored_wording(proposal, project, wording)
    return set(receipt['saved_jd_ids']) if receipt else set()


def explain_pair(*, final: dict, ranked: list[dict], proposal: dict, mode: str = SAME_WORK) -> dict:
    """Explain the best eligible opposite-source peer in the frozen project."""
    from tailoring.phase9f_comparison_pair_guard_v37 import classify_comparison_pair, classify_related_pair
    from tailoring.phase9f_same_work_selection_v37 import _confident_same_work

    project, wording = str(final['project']), str(final['bullet'])
    pool = [row for row in ranked if isinstance(row, dict) and
            _norm(row.get('project')) == _norm(project)]
    exact = [row for row in pool if _norm(row.get('bullet')) == _norm(wording)]
    neutral = {'source': 'unknown', 'base': None, 'library': None, 'overlap': False}
    if len(exact) != 1:
        return {**neutral, 'reason': 'This final wording has no unique attribution in the frozen sources.'}
    current = exact[0]
    origins = set(current.get('sources') or [])
    own_base = 'Selected Base' in origins
    own_library = 'Evidence Library' in origins
    if own_base and own_library:
        return {**neutral, 'source': 'shared', 'base': current, 'library': current,
                'reason': 'Both frozen sources contain this exact wording.'}
    if not own_base and not own_library:
        return {**neutral, 'reason': 'This final wording was found only in the DOCX. Its source is unknown.'}

    opposite = 'Evidence Library' if own_base else 'Selected Base'
    alternatives = [row for row in pool if row is not current and opposite in (row.get('sources') or [])]
    current_ids = _pair_links(proposal, project, wording)
    eligible = []
    for other in alternatives:
        peer_word = other['bullet']
        strict = _confident_same_work(wording, peer_word)
        if mode == SAME_WORK and not strict:
            continue
        base, library = (current, other) if own_base else (other, current)
        classifier = classify_related_pair if mode == SAME_WORK else classify_comparison_pair
        relation = classifier(base, library)
        if relation['eligible']:
            peer_score = scored_wording(proposal, project, peer_word)
            shared = len(current_ids & _pair_links(proposal, project, peer_word))
            specificity = len(relation.get('shared_activities') or ())
            points = float(peer_score['standalone_weighted_points']) if peer_score else -1.0
            order = (-int(strict), -shared, -specificity, -points, peer_word)
            eligible.append((order, other, relation, strict))

    compare = f'{len(eligible)} eligible of {len(alternatives)} opposite-source alternatives.'
    if eligible:
        _, peer, relation, strict = min(eligible, key=lambda candidate: candidate[0])
        summary = 'Overlapping evidence.' if strict else 'Complementary evidence.'
        reason = f"{summary} {relation['reason']} {compare}"
    else:
        peer, strict = None, False
        reason = f'No counterpart met the {mode.lower()} criteria. {compare}'
    return {'source': 'base' if own_base else 'library', 'overlap': strict,
            'base': current if own_base else peer, 'library': current if own_library else peer,
            'reason': reason}


def _manual_comparison(st: Any, pool: list[dict], project_key: str) -> dict:
    from tailoring.phase9f_comparison_pair_guard_v37 import classify_comparison_pair
    from tailoring.phase9f_same_work_selection_v37 import _confident_same_work

    chosen = {}
    for key, label, source in (
        ('base', 'Frozen Base Resume wording', 'Selected Base'),
        ('library', 'Frozen Evidence Library wording', 'Evidence Library'),
    ):
        wordings = {row['bullet']: row for row in pool if source in (row.get('sources') or [])}
        wording = st.selectbox(label, list(wordings), key=project_key + '_manual_' + key) if wordings else None
        chosen[key] = wordings.get(wording)
    base, library = chosen['base'], chosen['library']
    if base is None or library is None:
        reason = 'This project needs a frozen wording from each source for a manual comparison.'
    elif _norm(base['bullet']) == _norm(library['bullet']):
        reason = 'Both frozen sources contain this exact wording.'
    else:
        related = classify_comparison_pair(base, library)
        if related['eligible']:
            overlap = _confident_same_work(base['bullet'], library['bullet'])
            reason = ('Overlapping evidence. ' if overlap else 'Complementary evidence. ') + related['reason']
        else:
            reason = 'Different details from the same project. The wordings have no established overlap.'
    return {**chosen, 'source': 'manual', 'reason': reason}


def _frozen_comparison_rows(audit: dict, ranked: list[dict], proposal: dict, catalog: dict) -> list[dict]:
    from tailoring.phase9f_bullet_inspector import inspector_rows

    rows, _ = inspector_rows({}, audit)
    details = {}
    for row in ranked:
        key = (_norm(row['project']), _norm(row['bullet']))
        details.setdefault(key, []).append(row)
    for row in rows:
        project, bullet = row['project'], row['bullet']
        matches = details.get((_norm(project), _norm(bullet)), [])
        compatible = {link['id']: link for link in matches[0].get('jd_links', [])} if len(matches) == 1 else {}
        row['jd_links'] = [compatible.get(rid) or {'id': rid, **catalog.get(rid, {})}
                           for rid in sorted(_pair_links(proposal, project, bullet))]
    return rows


def _show_shared_saved_links(st: Any, relation: dict, proposal: dict, project: str, catalog: dict) -> None:
    if relation['base'] is None or relation['library'] is None:
        return
    receipts = [scored_wording(proposal, project, relation[key]['bullet']) for key in ('base', 'library')]
    if any(receipt is None for receipt in receipts):
        st.caption('Scores for both wordings are needed to compare shared and unique saved links.')
        return
    base_ids, library_ids = (set(receipt['saved_jd_ids']) for receipt in receipts)
    for label, ids in (('Shared', base_ids & library_ids), ('Base only', base_ids - library_ids),
                       ('Library only', library_ids - base_ids)):
        requirements = ', '.join(str(catalog.get(rid, {}).get('text') or rid) for rid in sorted(ids))
        st.caption(f"{label} saved JD links · {requirements or 'None'}")

    from tailoring.phase6d_ranking_adapter import match_requirement_to_candidate

    for rid in sorted(base_ids | library_ids):
        entry = catalog.get(rid, {})
        text = entry.get('text')
        if not text:
            continue
        requirement = {'text': text, 'atomic_focus': text, 'importance': entry.get('importance') or 'required'}
        for key, label, ids in (('base', 'Base Resume', base_ids), ('library', 'Evidence Library', library_ids)):
            match = match_requirement_to_candidate(requirement=requirement,
                                                   candidate_evidence_text=relation[key]['bullet'])
            missing = match.get('missing_testing_modalities') or []
            if not missing or not match.get('qa_testing_policy_version'):
                continue
            if (rid in ids) != (match.get('label') != 'none'):
                continue
            missing = ', '.join('user acceptance' if item == 'acceptance' else item for item in missing)
            st.caption(f'{label} wording does not establish these requested test types · {missing}.')


def _show_panel(st: Any, *, title: str, row: dict | None, proposal: dict,
                project: str, catalog: dict, optimizer_proposal: dict | None = None,
                final_wordings: set[str] | None = None) -> None:
    # Keep the V3.9 selected-final-only model; source panels are read-only.
    with st.container(border=True):
        st.markdown('##### '+title)
        if row is None:
            st.caption('No verified related wording from this source.')
            return
        wording = str(row['bullet'])
        st.write(wording)
        if final_wordings is not None:
            st.caption('Exact wording in the selected DOCX' if _norm(wording) in final_wordings
                       else 'Exact wording absent from the selected DOCX')
        scored = scored_wording(proposal, project, wording)
        if scored is not None:
            st.metric('Weighted JD relevance (saved-link points)',
                      f"{scored['standalone_weighted_points']:.3f}")
            st.caption(f"{len(scored['saved_jd_ids'])} distinct saved JD requirements. Not a native per-bullet Job Match score.")
            if float(scored['standalone_weighted_points']) == 0.0:
                st.caption('0.000 means no saved linked-JD points for this wording, not a judgement that the work is worthless.')
            marginal = scored.get('marginal_in_proposal_points')
            # Proposal marginal remains separate, and only if the caller has
            # already verified its scope and its standalone score agrees.
            old = scored_wording(optimizer_proposal, project, wording) if optimizer_proposal else None
            if (marginal is None and old is not None
                    and old.get('standalone_weighted_points') == scored.get('standalone_weighted_points')
                    and sorted(old.get('saved_jd_ids') or []) == sorted(scored['saved_jd_ids'])):
                marginal = old.get('marginal_in_proposal_points')
            if marginal is not None:
                st.caption(f"Marginal points in proposed slate: {marginal:.3f} (not the final-document impact).")
        else:
            receipt = (proposal or {}).get('v38_bullet_score_receipt') or {}
            if receipt.get('status') != 'available':
                reason = str(receipt.get('reason') or 'No valid weighted JD receipt for this generation.')
            else:
                matching_project = [r for r in receipt.get('bullets') or []
                                    if isinstance(r, dict) and _norm(r.get('project')) == _norm(project)]
                exact = [r for r in matching_project if _norm(r.get('wording')) == _norm(wording)]
                if not matching_project:
                    reason = 'No score rows bound to this exact project title.'
                elif not exact:
                    reason = 'This exact wording was not included in the saved scored source pool.'
                else:
                    reason = 'Multiple score rows for this exact wording; score withheld.'
            st.caption('Weighted JD score unavailable for this exact wording or generation.')
            st.caption('Reason: ' + reason)
        from tailoring.phase9f_wording_explanation_ui import wording_facts
        facts = wording_facts(row, catalog)
        st.caption(str(facts['words'])+' words · source: '+', '.join(row.get('sources') or []))
        st.markdown('**:green[Strengths]**')
        for strength in facts.get('strengths') or []:
            st.write('＋ '+strength)
        st.markdown('**:red[Weaknesses / limits]**')
        for limit in facts.get('limits') or ['This wording alone does not verify a native score gain.']:
            st.write('− '+limit)


def _verified_prefit_pair(*, selected: dict, chosen: dict, receipt: dict | None) -> dict | None:
    """Explain a saved pre-fit decision only if the exact final DOCX confirms removal.

    This is a deterministic selection receipt, NOT a controlled native bullet trial.
    """
    if not isinstance(receipt, dict) or receipt.get('version') != 'phase9f-v39-pre-fit-dedupe-v1' or receipt.get('status') != 'removed_before_fit':
        return None
    if chosen.get('status') != 'verified_fitted':
        return None
    project = _norm(selected.get('project'))
    final = {_norm(x.get('bullet')) for x in chosen.get('bullets') or [] if _norm(x.get('project')) == project}
    if _norm(selected.get('bullet')) not in final:
        return None
    matches = [row for row in receipt.get('removals') or [] if isinstance(row, dict)
               and _norm(row.get('project')) == project
               and _norm(row.get('retained')) == _norm(selected.get('bullet'))
               and _norm(row.get('removed')) not in final
               and row.get('recorded_at_stage') == 'pre_fitting'
               and isinstance(row.get('removed_saved_evidence_points'), (int,float))
               and isinstance(row.get('retained_saved_evidence_points'), (int,float))]
    return matches[0] if len(matches) == 1 else None


def _render_detailed_comparison(st: Any, *, base: dict | None, library: dict | None, catalog: dict) -> None:
    """Reuse the existing wording estimator; present it without creating source controls."""
    from tailoring.phase9f_wording_explanation_ui import wording_facts, _comparison_table
    from tailoring.bullet_choice_estimated import estimate_pair
    st.markdown('''<style>
    .bullet-fit-table {width:100%; overflow-x:auto; border:1px solid #56627366; border-radius:8px; margin:0.25rem 0 0.9rem}
    .bullet-fit-table table {width:100%; table-layout:fixed; border-collapse:collapse; font-size:14px}
    .bullet-fit-table th,.bullet-fit-table td {padding:12px; vertical-align:top; text-align:left; overflow-wrap:anywhere; border-bottom:1px solid #56627355}
    @media(max-width:800px) {.bullet-fit-table th,.bullet-fit-table td {padding:7px; font-size:12px}}
    </style>''', unsafe_allow_html=True)
    rows = [wording_facts(r,catalog) if r is not None else None for r in (base,library)]
    st.markdown('##### JD requirements & keyword evidence')
    st.caption('Estimated wording interpretation, not native match credit. Exact saved JD requirement identities and importance are preserved.')
    by_id = [{item['id']:item for item in facts.get('requirements', [])} if facts else {} for facts in rows]
    ids = list(dict.fromkeys([item['id'] for facts in rows if facts for item in facts.get('requirements', [])]))
    table=[]
    for rid in ids:
        a,b=(d.get(rid) for d in by_id)
        if not any(item and item.get('relevant') for item in (a,b)):
            continue
        item=a or b
        def describe(q):
            if not q:return 'No established related wording'
            quote='“'+'”, “'.join(q['phrases'])+'”. ' if q.get('phrases') else ''
            return q.get('kind','')+' · '+quote+q.get('reason','')
        table.append([str(item.get('importance','')).replace('_',' ').title()+' · '+str(item.get('text','')),
                      describe(a),describe(b)])
    if table:
        _comparison_table(st,['Current JD requirement','Base Resume','Evidence Library'],table)
    else:
        st.caption('No compatible requirement-level wording relationship is recorded.')
    st.markdown('##### Keyword comparison at a glance')
    _comparison_table(st,['Category','Base Resume','Evidence Library'],[
        ['Explicit technologies',*[((', '.join(f['technologies']) or 'None named') if f else 'Unavailable') for f in rows]],
        ['Related activity phrases',*[(('; '.join(x for phrases in f['phrases'].values() for x in phrases) or 'None established') if f else 'Unavailable') for f in rows]],
        ['Word count',*[(str(f['words']) if f else 'Unavailable') for f in rows]],
    ])
    st.markdown('##### JD relevance and wording trade-offs (estimated)')
    if base is None or library is None or _norm(base['bullet']) == _norm(library['bullet']):
        st.caption('No distinct verified related pair; no source winner inferred.')
        return
    estimate=estimate_pair(base['bullet'],library['bullet'],list(catalog.values()))
    st.write('Estimated wording relevance: '+str(estimate.get('outcome','unavailable'))+'. '+str(estimate.get('reason','')))
    dimensions=[]
    for key,label in [('features','Specific implementation detail'),('team','Team contribution'),('release','Product delivery')]:
        a,b=bool(rows[0]['phrases'][key]),bool(rows[1]['phrases'][key])
        dimensions.append([label,'Both explicitly describe this context' if a and b else
            'Base explicitly describes this context' if a else 'Library explicitly describes this context' if b else 'Not stated in either wording'])
    delta=rows[1]['words']-rows[0]['words']
    dimensions.extend([
      ['Word efficiency',f"Base {rows[0]['words']} vs Library {rows[1]['words']} words ({abs(delta)}-word difference). Physical page-space benefit is unmeasured."],
      ['Other retained bullets','Other bullets may already cover the same JD requirements; source scores are not additive native Job Match credit.'],
      ['Broader JD corpus','Not measured; no universal bullet-quality rating is inferred.'],
    ])
    _comparison_table(st,['Dimension','Estimated trade-off'],dimensions)
    with st.expander('Supporting evidence & match details', expanded=False):
        for title,row in [('Base Resume',base),('Evidence Library',library)]:
            st.markdown('**'+title+' · exact saved JD links**')
            for link in row.get('jd_links') or []:
                st.write(str(link.get('importance') or '')+' · '+str(link.get('text') or ''))
                st.caption(str(link.get('status') or 'Saved JD link; not independent native credit'))
            if not row.get('jd_links'):
                st.caption('No compatible saved JD links for this wording.')


def render_verified_final_bullets(st: Any, *, audit: dict, result: dict, proposal: dict,
                                  ranked: list[dict], catalog: dict,
                                  application_id: int, context: str,
                                  repo_root: Path | None = None,
                                  prefit_receipt: dict | None = None,
                                  independent_scores: dict | None = None) -> bool:
    """Project selectors list ONLY the bytes of the verified chosen DOCX."""
    chosen = chosen_document(audit, result, repo_root=repo_root)
    if chosen['status'] == 'unavailable':
        st.warning('Final bullet inspection withheld: '+chosen['reason'])
        return False
    st.markdown('### Bullet Choices & Base vs Library')
    score_context = proposal
    if independent_scores is not None:
        # Never substitute stale proposal scores when the current scope fails.
        if independent_scores.get('status') == 'available':
            scope = independent_scores.get('scope') or {}
            if (not isinstance(scope, dict) or not scope.get('generation_id')
                    or not scope.get('a_docx_sha256') or not scope.get('raw_jd_sha256')
                    or scope.get('generation_id') != audit.get('generation_id')
                    or scope.get('a_docx_sha256') != audit.get('docx_sha256')):
                independent_scores = {'status': 'unavailable', 'reason': 'Independent score receipt does not match the fitted generation.'}
        score_context = {'v38_bullet_score_receipt': independent_scores}
        if independent_scores.get('status') == 'available':
            st.caption('JD points: independent saved-link coverage from this fitted generation and exact JD. '
                       'No optimizer challenger is required; these are not native Job Match points.')
        else:
            st.caption('JD points unavailable: '+str(independent_scores.get('reason') or 'Independent score inputs unavailable.'))
    if chosen['role'] == 'fitted':
        valid_removals = [r for r in (prefit_receipt or {}).get('removals', []) if isinstance(r, dict)] if isinstance(prefit_receipt, dict) and prefit_receipt.get('version') == 'phase9f-v39-pre-fit-dedupe-v1' else []
        if valid_removals:
            st.info('This fitted DOCX already underwent V3.9 pre-fit deduplication. Best-of retained the fitted document; its separate tested alternative was not applied.')
            for item in valid_removals:
                project_final = {_norm(x.get('bullet')) for x in chosen.get('bullets') or [] if _norm(x.get('project')) == _norm(item.get('project'))}
                if _norm(item.get('removed')) not in project_final:
                    st.caption('Pre-fit removal verified absent in DOCX · '+str(item.get('project'))+' · '+str(item.get('removed')))
                else:
                    st.warning('Pre-fit removal still appears in DOCX · '+str(item.get('project')))
        else:
            st.warning('The existing fitted document is still selected. A tested Best-of alternative is not an applied removal.')
        proposal_removed = [row for row in ranked if row.get('in_actual_a') is True and row.get('in_proposed_b') is False]
        if result.get('status') == 'verified' and proposal and proposal_removed:
            st.caption('Excluded only in the tested alternative (NOT removed from your fitted document):')
            for row in proposal_removed:
                st.write('• '+str(row['project'])+' — '+str(row['bullet']))
    else:
        st.success(f"The selected verified challenger contains {len(chosen['bullets'])} project bullets.")
        st.caption('This is the checked challenger DOCX, not an automatically approved or activated historical application résumé.')
        if chosen['removed']:
            st.markdown('**Removed from the selected verified challenger**')
            for removed in chosen['removed']:
                st.write('• '+removed['project']+' — '+removed['bullet'])
        else:
            st.caption('No exact project bullet was removed compared with the fitted document.')
    st.caption('Comparison is read-only. Same work looks for overlapping accomplishments. Related evidence includes complementary work in the same project. Manual comparison lets you choose exact frozen wordings from both sources.')
    frozen_rows = _frozen_comparison_rows(audit, ranked, score_context, catalog)
    names = list(dict.fromkeys(x['project'] for x in chosen['bullets']))
    token = f'v39_final_{int(application_id)}_{context}'
    from tailoring.phase9f_multi_project_evidence_v36 import project_checkboxes
    # Scope UI preferences to the chosen document, not an index or another generation.
    document_key = f"{audit.get('generation_id', '')}:{chosen['docx_sha256']}"
    token += '_'+sha256(document_key.encode()).hexdigest()[:16]
    with st.container(border=True):
        st.markdown('#### Projects to inspect')
        st.caption('Choose any number. Each checked project remains visible below.')
        selected_projects = project_checkboxes(st, names, key=token, default=names[:1], actions=True)
        st.caption(f'{len(selected_projects)} of {len(names)} selected')
    if not selected_projects:
        st.info('Select one or more projects to inspect.')
    for project in selected_projects:
        st.markdown('#### '+project)
        project_key = token+'_'+sha256(project.encode('utf-8')).hexdigest()[:16]
        options = [x for x in chosen['bullets'] if x['project'] == project]
        mode = st.selectbox('Comparison mode', (SAME_WORK, RELATED_EVIDENCE, MANUAL_COMPARISON),
                            key=project_key+'_mode')
        final_wordings = {_norm(row['bullet']) for row in options}
        if mode == MANUAL_COMPARISON:
            pool = [row for row in frozen_rows if _norm(row['project']) == _norm(project)]
            relation = _manual_comparison(st, pool, project_key)
            st.caption(relation['reason'])
            base, lib = st.columns(2)
            for column, label, key in ((base, 'Base Resume', 'base'), (lib, 'Evidence Library', 'library')):
                with column:
                    _show_panel(st, title=label, row=relation[key], proposal=score_context,
                                project=project, catalog=catalog, final_wordings=final_wordings)
            _show_shared_saved_links(st, relation, score_context, project, catalog)
            _render_detailed_comparison(st, base=relation['base'], library=relation['library'], catalog=catalog)
            continue
        # Freeze the display labels now. Streamlit may call this formatter
        # again after the loop has moved on to another project.
        labels = {}
        for option in options:
            word = option['bullet']
            score = scored_wording(score_context, project, word)
            points = f" · JD {score['standalone_weighted_points']:.3f} pts" if score is not None else ' · JD points unavailable'
            labels[word] = word + points
        # Exact wording identity survives hiding/reopening a checked project.
        widget = project_key+'_final'
        remembered = widget+'_remembered'
        wordings = [x['bullet'] for x in options]
        if st.session_state.get(widget) not in wordings:
            previous = st.session_state.get(remembered)
            st.session_state[widget] = previous if previous in wordings else wordings[0]
        selected_word = st.radio('Select one final résumé bullet', wordings,
                                 format_func=labels.__getitem__, key=widget)
        st.session_state[remembered] = selected_word
        selected = options[wordings.index(selected_word)]
        relation = explain_pair(final=selected, ranked=frozen_rows, proposal=score_context, mode=mode)
        st.caption(relation['reason'])
        if relation['base'] is None or relation['library'] is None:
            project_pool = [row for row in frozen_rows if _norm(row['project']) == _norm(project)]
            available_sources = {source for row in project_pool for source in row.get('sources', [])}
            if {'Selected Base', 'Evidence Library'} <= available_sources:
                mode_key = project_key+'_mode'
                st.button('Switch to manual comparison', key=project_key+'_switch_manual',
                          on_click=st.session_state.__setitem__, args=(mode_key, MANUAL_COMPARISON))
        base, lib = st.columns(2)
        with base:
            _show_panel(st, title='Base Resume', row=relation['base'], proposal=score_context,
                        project=project, catalog=catalog, optimizer_proposal=proposal, final_wordings=final_wordings)
        with lib:
            _show_panel(st, title='Evidence Library', row=relation['library'], proposal=score_context,
                        project=project, catalog=catalog, optimizer_proposal=proposal, final_wordings=final_wordings)
        selected_prefit=_verified_prefit_pair(selected=selected,chosen=chosen,receipt=prefit_receipt)
        st.markdown('**Automatic selection outcome**')
        st.caption('Selected wording: '+selected['bullet'])
        if selected_prefit is not None:
            base_pts=float(selected_prefit['removed_saved_evidence_points']) if 'Base Resume' in selected_prefit.get('removed_sources',[]) else float(selected_prefit['retained_saved_evidence_points'])
            library_pts=float(selected_prefit['retained_saved_evidence_points']) if 'Evidence Library' in selected_prefit.get('retained_sources',[]) else float(selected_prefit['removed_saved_evidence_points'])
            st.success('Verified pre-fit deduplication: Base '+f'{base_pts:.3f}'+' vs Library '+f'{library_pts:.3f}'+' saved pre-fit evidence points. '+str(selected_prefit.get('selection_reason') or 'Saved selection reason unavailable')+'.')
            st.caption('Removed from actual fitted DOCX: '+str(selected_prefit['removed']))
            st.caption('Source choice followed the recorded deterministic rule; this is NOT proof of a higher native per-bullet score.')
        counterpart = relation['library'] if relation['source'] == 'base' else relation['base'] if relation['source'] == 'library' else None
        if chosen['role'] == 'fitted':
            if selected_prefit is not None:
                st.caption('This wording was retained by V3.9 pre-fit deduplication and appears in the verified fitted DOCX. Best-of did not replace that fitted document.')
            else:
                st.caption('This wording appears in the fitted DOCX. Separate Best-of trials do not alter these document bytes.')
        else:
            st.caption('This exact wording appears in the independently verified chosen challenger DOCX. The whole-document native comparison selected that challenger; no individual native bullet score is claimed.')
        if counterpart is not None:
            other_wording = str(counterpart['bullet'])
            both_present = any(_norm(x['project']) == _norm(project) and
                               _norm(x['bullet']) == _norm(other_wording) for x in chosen['bullets'])
            if both_present and relation.get('overlap'):
                st.warning('Both overlapping wordings appear in the selected DOCX.')
            elif both_present:
                st.caption('Both related wordings appear in the selected DOCX.')
            elif chosen['role'] == 'challenger':
                st.caption('Related wording excluded from the verified selected challenger: '+other_wording)
                st.caption('The optimizer selected the complete résumé, not a causal per-bullet score winner. The source receipts provide the comparative JD evidence below.')
            elif selected_prefit is not None and _norm(other_wording) == _norm(selected_prefit['removed']):
                st.caption('Related Base/Library wording was removed before fitting under the recorded deterministic rule.')
            else:
                st.caption('The related wording is not in the fitted DOCX; no exact pre-fit rejection receipt is bound to this selected bullet.')

        _show_shared_saved_links(st, relation, score_context, project, catalog)
        _render_detailed_comparison(st,base=relation['base'],library=relation['library'],catalog=catalog)
    return True
