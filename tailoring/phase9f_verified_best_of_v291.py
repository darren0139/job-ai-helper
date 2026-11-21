"""V2.9.1 bounded, document-grounded best-of: existing fit vs real joint-slate candidate.

This never installs or auto-approves a generation. Actual 1-page DOCX and native
Phase 8 rescoring are mandatory. Immutable old generation remains the fallback.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
import math

VERSION = 'phase9f-verified-best-of-v2.9.1'
HARD = {'required', 'core', 'deal_breaker'}
RANK = {'none': 0, 'weak': 1, 'transferable': 2, 'direct': 3}


def _hold(reason: str, fallback: str = 'existing_final') -> dict[str, Any]:
    return {'status': 'withheld', 'winner': fallback, 'reason': reason,
            'candidate_approved': False, 'version': VERSION}


def _score(result: Any, *, expected_sha: str) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(result, dict) or result.get('comparison_valid') is not True or result.get('fit_one_page') is not True:
        return None, 'Native Phase 8 comparison or one-page verification failed.'
    doc = result.get('document_analysis')
    if not isinstance(doc, dict) or str(doc.get('final_document_sha256') or '') != expected_sha or not isinstance(doc.get('initial'), dict) or not isinstance(doc.get('final'), dict):
        return None, 'Scored final-document digest/authority does not match the actual candidate DOCX.'
    ab = result.get('job_match_ab')
    if not isinstance(ab, dict) or ab.get('comparable') is not True:
        return None, 'Initial-vs-final JD/scorer identity is not comparable.'
    selected = result.get('selected_base_analysis')
    if isinstance(selected, dict) and selected.get('same_as_initial') is not True:
        baseab = result.get('selected_base_job_match_ab')
        if not isinstance(baseab, dict) or baseab.get('comparable') is not True:
            return None, 'Selected Base-vs-final JD/scorer identity is not comparable.'
    after = result.get('after_stable_analysis')
    if not isinstance(after, dict):
        return None, 'Native final scoring receipt is absent.'
    version = str(after.get('scoring_version') or '')
    value = after.get('deterministic_alignment_score')
    if not version or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= float(value) <= 100:
        return None, 'Missing/invalid score or scorer version.'
    rows = after.get('canonical_requirements')
    if not isinstance(rows, list) or not rows:
        return None, 'Native final canonical requirements missing.'
    mapped = {}
    for row in rows:
        if not isinstance(row, dict):
            return None, 'Malformed canonical requirement.'
        rid = str(row.get('requirement_id') or '')
        match = str(row.get('match_label') or '').casefold()
        importance = str(row.get('importance') or '').casefold()
        if not rid or rid in mapped or match not in RANK or not importance:
            return None, 'Unknown/duplicate requirement match or importance.'
        mapped[rid] = (importance, match)
    lineage = result.get('claim_lineage')
    risks = lineage.get('claim_review_required_count') if isinstance(lineage, dict) else None
    if isinstance(risks, bool) or not isinstance(risks, int) or risks != 0:
        return None, 'Unresolved or missing claim-lineage review holds.'
    if result.get('important_regressions'):
        return None, 'Required/Core regression reported by native Phase 8.'
    if result.get('verdict') in ('regression_detected', 'invalid_canonical_mismatch', 'invalid_job_match_identity', 'review_required'):
        return None, 'Native Phase 8 verdict is not safe to recommend.'
    return {'score': float(value), 'scoring_version': version, 'requirements': mapped,
            'digest': expected_sha}, ''


def compare_native_phase8(*, original: dict, candidate: dict, original_sha: str,
                          candidate_sha: str) -> dict[str, Any]:
    """Choose B iff native actual-DOCX score rises, with zero hard regressions.

    Does NOT compare V1.16 and V1.17 or infer hiring outcomes. Source A remains
    default on ties, invalid candidate, or any unverified evidence identity.
    """
    a, error = _score(original, expected_sha=original_sha)
    if error:
        return _hold('Original fitted candidate cannot be scored safely: ' + error, fallback='none')
    b, error = _score(candidate, expected_sha=candidate_sha)
    if error:
        return {**_hold('Challenger rejected: '+error), 'original_score': a['score']}
    if a['scoring_version'] != b['scoring_version'] or a['requirements'].keys() != b['requirements'].keys():
        return _hold('Scorer versions or canonical JD requirement IDs differ across candidates.')
    if any(a['requirements'][rid][0] != b['requirements'][rid][0] for rid in a['requirements']):
        return _hold('Requirement importance differs between candidates.')
    losses = sorted(rid for rid, (importance, label) in a['requirements'].items()
                  if importance in HARD and RANK[b['requirements'][rid][1]] < RANK[label])
    gain = round(b['score'] - a['score'], 6)
    if losses:
        winner, reason = 'existing_final', 'Candidate B loses Required/Core match strength.'
    elif gain > 0:
        winner, reason = 'optimized_candidate', 'Candidate B scores higher, with no Required/Core loss.'
    elif gain == 0:
        winner, reason = 'existing_final', 'Identical score: preserve the current fitted résumé.'
    else:
        winner, reason = 'existing_final', 'Challenger scores lower: preserve the current fitted résumé.'
    # Do not confuse "best among A/B" with an improvement against the starting
    # résumé. This independent gate is informative, never a ranking shortcut.
    winner_native = candidate if winner == 'optimized_candidate' else original
    winner_rows = b['requirements'] if winner == 'optimized_candidate' else a['requirements']
    before = winner_native.get('before_stable_analysis')
    selected = winner_native.get('selected_base_analysis')
    baseline_rows = []
    if isinstance(before, dict):
        baseline_rows.append(('Initial', before))
    if isinstance(selected, dict) and selected.get('same_as_initial') is True and isinstance(before, dict):
        baseline_rows.append(('Selected Base', before))
    elif isinstance(selected, dict) and isinstance(selected.get('stable_analysis'), dict):
        baseline_rows.append(('Selected Base', selected['stable_analysis']))
    baseline_deltas = {}
    baseline_hard_regressions = {}
    for name, analysis in baseline_rows:
        val = analysis.get('deterministic_alignment_score')
        if (analysis.get('scoring_version') != a['scoring_version'] or isinstance(val, bool)
            or not isinstance(val, (int, float)) or not math.isfinite(float(val))):
            continue
        original_rows = analysis.get('canonical_requirements')
        if not isinstance(original_rows, list) or len(original_rows) != len(winner_rows):
            continue
        original_map = {}
        for row in original_rows:
            if not isinstance(row, dict):break
            rid=str(row.get('requirement_id') or '')
            typ=str(row.get('importance') or '').casefold()
            strength=str(row.get('match_label') or '').casefold()
            if not rid or rid in original_map or strength not in RANK or not typ:break
            original_map[rid]=(typ,strength)
        if (set(original_map)!=set(winner_rows) or any(
            original_map[rid][0]!=winner_rows[rid][0] for rid in winner_rows)):
            continue
        baseline_deltas[name] = round((b['score'] if winner=='optimized_candidate' else a['score']) - float(val), 6)
        baseline_hard_regressions[name]=sorted(rid for rid,(typ,strength) in original_map.items()
            if typ in HARD and RANK[winner_rows[rid][1]] < RANK[strength])
    improves_both = (set(baseline_deltas)=={'Initial','Selected Base'}
                     and all(x > 0 for x in baseline_deltas.values())
                     and not any(baseline_hard_regressions.values()))
    return {'version': VERSION, 'status': 'verified', 'winner': winner,
            'reason': reason, 'original_score': a['score'], 'candidate_score': b['score'],
            'delta': gain, 'scoring_version': a['scoring_version'],
            'hard_regressed_ids': losses, 'baseline_deltas': baseline_deltas,
            'baseline_required_core_regressions': baseline_hard_regressions,
            'improved_vs_both_baselines': improves_both,
            'original_docx_sha256': original_sha,
            'candidate_docx_sha256': candidate_sha, 'candidate_approved': False,
            'claim': 'Best verified among these two actual one-page candidates, not global optimum or automatic approval.'}


def build_candidate_scoring_state(*, original: dict, proposal: dict,
                                  output: dict) -> dict[str, Any]:
    """Keep metadata/identity, replace only fitted document and bullet content.

    Reject if proposal does not match actual saved fitter bullets before edit.
    """
    state = deepcopy(original)
    fit = state.get('fit_result')
    if not isinstance(fit, dict) or fit.get('fit_one_page') is not True:
        raise ValueError('Original generation is not a verified fitted result.')
    old_projs = (fit.get('tailored_projects_used') or {}).get('recommended_projects')
    changes = proposal.get('projects')
    if not isinstance(old_projs, list) or not old_projs or not isinstance(changes, list) or len(old_projs) != len(changes):
        raise ValueError('Candidate project set cannot be matched to fitted project set.')
    by_title = {}
    for row in changes:
        if not isinstance(row, dict):
            raise ValueError('Malformed candidate project row.')
        key = ' '.join(str(row.get('project') or '').split()).casefold()
        if not key or key in by_title or not isinstance(row.get('before'), list) or not isinstance(row.get('after'), list):
            raise ValueError('Invalid candidate project ownership and bullet list.')
        by_title[key] = row
    if len(by_title) != len(old_projs):
        raise ValueError('Candidate project count changed unexpectedly.')
    variable_counts = proposal.get('variable_bullet_counts') is True
    if variable_counts:
        # Only V3.1/V3.3 source-grounded slates may change bullet counts.  The
        # actual DOCX writer has already checked the source document and verified
        # a separate one-page render; this stage must still enforce ownership.
        from tailoring.phase9f_auto_optimize_v31 import VERSION as V31_VERSION
        from tailoring.phase9f_evidence_optimizer_v33 import VERSION as V33_VERSION
        from tailoring.phase9f_jd_relevance_optimizer_v35 import VERSION as V35_VERSION
        if (proposal.get('version') not in (V31_VERSION, V33_VERSION, V35_VERSION)
                or proposal.get('project_set_unchanged') is not True):
            raise ValueError('Variable-count candidate lacks V3.1/V3.3/V3.5 source ownership authority.')
    seen_projects = set()
    for row in old_projs:
        if not isinstance(row, dict):
            raise ValueError('Malformed saved fitted project row.')
        key = ' '.join(str(row.get('display_title') or row.get('title') or '').split()).casefold()
        if not key or key in seen_projects:
            raise ValueError('Duplicate or missing saved fitted project identity.')
        seen_projects.add(key)
        proposed = by_title.get(key)
        if proposed is None:
            raise ValueError('Candidate project identities differ from fitted project set.')
        # NEVER weaken this exact source-state check to accommodate a variable
        # count. An old fit, changed order or foreign bullets must fail closed.
        before = proposed['before']
        after = proposed['after']
        if row.get('draft_bullets') != before:
            raise ValueError('Candidate starting bullet text/order differs from saved fitted project: ' + key)
        if not before or not all(isinstance(s, str) and s.strip() for s in before):
            raise ValueError('Invalid saved starting project bullets.')
        if not isinstance(after, list) or not 1 <= len(after) <= 8 or not all(
                isinstance(s, str) and s.strip() and len(s) <= 1200 for s in after):
            raise ValueError('Non-text or out-of-range candidate bullets.')
        if not variable_counts and len(after) != len(before):
            raise ValueError('Fixed-count proposal changed project bullet count.')
        if ('before_count' in proposed and proposed['before_count'] != len(before)) or (
                'after_count' in proposed and proposed['after_count'] != len(after)):
            raise ValueError('Candidate bullet-count receipts differ from source and proposed content.')
        # Exact candidate IDs are already scoped to the original project by the
        # source-grounded writer. Updating the in-memory scoring state must not
        # leave the old bullets in the field preferred by Phase 8.
        row['draft_bullets'] = list(after)
        # Verifier must not accidentally read stale generated bullet alternatives.
        for field in ('rewritten_bullets', 'selected_blueprint_bullets', 'compact_bullets'):
            if field in row:
                row[field] = list(proposed['after'])
    if proposal.get('status') != 'candidate' or output.get('status') != 'generated' or output.get('pages') != 1:
        raise ValueError('Optimized one-page generation receipt missing.')
    fit['docx_path'] = str(output['docx_path'])
    fit['pdf_path'] = str(output['pdf_path'])
    fit['page_count'] = 1
    fit['fit_one_page'] = True
    fit['fit_status'] = 'best_of_trial_one_page'
    fit['candidate_is_approved'] = False
    # Important: candidate is an isolated materialized slate, not the source
    # generation's original fitting reduction history.
    fit['remaining_active_reductions'] = []
    fit.pop('fitting_input_snapshot', None)
    fit.pop('fitting_input_fingerprint', None)
    state['fit_result'] = fit
    return state


def evaluate_existing_vs_candidate(*, audit: dict, projects: dict, fit: dict,
                                   generation: dict, baseline_report: dict, raw_jd_text: str,
                                   source_docx: Path, repo_root: Path, application_id: int,
                                   generator: Callable, scorer: Callable,
                                   optimizer: Callable, base_reviewed: bool = False) -> dict[str, Any]:
    """Explicit one-shot candidate render + in-memory native scoring; no DB writes.

    generator is V2.6 materialize_verified_candidate. Any failure keeps A.
    """
    def hold(reason):return _hold(reason)
    if not isinstance(baseline_report, dict) or not isinstance((baseline_report.get('meta') or {}).get('document_analysis'), dict):
        return hold('Actual-document initial analysis is required for comparable final scoring.')
    if not isinstance(generation, dict) or str(generation.get('generation_id') or '') != str(audit.get('generation_id') or ''):
        return hold('Generation identity differs from verified audit.')
    if not isinstance(fit, dict) or fit.get('fit_one_page') is not True or str((generation.get('fit_result') or {}).get('docx_path') or '') != str(fit.get('docx_path') or ''):
        return hold('Saved one-page fit receipt does not match the generation.')
    if not isinstance(audit, dict) or audit.get('verified') is not True:
        return hold('Verified final DOCX source audit required.')
    doc = Path(source_docx).resolve()
    root = Path(repo_root).resolve()
    try:doc.relative_to((root/'outputs'/'tailored_resumes').resolve())
    except ValueError:return hold('Source DOCX is outside scoped output folder.')
    if not doc.is_file() or sha256(doc.read_bytes()).hexdigest() != audit.get('docx_sha256'):
        return hold('Saved final DOCX digest mismatch.')
    if not str(raw_jd_text or '').strip():
        return hold('Exact original JD is missing.')
    proposal = optimizer(audit, projects)
    if proposal.get('status') != 'candidate':
        return {**hold('No eligible better proxy slate available: '+str(proposal.get('reason') or '')), 'status':'no_challenger'}
    if proposal.get('requires_base_review') and not base_reviewed:
        return {**hold('Base-only factual evidence requires explicit review before candidate generation.'), 'status':'needs_base_review', 'proposal': proposal}
    try:
        scored_a = scorer(baseline_report=baseline_report, generation_state=deepcopy(generation), raw_jd_text=raw_jd_text)
        original_score, score_error = _score(scored_a, expected_sha=audit['docx_sha256'])
        if score_error:
            return hold('Existing final document Phase 8 preflight failed: '+score_error)
        output = generator(source_docx=doc, audit_sha=audit['docx_sha256'], proposal=proposal,
                           repo_root=root, application_id=application_id,
                           generation_id=str(audit['generation_id']))
        candidate = Path(output['docx_path']).resolve()
        candidate.relative_to((root/'outputs'/'tailored_resumes'/'optimizations').resolve())
        if not candidate.is_file() or candidate == doc or output.get('pages') != 1:
            return hold('Challenger output path/page count not verified.')
        candidate_sha = sha256(candidate.read_bytes()).hexdigest()
        state_b = build_candidate_scoring_state(original=generation, proposal=proposal, output=output)
        scored_b = scorer(baseline_report=baseline_report, generation_state=state_b, raw_jd_text=raw_jd_text)
        compared = compare_native_phase8(original=scored_a, candidate=scored_b,
                          original_sha=audit['docx_sha256'], candidate_sha=candidate_sha)
        compared['candidate_file'] = str(candidate)
        compared['candidate_pdf'] = str(output['pdf_path'])
        compared['candidate_generation_id'] = str(audit['generation_id'])
        compared['proposal_version'] = str(proposal.get('version') or '')
        return compared
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        return hold('Challenger generation/verification failed: '+type(exc).__name__+': '+str(exc))
